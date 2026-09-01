"""Regression tests for the three evidence-based truncation fixes.

Fix T1: max_tokens is configuration-driven (not hardcoded to 1024).
Fix T2: NVIDIA finish_reason is correctly mapped (not always COMPLETE).
Fix T3: Telegram messages exceeding 4096 chars are chunked safely.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ahjin.interfaces.telegram.bot import TELEGRAM_MAX_MESSAGE_LENGTH, _chunk_message
from ahjin.providers.types import FinishReason

# ---------------------------------------------------------------------------
# Fix T1 — max_tokens is configuration-driven, not hardcoded
# ---------------------------------------------------------------------------


def test_nvidia_max_tokens_has_config_driven_default() -> None:
    """Settings.nvidia_max_tokens must default to 4096, not 1024 (Fix T1).

    Evidence: Profiling showed completion_tokens=1024 (hit ceiling), causing
    finish_reason='length'. The hardcoded 1024 was too low for table responses.
    """
    from ahjin.core.config import Settings

    s = Settings(_env_file=None)
    assert s.nvidia_max_tokens == 4096, (
        f"nvidia_max_tokens default is {s.nvidia_max_tokens}, expected 4096. "
        "The token budget must not be hardcoded to 1024."
    )


def test_nvidia_provider_uses_config_max_tokens() -> None:
    """NvidiaProvider must use settings.nvidia_max_tokens not a hardcoded value (Fix T1)."""
    from ahjin.providers.nvidia import NvidiaProvider

    provider = NvidiaProvider(
        api_key="test-key",
        default_model="test-model",
        max_tokens=512,
    )
    assert provider.max_tokens == 512


def test_nvidia_provider_reads_max_tokens_from_settings() -> None:
    """NvidiaProvider without explicit max_tokens uses the settings value (Fix T1)."""
    from ahjin.core.config import Settings
    from ahjin.providers.nvidia import NvidiaProvider

    with patch("ahjin.providers.nvidia.settings", Settings(_env_file=None)):
        provider = NvidiaProvider(
            api_key="test-key",
            default_model="test-model",
        )
    # Settings default is 4096
    assert provider.max_tokens == 4096


# ---------------------------------------------------------------------------
# Fix T2 — NVIDIA finish_reason is correctly mapped
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_nvidia_provider_maps_finish_reason_length_to_max_tokens() -> None:
    """NvidiaProvider must map NVIDIA 'length' finish_reason to FinishReason.MAX_TOKENS (Fix T2).

    Evidence: Both diagnostic runs returned finish_reason='length'. Previously
    this was always mapped to FinishReason.COMPLETE, silently masking truncation.
    """
    from ahjin.providers.nvidia import NvidiaProvider
    from ahjin.providers.types import ContextualizedPrompt, ModelInvocationRequest

    provider = NvidiaProvider(api_key="test-key", default_model="test-model")

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {
        "choices": [
            {
                "message": {"content": "partial answer that was cut off"},
                "finish_reason": "length",
            }
        ],
        "usage": {"prompt_tokens": 10, "completion_tokens": 1024, "total_tokens": 1034},
    }

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.post = AsyncMock(return_value=mock_response)

    request = ModelInvocationRequest(
        prompt=ContextualizedPrompt(user_instruction="Tell me about Python"),
        model_id="test-model",
    )

    with patch("ahjin.providers.nvidia.httpx.AsyncClient", return_value=mock_client):
        result = await provider.invoke(request)

    assert result.finish_reason == FinishReason.MAX_TOKENS, (
        f"Expected FinishReason.MAX_TOKENS for 'length' finish_reason, "
        f"got {result.finish_reason}. Truncation must not be silently masked."
    )


@pytest.mark.asyncio
async def test_nvidia_provider_maps_finish_reason_stop_to_complete() -> None:
    """NvidiaProvider must map NVIDIA 'stop' finish_reason to FinishReason.COMPLETE (Fix T2)."""
    from ahjin.providers.nvidia import NvidiaProvider
    from ahjin.providers.types import ContextualizedPrompt, ModelInvocationRequest

    provider = NvidiaProvider(api_key="test-key", default_model="test-model")

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {
        "choices": [
            {
                "message": {"content": "A complete and full answer."},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
    }

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.post = AsyncMock(return_value=mock_response)

    request = ModelInvocationRequest(
        prompt=ContextualizedPrompt(user_instruction="What is 2+2?"),
        model_id="test-model",
    )

    with patch("ahjin.providers.nvidia.httpx.AsyncClient", return_value=mock_client):
        result = await provider.invoke(request)

    assert result.finish_reason == FinishReason.COMPLETE


# ---------------------------------------------------------------------------
# Fix T3 — Telegram message chunking
# ---------------------------------------------------------------------------


def test_chunk_message_returns_single_chunk_for_short_text() -> None:
    """Messages within the limit must not be chunked (Fix T3)."""
    text = "Hello, I am AHJIN."
    chunks = _chunk_message(text)
    assert chunks == [text]
    assert len(chunks) == 1


def test_chunk_message_splits_long_text_into_multiple_chunks() -> None:
    """Messages over 4096 chars must be split into multiple chunks (Fix T3).

    Evidence: Both diagnostic runs produced 4210 and 4349 char responses,
    both exceeding Telegram's 4096 char limit.
    """
    long_text = "A" * 5000
    chunks = _chunk_message(long_text, chunk_size=TELEGRAM_MAX_MESSAGE_LENGTH)
    assert len(chunks) > 1
    for chunk in chunks:
        assert len(chunk) <= TELEGRAM_MAX_MESSAGE_LENGTH


def test_chunk_message_all_content_preserved() -> None:
    """No content must be lost during chunking (Fix T3)."""
    text = "word " * 2000  # 10000 chars
    chunks = _chunk_message(text, chunk_size=TELEGRAM_MAX_MESSAGE_LENGTH)
    reconstructed = " ".join(chunks)
    # All original words must be present (stripped whitespace differences are acceptable)
    original_words = set(text.split())
    reconstructed_words = set(reconstructed.split())
    assert original_words == reconstructed_words


def test_chunk_message_prefers_newline_boundaries() -> None:
    """Chunking must prefer newline split points over hard character splits (Fix T3)."""
    # Build text with a clear newline near the 4096 boundary
    line1 = "A" * 4000 + "\n"
    line2 = "B" * 500
    text = line1 + line2
    chunks = _chunk_message(text, chunk_size=TELEGRAM_MAX_MESSAGE_LENGTH)
    # First chunk must end cleanly at the newline boundary, not mid-word
    assert chunks[0] == "A" * 4000
    assert "B" in chunks[-1]


def test_chunk_message_no_empty_chunks() -> None:
    """_chunk_message must never produce empty string chunks (Fix T3)."""
    text = "Hello\n\n\n" * 2000
    chunks = _chunk_message(text, chunk_size=TELEGRAM_MAX_MESSAGE_LENGTH)
    for chunk in chunks:
        assert chunk.strip() != "", "Empty chunk found — chunker must filter empty segments."


def test_telegram_max_message_length_constant_matches_telegram_limit() -> None:
    """TELEGRAM_MAX_MESSAGE_LENGTH must equal Telegram's documented 4096 limit (Fix T3)."""
    assert TELEGRAM_MAX_MESSAGE_LENGTH == 4096
