"""Unit tests for canonical contracts validation."""

from ahjin.core.types import Modality, RequestMetadata, TaskContext, TaskRequest, UserIntent


def test_task_request_contract_validation() -> None:
    """Verify TaskRequest instantiates with canonical defaults."""
    intent = UserIntent(primary_text="Hello AHJIN", modality=Modality.TEXT)
    context = TaskContext(session_id="test_session")
    metadata = RequestMetadata(source_interface="test")

    request = TaskRequest(
        intent=intent,
        context=context,
        metadata=metadata,
    )

    assert request.task_id is not None
    assert request.correlation_id is not None
    assert request.intent.primary_text == "Hello AHJIN"
    assert request.context.session_id == "test_session"
    assert request.metadata.schema_version == "1.0"
