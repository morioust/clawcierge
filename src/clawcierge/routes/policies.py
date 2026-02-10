import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from clawcierge.database import get_session
from clawcierge.middleware.auth import get_auth_context
from clawcierge.models.policy import Policy
from clawcierge.schemas.policy import PolicyResponse, UploadPoliciesRequest
from clawcierge.services.key_manager import AuthContext

router = APIRouter(prefix="/v1/agents", tags=["policies"])


@router.put("/{agent_id}/policies")
async def upload_policies(
    agent_id: uuid.UUID,
    body: UploadPoliciesRequest,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_session),
) -> PolicyResponse:
    if auth.owner_type != "agent" or auth.owner_id != agent_id:
        raise HTTPException(status_code=403, detail="Not authorized for this agent")

    # Get current max version
    result = await session.execute(
        select(Policy.version)
        .where(Policy.agent_id == agent_id)
        .order_by(Policy.version.desc())
        .limit(1)
    )
    current_version = result.scalar_one_or_none() or 0

    # Deactivate all existing active policies
    await session.execute(
        update(Policy)
        .where(Policy.agent_id == agent_id, Policy.is_active.is_(True))
        .values(is_active=False)
    )

    # Create new policy
    policy = Policy(
        agent_id=agent_id,
        version=current_version + 1,
        rules=[rule.model_dump() for rule in body.rules],
        is_active=True,
    )
    session.add(policy)
    await session.commit()
    await session.refresh(policy)

    return PolicyResponse(
        id=str(policy.id),
        agent_id=str(policy.agent_id),
        version=policy.version,
        rules=policy.rules,
        is_active=policy.is_active,
    )
