import uuid
from dataclasses import dataclass, field
from typing import Any


@dataclass
class StageResult:
    stage: str
    passed: bool
    reason: str = ""
    duration_ms: float = 0.0


@dataclass
class PipelineContext:
    request_id: uuid.UUID
    sender_id: str
    agent_id: uuid.UUID
    handle: str
    action: str
    params: dict[str, Any]
    capabilities: list[dict[str, Any]]
    policy_rules: list[dict[str, Any]]
    pipeline_log: list[StageResult] = field(default_factory=list)
    rejected: bool = False
    rejection_stage: str = ""
    rejection_reason: str = ""
