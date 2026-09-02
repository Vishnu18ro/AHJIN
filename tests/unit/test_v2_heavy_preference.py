"""Targeted tests for HEAVY model preference order and MiniMax M3 removal.

Validates Section 6 assertions:
1. MiniMax M3 is absent from the active catalog.
2. Kimi K3 remains present.
3. Kimi K3 is preferred for an eligible HEAVY request.
4. Nemotron Ultra is selected when Kimi K3 is unhealthy/excluded/ineligible.
5. DeepSeek V4 Pro is selected when both Kimi and Nemotron Ultra are unavailable/ineligible.
6. DeepSeek V4 Flash remains the next eligible HEAVY candidate.
7. Capability constraints override preference.
8. max_latency_ms overrides preference.
9. Health filtering overrides preference.
10. Excluded models are never selected during recovery.
11. BERU contains no provider/model-specific routing knowledge.
"""

from __future__ import annotations

from ahjin.beru.orchestrator import BeruOrchestrator
from ahjin.beru.types import CapabilityRequirements, ExecutionStrategy
from ahjin.models.catalog import ModelCatalog, create_default_catalog
from ahjin.models.health import ModelHealthTracker
from ahjin.models.router import ModelRouter
from ahjin.models.types import ModelCapabilities, ModelDescriptor, ModelTier

# ---------------------------------------------------------------------------
# Assertion 1 & 2 — Active Catalog Contents
# ---------------------------------------------------------------------------


def test_minimax_m3_absent_from_default_catalog() -> None:
    """Assertion 1: MiniMax M3 must NOT be present in active catalog."""
    catalog = create_default_catalog()
    model_ids = [m.model_id for m in catalog.list_models()]
    assert "minimaxai/minimax-m3" not in model_ids


def test_kimi_k3_present_in_default_catalog() -> None:
    """Assertion 2: Kimi K3 must remain present in active catalog."""
    catalog = create_default_catalog()
    model_ids = [m.model_id for m in catalog.list_models()]
    assert "moonshotai/kimi-k3" in model_ids


def test_exact_active_catalog_models() -> None:
    """Verify active catalog contains exactly the 5 intended models."""
    catalog = create_default_catalog()
    model_ids = set(m.model_id for m in catalog.list_models())
    expected = {
        "nvidia/nemotron-3.5-lightning-30b-a3b",
        "moonshotai/kimi-k3",
        "nvidia/nemotron-3-ultra-550b-a55b",
        "deepseek-ai/deepseek-v4-pro-0813",
        "deepseek-ai/deepseek-v4-flash-0731",
    }
    assert model_ids == expected


# ---------------------------------------------------------------------------
# Assertion 3, 4, 5, 6 — HEAVY Preference Fallback Chain
# ---------------------------------------------------------------------------


def test_kimi_k3_is_first_preferred_heavy_model() -> None:
    """Assertion 3: Kimi K3 is preferred for an eligible HEAVY request."""
    catalog = create_default_catalog()
    router = ModelRouter(catalog=catalog)
    reqs = CapabilityRequirements(requires_reasoning=True)
    strategy = ExecutionStrategy(capability_requirements=reqs, preferred_tier="HEAVY")

    selection = router.select_model(strategy)
    assert selection.model_id == "moonshotai/kimi-k3"
    assert selection.tier == ModelTier.HEAVY


def test_catalog_preference_order_strictly_wins_over_higher_quality_score() -> None:
    """Explicit catalog priority MUST strictly win over a higher quality_score.

    Kimi K3: priority=200, quality_score=87
    Nemotron Ultra: priority=170, quality_score=95

    When both are eligible, Kimi K3 MUST be selected despite Nemotron Ultra
    having a higher quality score.
    """
    catalog = create_default_catalog()
    router = ModelRouter(catalog=catalog)

    for pref in ["quality", "balanced", "speed"]:
        strategy = ExecutionStrategy(
            capability_requirements=CapabilityRequirements(requires_reasoning=True),
            preferred_tier="HEAVY",
            quality_preference=pref,
        )
        selection = router.select_model(strategy)
        assert selection.model_id == "moonshotai/kimi-k3", (
            f"Under quality_preference='{pref}', {selection.model_id} was selected "
            "instead of higher-priority moonshotai/kimi-k3."
        )


def test_nemotron_ultra_selected_when_kimi_k3_excluded() -> None:
    """Assertion 4: Nemotron Ultra is selected when Kimi K3 is excluded."""
    catalog = create_default_catalog()
    router = ModelRouter(catalog=catalog)
    strategy = ExecutionStrategy(
        capability_requirements=CapabilityRequirements(requires_reasoning=True),
        preferred_tier="HEAVY",
    )

    selection = router.select_model(
        strategy, excluded_model_ids={"moonshotai/kimi-k3"}
    )
    assert selection.model_id == "nvidia/nemotron-3-ultra-550b-a55b"


def test_deepseek_pro_selected_when_kimi_and_nemotron_ultra_excluded() -> None:
    """Assertion 5: DeepSeek V4 Pro selected when Kimi & Nemotron Ultra unavailable."""
    catalog = create_default_catalog()
    router = ModelRouter(catalog=catalog)
    strategy = ExecutionStrategy(
        capability_requirements=CapabilityRequirements(requires_reasoning=True),
        preferred_tier="HEAVY",
    )

    selection = router.select_model(
        strategy,
        excluded_model_ids={"moonshotai/kimi-k3", "nvidia/nemotron-3-ultra-550b-a55b"},
    )
    assert selection.model_id == "deepseek-ai/deepseek-v4-pro-0813"


def test_deepseek_flash_selected_when_top3_heavy_excluded() -> None:
    """Assertion 6: DeepSeek V4 Flash remains the next eligible HEAVY candidate."""
    catalog = create_default_catalog()
    router = ModelRouter(catalog=catalog)
    strategy = ExecutionStrategy(
        capability_requirements=CapabilityRequirements(requires_reasoning=True),
        preferred_tier="HEAVY",
    )

    selection = router.select_model(
        strategy,
        excluded_model_ids={
            "moonshotai/kimi-k3",
            "nvidia/nemotron-3-ultra-550b-a55b",
            "deepseek-ai/deepseek-v4-pro-0813",
        },
    )
    assert selection.model_id == "deepseek-ai/deepseek-v4-flash-0731"


# ---------------------------------------------------------------------------
# Assertion 7, 8, 9, 10 — Overrides & Filters
# ---------------------------------------------------------------------------


def test_capability_constraints_override_preference() -> None:
    """Assertion 7: Capability constraints MUST override model preference.

    If a preferred model lacks a required capability (e.g. vision), a capable
    model MUST be selected instead.
    """
    catalog = ModelCatalog()

    # Kimi K3: Preferred priority=200, but vision=False
    catalog.register(
        ModelDescriptor(
            model_id="moonshotai/kimi-k3",
            provider_id="nvidia",
            tier=ModelTier.HEAVY,
            priority=200,
            quality_score=87,
            capabilities=ModelCapabilities(reasoning=True, vision=False),
        )
    )
    # Vision Model: priority=100, but vision=True
    catalog.register(
        ModelDescriptor(
            model_id="vision-heavy-model",
            provider_id="nvidia",
            tier=ModelTier.HEAVY,
            priority=100,
            quality_score=80,
            capabilities=ModelCapabilities(reasoning=True, vision=True),
        )
    )

    router = ModelRouter(catalog=catalog)
    reqs = CapabilityRequirements(requires_vision=True)
    strategy = ExecutionStrategy(capability_requirements=reqs, preferred_tier="HEAVY")

    selection = router.select_model(strategy)
    # Vision model MUST win despite lower priority
    assert selection.model_id == "vision-heavy-model"


def test_max_latency_ms_overrides_preference() -> None:
    """Assertion 8: max_latency_ms constraint MUST override preference."""
    catalog = create_default_catalog()
    health = ModelHealthTracker()

    # Kimi K3 has an observed EMA latency of 8000ms (exceeds 5000ms budget)
    health.get_state("moonshotai/kimi-k3").record_success(8000.0)
    # Nemotron Ultra has observed latency of 1500ms (within budget)
    health.get_state("nvidia/nemotron-3-ultra-550b-a55b").record_success(1500.0)

    router = ModelRouter(catalog=catalog, health_tracker=health)
    reqs = CapabilityRequirements(requires_reasoning=True, max_latency_ms=5000)
    strategy = ExecutionStrategy(capability_requirements=reqs, preferred_tier="HEAVY")

    selection = router.select_model(strategy)
    # Nemotron Ultra MUST win because Kimi exceeds max_latency_ms constraint
    assert selection.model_id == "nvidia/nemotron-3-ultra-550b-a55b"


def test_health_filtering_overrides_preference() -> None:
    """Assertion 9: Health filtering MUST override preference."""
    catalog = create_default_catalog()
    health = ModelHealthTracker()

    # Kimi K3 is UNHEALTHY (3 failures)
    health.record_failure("moonshotai/kimi-k3")
    health.record_failure("moonshotai/kimi-k3")
    health.record_failure("moonshotai/kimi-k3")

    router = ModelRouter(catalog=catalog, health_tracker=health)
    strategy = ExecutionStrategy(
        capability_requirements=CapabilityRequirements(requires_reasoning=True),
        preferred_tier="HEAVY",
    )

    selection = router.select_model(strategy)
    # Unhealthy Kimi K3 filtered out -> Nemotron Ultra selected
    assert selection.model_id == "nvidia/nemotron-3-ultra-550b-a55b"


def test_excluded_models_never_selected_during_recovery() -> None:
    """Assertion 10: Excluded models are NEVER selected during recovery routing."""
    catalog = create_default_catalog()
    router = ModelRouter(catalog=catalog)
    strategy = ExecutionStrategy(
        capability_requirements=CapabilityRequirements(requires_reasoning=True),
        preferred_tier="HEAVY",
    )

    excluded = {"moonshotai/kimi-k3", "nvidia/nemotron-3-ultra-550b-a55b"}
    selection = router.select_model(strategy, excluded_model_ids=excluded)
    assert selection.model_id not in excluded


# ---------------------------------------------------------------------------
# Assertion 11 — BERU Purity
# ---------------------------------------------------------------------------


def test_beru_contains_no_provider_or_model_specific_routing_knowledge() -> None:
    """Assertion 11: BERU strategy contains ZERO model IDs or provider names."""
    orchestrator = BeruOrchestrator()
    reqs = orchestrator.analyze_task_requirements(
        "Explain quantum entanglement deeply using Python"
    )
    strategy = ExecutionStrategy(capability_requirements=reqs)

    dump = str(strategy.model_dump()).lower()
    for forbidden in ["kimi", "nemotron", "deepseek", "minimax", "nvidia"]:
        assert forbidden not in dump, f"BERU strategy leaked forbidden identifier '{forbidden}'"
