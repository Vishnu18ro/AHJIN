"""Harness Runner — Step sequencing and execution engine."""

import asyncio

import httpx
import structlog

from ahjin.beru.types import ExecutionPlan, StepType
from ahjin.core.errors import AhjinError, ErrorCategory
from ahjin.core.types import TaskContext, TaskResult
from ahjin.harness.context import ContextAssembler
from ahjin.harness.gateway import ProviderGateway
from ahjin.harness.state import ExecutionState, StepResult

logger = structlog.get_logger()


class HarnessRunner:
    """Executes ExecutionPlan steps reliably."""

    def __init__(
        self,
        context_assembler: ContextAssembler | None = None,
        gateway: ProviderGateway | None = None,
    ) -> None:
        self.context_assembler = context_assembler or ContextAssembler()
        self.gateway = gateway or ProviderGateway()

    async def run(self, plan: ExecutionPlan, context: TaskContext) -> TaskResult:
        """Run execution plan steps sequentially."""
        logger.info("Harness running plan", plan_id=str(plan.plan_id), steps=len(plan.steps))
        state = ExecutionState(task_id=plan.task_id, plan_id=plan.plan_id)

        last_output: str | None = None

        for step in plan.steps:
            if step.step_type == StepType.MODEL_INVOCATION and step.model_intent:
                prompt = self.context_assembler.assemble(
                    intent=step.model_intent,
                    task_context=context,
                    prior_results=state.step_results,
                )

                try:
                    response = await self.gateway.invoke(
                        prompt=prompt,
                        requirements=step.model_intent.capability_requirements,
                    )
                    step_res = StepResult(
                        step_id=step.step_id,
                        success=True,
                        output_text=response.content,
                    )
                    last_output = response.content
                except asyncio.CancelledError:
                    # Preserve asyncio cancellation semantics — do not swallow.
                    logger.warning("Step cancelled", step_id=str(step.step_id))
                    raise
                except (httpx.HTTPStatusError, httpx.RequestError) as exc:
                    # Expected provider-layer errors: HTTP errors and network issues.
                    logger.error(
                        "Provider invocation failed",
                        step_id=str(step.step_id),
                        error=str(exc),
                    )
                    err = AhjinError(
                        category=ErrorCategory.PROVIDER,
                        code="INVOCATION_FAILED",
                        message=str(exc),
                        is_retryable=isinstance(exc, httpx.RequestError),
                    )
                    step_res = StepResult(
                        step_id=step.step_id,
                        success=False,
                        error=err,
                    )
                    state.step_results.append(step_res)
                    return TaskResult(
                        task_id=plan.task_id,
                        correlation_id=plan.correlation_id,
                        success=False,
                        error=err,
                    )

                state.step_results.append(step_res)

        return TaskResult(
            task_id=plan.task_id,
            correlation_id=plan.correlation_id,
            success=True,
            output_text=last_output,
        )
