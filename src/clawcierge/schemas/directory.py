import uuid
from typing import Any

from pydantic import BaseModel, Field


class ResolveRequest(BaseModel):
    handle: str = Field(min_length=3, max_length=64)


class ResolveResponse(BaseModel):
    agent_id: uuid.UUID
    display_name: str
    handle: str
    status: str
    capabilities: list[dict[str, Any]] = []
