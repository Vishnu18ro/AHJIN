"""Base User Interface Adapter interface."""

from abc import ABC, abstractmethod


class BaseInterfaceAdapter(ABC):
    """Abstract interface for external user interface adapters."""

    @property
    @abstractmethod
    def interface_id(self) -> str:
        """Return unique interface identifier."""

    @abstractmethod
    async def start(self) -> None:
        """Start listening/handling interface events."""

    @abstractmethod
    async def stop(self) -> None:
        """Stop interface adapter."""
