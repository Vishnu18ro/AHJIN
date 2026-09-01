"""Unit tests for HarnessRunner with mock provider."""

from uuid import uuid4

import pytest

from ahjin.beru.types import (
    CapabilityRequirements,
    ExecutionPlan,
    ModelStepIntent,
    PlanStep,
    StepType,
)
from ahjin.core.types import TaskContext
from ahjin.harness.gateway import ProviderGateway
from ahjin.harness.runner import HarnessRunner
from ahjin.providers.base import BaseModelProvider
from ahjin.providers.registry import ProviderRegistry
from ahjin.providers.types import ModelInvocationRequest, ModelInvocationResponse


class MockHarnessProvider(BaseModelProvider):
    @property
    def provider_id(self) -> str:
        return "mock_harness"

    def get_default_model_id(self) -> str:
        return "mock-harness-model"

    async def invoke(self, request: ModelInvocationRequest) -> ModelInvocationResponse:
        return ModelInvocationResponse(
            invocation_id=request.invocation_id,
            content="Harness test answer",
            provider_id=self.provider_id,
            model_id=request.model_id,
        )


@pytest.mark.asyncio
async def test_harness_runner_executes_plan() -> None:
    registry = ProviderRegistry()
    mock_prov = MockHarnessProvider()
    registry.register(mock_prov, set_as_default=True)

    # Patch gateway to return mock provider
    gateway = ProviderGateway(registry=registry)
    runner = HarnessRunner(gateway=gateway)

    # Create plan
    plan = ExecutionPlan(
        task_id=uuid4(),
        correlation_id=uuid4(),
        steps=[
            PlanStep(
                step_type=StepType.MODEL_INVOCATION,
                model_intent=ModelStepIntent(
                    instruction="Hello",
                    capability_requirements=CapabilityRequirements(),
                ),
            )
        ],
    )
    context = TaskContext(session_id="test")

    result = await runner.run(plan, context)

    assert result.success is True
    assert result.output_text == "Harness test answer"
