"""
bot.py — Точка входа. SOCKS5 прокси, без Redis, запуск norm_scheduler.
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
from services.norm_service import norm_scheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s: %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)


def _build_session() -> AiohttpSession:
    if settings.SOCKS5_PROXY:
        connector = ProxyConnector.from_url(settings.SOCKS5_PROXY)
        logger.info("SOCKS5 proxy: %s", settings.SOCKS5_PROXY)
    else:
        connector = TCPConnector()
    return AiohttpSession(connector=connector)


async def on_startup(bot: Bot) -> None:
    await db.init_pool(settings.POSTGRES_DSN)
    logger.info("DB pool ready.")
    info = await bot.get_me()
    logger.info("Bot: @%s", info.username)


async def on_shutdown(bot: Bot) -> None:
    if db.pool:
        await db.pool.close()
    logger.info("Shutdown.")


async def main() -> None:
    bot = Bot(
        token=settings.BOT_TOKEN,
        session=_build_session(),
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())

    dp.include_router(start.router)
    dp.include_router(user_profile.router)
    dp.include_router(dialog.router)
    dp.include_router(admin_panel.router)
    dp.include_router(superadmin.router)
    dp.include_router(channel.router)

    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    # Запускаем планировщик нормы как фоновую задачу
    async def _run():
        await asyncio.gather(
            dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types()),
            norm_scheduler(bot),
        )

    await _run()


if __name__ == "__main__":
    asyncio.run(main())
