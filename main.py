"""Main entry point: FastAPI + Telegram bot with shared orchestrator/runtime."""

from __future__ import annotations

import asyncio
import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

import uvicorn

from api.server import app, automation_service, orchestrator
from config.settings import settings
from telegram_bot.bot import TelegramBot

log_dir = Path(__file__).resolve().parent / "logs"
log_dir.mkdir(parents=True, exist_ok=True)
log_handlers: list[logging.Handler] = [
    RotatingFileHandler(
        log_dir / "autoixb-web.log",
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
]
if sys.stderr is not None:
    log_handlers.append(logging.StreamHandler(sys.stderr))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=log_handlers,
    force=True,
)
logger = logging.getLogger(__name__)


async def main() -> None:
    bot = TelegramBot(orchestrator)
    await orchestrator.start()
    await automation_service.start()
    await bot.start()

    config = uvicorn.Config(
        app,
        host=settings.api_host,
        port=settings.api_port,
        log_level="info",
        lifespan="off",
    )
    server = uvicorn.Server(config)
    try:
        await server.serve()
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass
    finally:
        logger.info("Shutting down...")
        await bot.stop()
        await automation_service.stop()
        await orchestrator.stop()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
    except Exception:
        logger.exception("autoIXB web service stopped with an unhandled error")
        raise
