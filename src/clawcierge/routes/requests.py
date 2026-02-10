import uuid
from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from clawcierge.database import get_session
from clawcierge.errors import AgentNotConnectedError, AgentNotFoundError
from clawcierge.middleware.auth import get_auth_context
from clawcierge.pipeline.context import PipelineContext
from clawcierge.pipeline.executor import execute_pipeline
from clawcierge.schemas.envelope import RequestReceived
from clawcierge.schemas.request import RequestResponse, SubmitRequestBody
from clawcierge.services.agent_registry import get_agent_by_handle
from clawcierge.services.connection_manager import connection_manager
from clawcierge.services.key_manager import AuthContext
from clawcierge.services.request_tracker import create_request, get_request, update_status

router = APIRouter(tags=["requests"])


@router.post("/v1/agents/{handle}/requests", status_code=202)
async def submit_request(
    handle: str,
    body: SubmitRequestBody,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_session),
) -> RequestResponse:
    # Resolve handle
    try:
        agent = await get_agent_by_handle(session, handle)
    except AgentNotFoundError:
        raise HTTPException(status_code=404, detail=f"Agent with handle '{handle}' not found")

    # Load capabilities and policies
    capabilities = []
    policy_rules = []
    for contract in agent.capability_contracts:
        if contract.is_active:
            capabilities = contract.capabilities

    # Load active policies
    from clawcierge.models.policy import Policy
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload  # noqa: F811

    policy_result = await session.execute(
        select(Policy).where(Policy.agent_id == agent.id, Policy.is_active.is_(True))
    )
    active_policy = policy_result.scalar_one_or_none()
    if active_policy:
        policy_rules = active_policy.rules

    # Build pipeline context
    ctx = PipelineContext(
        request_id=uuid.uuid4(),
        sender_id=str(auth.owner_id),
        agent_id=agent.id,
        handle=handle,
        action=body.action,
        params=body.params,
        capabilities=capabilities,
        policy_rules=policy_rules,
    )

    # Run enforcement pipeline
    ctx = await execute_pipeline(ctx)

    if ctx.rejected:
        raise HTTPException(
            status_code=422,
            detail={
                "message": ctx.rejection_reason,
                "stage": ctx.rejection_stage,
            },
        )

    # Check agent is connected
    if not connection_manager.is_connected(agent.id):
        raise AgentNotConnectedError(str(agent.id))

    # Create request in DB
    pipeline_log = [asdict(entry) for entry in ctx.pipeline_log]
    req = await create_request(
        session=session,
        agent_id=agent.id,
        sender_id=str(auth.owner_id),
        handle=handle,
        action=body.action,
        payload=body.params,
        pipeline_log=pipeline_log,
    )
    await session.commit()

    # Send to agent via WebSocket
    envelope = RequestReceived(
        request_id=req.id,
        action=body.action,
        params=body.params,
        sender_id=str(auth.owner_id),
    )
    sent = await connection_manager.send(agent.id, envelope.model_dump(mode="json"))

    if sent:
        await update_status(session, req.id, "dispatched")
    else:
        await update_status(session, req.id, "timeout")
        raise AgentNotConnectedError(str(agent.id))

    return RequestResponse(
        id=req.id,
        status="dispatched",
        action_type=body.action,
    )


@router.get("/v1/requests/{request_id}")
async def get_request_status(
    request_id: uuid.UUID,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_session),
) -> RequestResponse:
    req = await get_request(session, request_id)
    if req is None:
        raise HTTPException(status_code=404, detail="Request not found")

    # Verify sender matches
    if req.sender_id != str(auth.owner_id):
        raise HTTPException(status_code=403, detail="Not authorized to view this request")

    return RequestResponse(
        id=req.id,
        status=req.status,
        action_type=req.action_type,
        result=req.result,
        created_at=req.created_at,
        updated_at=req.updated_at,
    )
