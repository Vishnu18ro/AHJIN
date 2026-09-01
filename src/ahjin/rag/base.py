"""RAG & Knowledge retrieval abstract contracts (Stubbed for v4)."""

from abc import ABC, abstractmethod

from pydantic import BaseModel, Field


class RetrievalChunk(BaseModel):
    """Document retrieval chunk contract."""

    content: str
    source_uri: str
    score: float = 0.0


class RetrievalContext(BaseModel):
    """Retrieved document knowledge contract."""

    chunks: list[RetrievalChunk] = Field(default_factory=list)  # pyright: ignore[reportUnknownVariableType]


class BaseRagEngine(ABC):
    """Abstract interface for RAG engine subsystem."""

    @abstractmethod
    async def retrieve(self, query: str) -> RetrievalContext:
        """Retrieve relevant document chunks."""
