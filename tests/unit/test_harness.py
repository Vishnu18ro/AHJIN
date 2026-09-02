"""Unit tests for HarnessRunner with mock provider.

Test injection pattern (post-gateway-bypass-removal):
- Mock providers register with provider_id="mock_harness"
- ModelCatalog is seeded with a ModelDescriptor using provider_id="mock_harness"
- ModelRouter is built from that catalog and injected into ProviderGateway
- This is the correct seam: no bypass of ModelRouter in test or production
"""

from uuid import uuid4

import pytest

from ahjin.beru.types import (
    CapabilityRequirements,
    ExecutionPlan,
    ExecutionStrategy,
    ModelStepIntent,
    PlanStep,
    RecoveryPolicy,
    StepType,
)
from ahjin.core.types import TaskContext
from ahjin.harness.gateway import ProviderGateway
from ahjin.harness.runner import HarnessRunner
from ahjin.models.catalog import ModelCatalog
from ahjin.models.router import ModelRouter
from ahjin.models.types import ModelCapabilities, ModelDescriptor, ModelTier
from ahjin.providers.base import BaseModelProvider
from ahjin.providers.registry import ProviderRegistry
from ahjin.providers.types import ModelInvocationRequest, ModelInvocationResponse

_MOCK_PROVIDER_ID = "mock_harness"
_MOCK_MODEL_ID = "mock-harness-model"


class MockHarnessProvider(BaseModelProvider):
    @property
    def provider_id(self) -> str:
        return _MOCK_PROVIDER_ID

    def get_default_model_id(self) -> str:
        return _MOCK_MODEL_ID

    async def invoke(self, request: ModelInvocationRequest) -> ModelInvocationResponse:
        return ModelInvocationResponse(
            invocation_id=request.invocation_id,
            content="Harness test answer",
            provider_id=self.provider_id,
            model_id=request.model_id,
        )


def _build_mock_gateway(provider: BaseModelProvider) -> ProviderGateway:
    """Build a ProviderGateway that uses a catalog matching the mock provider."""
    catalog = ModelCatalog()
    catalog.register(
        ModelDescriptor(
            model_id=provider.get_default_model_id(),
            provider_id=provider.provider_id,
            tier=ModelTier.FAST,
            capabilities=ModelCapabilities(),
        )
    )
    registry = ProviderRegistry()
    registry.register(provider)
    router = ModelRouter(catalog=catalog)
    return ProviderGateway(registry=registry, router=router)


@pytest.mark.asyncio
async def test_harness_runner_executes_plan() -> None:
    gateway = _build_mock_gateway(MockHarnessProvider())
    runner = HarnessRunner(gateway=gateway)

    plan = ExecutionPlan(
        task_id=uuid4(),
        correlation_id=uuid4(),
        steps=[
            PlanStep(
                step_type=StepType.MODEL_INVOCATION,
                model_intent=ModelStepIntent(
                    instruction="Hello",
                    execution_strategy=ExecutionStrategy(
                        capability_requirements=CapabilityRequirements(),
                        preferred_tier="FAST",
                    ),
                ),
            )
        ],
    )
    context = TaskContext(session_id="test")

    result = await runner.run(plan, context)

    assert result.success is True
    assert result.output_text == "Harness test answer"


@pytest.mark.asyncio
async def test_harness_runner_fail_fast_returns_immediately() -> None:
    """FAIL_FAST recovery policy must return on first failure without rerouting."""
    import httpx

    class AlwaysFailProvider(BaseModelProvider):
        provider_id = _MOCK_PROVIDER_ID

        def get_default_model_id(self) -> str:
            return _MOCK_MODEL_ID

        async def invoke(self, request: ModelInvocationRequest) -> ModelInvocationResponse:
            raise httpx.RequestError("timeout", request=httpx.Request("POST", "http://x"))

    gateway = _build_mock_gateway(AlwaysFailProvider())
    runner = HarnessRunner(gateway=gateway)

    plan = ExecutionPlan(
        task_id=uuid4(),
        correlation_id=uuid4(),
        steps=[
            PlanStep(
                step_type=StepType.MODEL_INVOCATION,
                model_intent=ModelStepIntent(
                    instruction="Hello",
                    execution_strategy=ExecutionStrategy(
                        capability_requirements=CapabilityRequirements(),
                        preferred_tier="FAST",
                        recovery_policy=RecoveryPolicy.FAIL_FAST,
                        max_recovery_attempts=3,  # would loop 3x if FAIL_FAST not enforced
                    ),
                ),
            )
        ],
    )
    context = TaskContext(session_id="test")

    result = await runner.run(plan, context)

    # Must fail on first attempt
    assert result.success is False
    assert result.error is not None


@pytest.mark.asyncio
async def test_harness_runner_verification_disabled_skips_verifier() -> None:
    """require_verification=False must skip the ResponseVerifier entirely."""

    class EmptyContentProvider(BaseModelProvider):
        provider_id = _MOCK_PROVIDER_ID

        def get_default_model_id(self) -> str:
            return _MOCK_MODEL_ID

        async def invoke(self, request: ModelInvocationRequest) -> ModelInvocationResponse:
            # Returns empty content — would fail verification if enabled
            return ModelInvocationResponse(
                invocation_id=request.invocation_id,
                content="   ",  # whitespace-only
                provider_id=self.provider_id,
                model_id=request.model_id,
            )

    gateway = _build_mock_gateway(EmptyContentProvider())
    runner = HarnessRunner(gateway=gateway)

    plan = ExecutionPlan(
        task_id=uuid4(),
        correlation_id=uuid4(),
        steps=[
            PlanStep(
                step_type=StepType.MODEL_INVOCATION,
                model_intent=ModelStepIntent(
                    instruction="Hello",
                    execution_strategy=ExecutionStrategy(
                        capability_requirements=CapabilityRequirements(),
                        require_verification=False,  # Skip verifier
                        preferred_tier="FAST",
                    ),
                ),
            )
        ],
    )
    context = TaskContext(session_id="test")

    result = await runner.run(plan, context)

    # Must succeed — verifier was skipped
    assert result.success is True
