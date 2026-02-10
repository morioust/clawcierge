import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class WsEnvelope(BaseModel):
    type: str
    request_id: uuid.UUID | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime | None = None


# Platform → Agent messages

class RequestReceived(BaseModel):
    type: str = "request.received"
    request_id: uuid.UUID
    action: str
    params: dict[str, Any] = Field(default_factory=dict)
    sender_id: str


class RequestCancel(BaseModel):
    type: str = "request.cancel"
    request_id: uuid.UUID
    reason: str = ""


class Ping(BaseModel):
    type: str = "ping"


# Agent → Platform messages

class Ack(BaseModel):
    type: str = "ack"
    request_id: uuid.UUID


class ActionResult(BaseModel):
    type: str = "action.result"
    request_id: uuid.UUID
    status: str = "completed"  # completed | error
    result: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None


class Heartbeat(BaseModel):
    type: str = "heartbeat"
