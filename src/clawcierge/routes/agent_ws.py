import uuid

import structlog
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from clawcierge.config import settings
from clawcierge.database import get_session
from clawcierge.models.agent import Agent
from clawcierge.services.connection_manager import connection_manager
from clawcierge.services.key_manager import validate_api_key
from clawcierge.services.request_tracker import update_status

log = structlog.get_logger()

router = APIRouter(tags=["websocket"])


async def _authenticate_ws(
    websocket: WebSocket, agent_id: uuid.UUID, session: AsyncSession
) -> bool:
    """Validate token query param and verify it belongs to this agent."""
    token = websocket.query_params.get("token")
    if not token:
        return False
    auth = await validate_api_key(session, token)
    if auth is None:
        return False
    if auth.owner_type != "agent" or auth.owner_id != agent_id:
        return False
    return True


@router.websocket("/v1/agents/{agent_id}/ws")
async def agent_websocket(
    websocket: WebSocket,
    agent_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> None:
    # Authenticate before accepting
    if not await _authenticate_ws(websocket, agent_id, session):
        await websocket.close(code=4001, reason="Authentication failed")
        return

    await websocket.accept()
    await connection_manager.register(agent_id, websocket)

    # Set agent status to active
    await session.execute(
        update(Agent).where(Agent.id == agent_id).values(status="active")
    )
    await session.commit()

    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type")

            if msg_type == "heartbeat":
                connection_manager.update_heartbeat(agent_id)

            elif msg_type == "ack":
                request_id = data.get("request_id")
                if request_id:
                    await update_status(session, uuid.UUID(request_id), "acked")

            elif msg_type == "action.result":
                request_id = data.get("request_id")
                status = data.get("status", "completed")
                result = data.get("result", {})
                error = data.get("error")

                if request_id:
                    result_data = result if status == "completed" else {"error": error}
                    final_status = "completed" if status == "completed" else "rejected"
                    await update_status(
                        session, uuid.UUID(request_id), final_status, result=result_data
                    )

    except WebSocketDisconnect:
        log.info("agent_ws_disconnect", agent_id=str(agent_id))
    except Exception as e:
        log.error("agent_ws_error", agent_id=str(agent_id), error=str(e))
    finally:
        await connection_manager.remove(agent_id)
        # Set agent status to inactive
        try:
            await session.execute(
                update(Agent).where(Agent.id == agent_id).values(status="inactive")
            )
            await session.commit()
        except Exception:
            pass
