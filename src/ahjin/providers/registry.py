"""Provider Registry for discovery and management of BaseModelProviders.

The registry starts empty. Providers are registered by the application bootstrap
(e.g. main.py) at startup. This avoids eager provider instantiation — and the
config/credential initialization side-effects that come with it — merely because
the registry class is constructed.
"""

from ahjin.providers.base import BaseModelProvider


class ProviderRegistry:
    """Registry managing available model provider instances.

    Starts empty. Use register() to add providers.
    The application bootstrap is responsible for registering all providers
    before the registry is first used.
    """

    def __init__(self) -> None:
        self._providers: dict[str, BaseModelProvider] = {}
        self._default_provider_id: str | None = None

    def register(self, provider: BaseModelProvider, set_as_default: bool = False) -> None:
        """Register a provider instance.

        The first registered provider is automatically set as default
        unless a default has already been explicitly set.
        """
        self._providers[provider.provider_id] = provider
        if set_as_default or self._default_provider_id is None:
            self._default_provider_id = provider.provider_id

    def get_provider(self, provider_id: str) -> BaseModelProvider:
        """Get provider by identifier."""
        if provider_id not in self._providers:
            raise KeyError(f"Provider '{provider_id}' is not registered.")
        return self._providers[provider_id]

    def get_default_provider(self) -> BaseModelProvider:
        """Get default provider.

        Raises RuntimeError if no providers have been registered.
        """
        if self._default_provider_id is None:
            raise RuntimeError(
                "No providers registered. Call ProviderRegistry.register() "
                "before invoking the gateway."
            )
        return self.get_provider(self._default_provider_id)
