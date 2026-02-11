"""Agent-to-agent communication tests.

Verifies that one registered agent can discover another by handle,
send it a request, and receive the result — all using agent API keys.
"""

import secrets
import time
import uuid
from collections.abc import AsyncGenerator

from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from starlette.testclient import TestClient

from clawcierge.config import settings
from clawcierge.database import Base, get_session
from clawcierge.main import app
from clawcierge.models.agent import Agent, Handle
from clawcierge.models.api_key import ApiKey
from clawcierge.models.capability import CapabilityContract
from clawcierge.services.key_manager import _hash_key

import clawcierge.models  # noqa: F401

TEST_DATABASE_URL = settings.database_url.rsplit("/", 1)[0] + "/clawcierge_test"
SYNC_URL = TEST_DATABASE_URL.replace("postgresql+asyncpg", "postgresql")


async def test_agent_resolves_another_agent(client: AsyncClient):
    """Agent 'green' can discover agent 'pink' by handle via directory resolve."""
    # Register both agents
    green = await client.post(
        "/v1/agents", json={"display_name": "Green Agent", "handle": "green"}
    )
    pink = await client.post(
        "/v1/agents", json={"display_name": "Pink Agent", "handle": "pink"}
    )
    assert green.status_code == 201
    assert pink.status_code == 201

    # Green resolves Pink by handle (no auth required for directory)
    resolve_resp = await client.post(
        "/v1/directory/resolve", json={"handle": "pink"}
    )
    assert resolve_resp.status_code == 200
    data = resolve_resp.json()
    assert data["display_name"] == "Pink Agent"
    assert data["handle"] == "pink"
    assert data["agent_id"] == pink.json()["id"]


async def test_agent_sends_request_to_another_agent(client: AsyncClient):
    """Agent 'green' can send a request to agent 'pink' using its own agent key."""
    # Register pink with capabilities
    pink = await client.post(
        "/v1/agents", json={"display_name": "Pink Agent", "handle": "pink.req"}
    )
    assert pink.status_code == 201
    pink_data = pink.json()

    await client.put(
        f"/v1/agents/{pink_data['id']}/capabilities",
        headers={"Authorization": f"Bearer {pink_data['api_key']}"},
        json={
            "capabilities": [
                {
                    "action": "echo",
                    "params_schema": {
                        "type": "object",
                        "required": ["message"],
                        "properties": {"message": {"type": "string"}},
                    },
                    "constraints": {},
                }
            ]
        },
    )

    # Register green
    green = await client.post(
        "/v1/agents", json={"display_name": "Green Agent", "handle": "green.req"}
    )
    assert green.status_code == 201
    green_data = green.json()

    # Green sends a request to pink using its own agent key
    # Pink is not connected, so we expect 503
    req_resp = await client.post(
        "/v1/agents/pink.req/requests",
        headers={"Authorization": f"Bearer {green_data['api_key']}"},
        json={"action": "echo", "params": {"message": "hello from green"}},
    )
    # Agent key is accepted for sending requests (503 = pink is offline, not auth error)
    assert req_resp.status_code == 503


def test_full_agent_to_agent_flow():
    """End-to-end: green discovers pink, sends a request, pink responds, green polls result."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    sync_engine = create_engine(SYNC_URL)
    Base.metadata.drop_all(sync_engine)
    Base.metadata.create_all(sync_engine)
    SyncSession = sessionmaker(sync_engine)

    green_agent_id = uuid.uuid4()
    pink_agent_id = uuid.uuid4()

    with SyncSession() as s:
        # Create pink agent with capabilities
        pink = Agent(id=pink_agent_id, owner_id=uuid.uuid4(), display_name="Pink Agent", status="inactive")
        s.add(pink)
        s.flush()
        s.add(Handle(handle="pink.e2e", agent_id=pink_agent_id))

        pink_raw_key = f"clw_agent_{secrets.token_hex(16)}"
        s.add(ApiKey(
            key_hash=_hash_key(pink_raw_key),
            key_prefix=pink_raw_key[:16],
            owner_type="agent",
            owner_id=pink_agent_id,
            scopes=["agent:manage"],
        ))

        s.add(CapabilityContract(
            agent_id=pink_agent_id,
            version=1,
            capabilities=[{
                "action": "echo",
                "params_schema": {
                    "type": "object",
                    "required": ["message"],
                    "properties": {"message": {"type": "string"}},
                },
                "constraints": {},
            }],
            constraints={},
            is_active=True,
        ))

        # Create green agent (the sender)
        green = Agent(id=green_agent_id, owner_id=uuid.uuid4(), display_name="Green Agent", status="inactive")
        s.add(green)
        s.flush()
        s.add(Handle(handle="green.e2e", agent_id=green_agent_id))

        green_raw_key = f"clw_agent_{secrets.token_hex(16)}"
        s.add(ApiKey(
            key_hash=_hash_key(green_raw_key),
            key_prefix=green_raw_key[:16],
            owner_type="agent",
            owner_id=green_agent_id,
            scopes=["agent:manage"],
        ))

        s.commit()

    # Override session dependency
    test_engine = create_async_engine(TEST_DATABASE_URL)
    test_factory = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_session() -> AsyncGenerator[AsyncSession]:
        async with test_factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session

    try:
        with TestClient(app) as tc:
            # Step 1: Green resolves Pink by handle
            resolve_resp = tc.post("/v1/directory/resolve", json={"handle": "pink.e2e"})
            assert resolve_resp.status_code == 200
            pink_info = resolve_resp.json()
            assert pink_info["display_name"] == "Pink Agent"
            assert pink_info["agent_id"] == str(pink_agent_id)

            # Step 2: Pink connects via WebSocket
            with tc.websocket_connect(
                f"/v1/agents/{pink_agent_id}/ws?token={pink_raw_key}"
            ) as ws:
                # Step 3: Green sends a request to Pink using its agent key
                req_resp = tc.post(
                    "/v1/agents/pink.e2e/requests",
                    headers={"Authorization": f"Bearer {green_raw_key}"},
                    json={"action": "echo", "params": {"message": "hello from green"}},
                )
                assert req_resp.status_code == 202, req_resp.text
                request_id = req_resp.json()["id"]

                # Step 4: Pink receives the request
                msg = ws.receive_json()
                assert msg["type"] == "request.received"
                assert msg["action"] == "echo"
                assert msg["params"]["message"] == "hello from green"
                assert msg["sender_id"] == str(green_agent_id)

                # Step 5: Pink acks and responds
                ws.send_json({"type": "ack", "request_id": request_id})
                ws.send_json({
                    "type": "action.result",
                    "request_id": request_id,
                    "status": "completed",
                    "result": {"echo": "hello from green", "from": "pink"},
                })

                time.sleep(0.2)

                # Step 6: Green polls for the result using its agent key
                result_resp = tc.get(
                    f"/v1/requests/{request_id}",
                    headers={"Authorization": f"Bearer {green_raw_key}"},
                )
                assert result_resp.status_code == 200
                result_data = result_resp.json()
                assert result_data["status"] == "completed"
                assert result_data["result"]["echo"] == "hello from green"
                assert result_data["result"]["from"] == "pink"
    finally:
        app.dependency_overrides.clear()
