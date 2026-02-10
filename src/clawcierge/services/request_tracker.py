import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import structlog
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from clawcierge.config import settings
from clawcierge.models.request import Request

log = structlog.get_logger()


async def create_request(
    session: AsyncSession,
    agent_id: uuid.UUID,
    sender_id: str,
    handle: str,
    action: str,
    payload: dict[str, Any],
    pipeline_log: list[dict[str, Any]],
    expiry_seconds: int | None = None,
) -> Request:
    expiry = expiry_seconds or settings.request_expiry_seconds
    req = Request(
        agent_id=agent_id,
        sender_id=sender_id,
        handle=handle,
        status="pending",
        action_type=action,
        payload=payload,
        pipeline_log=pipeline_log,
        expires_at=datetime.now(timezone.utc) + timedelta(seconds=expiry),
    )
    session.add(req)
    await session.flush()
    return req


async def update_status(
    session: AsyncSession,
    request_id: uuid.UUID,
    status: str,
    result: dict[str, Any] | None = None,
) -> None:
    values: dict[str, Any] = {"status": status, "updated_at": datetime.now(timezone.utc)}
    if result is not None:
        values["result"] = result
    await session.execute(
        update(Request).where(Request.id == request_id).values(**values)
    )
    await session.commit()


async def get_request(session: AsyncSession, request_id: uuid.UUID) -> Request | None:
    result = await session.execute(select(Request).where(Request.id == request_id))
    return result.scalar_one_or_none()


async def expire_stale_requests(session: AsyncSession) -> int:
    """Mark expired pending/dispatched requests as timed out."""
    now = datetime.now(timezone.utc)
    result = await session.execute(
        update(Request)
        .where(
            Request.status.in_(["pending", "dispatched"]),
            Request.expires_at < now,
        )
        .values(status="timeout", updated_at=now)
    )
    await session.commit()
    count = result.rowcount  # type: ignore[assignment]
    if count:
        log.info("expired_requests", count=count)
    return count
