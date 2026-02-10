from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from clawcierge.database import get_session
from clawcierge.schemas.directory import ResolveRequest, ResolveResponse
from clawcierge.services.agent_registry import get_agent_by_handle

router = APIRouter(prefix="/v1/directory", tags=["directory"])


@router.post("/resolve")
async def resolve_handle(
    body: ResolveRequest,
    session: AsyncSession = Depends(get_session),
) -> ResolveResponse:
    agent = await get_agent_by_handle(session, body.handle)

    capabilities = []
    for contract in agent.capability_contracts:
        if contract.is_active:
            capabilities = contract.capabilities

    return ResolveResponse(
        agent_id=agent.id,
        display_name=agent.display_name,
        handle=agent.handle.handle if agent.handle else body.handle,
        status=agent.status,
        capabilities=capabilities,
    )
