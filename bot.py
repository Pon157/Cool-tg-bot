"""
bot.py — Точка входа. Инициализирует бота с SOCKS5 прокси, подключает БД,
регистрирует все роутеры.
"""
from __future__ import annotations

import asyncio
import logging
import sys

from aiohttp import TCPConnector
from aiohttp_socks import ProxyConnector
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from config import settings
import database as db
from handlers import start, user_profile, dialog, admin_panel, superadmin, channel

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s: %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)


def _build_session() -> AiohttpSession:
    """Build aiohttp session with optional SOCKS5 proxy."""
    if settings.SOCKS5_PROXY:
        connector = ProxyConnector.from_url(settings.SOCKS5_PROXY)
        logger.info("Using SOCKS5 proxy: %s", settings.SOCKS5_PROXY)
    else:
        connector = TCPConnector()
    return AiohttpSession(connector=connector)


async def on_startup(bot: Bot) -> None:
    await db.init_pool(settings.POSTGRES_DSN)
    logger.info("Database pool initialised.")
    info = await bot.get_me()
    logger.info("Bot started: @%s", info.username)


async def on_shutdown(bot: Bot) -> None:
    if db.pool:
        await db.pool.close()
    logger.info("Database pool closed.")


async def main() -> None:
    session = _build_session()

    bot = Bot(
        token=settings.BOT_TOKEN,
        session=session,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    # No Redis — in-memory FSM storage is sufficient for this use case.
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)

    # ── Register routers (order matters — more specific first) ──
    dp.include_router(start.router)
    dp.include_router(user_profile.router)
    dp.include_router(dialog.router)
    dp.include_router(admin_panel.router)
    dp.include_router(superadmin.router)
    dp.include_router(channel.router)

    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    logger.info("Starting polling...")
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


if __name__ == "__main__":
    asyncio.run(main())
