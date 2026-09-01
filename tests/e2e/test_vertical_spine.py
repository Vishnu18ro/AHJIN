"""End-to-End vertical spine test with mock provider."""

import pytest

from ahjin.beru.orchestrator import BeruOrchestrator
from ahjin.core.dispatcher import TaskDispatcher
from ahjin.harness.gateway import ProviderGateway
from ahjin.harness.runner import HarnessRunner
from ahjin.interfaces.telegram.mapper import TelegramMapper
from ahjin.providers.base import BaseModelProvider
from ahjin.providers.registry import ProviderRegistry
from ahjin.providers.types import ModelInvocationRequest, ModelInvocationResponse


class MockE2EProvider(BaseModelProvider):
    @property
    def provider_id(self) -> str:
        return "nvidia"

    def get_default_model_id(self) -> str:
        return "mock-nvidia-model"

    async def invoke(self, request: ModelInvocationRequest) -> ModelInvocationResponse:
        return ModelInvocationResponse(
            invocation_id=request.invocation_id,
            content="Mock E2E output response",
            provider_id=self.provider_id,
            model_id=request.model_id,
        )


@pytest.mark.asyncio
async def test_full_vertical_spine_flow() -> None:
    """Test full pipeline flow end-to-end.

    Telegram mapper -> TaskDispatcher -> BERU -> Harness -> Provider.
    """
    # 1. Setup mock provider & gateway
    registry = ProviderRegistry()
    registry.register(MockE2EProvider())
    gateway = ProviderGateway(registry=registry)

    # 2. Setup Harness, BERU, Dispatcher
    runner = HarnessRunner(gateway=gateway)
    orchestrator = BeruOrchestrator()
    dispatcher = TaskDispatcher(orchestrator=orchestrator, runner=runner)

    # 3. Simulate Telegram incoming update
    request = TelegramMapper.to_task_request(chat_id=999, message_text="What is AHJIN?")

    # 4. Dispatch request through Core
    result = await dispatcher.dispatch(request)

    # 5. Map result back to Telegram response
    output_text = TelegramMapper.to_telegram_response(result)

    assert result.success is True
    assert output_text == "Mock E2E output response"
