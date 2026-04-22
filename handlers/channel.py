"""
handlers/channel.py — Подписки на каналы администраторов.
"""
from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message

import database as db

logger = logging.getLogger(__name__)
router = Router(name="channel")


@router.callback_query(F.data.startswith("sub:"))
async def subscribe_cb(callback: CallbackQuery) -> None:
    admin_id = int(callback.data.split(":")[1])
    admin = await db.get_admin_by_id(admin_id)
    if not admin:
        await callback.answer("Администратор не найден.")
        return
    await db.subscribe(callback.from_user.id, admin_id)
    await callback.answer(f"Вы подписались на канал «{admin['channel_title']}».")


@router.callback_query(F.data.startswith("unsub:"))
async def unsubscribe_cb(callback: CallbackQuery) -> None:
    admin_id = int(callback.data.split(":")[1])
    admin = await db.get_admin_by_id(admin_id)
    if not admin:
        await callback.answer("Администратор не найден.")
        return
    await db.unsubscribe(callback.from_user.id, admin_id)
    await callback.answer(f"Вы отписались от канала «{admin['channel_title']}».")
