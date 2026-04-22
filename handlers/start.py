"""
handlers/start.py — /start, регистрация, главное меню.
"""
from __future__ import annotations

import logging
from typing import Optional

from aiogram import Bot, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

import database as db
from config import settings
from keyboards import main_menu
from services.profile_card import generate_profile_card
from services.s3_service import upload_bytes, upload_from_url
from states import UserRegistration

logger = logging.getLogger(__name__)
router = Router(name="start")


# ──────────────────────────────────────────────────────
#  Helpers
# ──────────────────────────────────────────────────────

async def _get_tg_avatar(bot: Bot, user_id: int) -> Optional[str]:
    try:
        photos = await bot.get_user_profile_photos(user_id, limit=1)
        if photos.total_count:
            file_id = photos.photos[0][-1].file_id
            tg_file = await bot.get_file(file_id)
            return (
                f"https://api.telegram.org/file/bot{settings.BOT_TOKEN}"
                f"/{tg_file.file_path}"
            )
    except Exception as e:
        logger.debug("get_tg_avatar: %s", e)
    return None


async def _regenerate_card(bot: Bot, telegram_id: int, user: dict) -> None:
    """Generate/re-generate profile card and save to S3."""
    try:
        avatar_url = await _get_tg_avatar(bot, telegram_id)
        card_bytes = await generate_profile_card(
            pseudonym=user.get("pseudonym", "Аноним"),
            age=user.get("age", "?"),
            characteristics=user.get("characteristics", ""),
            hobbies=user.get("hobbies", ""),
            avatar_url=avatar_url,
        )
        card_url = await upload_bytes(
            card_bytes,
            f"profiles/{telegram_id}_card.png",
            "image/png",
        )
        avatar_s3 = None
        if avatar_url:
            avatar_s3 = await upload_from_url(
                avatar_url, f"avatars/{telegram_id}.jpg"
            )
        await db.update_user(
            telegram_id,
            profile_card_url=card_url,
            avatar_url=avatar_s3 or avatar_url,
        )
    except Exception as e:
        logger.warning("_regenerate_card error: %s", e)


# ──────────────────────────────────────────────────────
#  /start
# ──────────────────────────────────────────────────────

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, bot: Bot) -> None:
    await state.clear()
    user = await db.get_user(message.from_user.id)

    if not user:
        await db.upsert_user(message.from_user.id, message.from_user.username)
        await message.answer(
            "Добро пожаловать в анонимный чат поддержки!\n\n"
            "Давай заполним твой профиль — это займёт меньше минуты.\n\n"
            "<b>Сколько тебе лет?</b>\n"
            "<i>(можешь написать «не хочу говорить»)</i>",
            parse_mode="HTML",
        )
        await state.set_state(UserRegistration.age)
        return

    if not user.get("is_registered"):
        await message.answer(
            "Кажется, ты не завершил регистрацию. Начнём заново!\n\n"
            "<b>Сколько тебе лет?</b>",
            parse_mode="HTML",
        )
        await state.set_state(UserRegistration.age)
        return

    is_admin      = bool(await db.get_admin_by_tg(message.from_user.id))
    is_superadmin = message.from_user.id in settings.SUPERADMIN_IDS

    await message.answer(
        f"👋 Привет, <b>{user.get('pseudonym', 'Аноним')}</b>!\n"
        "Выбери действие в меню ниже.",
        reply_markup=main_menu(is_admin, is_superadmin),
        parse_mode="HTML",
    )


# ──────────────────────────────────────────────────────
#  Registration FSM
# ──────────────────────────────────────────────────────

@router.message(UserRegistration.age)
async def reg_age(message: Message, state: FSMContext) -> None:
    await state.update_data(age=message.text.strip()[:30])
    await message.answer(
        "<b>Придумай псевдоним</b> — это имя увидит администратор.\n"
        "<i>(до 50 символов)</i>",
        parse_mode="HTML",
    )
    await state.set_state(UserRegistration.pseudonym)


@router.message(UserRegistration.pseudonym)
async def reg_pseudonym(message: Message, state: FSMContext) -> None:
    nick = message.text.strip()[:50]
    if len(nick) < 2:
        await message.answer("Слишком короткий псевдоним. Попробуй ещё раз:")
        return
    await state.update_data(pseudonym=nick)
    await message.answer(
        "<b>Опиши свои характеристики / качества</b>\n"
        "<i>Например: целеустремлённый, добрый, творческий...</i>",
        parse_mode="HTML",
    )
    await state.set_state(UserRegistration.characteristics)


@router.message(UserRegistration.characteristics)
async def reg_chars(message: Message, state: FSMContext) -> None:
    await state.update_data(characteristics=message.text.strip()[:300])
    await message.answer(
        "<b>Твои увлечения и хобби</b>\n"
        "<i>Например: музыка, спорт, аниме, программирование...</i>",
        parse_mode="HTML",
    )
    await state.set_state(UserRegistration.hobbies)


@router.message(UserRegistration.hobbies)
async def reg_hobbies(message: Message, state: FSMContext, bot: Bot) -> None:
    data = await state.get_data()
    hobbies = message.text.strip()[:300]
    await state.clear()

    await db.update_user(
        message.from_user.id,
        pseudonym=data["pseudonym"],
        age=data["age"],
        characteristics=data["characteristics"],
        hobbies=hobbies,
        is_registered=True,
    )

    await message.answer("⏳ Генерирую твою анкету...")
    await _regenerate_card(bot, message.from_user.id, {
        "pseudonym": data["pseudonym"],
        "age": data["age"],
        "characteristics": data["characteristics"],
        "hobbies": hobbies,
    })

    is_admin      = bool(await db.get_admin_by_tg(message.from_user.id))
    is_superadmin = message.from_user.id in settings.SUPERADMIN_IDS

    await message.answer(
        f"<b>Профиль создан!</b>\n\n"
        f"<b>Псевдоним:</b> {data['pseudonym']}\n"
        f"<b>Возраст:</b> {data['age']}\n"
        f"<b>Характеристики:</b> {data['characteristics']}\n"
        f"<b>Увлечения:</b> {hobbies}\n\n"
        "Теперь ты можешь начать общение!",
        reply_markup=main_menu(is_admin, is_superadmin),
        parse_mode="HTML",
    )
