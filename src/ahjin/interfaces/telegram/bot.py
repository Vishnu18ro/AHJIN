"""Telegram Bot Adapter."""

import asyncio
import time
from typing import Any

import structlog
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from ahjin.core.config import settings
from ahjin.core.dispatcher import TaskDispatcher
from ahjin.interfaces.base import BaseInterfaceAdapter
from ahjin.interfaces.telegram.mapper import TelegramMapper

logger = structlog.get_logger()

# Telegram's hard per-message character limit.
# Messages exceeding this are split into sequential chunks.
TELEGRAM_MAX_MESSAGE_LENGTH = 4096


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


class TelegramAdapter(BaseInterfaceAdapter):
    """Telegram Interface Adapter."""

    def __init__(
        self,
        token: str | None = None,
        dispatcher: TaskDispatcher | None = None,
    ) -> None:
        self.token = token or settings.telegram_bot_token
        self.dispatcher = dispatcher or TaskDispatcher()
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

        # 4. Reply to Telegram chat — chunked if response exceeds Telegram's limit.
        t0_reply = time.monotonic()
        chunks = _chunk_message(response_text)
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
            response_total_chars=len(response_text),
        )


    async def start(self) -> None:
        """Start Telegram bot application and block until stopped."""
        if not self.token:
            logger.warning("TELEGRAM_BOT_TOKEN not configured. Skipping Telegram adapter start.")
            return

        self.app = Application.builder().token(self.token).build()
        self.app.add_handler(CommandHandler("start", self._start_command))
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
