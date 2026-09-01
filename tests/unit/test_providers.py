"""Unit tests for Provider Registry."""

import pytest

from ahjin.providers.base import BaseModelProvider
from ahjin.providers.registry import ProviderRegistry
from ahjin.providers.types import ModelInvocationRequest, ModelInvocationResponse


class MockProvider(BaseModelProvider):
    """Mock Provider for testing."""

    @property
    def provider_id(self) -> str:
        return "mock"

    def get_default_model_id(self) -> str:
        return "mock-model"

    async def invoke(self, request: ModelInvocationRequest) -> ModelInvocationResponse:
        return ModelInvocationResponse(
            invocation_id=request.invocation_id,
            content="Mock response",
            provider_id=self.provider_id,
            model_id=request.model_id,
        )


class AnotherMockProvider(BaseModelProvider):
    """Second mock provider for multi-provider tests."""

    @property
    def provider_id(self) -> str:
        return "another_mock"

    def get_default_model_id(self) -> str:
        return "another-mock-model"

    async def invoke(self, request: ModelInvocationRequest) -> ModelInvocationResponse:
        return ModelInvocationResponse(
            invocation_id=request.invocation_id,
            content="Another mock response",
            provider_id=self.provider_id,
            model_id=request.model_id,
        )


def test_provider_registry_starts_empty_and_raises_without_providers() -> None:
    """Registry must not eagerly initialize any provider. Empty registry must raise."""
    registry = ProviderRegistry()
    with pytest.raises(RuntimeError, match="No providers registered"):
        registry.get_default_provider()


def test_provider_registry_first_registered_becomes_default() -> None:
    """First registered provider is automatically set as default."""
    registry = ProviderRegistry()
    mock_provider = MockProvider()
    registry.register(mock_provider)

    assert registry.get_default_provider().provider_id == "mock"


def test_provider_registry_registration_and_retrieval() -> None:
    """Verify registry registers and retrieves providers by ID."""
    registry = ProviderRegistry()
    mock_provider = MockProvider()

    registry.register(mock_provider)

    assert registry.get_provider("mock") == mock_provider


def test_provider_registry_explicit_default_override() -> None:
    """Explicit set_as_default overrides auto-default."""
    registry = ProviderRegistry()
    first = MockProvider()
    second = AnotherMockProvider()

    registry.register(first)
    registry.register(second, set_as_default=True)

    assert registry.get_default_provider().provider_id == "another_mock"


def test_provider_registry_does_not_import_nvidia_credentials() -> None:
    """Constructing ProviderRegistry must not touch NVIDIA config or credentials.

    Regression: ProviderRegistry.__init__ previously instantiated NvidiaProvider()
    which read settings.nvidia_api_key. This verifies it no longer does so.
    """
    # If ProviderRegistry.__init__ still eagerly creates NvidiaProvider,
    # this would fail because nvidia_model_id has no default and Settings() would raise.
    # (In test environment, NVIDIA_MODEL_ID is not set.)
    # This must succeed without any env variables set.
    registry = ProviderRegistry()
    # Registry is empty — no credentials read
    assert registry._default_provider_id is None  # noqa: SLF001
