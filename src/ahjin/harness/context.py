"""ContextAssembler — Context construction boundary.

v1 implementation lives under Harness for simplicity.
This does not imply context construction is permanently owned by Harness at the architectural level.

ContextualizedPrompt is defined in ahjin.providers.types as it is a provider-boundary concept.
ContextAssembler constructs it; providers consume it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ahjin.beru.types import ModelStepIntent
from ahjin.core.types import TaskContext
from ahjin.providers.types import ContextualizedPrompt

if TYPE_CHECKING:
    from ahjin.harness.state import StepResult
    from ahjin.memory.base import MemoryContext
    from ahjin.rag.base import RetrievalContext

__all__ = ["ContextAssembler", "ContextualizedPrompt"]


class ContextAssembler:
    """Assembles prompt content from context sources."""

    def assemble(
        self,
        intent: ModelStepIntent,
        task_context: TaskContext,
        memory: "MemoryContext | None" = None,
        retrieval: "RetrievalContext | None" = None,
        prior_results: list["StepResult"] | None = None,
    ) -> ContextualizedPrompt:
        """Assemble ContextualizedPrompt from task context and intent."""
        return ContextualizedPrompt(
            conversation_history=task_context.conversation_history,
            user_instruction=intent.instruction,
        )

