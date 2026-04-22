"""
handlers/user_profile.py — Просмотр профиля, редактирование, отзывы, AI рекомендации.
"""
from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    FSInputFile,
    InputMediaPhoto,
    Message,
)

import database as db
from keyboards import (
    cancel_kb,
    choose_admin_for_review_kb,
    edit_profile_menu,
    main_menu,
    profile_menu,
    rating_kb,
    skip_media_kb,
)
from services.profile_card import generate_profile_card
from services.s3_service import upload_bytes, upload_telegram_file
from states import CreateReview, EditProfile

logger = logging.getLogger(__name__)
router = Router(name="user_profile")


# ──────────────────────────────────────────────────────
#  Мой профиль
# ──────────────────────────────────────────────────────

@router.message(F.text == "👤 Мой профиль")
async def my_profile(message: Message) -> None:
    user = await db.get_user(message.from_user.id)
    if not user or not user.get("is_registered"):
        await message.answer("Пройди регистрацию — нажми /start")
        return
    await message.answer(
        f"👤 <b>Профиль</b>\n\n"
        f"Псевдоним: <b>{user.get('pseudonym','—')}</b>\n"
        f"Возраст: {user.get('age','—')}\n"
        f"Характеристики: {user.get('characteristics','—')}\n"
        f"Увлечения: {user.get('hobbies','—')}\n\n"
        f"⚠️ Предупреждений: {user.get('warn_count',0)}",
        reply_markup=profile_menu(),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "view_card")
async def view_card(callback: CallbackQuery) -> None:
    user = await db.get_user(callback.from_user.id)
    card_url = user.get("profile_card_url") if user else None
    if card_url:
        await callback.message.answer_photo(
            photo=card_url,
            caption="🖼 Твоя анкета",
        )
    else:
        await callback.message.answer("Анкета ещё генерируется. Попробуй позже.")
    await callback.answer()


# ──────────────────────────────────────────────────────
#  Редактирование профиля
# ──────────────────────────────────────────────────────

FIELD_LABELS = {
    "ep_pseudonym":       ("pseudonym",       "Введи новый псевдоним:"),
    "ep_age":             ("age",             "Введи новый возраст:"),
    "ep_characteristics": ("characteristics", "Опиши свои характеристики:"),
    "ep_hobbies":         ("hobbies",         "Опиши увлечения и хобби:"),
}


@router.callback_query(F.data == "edit_profile")
async def edit_profile(callback: CallbackQuery) -> None:
    await callback.message.edit_text("✏️ Что хочешь изменить?", reply_markup=edit_profile_menu())
    await callback.answer()


@router.callback_query(F.data.startswith("ep_"))
async def edit_field_start(callback: CallbackQuery, state: FSMContext) -> None:
    db_key, prompt = FIELD_LABELS[callback.data]
    await state.update_data(edit_field=db_key)
    await callback.message.edit_text(prompt, reply_markup=cancel_kb())
    await state.set_state(EditProfile.entering_value)
    await callback.answer()


@router.callback_query(F.data == "back_to_profile")
async def back_to_profile(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    user = await db.get_user(callback.from_user.id)
    await callback.message.edit_text(
        f"👤 <b>Профиль</b>\n\nПсевдоним: {user.get('pseudonym','—')}",
        reply_markup=profile_menu(),
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(EditProfile.entering_value)
async def edit_field_done(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    field = data["edit_field"]
    await state.clear()

    await db.update_user(message.from_user.id, **{field: message.text.strip()[:300]})

    # Regenerate card
    user = await db.get_user(message.from_user.id)
    try:
        card_bytes = await generate_profile_card(
            pseudonym=user.get("pseudonym", ""),
            age=user.get("age", ""),
            characteristics=user.get("characteristics", ""),
            hobbies=user.get("hobbies", ""),
            avatar_url=user.get("avatar_url"),
        )
        url = await upload_bytes(card_bytes, f"profiles/{message.from_user.id}_card.png", "image/png")
        await db.update_user(message.from_user.id, profile_card_url=url)
    except Exception as e:
        logger.warning("card regen: %s", e)

    is_admin      = bool(await db.get_admin_by_tg(message.from_user.id))
    is_superadmin = bool(message.from_user.id in __import__("config").settings.SUPERADMIN_IDS)

    await message.answer(
        "✅ Профиль обновлён!",
        reply_markup=main_menu(is_admin, is_superadmin),
    )


# ──────────────────────────────────────────────────────
#  Мои отзывы
# ──────────────────────────────────────────────────────

@router.callback_query(F.data == "my_reviews")
async def my_reviews(callback: CallbackQuery) -> None:
    reviews = await db.get_user_reviews(callback.from_user.id)
    if not reviews:
        await callback.message.answer("У тебя пока нет отзывов.")
        await callback.answer()
        return
    lines = []
    for r in reviews[:10]:
        stars = "⭐" * r["rating"]
        lines.append(f"<b>{r['admin_pseudonym']}</b> — {stars}\n{r['text'] or '—'}")
    await callback.message.answer(
        "⭐ <b>Мои отзывы:</b>\n\n" + "\n\n".join(lines),
        parse_mode="HTML",
    )
    await callback.answer()


# ──────────────────────────────────────────────────────
#  AI Рекомендации
# ──────────────────────────────────────────────────────

@router.callback_query(F.data == "ai_recs")
async def ai_recs(callback: CallbackQuery) -> None:
    recs = await db.get_user_recommendations(callback.from_user.id, limit=5)
    if not recs:
        await callback.message.answer(
            "🤖 Рекомендации появятся после завершения диалога с администратором."
        )
        await callback.answer()
        return
    lines = []
    for rec in recs:
        import json as _json
        kw = ", ".join(_json.loads(rec.get("keywords") or "[]")[:5])
        lines.append(
            f"📌 <b>{rec['emotional_tone'] or ''}</b>\n"
            f"{rec['recommendation']}\n"
            f"<i>Темы: {kw or '—'}</i>"
        )
    await callback.message.answer(
        "🤖 <b>Рекомендации ИИ:</b>\n\n" + "\n\n─────────\n\n".join(lines),
        parse_mode="HTML",
    )
    await callback.answer()


# ──────────────────────────────────────────────────────
#  Создание отзыва (FSM)
# ──────────────────────────────────────────────────────

@router.callback_query(F.data == "cancel")
async def cancel_any(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text("Отменено.")
    await callback.answer()


@router.message(F.text == "⭐ Оставить отзыв")
async def start_review(message: Message, state: FSMContext) -> None:
    """Entry point: user wants to leave a review."""
    dialogs = await db.get_user_closed_dialogs(message.from_user.id)
    if not dialogs:
        await message.answer(
            "Отзыв можно оставить только после завершённого диалога с администратором."
        )
        return
    await message.answer(
        "⭐ Выбери администратора, которому хочешь оставить отзыв:",
        reply_markup=choose_admin_for_review_kb(dialogs),
    )
    await state.set_state(CreateReview.choose_admin)


@router.callback_query(CreateReview.choose_admin, F.data.startswith("rev_admin:"))
async def review_admin_chosen(callback: CallbackQuery, state: FSMContext) -> None:
    _, admin_id, dialog_id = callback.data.split(":")
    await state.update_data(admin_id=int(admin_id), dialog_id=int(dialog_id))
    await callback.message.edit_text(
        "✍️ Напиши текст отзыва:",
        reply_markup=cancel_kb(),
    )
    await state.set_state(CreateReview.enter_text)
    await callback.answer()


@router.message(CreateReview.enter_text)
async def review_text(message: Message, state: FSMContext) -> None:
    await state.update_data(text=message.text.strip()[:1000])
    data = await state.get_data()
    await message.answer(
        "⭐ Поставь оценку:",
        reply_markup=rating_kb(data["admin_id"], data["dialog_id"]),
    )
    await state.set_state(CreateReview.choose_rating)


@router.callback_query(CreateReview.choose_rating, F.data.startswith("rev_rate:"))
async def review_rating(callback: CallbackQuery, state: FSMContext) -> None:
    _, admin_id, dialog_id, rating = callback.data.split(":")
    await state.update_data(admin_id=int(admin_id), dialog_id=int(dialog_id), rating=int(rating))
    await callback.message.edit_text(
        "📎 Прикрепи фото/видео к отзыву (или пропусти):",
        reply_markup=skip_media_kb(),
    )
    await state.set_state(CreateReview.attach_media)
    await callback.answer()


@router.callback_query(CreateReview.attach_media, F.data == "rev_skip_media")
async def review_skip_media(callback: CallbackQuery, state: FSMContext) -> None:
    await _finalize_review(callback.message, state, callback.from_user.id, [])
    await callback.answer()


@router.message(CreateReview.attach_media, F.photo | F.video | F.document)
async def review_media(message: Message, state: FSMContext) -> None:
    media_urls = []
    try:
        if message.photo:
            url = await upload_telegram_file(
                message.bot, message.photo[-1].file_id, "review_media"
            )
            media_urls.append({"type": "photo", "url": url})
        elif message.video:
            url = await upload_telegram_file(
                message.bot, message.video.file_id, "review_media"
            )
            media_urls.append({"type": "video", "url": url})
    except Exception as e:
        logger.warning("review media upload: %s", e)
    await _finalize_review(message, state, message.from_user.id, media_urls)


async def _finalize_review(
    message: Message, state: FSMContext, user_id: int, media_urls: list
) -> None:
    data = await state.get_data()
    await state.clear()
    await db.upsert_review(
        user_id=user_id,
        admin_id=data["admin_id"],
        dialog_id=data["dialog_id"],
        text=data.get("text", ""),
        rating=data.get("rating", 5),
        media_urls=media_urls,
    )
    await message.answer("✅ Отзыв сохранён! Спасибо за обратную связь.")
