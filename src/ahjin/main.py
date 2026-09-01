"""AHJIN 2.0 CLI entry point."""

import asyncio
import sys

import structlog

from ahjin.core.dispatcher import TaskDispatcher
from ahjin.harness.gateway import ProviderGateway
from ahjin.harness.runner import HarnessRunner
from ahjin.interfaces.telegram.bot import TelegramAdapter
from ahjin.providers.nvidia import NvidiaProvider
from ahjin.providers.registry import ProviderRegistry

logger = structlog.get_logger()


async def main() -> None:
    """Bootstrap AHJIN 2.0 application."""
    logger.info("AHJIN 2.0 starting up", version="2.0.0")

    # --- Provider bootstrap ---
    # Providers are registered here, not inside ProviderRegistry.__init__.
    # This keeps registry construction free of config/credential side-effects.
    registry = ProviderRegistry()
    registry.register(NvidiaProvider())

    # --- Dependency wiring ---
    gateway = ProviderGateway(registry=registry)
    runner = HarnessRunner(gateway=gateway)
    dispatcher = TaskDispatcher(runner=runner)
    adapter = TelegramAdapter(dispatcher=dispatcher)

    logger.info("AHJIN 2.0 initialization complete")

    # --- Start interfaces ---
    await adapter.start()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(0)
