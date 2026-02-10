import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class SubmitRequestBody(BaseModel):
    action: str = Field(min_length=1, max_length=200)
    params: dict[str, Any] = Field(default_factory=dict)


class RequestResponse(BaseModel):
    id: uuid.UUID
    status: str
    action_type: str | None = None
    result: dict[str, Any] | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
