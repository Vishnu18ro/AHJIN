"""Telegram Bot Adapter — V2 with runtime observability footer and /health /models commands."""

import asyncio
import time
from typing import Any

import structlog
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from ahjin.core.config import settings
from ahjin.core.dispatcher import TaskDispatcher
from ahjin.core.types import RuntimeInfo
from ahjin.interfaces.base import BaseInterfaceAdapter
from ahjin.interfaces.telegram.mapper import TelegramMapper
from ahjin.models.health import ModelHealthStatus
from ahjin.models.router import ModelRouter

logger = structlog.get_logger()

# Telegram's hard per-message character limit.
# Messages exceeding this are split into sequential chunks.
TELEGRAM_MAX_MESSAGE_LENGTH = 4096

# Maximum length for the main body before appending footer.
# Footer is always kept on the final chunk.
_FOOTER_RESERVED = 350


def _chunk_message(text: str, chunk_size: int = TELEGRAM_MAX_MESSAGE_LENGTH) -> list[str]:
    """Split text into chunks of at most chunk_size characters.

    Splits on newline or space boundaries where possible to avoid
    cutting mid-word. Falls back to hard split if no boundary exists.
    """
    if len(text) <= chunk_size:
        return [text]

    chunks: list[str] = []
    while text:
        if len(text) <= chunk_size:
            chunks.append(text)
            break
        # Prefer splitting on a newline or space within the budget
        split_at = text.rfind("\n", 0, chunk_size)
        if split_at == -1:
            split_at = text.rfind(" ", 0, chunk_size)
        if split_at == -1:
            # No safe boundary found — hard split at chunk_size
            split_at = chunk_size
        chunks.append(text[:split_at].rstrip())
        text = text[split_at:].lstrip()
    return [c for c in chunks if c]


def _model_short_name(model_id: str) -> str:
    """Return a compact, human-readable model name for the footer."""
    label_map = {
        "nvidia/nemotron-3.5-lightning-30b-a3b": "Nemotron Lightning 30B",
        "nvidia/nemotron-3-ultra-550b-a55b": "Nemotron Ultra 550B",
        "deepseek-ai/deepseek-v4-pro-0813": "DeepSeek V4 Pro",
        "deepseek-ai/deepseek-v4-flash-0731": "DeepSeek V4 Flash",
        "moonshotai/kimi-k3": "Kimi K3",
    }
    return label_map.get(model_id, model_id.split("/")[-1])


def _health_icon(status: str) -> str:
    """Map health status string to a compact emoji indicator."""
    return {
        ModelHealthStatus.HEALTHY.value: "🟢",
        ModelHealthStatus.DEGRADED.value: "🟡",
        ModelHealthStatus.UNHEALTHY.value: "🔴",
    }.get(status, "⚪")


def _build_runtime_footer(info: RuntimeInfo) -> str:
    """Build compact runtime observability footer from RuntimeInfo.

    Only shows what was actually measured. Does not fabricate metrics.
    Never exposes API keys, tokens, stack traces, or raw HTTP payloads.
    """
    route_label = "↪ Rerouted" if info.was_rerouted else "Direct"
    health_icon = _health_icon(info.health_status)

    lines = [
        "━━━━━━━━━━━━━━━━",
        "⚡ AHJIN Runtime",
        f"Model: {_model_short_name(info.selected_model)}",
        f"Route: {info.tier}",
        f"AHJIN: {info.ahjin_internal_ms:.0f}ms",
        f"Model: {info.model_api_ms:.0f}ms",
        f"Total: {info.total_ms:.0f}ms",
        f"Path:  {route_label}",
        f"Health: {health_icon} {info.health_status.title()}",
    ]

    if info.was_rerouted and info.failed_model:
        lines.append(f"From: {_model_short_name(info.failed_model)}")
        if info.failure_reason:
            lines.append(f"Reason: {info.failure_reason}")

    lines.append("━━━━━━━━━━━━━━━━")
    return "\n".join(lines)


def _build_health_snapshot(router: ModelRouter) -> str:
    """Build a compact health snapshot for /health command output."""
    models = router.catalog.list_models()
    if not models:
        return "No models registered."

    lines = ["<b>AHJIN Model Health</b>", ""]
    for descriptor in models:
        state = router.health_tracker.get_state(descriptor.model_id)
        status = state.snapshot_status.value
        icon = _health_icon(status)
        ema = state.snapshot_ema_latency_ms
        failures = state.snapshot_consecutive_failures

        name = _model_short_name(descriptor.model_id)
        tier_label = descriptor.tier.value

        if ema > 0:
            latency_label = f"EMA {ema / 1000:.1f}s"
        else:
            latency_label = "no latency data"

        status_line = f"{icon} {name} [{tier_label}]"
        detail_line = f"   {status.title()}"
        if failures > 0:
            detail_line += f" · {failures} failure{'s' if failures != 1 else ''}"
        detail_line += f" · {latency_label}"

        lines.append(status_line)
        lines.append(detail_line)
        lines.append("")

    return "\n".join(lines).strip()


class TelegramAdapter(BaseInterfaceAdapter):
    """Telegram Interface Adapter — V2 with runtime observability."""

    def __init__(
        self,
        token: str | None = None,
        dispatcher: TaskDispatcher | None = None,
        router: ModelRouter | None = None,
    ) -> None:
        self.token = token or settings.telegram_bot_token
        self.dispatcher = dispatcher or TaskDispatcher()
        self.router = router  # Optional; enables /health and /models commands
        self.app: Application[Any, Any, Any, Any, Any, Any] | None = None
        self._stop_event: asyncio.Event = asyncio.Event()

    @property
    def interface_id(self) -> str:
        return "telegram"

    async def _start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /start command."""
        if update.message:
            await update.message.reply_text(
                "Welcome to AHJIN 2.0 — Personal Agentic AI Operating Layer."
            )

    async def _health_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /health command — compact model health snapshot."""
        if not update.message:
            return
        if self.router is None:
            await update.message.reply_text("Health tracking not available.")
            return
        snapshot = _build_health_snapshot(self.router)
        await update.message.reply_text(snapshot, parse_mode="HTML")

    async def _models_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /models command — alias for /health."""
        await self._health_command(update, context)

    async def _handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle incoming text messages."""
        if not update.message or not update.message.text:
            return

        t0_recv = time.monotonic()
        chat_id = update.message.chat_id
        text = update.message.text

        logger.info("[PROFILE] Telegram update received", chat_id=chat_id, text_length=len(text))

        # 1. Map Telegram input to TaskRequest
        t0_map = time.monotonic()
        request = TelegramMapper.to_task_request(chat_id, text)
        t_map_ms = (time.monotonic() - t0_map) * 1000.0

        # 2. Dispatch to AHJIN Core — adapter-level error boundary.
        t0_dispatch = time.monotonic()
        try:
            result = await self.dispatcher.dispatch(request)
        except Exception as exc:
            logger.error("Unhandled dispatch error", chat_id=chat_id, error=str(exc))
            await update.message.reply_text("An internal error occurred. Please try again.")
            return
        t_dispatch_ms = (time.monotonic() - t0_dispatch) * 1000.0

        # 3. Map TaskResult to Telegram output
        response_text = TelegramMapper.to_telegram_response(result)

        # 4. Build runtime footer if observability data is available
        footer = ""
        if result.runtime_info is not None:
            # Override total_ms with the full wall-clock time including Telegram mapping overhead
            total_wall_ms = (time.monotonic() - t0_recv) * 1000.0
            # Patch total_ms for accurate reporting; other fields come from runner
            patched_info = result.runtime_info.model_copy(
                update={"total_ms": round(total_wall_ms, 1)}
            )
            footer = "\n\n" + _build_runtime_footer(patched_info)

        # 5. Combine response + footer, then chunk for Telegram's 4096-char limit.
        # Footer always appears on the final chunk.
        full_text = response_text + footer
        chunks = _chunk_message(full_text)

        # 6. Reply to Telegram chat
        t0_reply = time.monotonic()
        for i, chunk in enumerate(chunks):
            await update.message.reply_text(chunk)
            if len(chunks) > 1:
                logger.info(
                    "[PROFILE] Telegram chunk sent",
                    chat_id=chat_id,
                    chunk_index=i + 1,
                    total_chunks=len(chunks),
                    chunk_length=len(chunk),
                )
        t_reply_ms = (time.monotonic() - t0_reply) * 1000.0
        t_total_ms = (time.monotonic() - t0_recv) * 1000.0

        logger.info(
            "[PROFILE] Telegram message pipeline finished",
            chat_id=chat_id,
            input_mapping_ms=round(t_map_ms, 3),
            core_dispatch_ms=round(t_dispatch_ms, 3),
            telegram_send_ms=round(t_reply_ms, 3),
            total_end_to_end_ms=round(t_total_ms, 3),
            response_chunks=len(chunks),
            response_total_chars=len(full_text),
            model_used=result.runtime_info.selected_model if result.runtime_info else "unknown",
            was_rerouted=result.runtime_info.was_rerouted if result.runtime_info else False,
        )

    async def start(self) -> None:
        """Start Telegram bot application and block until stopped."""
        if not self.token:
            logger.warning("TELEGRAM_BOT_TOKEN not configured. Skipping Telegram adapter start.")
            return

        self.app = Application.builder().token(self.token).build()
        self.app.add_handler(CommandHandler("start", self._start_command))
        self.app.add_handler(CommandHandler("health", self._health_command))
        self.app.add_handler(CommandHandler("models", self._models_command))
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_message))

        logger.info("Starting Telegram bot polling...")
        await self.app.initialize()
        await self.app.start()
        await self.app.updater.start_polling()  # type: ignore[union-attr]

        logger.info("AHJIN Telegram adapter is live — waiting for updates.")
        # Block here indefinitely. Without this the coroutine returns immediately,
        # tearing down the event loop before any Telegram updates can arrive.
        await self._stop_event.wait()

    async def stop(self) -> None:
        """Stop Telegram bot application."""
        self._stop_event.set()  # unblock start()
        if self.app:
            logger.info("Stopping Telegram bot...")
            if self.app.updater:
                await self.app.updater.stop()
            await self.app.stop()
            await self.app.shutdown()
