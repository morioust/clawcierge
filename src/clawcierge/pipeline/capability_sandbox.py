import jsonschema

from clawcierge.pipeline.context import PipelineContext, StageResult

STAGE_NAME = "capability_sandbox"


def execute(ctx: PipelineContext) -> StageResult:
    """Validate the requested action and params against the agent's capability contract."""
    if not ctx.capabilities:
        return StageResult(
            stage=STAGE_NAME,
            passed=False,
            reason="No capabilities defined for this agent",
        )

    # Find matching capability
    matching = None
    for cap in ctx.capabilities:
        if cap.get("action") == ctx.action:
            matching = cap
            break

    if matching is None:
        return StageResult(
            stage=STAGE_NAME,
            passed=False,
            reason=f"Action '{ctx.action}' is not in the agent's capability contract",
        )

    # Validate params against JSON Schema
    params_schema = matching.get("params_schema", {})
    if params_schema:
        try:
            jsonschema.validate(instance=ctx.params, schema=params_schema)
        except jsonschema.ValidationError as e:
            return StageResult(
                stage=STAGE_NAME,
                passed=False,
                reason=f"Parameter validation failed: {e.message}",
            )

    # Enforce constraints
    constraints = matching.get("constraints", {})
    for constraint_key, constraint_value in constraints.items():
        if constraint_key.startswith("max_"):
            param_name = constraint_key[4:]  # e.g. max_duration_minutes → duration_minutes
            param_value = ctx.params.get(param_name)
            if param_value is not None and param_value > constraint_value:
                return StageResult(
                    stage=STAGE_NAME,
                    passed=False,
                    reason=f"Constraint violation: {param_name}={param_value} exceeds max of {constraint_value}",
                )
        elif constraint_key.startswith("min_"):
            param_name = constraint_key[4:]
            param_value = ctx.params.get(param_name)
            if param_value is not None and param_value < constraint_value:
                return StageResult(
                    stage=STAGE_NAME,
                    passed=False,
                    reason=f"Constraint violation: {param_name}={param_value} below min of {constraint_value}",
                )

    return StageResult(stage=STAGE_NAME, passed=True)
