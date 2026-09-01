"""Integration tests for TelegramMapper."""

from uuid import uuid4

from ahjin.core.types import TaskResult
from ahjin.interfaces.telegram.mapper import TelegramMapper


def test_telegram_mapper_to_task_request() -> None:
    request = TelegramMapper.to_task_request(chat_id=12345, message_text="Test msg")

    assert request.intent.primary_text == "Test msg"
    assert request.context.session_id == "telegram:12345"
    assert request.metadata.source_interface == "telegram"


def test_telegram_mapper_to_telegram_response() -> None:
    result = TaskResult(
        task_id=uuid4(),
        correlation_id=uuid4(),
        success=True,
        output_text="Response text",
    )

    response = TelegramMapper.to_telegram_response(result)
    assert response == "Response text"
