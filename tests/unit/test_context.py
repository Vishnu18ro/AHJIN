"""Unit tests for ContextAssembler."""

from ahjin.beru.types import ModelStepIntent
from ahjin.core.types import ConversationTurn, Role, TaskContext
from ahjin.harness.context import ContextAssembler


def test_context_assembler_assembles_prompt() -> None:
    """Verify ContextAssembler builds ContextualizedPrompt correctly."""
    assembler = ContextAssembler()
    intent = ModelStepIntent(instruction="Explain gravity")
    context = TaskContext(
        session_id="s1",
        conversation_history=[
            ConversationTurn(role=Role.USER, content="Hello"),
            ConversationTurn(role=Role.ASSISTANT, content="Hi! How can I help?"),
        ],
    )

    prompt = assembler.assemble(intent=intent, task_context=context)

    assert prompt.user_instruction == "Explain gravity"
    assert len(prompt.conversation_history) == 2
    assert prompt.system_instruction != ""
