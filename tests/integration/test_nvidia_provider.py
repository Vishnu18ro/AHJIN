"""Integration test structure for NvidiaProvider."""

import pytest

from ahjin.harness.context import ContextualizedPrompt
from ahjin.providers.nvidia import NvidiaProvider
from ahjin.providers.types import ModelInvocationRequest


@pytest.mark.asyncio
async def test_nvidia_provider_initialization() -> None:
    """Verify NvidiaProvider initializes cleanly with settings."""
    provider = NvidiaProvider(api_key="test_key", default_model="test-model")
    assert provider.provider_id == "nvidia"
    assert provider.get_default_model_id() == "test-model"

    request = ModelInvocationRequest(
        prompt=ContextualizedPrompt(user_instruction="Hi"),
        model_id="test-model",
    )
    assert request.model_id == "test-model"
