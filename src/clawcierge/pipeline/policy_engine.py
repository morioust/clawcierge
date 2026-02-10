import simpleeval

from clawcierge.pipeline.context import PipelineContext, StageResult

STAGE_NAME = "policy_engine"


def _build_namespace(ctx: PipelineContext) -> dict:
    """Build a restricted namespace for policy evaluation."""
    ns: dict = {
        "sender_id": ctx.sender_id,
        "action": ctx.action,
    }
    # Flatten params into namespace with params. prefix
    for k, v in ctx.params.items():
        ns[f"params_{k}"] = v
    return ns


def execute(ctx: PipelineContext) -> StageResult:
    """Evaluate policy rules against the request context."""
    if not ctx.policy_rules:
        return StageResult(stage=STAGE_NAME, passed=True)

    evaluator = simpleeval.EvalWithCompoundTypes()

    namespace = _build_namespace(ctx)

    for rule in ctx.policy_rules:
        condition = rule.get("condition", "")
        rule_action = rule.get("action", "")
        reason = rule.get("reason", "Policy rule matched")

        evaluator.names = namespace

        try:
            result = evaluator.eval(condition)
        except Exception:
            # Fail-closed: if we can't evaluate a rule, reject
            return StageResult(
                stage=STAGE_NAME,
                passed=False,
                reason=f"Policy evaluation error for condition: {condition}",
            )

        if result and rule_action == "reject":
            return StageResult(
                stage=STAGE_NAME,
                passed=False,
                reason=reason,
            )

    return StageResult(stage=STAGE_NAME, passed=True)
