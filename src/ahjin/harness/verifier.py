"""Structural response verification boundary."""

from pydantic import BaseModel


class VerificationError(Exception):
    """Raised when response verification fails."""

    def __init__(self, message: str, model_id: str | None = None) -> None:
        super().__init__(message)
        self.model_id = model_id


class VerificationResult(BaseModel):
    """Result of response verification pass."""

    is_valid: bool
    reason: str | None = None


class ResponseVerifier:
    """Performs structural verification on model responses before returning to caller."""

    def verify(self, content: str) -> VerificationResult:
        """Verify model output text structure and non-emptiness."""
        if not content or not content.strip():
            return VerificationResult(
                is_valid=False,
                reason="Model output is empty or whitespace only.",
            )
        return VerificationResult(is_valid=True)
