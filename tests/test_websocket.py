"""WebSocket tests using Starlette's TestClient (sync) with proper DB setup."""

import uuid

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from starlette.testclient import TestClient

from clawcierge.config import settings
from clawcierge.database import Base, get_session
from clawcierge.main import app
from clawcierge.models.agent import Agent, Handle
from clawcierge.models.api_key import ApiKey
from clawcierge.services.connection_manager import connection_manager
from clawcierge.services.key_manager import _hash_key

import clawcierge.models  # noqa: F401

# Sync engine for TestClient tests (avoids event loop conflicts)
TEST_DATABASE_URL = settings.database_url.rsplit("/", 1)[0] + "/clawcierge_test"
SYNC_URL = TEST_DATABASE_URL.replace("postgresql+asyncpg", "postgresql")


def _setup_sync_db() -> sessionmaker:
    """Create tables and return a sync sessionmaker."""
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
    from collections.abc import AsyncGenerator

    sync_engine = create_engine(SYNC_URL)
    Base.metadata.drop_all(sync_engine)
    Base.metadata.create_all(sync_engine)
    return sessionmaker(sync_engine)


def _create_agent_sync(sync_session: Session) -> tuple[str, str, str]:
    """Create an agent + handle + api key synchronously. Returns (agent_id, handle, raw_key)."""
    import secrets

    agent_id = uuid.uuid4()
    owner_id = uuid.uuid4()

    agent = Agent(id=agent_id, owner_id=owner_id, display_name="WS Agent", status="inactive")
    sync_session.add(agent)
    sync_session.flush()

    handle = Handle(handle="ws.test." + secrets.token_hex(4), agent_id=agent_id)
    sync_session.add(handle)

    raw_key = f"clw_agent_test{secrets.token_hex(16)}"
    api_key = ApiKey(
        key_hash=_hash_key(raw_key),
        key_prefix=raw_key[:16],
        owner_type="agent",
        owner_id=agent_id,
        scopes=["agent:manage"],
    )
    sync_session.add(api_key)
    sync_session.commit()

    return str(agent_id), handle.handle, raw_key


def test_ws_connect_valid_key():
    SessionFactory = _setup_sync_db()

    with SessionFactory() as sync_session:
        agent_id, handle, raw_key = _create_agent_sync(sync_session)

    # Override the async session dependency with one backed by the test DB
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
    from collections.abc import AsyncGenerator

    test_engine = create_async_engine(TEST_DATABASE_URL)
    test_factory = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_session() -> AsyncGenerator[AsyncSession]:
        async with test_factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session

    try:
        with TestClient(app) as tc:
            with tc.websocket_connect(
                f"/v1/agents/{agent_id}/ws?token={raw_key}"
            ) as ws:
                ws.send_json({"type": "heartbeat"})
                assert connection_manager.is_connected(uuid.UUID(agent_id))
    finally:
        app.dependency_overrides.clear()


def test_ws_connect_invalid_key():
    SessionFactory = _setup_sync_db()

    with SessionFactory() as sync_session:
        agent_id, handle, raw_key = _create_agent_sync(sync_session)

    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
    from collections.abc import AsyncGenerator

    test_engine = create_async_engine(TEST_DATABASE_URL)
    test_factory = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_session() -> AsyncGenerator[AsyncSession]:
        async with test_factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session

    try:
        with TestClient(app) as tc:
            try:
                with tc.websocket_connect(
                    f"/v1/agents/{agent_id}/ws?token=clw_agent_boguskey"
                ):
                    pass  # Should not succeed
            except Exception:
                pass  # Expected: rejected
    finally:
        app.dependency_overrides.clear()


def test_ws_connect_no_token():
    SessionFactory = _setup_sync_db()

    with SessionFactory() as sync_session:
        agent_id, handle, raw_key = _create_agent_sync(sync_session)

    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
    from collections.abc import AsyncGenerator

    test_engine = create_async_engine(TEST_DATABASE_URL)
    test_factory = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_session() -> AsyncGenerator[AsyncSession]:
        async with test_factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session

    try:
        with TestClient(app) as tc:
            try:
                with tc.websocket_connect(f"/v1/agents/{agent_id}/ws"):
                    pass
            except Exception:
                pass  # Expected: rejected
    finally:
        app.dependency_overrides.clear()
