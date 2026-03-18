"""Main entry-point – starts FastAPI server + Telegram bot together."""

from __future__ import annotations

import asyncio
import logging
import sys

import uvicorn

from api.server import app, orchestrator
from config.settings import settings
from telegram.bot import TelegramBot

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


async def main() -> None:
    # Start Telegram bot alongside FastAPI
    bot = TelegramBot(orchestrator)

    # Start orchestrator (task queue)
    await orchestrator.start()

    # Start Telegram bot (non-blocking)
    await bot.start()

    # Run FastAPI via uvicorn
    config = uvicorn.Config(
        app,
        host=settings.api_host,
        port=settings.api_port,
        log_level="info",
    )
    server = uvicorn.Server(config)

    try:
        await server.serve()
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass
    finally:
        logger.info("Shutting down…")
        await bot.stop()
        await orchestrator.stop()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
