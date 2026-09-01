"""BERU Orchestrator — Cognitive decision engine."""

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
        """Analyze TaskRequest and produce ExecutionPlan.

        v1 Implementation: Produces a trivial 1-step model execution plan.
        """
        logger.info("BERU planning task", task_id=str(request.task_id))

        model_intent = ModelStepIntent(
            instruction=request.intent.primary_text,
            capability_requirements=CapabilityRequirements(),
        )

        step = PlanStep(
            step_type=StepType.MODEL_INVOCATION,
            model_intent=model_intent,
        )

        return ExecutionPlan(
            task_id=request.task_id,
            correlation_id=request.correlation_id,
            steps=[step],
        )
