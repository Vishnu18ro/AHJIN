"""Canonical error definitions for AHJIN 2.0."""

from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class ErrorCategory(str, Enum):
    """Canonical error categories."""

    VALIDATION = "VALIDATION"
    PROVIDER = "PROVIDER"
    TOOL = "TOOL"
    TIMEOUT = "TIMEOUT"
    CANCELLATION = "CANCELLATION"
    INTERNAL = "INTERNAL"


class AhjinError(BaseModel):
    """Canonical error contract across AHJIN subsystems."""

    error_id: UUID = Field(default_factory=uuid4)
    category: ErrorCategory
    code: str
    message: str
    is_retryable: bool = False
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
