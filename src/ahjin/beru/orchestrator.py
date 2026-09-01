"""BERU Orchestrator — Cognitive decision engine."""

import time

import structlog

from ahjin.beru.types import (
    CapabilityRequirements,
    ExecutionPlan,
    ModelStepIntent,
    PlanStep,
    StepType,
)
from ahjin.core.types import TaskRequest

logger = structlog.get_logger()


class BeruOrchestrator:
    """BERU engine for task understanding and plan generation."""

    async def plan(self, request: TaskRequest) -> ExecutionPlan:
        """Analyze TaskRequest and produce ExecutionPlan."""
        t0 = time.monotonic()
        logger.info("[PROFILE] BERU planning start", task_id=str(request.task_id))

        model_intent = ModelStepIntent(
            instruction=request.intent.primary_text,
            capability_requirements=CapabilityRequirements(),
        )

        step = PlanStep(
            step_type=StepType.MODEL_INVOCATION,
            model_intent=model_intent,
        )

        plan_res = ExecutionPlan(
            task_id=request.task_id,
            correlation_id=request.correlation_id,
            steps=[step],
        )

        t_beru_ms = (time.monotonic() - t0) * 1000.0
        logger.info(
            "[PROFILE] BERU planning end",
            task_id=str(request.task_id),
            planning_ms=round(t_beru_ms, 3),
        )
        return plan_res
