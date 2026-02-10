import re
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from clawcierge.errors import AgentNotFoundError, HandleTakenError
from clawcierge.models.agent import Agent, Handle
from clawcierge.models.capability import CapabilityContract
from clawcierge.services.key_manager import generate_api_key

HANDLE_PATTERN = re.compile(r"^[a-z0-9][a-z0-9.]{1,62}[a-z0-9]$")


def validate_handle_format(handle: str) -> bool:
    return bool(HANDLE_PATTERN.match(handle))


async def create_agent(
    session: AsyncSession,
    display_name: str,
    handle: str,
    owner_id: uuid.UUID,
) -> tuple[Agent, str]:
    """Create an agent with a handle and API key. Returns (agent, raw_api_key)."""
    # Check handle is available
    existing = await session.execute(select(Handle).where(Handle.handle == handle))
    if existing.scalar_one_or_none() is not None:
        raise HandleTakenError(handle)

    agent = Agent(
        owner_id=owner_id,
        display_name=display_name,
        status="inactive",
    )
    session.add(agent)
    await session.flush()

    handle_obj = Handle(handle=handle, agent_id=agent.id)
    session.add(handle_obj)

    raw_key = await generate_api_key(session, "agent", agent.id, scopes=["agent:manage"])
    await session.commit()

    # Refresh to get relationships
    await session.refresh(agent, ["handle"])
    return agent, raw_key


async def get_agent(session: AsyncSession, agent_id: uuid.UUID) -> Agent:
    result = await session.execute(
        select(Agent).options(selectinload(Agent.handle)).where(Agent.id == agent_id)
    )
    agent = result.scalar_one_or_none()
    if agent is None:
        raise AgentNotFoundError(str(agent_id))
    return agent


async def get_agent_by_handle(session: AsyncSession, handle: str) -> Agent:
    result = await session.execute(
        select(Agent)
        .join(Handle)
        .options(
            selectinload(Agent.handle),
            selectinload(Agent.capability_contracts.and_(CapabilityContract.is_active.is_(True))),
        )
        .where(Handle.handle == handle)
    )
    agent = result.scalar_one_or_none()
    if agent is None:
        raise AgentNotFoundError(handle)
    return agent
