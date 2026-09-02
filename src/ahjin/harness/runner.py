"""Harness Runner — Step sequencing, verification, and same-request recovery engine.

Execution contract:
- require_verification from ExecutionStrategy is ENFORCED:
  if False → verifier is skipped entirely.
- recovery_policy from ExecutionStrategy is ENFORCED:
  FAIL_FAST → no rerouting, first failure returns immediately.
  REROUTE   → same-request rerouting up to max_recovery_attempts.
- Failed model identity comes from exc.model_id (attached by ProviderGateway).
- excluded_models is request-local; no global shared exclusion state.
- RuntimeInfo is populated after each invocation for Telegram observability.
"""

import asyncio
import time

import httpx
import structlog

from ahjin.beru.types import (
    ExecutionPlan,
    RecoveryPolicy,
    StepType,
)
from ahjin.core.errors import AhjinError, ErrorCategory
from ahjin.core.types import RuntimeInfo, TaskContext, TaskResult
from ahjin.harness.context import ContextAssembler
from ahjin.harness.gateway import ProviderGateway
from ahjin.harness.state import ExecutionState, StepResult
from ahjin.harness.verifier import ResponseVerifier, VerificationError
from ahjin.models.router import CapabilityUnavailableError

logger = structlog.get_logger()


class HarnessRunner:
    """Executes ExecutionPlan steps reliably with verification and same-request rerouting."""

    def __init__(
        self,
        context_assembler: ContextAssembler | None = None,
        gateway: ProviderGateway | None = None,
        verifier: ResponseVerifier | None = None,
    ) -> None:
        self.context_assembler = context_assembler or ContextAssembler()
        self.gateway = gateway or ProviderGateway()
        self.verifier = verifier or ResponseVerifier()

    async def run(self, plan: ExecutionPlan, context: TaskContext) -> TaskResult:
        """Run execution plan steps sequentially with same-request failure recovery."""
        logger.info("Harness running plan", plan_id=str(plan.plan_id), steps=len(plan.steps))
        state = ExecutionState(task_id=plan.task_id, plan_id=plan.plan_id)

        last_output: str | None = None
        runtime_info: RuntimeInfo | None = None

        for step in plan.steps:
            if step.step_type == StepType.MODEL_INVOCATION and step.model_intent:
                intent = step.model_intent
                strategy = intent.execution_strategy

                # Strategy fields that govern execution behaviour
                max_attempts: int = strategy.max_recovery_attempts
                require_verification: bool = strategy.require_verification
                recovery_policy: RecoveryPolicy = strategy.recovery_policy

                t0_ctx = time.monotonic()
                prompt = self.context_assembler.assemble(
                    intent=intent,
                    task_context=context,
                    prior_results=state.step_results,
                )
                t_ctx_ms = (time.monotonic() - t0_ctx) * 1000.0
                logger.info(
                    "[PROFILE] ContextAssembler execution",
                    step_id=str(step.step_id),
                    context_assembly_ms=round(t_ctx_ms, 3),
                )

                # excluded_models is request-local — never shared across concurrent requests
                excluded_models: set[str] = set()
                attempts = 0
                step_success = False

                # RuntimeInfo tracking for observability
                first_failed_model: str | None = None
                first_failure_reason: str | None = None
                step_t0 = time.monotonic()

                while attempts < max_attempts and not step_success:
                    attempts += 1
                    t0_gw = time.monotonic()
                    try:
                        gw_result = await self.gateway.invoke(
                            prompt=prompt,
                            requirements=strategy,
                            excluded_model_ids=excluded_models,
                        )
                        t_gw_ms = (time.monotonic() - t0_gw) * 1000.0
                        response = gw_result.response
                        selection = gw_result.selection

                        logger.info(
                            "[PROFILE] ProviderGateway execution",
                            step_id=str(step.step_id),
                            gateway_invoke_ms=round(t_gw_ms, 3),
                            attempt=attempts,
                            model_id=response.model_id,
                        )

                        # Structural Verification Boundary.
                        # Skipped entirely when require_verification=False.
                        if require_verification:
                            ver_res = self.verifier.verify(response.content)
                            if not ver_res.is_valid:
                                raise VerificationError(
                                    f"Verification failed: {ver_res.reason}",
                                    model_id=response.model_id,
                                )

                        step_res = StepResult(
                            step_id=step.step_id,
                            success=True,
                            output_text=response.content,
                        )
                        last_output = response.content
                        step_success = True
                        state.step_results.append(step_res)

                        # Build RuntimeInfo for observability footer
                        step_total_ms = (time.monotonic() - step_t0) * 1000.0
                        ahjin_overhead_ms = step_total_ms - response.latency_ms
                        health_state = self.gateway.router.health_tracker.get_state(
                            response.model_id
                        )
                        runtime_info = RuntimeInfo(
                            selected_model=response.model_id,
                            tier=selection.tier.value,
                            provider_id=selection.provider_id,
                            ahjin_internal_ms=round(max(ahjin_overhead_ms, 0.0), 1),
                            model_api_ms=round(response.latency_ms, 1),
                            total_ms=round(step_total_ms, 1),
                            was_rerouted=(first_failed_model is not None),
                            failed_model=first_failed_model,
                            failure_reason=first_failure_reason,
                            health_status=health_state.snapshot_status.value,
                        )

                    except asyncio.CancelledError:
                        logger.warning("Step cancelled", step_id=str(step.step_id))
                        raise
                    except (
                        httpx.HTTPStatusError,
                        httpx.RequestError,
                        VerificationError,
                        CapabilityUnavailableError,
                    ) as exc:
                        # Extract the failed model ID (attached by ProviderGateway before re-raise).
                        failed_model = getattr(exc, "model_id", None)
                        if failed_model:
                            excluded_models.add(str(failed_model))
                            # Record first failure for rerouting observability
                            if first_failed_model is None:
                                first_failed_model = str(failed_model)
                                first_failure_reason = _classify_failure_reason(exc)

                        logger.warning(
                            "[PROFILE] Model invocation failed — checking same-request recovery",
                            step_id=str(step.step_id),
                            attempt=attempts,
                            max_attempts=max_attempts,
                            recovery_policy=recovery_policy.value,
                            error=str(exc),
                        )

                        # FAIL_FAST: return immediately without rerouting
                        if recovery_policy == RecoveryPolicy.FAIL_FAST:
                            err = AhjinError(
                                category=ErrorCategory.PROVIDER,
                                code="INVOCATION_FAILED",
                                message=str(exc),
                                is_retryable=False,
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

                        if (
                            attempts >= max_attempts
                            or isinstance(exc, CapabilityUnavailableError)
                        ):
                            # Exhausted recovery budget or capability unavailable
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

                        # REROUTE: continue loop — next iteration selects alternate model
                        # (excluded_models now contains the failed model)

        return TaskResult(
            task_id=plan.task_id,
            correlation_id=plan.correlation_id,
            success=True,
            output_text=last_output,
            runtime_info=runtime_info,
        )


def _classify_failure_reason(exc: Exception) -> str:
    """Classify the failure reason for observability reporting.

    Returns a human-readable string describing the actual cause.
    Never invents reasons — reports what the exception type indicates.
    """
    if isinstance(exc, httpx.TimeoutException):
        return "timeout"
    if isinstance(exc, httpx.HTTPStatusError):
        return f"HTTP {exc.response.status_code}"
    if isinstance(exc, httpx.RequestError):
        return "network error"
    if isinstance(exc, VerificationError):
        return "verification failure"
    if isinstance(exc, CapabilityUnavailableError):
        return "capability unavailable"
    return "provider error"
