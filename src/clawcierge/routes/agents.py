import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from clawcierge.database import get_session
from clawcierge.errors import AgentNotFoundError
from clawcierge.schemas.agent import AgentResponse, CreateAgentRequest, CreateAgentResponse
from clawcierge.services.agent_registry import (
    create_agent,
    get_agent,
    get_agent_by_handle,
    validate_handle_format,
)

router = APIRouter(prefix="/v1/agents", tags=["agents"])


@router.post("", status_code=201)
async def register_agent(
    body: CreateAgentRequest,
    session: AsyncSession = Depends(get_session),
) -> CreateAgentResponse:
    if not validate_handle_format(body.handle):
        raise HTTPException(
            status_code=422,
            detail=(
                "Invalid handle format. Must be 3-64 chars, lowercase alphanumeric and dots, "
                "starting and ending with alphanumeric."
            ),
        )

    # For MVP, owner_id is auto-generated (no user accounts yet)
    owner_id = uuid.uuid4()
    agent, raw_key = await create_agent(session, body.display_name, body.handle, owner_id)

    return CreateAgentResponse(
        id=agent.id,
        handle=body.handle,
        api_key=raw_key,
        display_name=agent.display_name,
        status=agent.status,
    )


@router.get("/{identifier}")
async def get_agent_details(
    identifier: str,
    session: AsyncSession = Depends(get_session),
) -> AgentResponse:
    """Look up an agent by UUID or handle."""
    try:
        agent_id = uuid.UUID(identifier)
        agent = await get_agent(session, agent_id)
    except (ValueError, AgentNotFoundError):
        # Not a valid UUID or not found by UUID — try as handle
        try:
            agent = await get_agent_by_handle(session, identifier)
        except AgentNotFoundError:
            raise HTTPException(status_code=404, detail="Agent not found")

    return AgentResponse(
        id=agent.id,
        owner_id=agent.owner_id,
        display_name=agent.display_name,
        handle=agent.handle.handle if agent.handle else None,
        status=agent.status,
        created_at=agent.created_at,
        updated_at=agent.updated_at,
    )
