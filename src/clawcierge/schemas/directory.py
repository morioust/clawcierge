import uuid
from typing import Any

from pydantic import BaseModel


class ResolveResponse(BaseModel):
    agent_id: uuid.UUID
    display_name: str
    handle: str
    status: str
    capabilities: list[dict[str, Any]] = []
