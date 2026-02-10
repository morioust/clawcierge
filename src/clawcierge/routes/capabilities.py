import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from clawcierge.database import get_session
from clawcierge.middleware.auth import get_auth_context
from clawcierge.models.capability import CapabilityContract
from clawcierge.schemas.capability import CapabilityContractResponse, UploadCapabilitiesRequest
from clawcierge.services.key_manager import AuthContext

router = APIRouter(prefix="/v1/agents", tags=["capabilities"])


@router.put("/{agent_id}/capabilities")
async def upload_capabilities(
    agent_id: uuid.UUID,
    body: UploadCapabilitiesRequest,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_session),
) -> CapabilityContractResponse:
    if auth.owner_type != "agent" or auth.owner_id != agent_id:
        raise HTTPException(status_code=403, detail="Not authorized for this agent")

    # Get current max version
    result = await session.execute(
        select(CapabilityContract.version)
        .where(CapabilityContract.agent_id == agent_id)
        .order_by(CapabilityContract.version.desc())
        .limit(1)
    )
    current_version = result.scalar_one_or_none() or 0

    # Deactivate all existing active contracts
    await session.execute(
        update(CapabilityContract)
        .where(CapabilityContract.agent_id == agent_id, CapabilityContract.is_active.is_(True))
        .values(is_active=False)
    )

    # Create new contract
    contract = CapabilityContract(
        agent_id=agent_id,
        version=current_version + 1,
        capabilities=[cap.model_dump() for cap in body.capabilities],
        constraints={},
        is_active=True,
    )
    session.add(contract)
    await session.commit()
    await session.refresh(contract)

    return CapabilityContractResponse(
        id=str(contract.id),
        agent_id=str(contract.agent_id),
        version=contract.version,
        capabilities=contract.capabilities,
        constraints=contract.constraints,
        is_active=contract.is_active,
    )
