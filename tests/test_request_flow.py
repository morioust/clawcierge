"""Request flow tests — tests that need both HTTP client and WebSocket use the sync TestClient."""

import secrets
import time
import uuid
from collections.abc import AsyncGenerator

from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session, sessionmaker
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


async def _create_agent_with_caps(client: AsyncClient, handle: str) -> dict:
    """Create agent and upload capabilities via async client."""
    resp = await client.post(
        "/v1/agents",
        json={"display_name": "Flow Agent", "handle": handle},
    )
    agent = resp.json()

    await client.put(
        f"/v1/agents/{agent['id']}/capabilities",
        headers={"Authorization": f"Bearer {agent['api_key']}"},
        json={
            "capabilities": [
                {
                    "action": "calendar.schedule",
                    "params_schema": {
                        "type": "object",
                        "required": ["title", "duration_minutes"],
                        "properties": {
                            "title": {"type": "string"},
                            "duration_minutes": {"type": "integer", "minimum": 15},
                        },
                    },
                    "constraints": {"max_duration_minutes": 120},
                }
            ]
        },
    )
    return agent


async def _create_sender_key(client: AsyncClient) -> str:
    """Create a sender API key via the test DB."""
    engine = create_async_engine(TEST_DATABASE_URL)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with factory() as session:
        from clawcierge.services.key_manager import generate_api_key

        sender_key = await generate_api_key(
            session, "sender", uuid.uuid4(), scopes=["request"]
        )
        await session.commit()

    await engine.dispose()
    return sender_key


async def test_send_request_to_disconnected_agent(client: AsyncClient):
    agent = await _create_agent_with_caps(client, "flow.disconn")
    sender_key = await _create_sender_key(client)

    response = await client.post(
        f"/v1/agents/{agent['handle']}/requests",
        headers={"Authorization": f"Bearer {sender_key}"},
        json={"action": "calendar.schedule", "params": {"title": "Sync", "duration_minutes": 30}},
    )
    assert response.status_code == 503


async def test_request_pipeline_rejection(client: AsyncClient):
    agent = await _create_agent_with_caps(client, "flow.reject")
    sender_key = await _create_sender_key(client)

    response = await client.post(
        f"/v1/agents/{agent['handle']}/requests",
        headers={"Authorization": f"Bearer {sender_key}"},
        json={"action": "nonexistent.action", "params": {}},
    )
    assert response.status_code == 422
    data = response.json()
    assert "stage" in data["detail"]


def test_full_request_flow():
    """End-to-end: register, capabilities, connect WS, send request, get result.

    Uses sync TestClient to avoid event loop conflicts.
    """
    # Setup DB
    sync_engine = create_engine(SYNC_URL)
    Base.metadata.drop_all(sync_engine)
    Base.metadata.create_all(sync_engine)
    SyncSession = sessionmaker(sync_engine)

    # Create agent + handle + agent key + capabilities + sender key
    agent_id = uuid.uuid4()
    owner_id = uuid.uuid4()
    sender_id = uuid.uuid4()

    with SyncSession() as s:
        agent = Agent(id=agent_id, owner_id=owner_id, display_name="E2E Agent", status="inactive")
        s.add(agent)
        s.flush()

        handle = Handle(handle="flow.e2e", agent_id=agent_id)
        s.add(handle)

        agent_raw_key = f"clw_agent_{secrets.token_hex(16)}"
        s.add(ApiKey(
            key_hash=_hash_key(agent_raw_key),
            key_prefix=agent_raw_key[:16],
            owner_type="agent",
            owner_id=agent_id,
            scopes=["agent:manage"],
        ))

        sender_raw_key = f"clw_sender_{secrets.token_hex(16)}"
        s.add(ApiKey(
            key_hash=_hash_key(sender_raw_key),
            key_prefix=sender_raw_key[:16],
            owner_type="sender",
            owner_id=sender_id,
            scopes=["request"],
        ))

        cap = CapabilityContract(
            agent_id=agent_id,
            version=1,
            capabilities=[
                {
                    "action": "calendar.schedule",
                    "params_schema": {
                        "type": "object",
                        "required": ["title", "duration_minutes"],
                        "properties": {
                            "title": {"type": "string"},
                            "duration_minutes": {"type": "integer", "minimum": 15},
                        },
                    },
                    "constraints": {"max_duration_minutes": 120},
                }
            ],
            constraints={},
            is_active=True,
        )
        s.add(cap)
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
            # Connect agent via WebSocket
            with tc.websocket_connect(
                f"/v1/agents/{agent_id}/ws?token={agent_raw_key}"
            ) as ws:
                # Submit request via HTTP
                resp = tc.post(
                    "/v1/agents/flow.e2e/requests",
                    headers={"Authorization": f"Bearer {sender_raw_key}"},
                    json={
                        "action": "calendar.schedule",
                        "params": {"title": "Sync", "duration_minutes": 30},
                    },
                )
                assert resp.status_code == 202, resp.text
                request_id = resp.json()["id"]

                # Agent receives the request
                msg = ws.receive_json()
                assert msg["type"] == "request.received"
                assert msg["action"] == "calendar.schedule"
                assert msg["request_id"] == request_id

                # Agent sends ack
                ws.send_json({"type": "ack", "request_id": request_id})

                # Agent sends result
                ws.send_json({
                    "type": "action.result",
                    "request_id": request_id,
                    "status": "completed",
                    "result": {"event_id": "evt-123", "scheduled_time": "2024-01-01T10:00:00Z"},
                })

                # Give the server a moment to process
                time.sleep(0.2)

                # Poll for result
                result_resp = tc.get(
                    f"/v1/requests/{request_id}",
                    headers={"Authorization": f"Bearer {sender_raw_key}"},
                )
                assert result_resp.status_code == 200
                result_data = result_resp.json()
                assert result_data["status"] == "completed"
                assert result_data["result"]["event_id"] == "evt-123"
    finally:
        app.dependency_overrides.clear()
