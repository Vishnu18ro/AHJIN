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


def test_nvidia_model_id_has_no_hardcoded_default() -> None:
    """Settings.nvidia_model_id must not contain a hardcoded model name (Fix C1).

    The empty string sentinel means 'not configured'.
    Model selection is operator-driven, not a code decision (ADR-003).
    """
    from ahjin.core.config import Settings

    # Instantiate fresh Settings without reading .env file to test code defaults
    s = Settings(_env_file=None)
    # The default must be empty — not a real model identifier
    assert s.nvidia_model_id == "", (
        f"nvidia_model_id has a hardcoded default '{s.nvidia_model_id}'. "
        "Model selection must be operator-driven configuration."
    )


def test_nvidia_provider_raises_if_model_id_not_configured() -> None:
    """NvidiaProvider must raise ValueError if model_id is empty (Fix C1)."""
    with pytest.raises(ValueError, match="NVIDIA_MODEL_ID is not configured"):
        from ahjin.providers.nvidia import NvidiaProvider

        NvidiaProvider(api_key="test-key", default_model="")


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

    def __init__(self) -> None:
        self.last_request: ModelInvocationRequest | None = None

    @property
    def provider_id(self) -> str:
        return "cap_logging"

    def get_default_model_id(self) -> str:
        return "cap-logging-model"

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
    """
    registry = ProviderRegistry()
    provider = CapabilityLoggingProvider()
    registry.register(provider)
    gateway = ProviderGateway(registry=registry)

    prompt = ContextualizedPrompt(user_instruction="What is 2+2?")
    requirements = CapabilityRequirements(
        requires_reasoning=True,
        max_latency_ms=5000,
    )

    # Gateway must not raise and must invoke the provider
    response = await gateway.invoke(prompt=prompt, requirements=requirements)
    assert response.content == "ok"
    assert provider.last_request is not None


# ---------------------------------------------------------------------------
# Fix 6 — Harness error handling: specific exceptions only
# ---------------------------------------------------------------------------


class FailingProvider(BaseModelProvider):
    """Provider that raises an httpx error to simulate a real network failure."""

    def __init__(self, exc: Exception) -> None:
        self._exc = exc

    @property
    def provider_id(self) -> str:
        return "failing"

    def get_default_model_id(self) -> str:
        return "failing-model"

    async def invoke(self, request: ModelInvocationRequest) -> ModelInvocationResponse:
        raise self._exc


@pytest.mark.asyncio
async def test_harness_runner_returns_failure_on_http_error() -> None:
    """Harness must catch httpx errors and return TaskResult.success=False (Fix 6)."""
    registry = ProviderRegistry()
    registry.register(
        FailingProvider(
            httpx.HTTPStatusError(
                "500 Internal Server Error",
                request=httpx.Request("POST", "https://api.nvidia.com/v1"),
                response=httpx.Response(500),
            )
        )
    )
    gateway = ProviderGateway(registry=registry)
    runner = HarnessRunner(gateway=gateway)

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

    assert result.success is False
    assert result.error is not None
    assert result.error.code == "INVOCATION_FAILED"


@pytest.mark.asyncio
async def test_harness_runner_propagates_programming_errors() -> None:
    """Non-httpx exceptions must NOT be swallowed by Harness (Fix 6).

    Real bugs (ValueError, KeyError, etc.) must propagate so they are
    visible and not silently converted to INVOCATION_FAILED errors.
    """
    registry = ProviderRegistry()
    registry.register(FailingProvider(ValueError("BUG: unexpected state")))
    gateway = ProviderGateway(registry=registry)
    runner = HarnessRunner(gateway=gateway)

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
