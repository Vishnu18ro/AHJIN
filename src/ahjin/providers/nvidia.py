"""NVIDIA Model Provider implementation.

All NVIDIA-specific authentication, HTTP headers, payload formatting,
and API error handling stay entirely within this file.
"""

import time
from typing import Any

import httpx
import structlog

from ahjin.core.config import settings
from ahjin.providers.base import BaseModelProvider
from ahjin.providers.types import (
    FinishReason,
    ModelInvocationRequest,
    ModelInvocationResponse,
    TokenUsage,
)

logger = structlog.get_logger()


class NvidiaProvider(BaseModelProvider):
    """NVIDIA API Model Provider."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        default_model: str | None = None,
    ) -> None:
        self.api_key = settings.nvidia_api_key if api_key is None else api_key
        self.base_url = (base_url or settings.nvidia_base_url).rstrip("/")
        self.default_model = (
            settings.nvidia_model_id if default_model is None else default_model
        )

        # Fast-fail: do not allow construction with unconfigured credentials or model.
        # model selection is operator-driven configuration, not a code default (ADR-003).
        if not self.default_model:
            raise ValueError(
                "NVIDIA_MODEL_ID is not configured. "
                "Set it in environment or .env before constructing NvidiaProvider."
            )
        if not self.api_key:
            raise ValueError(
                "NVIDIA_API_KEY is not configured. "
                "Set it in environment or .env before constructing NvidiaProvider."
            )

    @property
    def provider_id(self) -> str:
        return "nvidia"

    def get_default_model_id(self) -> str:
        return self.default_model

    async def invoke(self, request: ModelInvocationRequest) -> ModelInvocationResponse:
        """Invoke NVIDIA OpenAI-compatible chat completions API."""
        start_time = time.monotonic()

        messages: list[dict[str, str]] = []
        if request.prompt.system_instruction:
            messages.append({"role": "system", "content": request.prompt.system_instruction})

        for turn in request.prompt.conversation_history:
            messages.append({"role": turn.role.value, "content": turn.content})

        messages.append({"role": "user", "content": request.prompt.user_instruction})

        payload = {
            "model": request.model_id or self.default_model,
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 1024,
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        url = f"{self.base_url}/chat/completions"

        logger.info("Calling NVIDIA API", model=payload["model"], url=url)

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            data: dict[str, Any] = resp.json()

        elapsed_ms = (time.monotonic() - start_time) * 1000.0

        choices = data.get("choices", [])
        raw_content: str | None = choices[0]["message"].get("content") if choices else None

        if not raw_content:
            # Model returned empty or null content — surface as an invocation error
            # so the error boundary in HarnessRunner handles it correctly.
            raise ValueError(
                f"NVIDIA model '{payload['model']}' returned empty content. "
                "Try a different model or retry the request."
            )

        usage_data = data.get("usage", {})
        usage = TokenUsage(
            prompt_tokens=usage_data.get("prompt_tokens", 0),
            completion_tokens=usage_data.get("completion_tokens", 0),
            total_tokens=usage_data.get("total_tokens", 0),
        )

        return ModelInvocationResponse(
            invocation_id=request.invocation_id,
            content=raw_content,
            finish_reason=FinishReason.COMPLETE,
            usage=usage,
            latency_ms=elapsed_ms,
            provider_id=self.provider_id,
            model_id=str(payload["model"]),
        )
