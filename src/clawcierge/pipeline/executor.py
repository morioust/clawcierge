import asyncio
import time
from collections.abc import Callable

import structlog

from clawcierge.config import settings
from clawcierge.pipeline import capability_sandbox, policy_engine
from clawcierge.pipeline.context import PipelineContext, StageResult

log = structlog.get_logger()

# Ordered list of pipeline stages
STAGES: list[tuple[str, Callable[[PipelineContext], StageResult]]] = [
    ("policy_engine", policy_engine.execute),
    ("capability_sandbox", capability_sandbox.execute),
]


async def execute_pipeline(ctx: PipelineContext) -> PipelineContext:
    """Run all pipeline stages sequentially. Stop on first rejection."""
    timeout = settings.pipeline_stage_timeout_seconds

    for stage_name, stage_fn in STAGES:
        start = time.monotonic()
        try:
            result = await asyncio.wait_for(
                asyncio.get_event_loop().run_in_executor(None, stage_fn, ctx),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            result = StageResult(
                stage=stage_name,
                passed=False,
                reason=f"Stage timed out after {timeout}s",
            )
        except Exception as e:
            # Fail-closed: stage crash = rejection
            log.error("pipeline_stage_error", stage=stage_name, error=str(e))
            result = StageResult(
                stage=stage_name,
                passed=False,
                reason=f"Stage error: {type(e).__name__}",
            )

        result.duration_ms = (time.monotonic() - start) * 1000
        ctx.pipeline_log.append(result)

        if not result.passed:
            ctx.rejected = True
            ctx.rejection_stage = result.stage
            ctx.rejection_reason = result.reason
            log.info(
                "pipeline_rejected",
                stage=result.stage,
                reason=result.reason,
                request_id=str(ctx.request_id),
            )
            break

    return ctx
