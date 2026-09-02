"""Targeted regression tests for AHJIN V2 Deep Architectural Correction Pass.

Covers the following verified fixes:
- Issue A: BERU vision multi-word phrase detection
- Issue B: require_verification enforced by runner
- Issue B: recovery_policy=FAIL_FAST enforced by runner
- Issue B: quality_preference actually changes ranking
- Issue C: max_latency_ms constraint enforced by router
- Issue D: Health recovery is evidence-based (not time-based auto-reset)
- Issue G: ProviderGateway raises explicitly when provider not registered
- Issue J: ModelHealthState thread safety
"""

from __future__ import annotations

import threading
import time
from uuid import uuid4

import httpx
import pytest

from ahjin.beru.orchestrator import BeruOrchestrator
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
from ahjin.models.health import ModelHealthState, ModelHealthStatus, ModelHealthTracker
from ahjin.models.router import CapabilityUnavailableError, ModelRouter
from ahjin.models.types import ModelCapabilities, ModelDescriptor, ModelTier
from ahjin.providers.base import BaseModelProvider
from ahjin.providers.registry import ProviderRegistry
from ahjin.providers.types import ModelInvocationRequest, ModelInvocationResponse

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _simple_catalog(
    model_id: str = "test-model",
    provider_id: str = "test-provider",
    tier: ModelTier = ModelTier.FAST,
    quality_score: int = 80,
    capabilities: ModelCapabilities | None = None,
) -> ModelCatalog:
    catalog = ModelCatalog()
    catalog.register(
        ModelDescriptor(
            model_id=model_id,
            provider_id=provider_id,
            tier=tier,
            quality_score=quality_score,
            capabilities=capabilities or ModelCapabilities(),
        )
    )
    return catalog


class OkProvider(BaseModelProvider):
    def __init__(self, provider_id: str = "test-provider", model_id: str = "test-model") -> None:
        self._provider_id = provider_id
        self._model_id = model_id

    @property
    def provider_id(self) -> str:
        return self._provider_id

    def get_default_model_id(self) -> str:
        return self._model_id

    async def invoke(self, request: ModelInvocationRequest) -> ModelInvocationResponse:
        return ModelInvocationResponse(
            invocation_id=request.invocation_id,
            content="ok response",
            provider_id=self._provider_id,
            model_id=request.model_id,
        )


# ---------------------------------------------------------------------------
# Issue A — BERU vision phrase detection
# ---------------------------------------------------------------------------


def test_beru_detects_single_word_vision_keyword() -> None:
    beru = BeruOrchestrator()
    reqs = beru.analyze_task_requirements("Describe this image")
    assert reqs.requires_vision is True


def test_beru_detects_multiword_vision_phrase_look_at() -> None:
    """'look at' is a multi-word phrase — the old split-token approach missed it."""
    beru = BeruOrchestrator()
    reqs = beru.analyze_task_requirements("Can you look at this and tell me what you see?")
    assert reqs.requires_vision is True


def test_beru_detects_multiword_vision_phrase_in_this_image() -> None:
    beru = BeruOrchestrator()
    reqs = beru.analyze_task_requirements("What does the graph show in this image?")
    assert reqs.requires_vision is True


def test_beru_does_not_hallucinate_vision_for_text_task() -> None:
    beru = BeruOrchestrator()
    reqs = beru.analyze_task_requirements("Explain how sorting algorithms work")
    assert reqs.requires_vision is False


def test_beru_produces_no_model_or_provider_ids() -> None:
    """BERU strategy must contain ZERO model IDs or provider strings."""
    beru = BeruOrchestrator()
    reqs = beru.analyze_task_requirements("Write a Python function to sort a list")
    strategy = ExecutionStrategy(
        capability_requirements=reqs,
        preferred_tier="HEAVY",
    )
    dump = str(strategy.model_dump())
    assert "nvidia" not in dump.lower()
    assert "deepseek" not in dump.lower()
    assert "nemotron" not in dump.lower()
    assert "kimi" not in dump.lower()


# ---------------------------------------------------------------------------
# Issue B — require_verification enforcement
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_require_verification_false_skips_verifier() -> None:
    """Whitespace-only response must succeed when require_verification=False."""
    provider_id = "vtest-provider"
    model_id = "vtest-model"

    class WhitespaceProvider(BaseModelProvider):
        @property
        def provider_id(self) -> str:
            return provider_id

        def get_default_model_id(self) -> str:
            return model_id

        async def invoke(self, request: ModelInvocationRequest) -> ModelInvocationResponse:
            return ModelInvocationResponse(
                invocation_id=request.invocation_id,
                content="   ",
                provider_id=provider_id,
                model_id=request.model_id,
            )

    catalog = _simple_catalog(model_id=model_id, provider_id=provider_id)
    registry = ProviderRegistry()
    registry.register(WhitespaceProvider())
    router = ModelRouter(catalog=catalog)
    gateway = ProviderGateway(registry=registry, router=router)
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
                        require_verification=False,
                        preferred_tier="FAST",
                    ),
                ),
            )
        ],
    )
    result = await runner.run(plan, TaskContext(session_id="t"))
    assert result.success is True


@pytest.mark.asyncio
async def test_require_verification_true_rejects_empty_response() -> None:
    """Whitespace-only response must fail verification when require_verification=True."""
    provider_id = "vtrue-provider"
    model_id = "vtrue-model"

    class WhitespaceProvider(BaseModelProvider):
        @property
        def provider_id(self) -> str:
            return provider_id

        def get_default_model_id(self) -> str:
            return model_id

        async def invoke(self, request: ModelInvocationRequest) -> ModelInvocationResponse:
            return ModelInvocationResponse(
                invocation_id=request.invocation_id,
                content="   ",
                provider_id=provider_id,
                model_id=request.model_id,
            )

    catalog = _simple_catalog(model_id=model_id, provider_id=provider_id)
    registry = ProviderRegistry()
    registry.register(WhitespaceProvider())
    router = ModelRouter(catalog=catalog)
    gateway = ProviderGateway(registry=registry, router=router)
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
                        require_verification=True,  # default
                        max_recovery_attempts=1,
                        preferred_tier="FAST",
                    ),
                ),
            )
        ],
    )
    result = await runner.run(plan, TaskContext(session_id="t"))
    assert result.success is False


# ---------------------------------------------------------------------------
# Issue B — FAIL_FAST enforcement
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fail_fast_returns_on_first_failure_without_rerouting() -> None:
    """FAIL_FAST must return immediately — no rerouting attempts."""
    provider_id = "ff-provider"
    model_id = "ff-model"
    invocation_count = 0

    class CountingFailProvider(BaseModelProvider):
        @property
        def provider_id(self) -> str:
            return provider_id

        def get_default_model_id(self) -> str:
            return model_id

        async def invoke(self, request: ModelInvocationRequest) -> ModelInvocationResponse:
            nonlocal invocation_count
            invocation_count += 1
            raise httpx.RequestError("timeout", request=httpx.Request("POST", "http://x"))

    catalog = _simple_catalog(model_id=model_id, provider_id=provider_id)
    registry = ProviderRegistry()
    registry.register(CountingFailProvider())
    router = ModelRouter(catalog=catalog)
    gateway = ProviderGateway(registry=registry, router=router)
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
                        recovery_policy=RecoveryPolicy.FAIL_FAST,
                        max_recovery_attempts=5,  # FAIL_FAST must override this
                        preferred_tier="FAST",
                    ),
                ),
            )
        ],
    )
    result = await runner.run(plan, TaskContext(session_id="t"))
    assert result.success is False
    # Model was invoked exactly once — FAIL_FAST prevented rerouting
    assert invocation_count == 1


# ---------------------------------------------------------------------------
# Issue B — quality_preference changes ranking
# ---------------------------------------------------------------------------


def test_quality_preference_quality_favours_high_quality_model() -> None:
    """quality_preference='quality' must elevate the highest quality_score model."""
    catalog = ModelCatalog()
    catalog.register(
        ModelDescriptor(
            model_id="high-quality",
            provider_id="p",
            tier=ModelTier.HEAVY,
            quality_score=95,
            priority=100,
            capabilities=ModelCapabilities(reasoning=True),
        )
    )
    catalog.register(
        ModelDescriptor(
            model_id="low-quality-fast",
            provider_id="p",
            tier=ModelTier.HEAVY,
            quality_score=60,
            priority=100,
            capabilities=ModelCapabilities(reasoning=True),
        )
    )
    # Pre-seed high latency on high-quality model so "balanced" might not pick it
    health = ModelHealthTracker()
    health.get_state("high-quality").record_success(5000.0)  # 5000ms EMA latency

    router = ModelRouter(catalog=catalog, health_tracker=health)
    reqs = CapabilityRequirements(requires_reasoning=True)
    strategy = ExecutionStrategy(
        capability_requirements=reqs,
        preferred_tier="HEAVY",
        quality_preference="quality",  # should override latency penalty
    )
    result = router.select_model(strategy)
    # Quality preference should pick the high quality model despite latency
    assert result.model_id == "high-quality"


def test_quality_preference_speed_favours_low_latency_model() -> None:
    """quality_preference='speed' must heavily penalise high-latency models."""
    catalog = ModelCatalog()
    catalog.register(
        ModelDescriptor(
            model_id="slow-high-quality",
            provider_id="p",
            tier=ModelTier.HEAVY,
            quality_score=95,
            priority=100,
            capabilities=ModelCapabilities(reasoning=True),
        )
    )
    catalog.register(
        ModelDescriptor(
            model_id="fast-lower-quality",
            provider_id="p",
            tier=ModelTier.HEAVY,
            quality_score=70,
            priority=100,
            capabilities=ModelCapabilities(reasoning=True),
        )
    )
    health = ModelHealthTracker()
    health.get_state("slow-high-quality").record_success(8000.0)   # 8s EMA
    health.get_state("fast-lower-quality").record_success(200.0)   # 200ms EMA

    router = ModelRouter(catalog=catalog, health_tracker=health)
    reqs = CapabilityRequirements(requires_reasoning=True)
    strategy = ExecutionStrategy(
        capability_requirements=reqs,
        preferred_tier="HEAVY",
        quality_preference="speed",
    )
    result = router.select_model(strategy)
    assert result.model_id == "fast-lower-quality"


# ---------------------------------------------------------------------------
# Issue C — max_latency_ms constraint enforcement
# ---------------------------------------------------------------------------


def test_max_latency_ms_excludes_slow_models_with_observed_ema() -> None:
    """Models whose observed EMA latency exceeds max_latency_ms must be excluded."""
    catalog = ModelCatalog()
    catalog.register(
        ModelDescriptor(
            model_id="slow-model",
            provider_id="p",
            tier=ModelTier.HEAVY,
            quality_score=95,
            capabilities=ModelCapabilities(reasoning=True),
        )
    )
    catalog.register(
        ModelDescriptor(
            model_id="fast-model",
            provider_id="p",
            tier=ModelTier.HEAVY,
            quality_score=70,
            capabilities=ModelCapabilities(reasoning=True),
        )
    )
    health = ModelHealthTracker()
    health.get_state("slow-model").record_success(6000.0)   # 6s EMA — exceeds 5s limit
    health.get_state("fast-model").record_success(800.0)    # 800ms EMA — within limit

    router = ModelRouter(catalog=catalog, health_tracker=health)
    reqs = CapabilityRequirements(requires_reasoning=True, max_latency_ms=5000)
    result = router.select_model(reqs)
    # slow-model must be excluded due to latency constraint
    assert result.model_id == "fast-model"


def test_max_latency_ms_does_not_exclude_models_without_ema_data() -> None:
    """Models without observed latency data must remain eligible when max_latency_ms is set."""
    catalog = ModelCatalog()
    catalog.register(
        ModelDescriptor(
            model_id="new-model",
            provider_id="p",
            tier=ModelTier.FAST,
            quality_score=80,
            capabilities=ModelCapabilities(),
        )
    )
    router = ModelRouter(catalog=catalog)
    reqs = CapabilityRequirements(max_latency_ms=1000)  # tight budget
    result = router.select_model(reqs)
    # new-model has no EMA → must not be excluded
    assert result.model_id == "new-model"


# ---------------------------------------------------------------------------
# Issue D — Health recovery is evidence-based, not time-based
# ---------------------------------------------------------------------------


def test_health_cooldown_expiry_does_not_reset_status() -> None:
    """Cooldown expiry makes the model eligible for a probe but does NOT reset status to HEALTHY.

    Status is only restored by record_success() — evidence-based recovery.
    """
    state = ModelHealthState(cooldown_seconds=0.01)  # 10ms cooldown
    state.record_failure()
    state.record_failure()
    state.record_failure()
    assert state.status == ModelHealthStatus.UNHEALTHY

    time.sleep(0.02)  # Wait for cooldown to expire

    # is_available() should return True (probe eligible) but status stays UNHEALTHY
    available = state.is_available()
    assert available is True
    assert state.status == ModelHealthStatus.UNHEALTHY, (
        "Status must NOT auto-reset on cooldown. Only record_success() restores HEALTHY."
    )


def test_health_record_success_restores_healthy_after_unhealthy() -> None:
    """Evidence-based recovery: record_success() after probe must restore HEALTHY."""
    state = ModelHealthState(cooldown_seconds=0.01)
    state.record_failure()
    state.record_failure()
    state.record_failure()
    assert state.status == ModelHealthStatus.UNHEALTHY

    time.sleep(0.02)
    assert state.is_available()  # probe eligible

    # Successful probe invocation
    state.record_success(latency_ms=300.0)
    assert state.status == ModelHealthStatus.HEALTHY
    assert state.snapshot_consecutive_failures == 0


def test_health_degraded_model_remains_eligible_for_routing() -> None:
    """DEGRADED models (1-2 failures) must remain eligible — not excluded like UNHEALTHY."""
    state = ModelHealthState()
    state.record_failure()
    assert state.status == ModelHealthStatus.DEGRADED
    assert state.is_available() is True


# ---------------------------------------------------------------------------
# Issue G — ProviderGateway raises explicitly for unknown provider
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_gateway_raises_key_error_for_unregistered_provider() -> None:
    """Gateway must raise KeyError explicitly — no silent default-model bypass."""
    from ahjin.providers.types import ContextualizedPrompt

    # Catalog references "unknown-provider" but nothing is registered in registry
    catalog = _simple_catalog(provider_id="unknown-provider", model_id="some-model")
    registry = ProviderRegistry()  # empty — no providers registered
    router = ModelRouter(catalog=catalog)
    gateway = ProviderGateway(registry=registry, router=router)

    prompt = ContextualizedPrompt(user_instruction="Hello")
    with pytest.raises(KeyError):
        await gateway.invoke(prompt=prompt, requirements=CapabilityRequirements())


# ---------------------------------------------------------------------------
# Issue J — Health state thread safety
# ---------------------------------------------------------------------------


def test_health_state_concurrent_failures_do_not_corrupt_count() -> None:
    """Multiple threads recording failures concurrently must not corrupt the counter."""
    state = ModelHealthState()
    n_threads = 20
    failures_each = 10

    def record_many_failures() -> None:
        for _ in range(failures_each):
            state.record_failure()

    threads = [threading.Thread(target=record_many_failures) for _ in range(n_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # Total failures must equal exactly n_threads * failures_each
    assert state.snapshot_consecutive_failures == n_threads * failures_each
    assert state.status == ModelHealthStatus.UNHEALTHY


def test_concurrent_requests_have_isolated_excluded_models() -> None:
    """excluded_models for recovery must be request-local, not shared.

    Two concurrent requests: if request A excludes model X, request B must
    still be able to select model X.
    """
    catalog = ModelCatalog()
    catalog.register(
        ModelDescriptor(
            model_id="model-a",
            provider_id="p",
            tier=ModelTier.FAST,
            quality_score=90,
            capabilities=ModelCapabilities(),
        )
    )
    catalog.register(
        ModelDescriptor(
            model_id="model-b",
            provider_id="p",
            tier=ModelTier.FAST,
            quality_score=80,
            capabilities=ModelCapabilities(),
        )
    )
    health = ModelHealthTracker()
    router = ModelRouter(catalog=catalog, health_tracker=health)

    reqs = CapabilityRequirements()

    # Request A excludes model-a
    result_a = router.select_model(reqs, excluded_model_ids={"model-a"})
    # Request B has no exclusions — must still be able to select model-a
    result_b = router.select_model(reqs, excluded_model_ids=None)

    assert result_a.model_id == "model-b"
    assert result_b.model_id == "model-a"  # model-a not excluded for B


# ---------------------------------------------------------------------------
# Capability + quality golden rule regression
# ---------------------------------------------------------------------------


def test_strong_incapable_model_never_beats_weaker_capable_model() -> None:
    """CRITICAL: A model missing a required capability must NEVER be selected."""
    catalog = ModelCatalog()
    catalog.register(
        ModelDescriptor(
            model_id="strong-no-vision",
            provider_id="p",
            tier=ModelTier.HEAVY,
            quality_score=99,
            capabilities=ModelCapabilities(reasoning=True, vision=False),
        )
    )
    catalog.register(
        ModelDescriptor(
            model_id="weaker-with-vision",
            provider_id="p",
            tier=ModelTier.HEAVY,
            quality_score=70,
            capabilities=ModelCapabilities(reasoning=True, vision=True),
        )
    )
    router = ModelRouter(catalog=catalog)
    reqs = CapabilityRequirements(requires_vision=True)
    result = router.select_model(reqs)
    assert result.model_id == "weaker-with-vision"


def test_all_incapable_models_raises_capability_unavailable() -> None:
    """If no capable model exists, CapabilityUnavailableError must be raised."""
    catalog = _simple_catalog(
        model_id="text-only",
        capabilities=ModelCapabilities(vision=False),
    )
    router = ModelRouter(catalog=catalog)
    with pytest.raises(CapabilityUnavailableError):
        router.select_model(CapabilityRequirements(requires_vision=True))
