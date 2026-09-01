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

        # 4. Reply to Telegram chat
        t0_reply = time.monotonic()
        await update.message.reply_text(response_text)
        t_reply_ms = (time.monotonic() - t0_reply) * 1000.0
        t_total_ms = (time.monotonic() - t0_recv) * 1000.0

        logger.info(
            "[PROFILE] Telegram message pipeline finished",
            chat_id=chat_id,
            input_mapping_ms=round(t_map_ms, 3),
            core_dispatch_ms=round(t_dispatch_ms, 3),
            telegram_send_ms=round(t_reply_ms, 3),
            total_end_to_end_ms=round(t_total_ms, 3),
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
