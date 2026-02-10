import uuid

from clawcierge.pipeline.capability_sandbox import execute as cap_execute
from clawcierge.pipeline.context import PipelineContext
from clawcierge.pipeline.executor import execute_pipeline
from clawcierge.pipeline.policy_engine import execute as pol_execute

SAMPLE_CAPABILITIES = [
    {
        "action": "calendar.schedule",
        "params_schema": {
            "type": "object",
            "required": ["title", "duration_minutes"],
            "properties": {
                "title": {"type": "string"},
                "duration_minutes": {"type": "integer", "minimum": 15},
            },
        },
        "constraints": {"max_duration_minutes": 120},
    }
]


def _make_ctx(
    action: str = "calendar.schedule",
    params: dict | None = None,
    capabilities: list | None = None,
    policy_rules: list | None = None,
) -> PipelineContext:
    return PipelineContext(
        request_id=uuid.uuid4(),
        sender_id="test_sender",
        agent_id=uuid.uuid4(),
        handle="test.agent",
        action=action,
        params=params or {"title": "Sync", "duration_minutes": 30},
        capabilities=capabilities if capabilities is not None else SAMPLE_CAPABILITIES,
        policy_rules=policy_rules or [],
    )


# --- Capability Sandbox Tests ---


def test_cap_action_not_in_contract():
    ctx = _make_ctx(action="email.send")
    result = cap_execute(ctx)
    assert not result.passed
    assert "not in the agent's capability contract" in result.reason


def test_cap_params_fail_schema():
    ctx = _make_ctx(params={"title": 123, "duration_minutes": 30})  # title should be string
    result = cap_execute(ctx)
    assert not result.passed
    assert "Parameter validation failed" in result.reason


def test_cap_params_exceed_constraint():
    ctx = _make_ctx(params={"title": "Long", "duration_minutes": 200})
    result = cap_execute(ctx)
    assert not result.passed
    assert "Constraint violation" in result.reason


def test_cap_valid_action_and_params():
    ctx = _make_ctx()
    result = cap_execute(ctx)
    assert result.passed


def test_cap_no_capabilities():
    ctx = _make_ctx(capabilities=[])
    result = cap_execute(ctx)
    assert not result.passed
    assert "No capabilities defined" in result.reason


# --- Policy Engine Tests ---


def test_pol_rule_matches_reject():
    ctx = _make_ctx(
        policy_rules=[
            {
                "condition": "sender_id == 'test_sender'",
                "action": "reject",
                "reason": "Blocked sender",
            }
        ]
    )
    result = pol_execute(ctx)
    assert not result.passed
    assert result.reason == "Blocked sender"


def test_pol_rule_no_match():
    ctx = _make_ctx(
        policy_rules=[
            {
                "condition": "sender_id == 'other_sender'",
                "action": "reject",
                "reason": "Blocked sender",
            }
        ]
    )
    result = pol_execute(ctx)
    assert result.passed


def test_pol_no_rules():
    ctx = _make_ctx(policy_rules=[])
    result = pol_execute(ctx)
    assert result.passed


# --- Full Pipeline Tests ---


async def test_pipeline_valid_request():
    ctx = _make_ctx()
    result = await execute_pipeline(ctx)
    assert not result.rejected
    assert len(result.pipeline_log) == 2


async def test_pipeline_policy_rejects():
    ctx = _make_ctx(
        policy_rules=[
            {
                "condition": "sender_id == 'test_sender'",
                "action": "reject",
                "reason": "Nope",
            }
        ]
    )
    result = await execute_pipeline(ctx)
    assert result.rejected
    assert result.rejection_stage == "policy_engine"


async def test_pipeline_capability_rejects():
    ctx = _make_ctx(action="nonexistent.action")
    result = await execute_pipeline(ctx)
    assert result.rejected
    assert result.rejection_stage == "capability_sandbox"
