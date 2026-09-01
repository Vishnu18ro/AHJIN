"""Memory subsystem abstract contracts (Stubbed for v3)."""

from abc import ABC, abstractmethod

from pydantic import BaseModel, Field


class MemoryContext(BaseModel):
    """Retrieved memory context contract."""

    user_facts: list[str] = Field(default_factory=list)
    relevant_past_interactions: list[str] = Field(default_factory=list)


class BaseMemoryStore(ABC):
    """Abstract interface for Memory store subsystem."""

    @abstractmethod
    async def get_context(self, session_id: str, query: str) -> MemoryContext:
        """Fetch memory context."""
