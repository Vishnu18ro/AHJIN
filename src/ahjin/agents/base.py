"""Specialized Agent abstract contracts (Stubbed for v5)."""

from abc import ABC, abstractmethod
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from ahjin.core.errors import AhjinError


class AgentStepPayload(BaseModel):
    """Payload for invoking a specialized agent."""

    agent_type: str
    parameters: dict[str, Any] = Field(default_factory=dict)


class AgentResult(BaseModel):
    """Result returned by a specialized agent."""

    invocation_id: UUID = Field(default_factory=uuid4)
    agent_type: str
    success: bool
    output: Any | None = None
    error: AhjinError | None = None


class BaseAgent(ABC):
    """Abstract interface for all specialized agents."""

    @property
    @abstractmethod
    def agent_type(self) -> str:
        """Return agent identifier."""

    @abstractmethod
    async def run(self, payload: AgentStepPayload) -> AgentResult:
        """Run agent workflow."""
