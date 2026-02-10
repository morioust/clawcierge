import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class CreateAgentRequest(BaseModel):
    display_name: str = Field(min_length=1, max_length=200)
    handle: str = Field(min_length=3, max_length=64)


class AgentResponse(BaseModel):
    id: uuid.UUID
    owner_id: uuid.UUID
    display_name: str
    handle: str | None = None
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CreateAgentResponse(BaseModel):
    id: uuid.UUID
    handle: str
    api_key: str
    display_name: str
    status: str
