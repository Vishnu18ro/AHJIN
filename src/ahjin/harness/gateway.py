"""ProviderGateway — Capability matching and model provider lookup.

v1 behaviour: uses the registry default provider unconditionally.
CapabilityRequirements are received and logged; sophisticated routing
is deferred to a future routing layer (see architecture docs).
"""

import structlog

from ahjin.beru.types import CapabilityRequirements
from ahjin.providers.base import BaseModelProvider
from ahjin.providers.registry import ProviderRegistry
from ahjin.providers.types import (
    ContextualizedPrompt,
    ModelInvocationRequest,
    ModelInvocationResponse,
)

logger = structlog.get_logger()


class ProviderGateway:
    """Matches capability requirements to concrete providers and invokes them.

    v1: defers capability-based routing to future implementation.
    The default provider is used for all requests.
    CapabilityRequirements are forwarded to the provider and logged.
    """

    def __init__(self, registry: ProviderRegistry | None = None) -> None:
        self.registry = registry or ProviderRegistry()

    async def invoke(
        self,
        prompt: ContextualizedPrompt,
        requirements: CapabilityRequirements,
    ) -> ModelInvocationResponse:
        """Resolve provider and invoke model.

        v1 routing: always uses the registry default provider.
        CapabilityRequirements are logged for observability.
        TODO: implement capability-based provider selection when multiple
        providers with distinct capabilities are registered.
        """
        # v1: Log requirements explicitly — capability matching not yet implemented.
        # Do NOT silently discard them; they are a canonical architectural concept.
        logger.debug(
            "CapabilityRequirements received (v1: default provider used)",
            requires_reasoning=requirements.requires_reasoning,
            requires_code=requirements.requires_code,
            requires_vision=requirements.requires_vision,
            max_latency_ms=requirements.max_latency_ms,
        )

        provider: BaseModelProvider = self.registry.get_default_provider()

        request = ModelInvocationRequest(
            prompt=prompt,
            model_id=provider.get_default_model_id(),
        )

        logger.info(
            "Invoking provider via gateway",
            provider_id=provider.provider_id,
            model_id=request.model_id,
        )

        return await provider.invoke(request)

