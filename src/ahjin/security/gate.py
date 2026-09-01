"""Security & Permission boundary interface stubs (Stubbed for v2)."""

from abc import ABC, abstractmethod


class PermissionGate(ABC):
    """Abstract Permission Gate interface for checking tool execution rights."""

    @abstractmethod
    async def check_permission(self, tool_name: str, parameters: dict) -> bool:  # type: ignore[type-arg]
        """Check if action is authorized."""
