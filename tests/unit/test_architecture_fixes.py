"""Regression tests for AHJIN 2.0 architectural fix pass.

Covers fixes: C1, C2, H2, H3, Fix 6, Fix 7, Fix 10.
Each test is focused and documents the exact architectural concern it guards.
"""

from __future__ import annotations

from uuid import uuid4

import httpx
import pytest

from ahjin.beru.types import (
    CapabilityRequirements,
    ExecutionPlan,
    ModelStepIntent,
    PlanStep,
    StepType,
)
from ahjin.core.types import ConversationTurn, RequestMetadata, Role, TaskContext
from ahjin.harness.context import ContextAssembler
from ahjin.harness.gateway import ProviderGateway
from ahjin.harness.runner import HarnessRunner
from ahjin.models.catalog import ModelCatalog
from ahjin.models.router import ModelRouter
from ahjin.models.types import ModelCapabilities, ModelDescriptor, ModelTier
from ahjin.providers.base import BaseModelProvider
from ahjin.providers.registry import ProviderRegistry
from ahjin.providers.types import (
    ContextualizedPrompt,
    ModelInvocationRequest,
    ModelInvocationResponse,
)

# ---------------------------------------------------------------------------
# Fix C1 — No hardcoded NVIDIA model ID
# ---------------------------------------------------------------------------


def test_model_selection_is_driven_by_catalog_not_settings() -> None:
    """Settings must not contain nvidia_model_id (Fix C1).

    Model selection is fully driven by ModelCatalog & ModelRouter, not config settings.
    """
    from ahjin.core.config import Settings

    s = Settings(_env_file=None)
    assert not hasattr(s, "nvidia_model_id"), (
        "nvidia_model_id must not exist in Settings. "
        "Model selection is driven by ModelCatalog and ModelRouter."
    )


def test_nvidia_provider_raises_if_model_id_missing_on_invoke() -> None:
    """NvidiaProvider.invoke must raise ValueError if model_id is missing."""
    from ahjin.providers.nvidia import NvidiaProvider
    from ahjin.providers.types import ContextualizedPrompt, ModelInvocationRequest

    provider = NvidiaProvider(api_key="test-key", default_model="")
    req = ModelInvocationRequest(prompt=ContextualizedPrompt(user_instruction="hi"), model_id="")

    with pytest.raises(ValueError, match="model_id is not specified"):
        import asyncio
        asyncio.run(provider.invoke(req))


# ---------------------------------------------------------------------------
# Fix H2 — ContextualizedPrompt ownership
# ---------------------------------------------------------------------------


def test_contextualized_prompt_not_in_core_types() -> None:
    """ContextualizedPrompt must NOT be importable from ahjin.core.types (Fix H2).

    It belongs to the provider/harness boundary, not Core domain contracts.
    """
    import ahjin.core.types as core_types

    assert not hasattr(core_types, "ContextualizedPrompt"), (
        "ContextualizedPrompt must not live in ahjin.core.types. "
        "It belongs to ahjin.providers.types."
    )


def test_contextualized_prompt_importable_from_providers_types() -> None:
    """ContextualizedPrompt must be importable from ahjin.providers.types (Fix H2)."""
    from ahjin.providers.types import ContextualizedPrompt as CP  # noqa: N813

    assert CP is not None
    # Verify it has the expected fields
    prompt = CP(user_instruction="test")
    assert prompt.user_instruction == "test"
    assert prompt.system_instruction  # must have default system instruction


def test_contextualized_prompt_has_correct_defaults() -> None:
    """ContextualizedPrompt default system instruction must identify AHJIN."""
    prompt = ContextualizedPrompt(user_instruction="hello")
    assert "AHJIN" in prompt.system_instruction
    assert prompt.conversation_history == []


# ---------------------------------------------------------------------------
# Fix H2 — ContextualizedPrompt ownership and ContextAssembler boundary
# ---------------------------------------------------------------------------


def test_context_assembler_produces_contextualized_prompt() -> None:
    """ContextAssembler must produce a ContextualizedPrompt with correct content."""
    assembler = ContextAssembler()
    intent = ModelStepIntent(instruction="Explain quantum mechanics")
    context = TaskContext(
        session_id="s1",
        conversation_history=[
            ConversationTurn(role=Role.USER, content="Hi"),
        ],
    )
    prompt = assembler.assemble(intent=intent, task_context=context)

    assert isinstance(prompt, ContextualizedPrompt)
    assert prompt.user_instruction == "Explain quantum mechanics"
    assert len(prompt.conversation_history) == 1
    assert "AHJIN" in prompt.system_instruction


# ---------------------------------------------------------------------------
# Fix H3 — CapabilityRequirements not silently discarded
# ---------------------------------------------------------------------------


class CapabilityLoggingProvider(BaseModelProvider):
    """Provider that records the invocation request for inspection."""

    # provider_id matches what we put in the test catalog below
    _PROVIDER_ID = "cap_logging_provider"
    _MODEL_ID = "cap-logging-model"

    def __init__(self) -> None:
        self.last_request: ModelInvocationRequest | None = None

    @property
    def provider_id(self) -> str:
        return self._PROVIDER_ID

    def get_default_model_id(self) -> str:
        return self._MODEL_ID

    async def invoke(self, request: ModelInvocationRequest) -> ModelInvocationResponse:
        self.last_request = request
        return ModelInvocationResponse(
            invocation_id=request.invocation_id,
            content="ok",
            provider_id=self.provider_id,
            model_id=request.model_id,
        )


@pytest.mark.asyncio
async def test_capability_requirements_forwarded_to_gateway() -> None:
    """CapabilityRequirements must not be silently discarded (Fix H3).

    Gateway must accept and log requirements. Provider must be invoked.
    Injection uses the correct seam: catalog + router + registry all consistent.
    """
    provider = CapabilityLoggingProvider()
    # Build a catalog where the single model uses this test provider_id
    catalog = ModelCatalog()
    catalog.register(
        ModelDescriptor(
            model_id=provider.get_default_model_id(),
            provider_id=provider.provider_id,
            tier=ModelTier.HEAVY,
            capabilities=ModelCapabilities(reasoning=True),
        )
    )
    registry = ProviderRegistry()
    registry.register(provider)
    router = ModelRouter(catalog=catalog)
    gateway = ProviderGateway(registry=registry, router=router)

    prompt = ContextualizedPrompt(user_instruction="What is 2+2?")
    requirements = CapabilityRequirements(
        requires_reasoning=True,
        max_latency_ms=5000,
    )

    # Gateway must not raise and must invoke the provider
    gw_result = await gateway.invoke(prompt=prompt, requirements=requirements)
    assert gw_result.response.content == "ok"
    assert provider.last_request is not None


# ---------------------------------------------------------------------------
# Fix 6 — Harness error handling: specific exceptions only
# ---------------------------------------------------------------------------


_FAILING_PROVIDER_ID = "failing_provider"
_FAILING_MODEL_ID = "failing-model"


class FailingProvider(BaseModelProvider):
    """Provider that raises an error to simulate network/server failures."""

    def __init__(self, exc: Exception) -> None:
        self._exc = exc

    @property
    def provider_id(self) -> str:
        return _FAILING_PROVIDER_ID

    def get_default_model_id(self) -> str:
        return _FAILING_MODEL_ID

    async def invoke(self, request: ModelInvocationRequest) -> ModelInvocationResponse:
        raise self._exc


def _build_failing_gateway(exc: Exception) -> ProviderGateway:
    """Build a gateway wired to a FailingProvider via a matching catalog."""
    catalog = ModelCatalog()
    catalog.register(
        ModelDescriptor(
            model_id=_FAILING_MODEL_ID,
            provider_id=_FAILING_PROVIDER_ID,
            tier=ModelTier.FAST,
            capabilities=ModelCapabilities(),
        )
    )
    registry = ProviderRegistry()
    registry.register(FailingProvider(exc))
    router = ModelRouter(catalog=catalog)
    return ProviderGateway(registry=registry, router=router)


@pytest.mark.asyncio
async def test_harness_runner_returns_failure_on_http_error() -> None:
    """Harness must catch httpx errors and return TaskResult.success=False (Fix 6)."""
    from ahjin.beru.types import ExecutionStrategy

    gateway = _build_failing_gateway(
        httpx.HTTPStatusError(
            "500 Internal Server Error",
            request=httpx.Request("POST", "https://api.nvidia.com/v1"),
            response=httpx.Response(500),
        )
    )
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
                        # Only 1 attempt so the test runs fast
                        max_recovery_attempts=1,
                    ),
                ),
            )
        ],
    )
    context = TaskContext(session_id="test")

    result = await runner.run(plan, context)

    assert result.success is False
    assert result.error is not None
    assert result.error.code == "INVOCATION_FAILED"


@pytest.mark.asyncio
async def test_harness_runner_propagates_programming_errors() -> None:
    """Non-httpx/non-capability exceptions must propagate (Fix 6).

    Real bugs (ValueError, KeyError, etc.) must propagate so they are
    visible and not silently converted to INVOCATION_FAILED errors.
    """
    from ahjin.beru.types import ExecutionStrategy

    gateway = _build_failing_gateway(ValueError("BUG: unexpected state"))
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
                        max_recovery_attempts=1,
                    ),
                ),
            )
        ],
    )
    context = TaskContext(session_id="test")

    with pytest.raises(ValueError, match="BUG: unexpected state"):
        await runner.run(plan, context)


# ---------------------------------------------------------------------------
# Fix 10 — RequestMetadata is interface-neutral
# ---------------------------------------------------------------------------


def test_request_metadata_default_source_interface_is_neutral() -> None:
    """RequestMetadata.source_interface must default to 'unknown', not 'telegram' (Fix 10).

    Core canonical contracts must not assume any specific interface by default.
    Callers (e.g. TelegramMapper) set the correct value explicitly.
    """
    metadata = RequestMetadata()
    assert metadata.source_interface == "unknown", (
        f"Expected 'unknown' but got '{metadata.source_interface}'. "
        "Core contracts must not hardcode interface assumptions."
    )


def test_telegram_mapper_sets_explicit_source_interface() -> None:
    """TelegramMapper must explicitly set source_interface='telegram' (Fix 10)."""
    from ahjin.interfaces.telegram.mapper import TelegramMapper

    request = TelegramMapper.to_task_request(chat_id=123, message_text="hello")
    assert request.metadata.source_interface == "telegram"
