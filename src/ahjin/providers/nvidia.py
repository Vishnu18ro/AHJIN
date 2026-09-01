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
        max_tokens: int | None = None,
    ) -> None:
        self.api_key = settings.nvidia_api_key if api_key is None else api_key
        self.base_url = (base_url or settings.nvidia_base_url).rstrip("/")
        self.default_model = (
            settings.nvidia_model_id if default_model is None else default_model
        )
        # max_tokens: configuration-driven, not hardcoded.
        # Operators set NVIDIA_MAX_TOKENS in environment. Default is 4096.
        self.max_tokens = max_tokens if max_tokens is not None else settings.nvidia_max_tokens

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

        t0_prep = time.monotonic()
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
            "max_tokens": self.max_tokens,
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        url = f"{self.base_url}/chat/completions"
        t_prep_ms = (time.monotonic() - t0_prep) * 1000.0

        logger.info("[PROFILE] Calling NVIDIA API start", model=payload["model"], url=url)

        t0_net = time.monotonic()
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(url, json=payload, headers=headers)
            t_net_ms = (time.monotonic() - t0_net) * 1000.0
            resp.raise_for_status()

            t0_parse = time.monotonic()
            data: dict[str, Any] = resp.json()
            t_parse_ms = (time.monotonic() - t0_parse) * 1000.0

        elapsed_ms = (time.monotonic() - start_time) * 1000.0

        logger.info(
            "[PROFILE] NVIDIA API response received",
            model=payload["model"],
            payload_prep_ms=round(t_prep_ms, 3),
            network_http_ms=round(t_net_ms, 3),
            json_parse_ms=round(t_parse_ms, 3),
            provider_total_ms=round(elapsed_ms, 3),
        )

        choices = data.get("choices", [])
        raw_content: str | None = choices[0]["message"].get("content") if choices else None

        if not raw_content:
            # Model returned empty or null content — surface as an invocation error
            # so the error boundary in HarnessRunner handles it correctly.
            raise ValueError(
                f"NVIDIA model '{payload['model']}' returned empty content. "
                "Try a different model or retry the request."
            )

        # Map NVIDIA's raw finish_reason to AHJIN's canonical FinishReason.
        # NVIDIA returns: 'stop' (natural end), 'length' (max_tokens hit), others.
        # Previously hardcoded to COMPLETE — this masked truncation events.
        raw_finish_reason: str = (
            choices[0].get("finish_reason") or "stop"
        ) if choices else "stop"
        if raw_finish_reason == "length":
            finish_reason = FinishReason.MAX_TOKENS
        elif raw_finish_reason in ("stop", "eos"):
            finish_reason = FinishReason.COMPLETE
        else:
            finish_reason = FinishReason.COMPLETE

        logger.info(
            "[PROFILE] NVIDIA finish_reason mapped",
            raw_finish_reason=raw_finish_reason,
            canonical_finish_reason=finish_reason.value,
            max_tokens_configured=payload["max_tokens"],
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
            finish_reason=finish_reason,
            usage=usage,
            latency_ms=elapsed_ms,
            provider_id=self.provider_id,
            model_id=str(payload["model"]),
        )
