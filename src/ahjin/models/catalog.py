"""ModelCatalog — In-memory registry of known model descriptors."""

import structlog

from ahjin.models.types import ModelCapabilities, ModelDescriptor, ModelLimits, ModelTier

logger = structlog.get_logger()


class ModelCatalog:
    """In-memory catalog managing available ModelDescriptors."""

    def __init__(self) -> None:
        self._models: dict[str, ModelDescriptor] = {}

    def register(self, descriptor: ModelDescriptor) -> None:
        """Register a ModelDescriptor in the catalog."""
        self._models[descriptor.model_id] = descriptor
        logger.info(
            "Registered model in catalog",
            model_id=descriptor.model_id,
            provider_id=descriptor.provider_id,
            tier=descriptor.tier.value,
            quality_score=descriptor.quality_score,
            endpoint_verified=descriptor.endpoint_verified,
        )

    def get_model(self, model_id: str) -> ModelDescriptor:
        """Retrieve model descriptor by ID."""
        if model_id not in self._models:
            raise KeyError(f"Model '{model_id}' not found in ModelCatalog.")
        return self._models[model_id]

    def list_models(self) -> list[ModelDescriptor]:
        """List all active registered model descriptors."""
        return [m for m in self._models.values() if m.is_active]


def create_default_catalog() -> ModelCatalog:
    """Create and return default ModelCatalog seeded with candidate models.

    Active catalog (5 models):
      FAST  tier: Nemotron Lightning 30B
      HEAVY tier: Kimi K3 (preferred #1), Nemotron Ultra 550B (#2),
                  DeepSeek V4 Pro (#3), DeepSeek V4 Flash (#4)

    Explicit preference is encoded in ``priority``. The router ranking formula
    weights priority heavily (×10) so that catalog preference ordering is always
    preserved among otherwise-eligible candidates, regardless of quality_preference
    mode. quality_score still differentiates within the same-priority group.
    """
    catalog = ModelCatalog()

    # 1. FAST EXECUTION TIER Candidate (Verified Active Endpoint)
    catalog.register(
        ModelDescriptor(
            model_id="nvidia/nemotron-3.5-lightning-30b-a3b",
            provider_id="nvidia",
            tier=ModelTier.FAST,
            capabilities=ModelCapabilities(
                reasoning=False,
                coding=True,
                vision=False,
                tool_calling=True,
                long_context=False,
            ),
            limits=ModelLimits(max_context_tokens=128000, max_output_tokens=4096),
            priority=200,
            quality_score=85,
            endpoint_verified=True,
        )
    )

    # 2. HEAVY / CORE REASONING TIER Candidates — preference order encoded in priority.
    #    Kimi K3 (priority=200) → Nemotron Ultra (170) → DeepSeek Pro (150) → DeepSeek Flash (130)

    # Preference #1: Kimi K3
    catalog.register(
        ModelDescriptor(
            model_id="moonshotai/kimi-k3",
            provider_id="nvidia",
            tier=ModelTier.HEAVY,
            capabilities=ModelCapabilities(
                reasoning=True,
                coding=True,
                vision=False,
                tool_calling=True,
                long_context=True,
            ),
            limits=ModelLimits(max_context_tokens=128000, max_output_tokens=4096),
            priority=200,
            quality_score=87,
            endpoint_verified=False,
        )
    )

    # Preference #2: Nemotron Ultra 550B
    catalog.register(
        ModelDescriptor(
            model_id="nvidia/nemotron-3-ultra-550b-a55b",
            provider_id="nvidia",
            tier=ModelTier.HEAVY,
            capabilities=ModelCapabilities(
                reasoning=True,
                coding=True,
                vision=False,
                tool_calling=True,
                long_context=True,
            ),
            limits=ModelLimits(max_context_tokens=128000, max_output_tokens=4096),
            priority=170,
            quality_score=95,
            endpoint_verified=True,
        )
    )

    # Preference #3: DeepSeek V4 Pro
    catalog.register(
        ModelDescriptor(
            model_id="deepseek-ai/deepseek-v4-pro-0813",
            provider_id="nvidia",
            tier=ModelTier.HEAVY,
            capabilities=ModelCapabilities(
                reasoning=True,
                coding=True,
                vision=False,
                tool_calling=True,
                long_context=True,
            ),
            limits=ModelLimits(max_context_tokens=128000, max_output_tokens=4096),
            priority=150,
            quality_score=92,
            endpoint_verified=False,
        )
    )

    # Preference #4: DeepSeek V4 Flash
    catalog.register(
        ModelDescriptor(
            model_id="deepseek-ai/deepseek-v4-flash-0731",
            provider_id="nvidia",
            tier=ModelTier.HEAVY,
            capabilities=ModelCapabilities(
                reasoning=True,
                coding=True,
                vision=False,
                tool_calling=True,
                long_context=True,
            ),
            limits=ModelLimits(max_context_tokens=128000, max_output_tokens=4096),
            priority=130,
            quality_score=90,
            endpoint_verified=False,
        )
    )

    return catalog
