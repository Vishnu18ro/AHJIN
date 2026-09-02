"""AHJIN 2.0 CLI entry point."""

import asyncio
import sys

import structlog

from ahjin.core.dispatcher import TaskDispatcher
from ahjin.harness.gateway import ProviderGateway
from ahjin.harness.runner import HarnessRunner
from ahjin.interfaces.telegram.bot import TelegramAdapter
from ahjin.models import ModelRouter, create_default_catalog
from ahjin.providers.nvidia import NvidiaProvider
from ahjin.providers.registry import ProviderRegistry

logger = structlog.get_logger()


async def main() -> None:
    """Bootstrap AHJIN 2.0 application."""
    logger.info("AHJIN 2.0 starting up", version="2.0.0")

    # --- Provider & Model Catalog bootstrap ---
    registry = ProviderRegistry()
    registry.register(NvidiaProvider())

    catalog = create_default_catalog()
    router = ModelRouter(catalog=catalog)

    # --- Dependency wiring ---
    gateway = ProviderGateway(registry=registry, router=router)
    runner = HarnessRunner(gateway=gateway)
    dispatcher = TaskDispatcher(runner=runner)
    adapter = TelegramAdapter(dispatcher=dispatcher, router=router)

    logger.info("AHJIN 2.0 initialization complete — Multi-Model Router ready")

    # --- Start interfaces ---
    await adapter.start()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(0)
