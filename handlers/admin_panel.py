"""
handlers/admin_panel.py — Панель администратора: заполнение профиля, канал, список диалогов.
"""
from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

import database as db
from config import settings
from keyboards import (
    admin_panel_menu_kb,
    cancel_kb,
    channel_manage_kb,
    main_menu,
)
from services.profile_card import generate_profile_card
from services.s3_service import upload_bytes, upload_telegram_file
from states import AdminEditChannel, AdminFillProfile, CreateChannelPost

logger = logging.getLogger(__name__)
router = Router(name="admin_panel")


def _is_admin_filter(message: Message) -> bool:
    return True  # actual check inside handler


# ──────────────────────────────────────────────────────
#  Вход в панель
# ──────────────────────────────────────────────────────

@router.message(F.text == "🛠 Панель администратора")
async def admin_panel(message: Message) -> None:
    admin = await db.get_admin_by_tg(message.from_user.id)
    if not admin:
        await message.answer("❌ У вас нет прав администратора.")
        return
    status = "🟢 В сети" if admin["is_online"] else "🔴 Не в сети"
    await message.answer(
        f"🛠 <b>Панель администратора</b>\n\n"
        f"Псевдоним: <b>{admin['pseudonym']}</b>\n"
        f"Статус: {status}\n"
        f"Канал: {admin.get('channel_title','—')}",
        reply_markup=admin_panel_menu_kb(),
        parse_mode="HTML",
    )


# ──────────────────────────────────────────────────────
#  Список диалогов
# ──────────────────────────────────────────────────────

@router.callback_query(F.data == "adm_my_dialogs")
async def adm_my_dialogs(callback: CallbackQuery) -> None:
    admin = await db.get_admin_by_tg(callback.from_user.id)
    if not admin:
        await callback.answer("Нет прав")
        return
    dialogs = await db.get_admin_active_dialogs(admin["id"])
    if not dialogs:
        await callback.message.answer("У вас нет активных диалогов.")
        await callback.answer()
        return
    lines = []
    for d in dialogs:
        unread = d.get("unread", 0)
        badge = f" 🔴 {unread} непрочит." if unread else ""
        lines.append(f"• Диалог #{d['id']}{badge} — {'анонимный' if d['is_anonymous'] else 'с профилем'}")
    await callback.message.answer(
        "💬 <b>Активные диалоги:</b>\n\n" + "\n".join(lines) + "\n\n"
        "Переключайтесь между диалогами в веб-панели.",
        parse_mode="HTML",
    )
    await callback.answer()


# ──────────────────────────────────────────────────────
#  Заполнение профиля администратора (FSM)
# ──────────────────────────────────────────────────────

@router.callback_query(F.data == "adm_fill_profile")
async def adm_fill_start(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.message.answer(
        "📝 Заполним ваш профиль администратора.\n\n"
        "🎂 <b>Ваш возраст:</b> (или «не хочу говорить»)",
        reply_markup=cancel_kb(),
        parse_mode="HTML",
    )
    await state.set_state(AdminFillProfile.age)
    await callback.answer()


@router.message(AdminFillProfile.age)
async def adm_fp_age(message: Message, state: FSMContext) -> None:
    await state.update_data(age=message.text.strip()[:30])
    await message.answer(
        "✨ <b>Ваши характеристики / качества:</b>",
        parse_mode="HTML",
    )
    await state.set_state(AdminFillProfile.characteristics)


@router.message(AdminFillProfile.characteristics)
async def adm_fp_chars(message: Message, state: FSMContext) -> None:
    await state.update_data(characteristics=message.text.strip()[:300])
    await message.answer("🎯 <b>Ваши увлечения и хобби:</b>", parse_mode="HTML")
    await state.set_state(AdminFillProfile.hobbies)


@router.message(AdminFillProfile.hobbies)
async def adm_fp_hobbies(message: Message, state: FSMContext) -> None:
    await state.update_data(hobbies=message.text.strip()[:300])
    await message.answer("📄 <b>Краткое описание — несколько слов о себе:</b>", parse_mode="HTML")
    await state.set_state(AdminFillProfile.description)


@router.message(AdminFillProfile.description)
async def adm_fp_done(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    await state.clear()

    admin = await db.get_admin_by_tg(message.from_user.id)
    if not admin:
        await message.answer("Ошибка: администратор не найден.")
        return

    await db.update_admin(
        admin["id"],
        age=data["age"],
        characteristics=data["characteristics"],
        hobbies=data["hobbies"],
        description=message.text.strip()[:500],
        is_profile_filled=True,
    )

    # Generate card
    try:
        card_bytes = await generate_profile_card(
            pseudonym=admin["pseudonym"],
            age=data["age"],
            characteristics=data["characteristics"],
            hobbies=data["hobbies"],
        )
        card_url = await upload_bytes(
            card_bytes, f"admin_profiles/{admin['id']}_card.png", "image/png"
        )
        await db.update_admin(admin["id"], avatar_url=card_url)
    except Exception as e:
        logger.warning("admin card: %s", e)

    await message.answer(
        "✅ Профиль администратора заполнен!\n\n"
        f"Теперь система сможет рекомендовать вас пользователям на основе интересов.",
    )


# ──────────────────────────────────────────────────────
#  Управление каналом
# ──────────────────────────────────────────────────────

@router.callback_query(F.data == "adm_my_channel")
async def adm_channel_menu(callback: CallbackQuery) -> None:
    admin = await db.get_admin_by_tg(callback.from_user.id)
    if not admin:
        await callback.answer("Нет прав")
        return
    posts = await db.get_admin_posts(admin["id"], limit=3)
    posts_text = ""
    for p in posts:
        posts_text += f"\n• {p['created_at'].strftime('%d.%m')} — {(p['content'] or '')[:50]}..."
    await callback.message.answer(
        f"📺 <b>Ваш канал: {admin.get('channel_title','—')}</b>\n"
        f"{admin.get('channel_description','')}\n\n"
        f"Последние посты:{posts_text or ' нет'}",
        reply_markup=channel_manage_kb(admin["id"]),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data == "ch_new_post")
async def ch_new_post_start(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.message.answer(
        "✍️ Напишите текст поста (или отправьте медиа):",
        reply_markup=cancel_kb(),
    )
    await state.set_state(CreateChannelPost.enter_content)
    await state.update_data(media_urls=[])
    await callback.answer()


@router.message(CreateChannelPost.enter_content)
async def ch_post_content(message: Message, state: FSMContext) -> None:
    if message.text:
        await state.update_data(content=message.text.strip())
    await state.update_data(content=getattr(message, 'text', message.caption or "") or "")
    await message.answer(
        "📎 Прикрепите медиа к посту (фото/видео) или нажмите /skip для публикации без медиа:"
    )
    await state.set_state(CreateChannelPost.attach_media)


@router.message(CreateChannelPost.attach_media, F.photo | F.video)
async def ch_post_media(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    media_urls = data.get("media_urls", [])
    try:
        if message.photo:
            url = await upload_telegram_file(message.bot, message.photo[-1].file_id, "channel_media")
            media_urls.append({"type": "photo", "url": url})
        elif message.video:
            url = await upload_telegram_file(message.bot, message.video.file_id, "channel_media")
            media_urls.append({"type": "video", "url": url})
    except Exception as e:
        logger.warning("ch media upload: %s", e)
    await state.update_data(media_urls=media_urls)
    await message.answer(f"✅ Медиа добавлено ({len(media_urls)} шт.). Отправьте ещё или /skip.")


@router.message(CreateChannelPost.attach_media, F.text == "/skip")
@router.message(CreateChannelPost.attach_media, F.text.startswith("/skip"))
async def ch_post_publish(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    await state.clear()

    admin = await db.get_admin_by_tg(message.from_user.id)
    if not admin:
        await message.answer("Ошибка.")
        return

    post = await db.create_channel_post(
        admin["id"],
        data.get("content", ""),
        data.get("media_urls", []),
    )

    # Notify subscribers
    subscribers = await db.get_admin_subscribers(admin["id"])
    sent = 0
    for uid in subscribers:
        try:
            await message.bot.send_message(
                uid,
                f"📺 <b>Новый пост от {admin['pseudonym']}</b>\n\n{post['content'] or ''}",
                parse_mode="HTML",
            )
            sent += 1
        except Exception:
            pass

    await message.answer(
        f"✅ Пост опубликован! Уведомлено подписчиков: {sent}"
    )


# ──────────────────────────────────────────────────────
#  Редактирование канала
# ──────────────────────────────────────────────────────

CHANNEL_FIELDS = {
    "ch_edit:title":       ("channel_title",       "Введите новое название канала:"),
    "ch_edit:description": ("channel_description", "Введите новое описание канала:"),
    "ch_edit:avatar":      ("channel_avatar_url",  "Отправьте новый аватар (фото):"),
}


@router.callback_query(F.data.startswith("ch_edit:"))
async def ch_edit_field(callback: CallbackQuery, state: FSMContext) -> None:
    db_key, prompt = CHANNEL_FIELDS[callback.data]
    await state.update_data(edit_field=db_key)
    await callback.message.answer(prompt, reply_markup=cancel_kb())
    await state.set_state(AdminEditChannel.entering_value)
    await callback.answer()


@router.message(AdminEditChannel.entering_value, F.text)
async def ch_edit_text_done(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    await state.clear()
    admin = await db.get_admin_by_tg(message.from_user.id)
    if not admin:
        return
    await db.update_admin(admin["id"], **{data["edit_field"]: message.text.strip()[:200]})
    await message.answer("✅ Обновлено!")


@router.message(AdminEditChannel.entering_value, F.photo)
async def ch_edit_avatar_done(message: Message, state: FSMContext) -> None:
    await state.clear()
    admin = await db.get_admin_by_tg(message.from_user.id)
    if not admin:
        return
    url = await upload_telegram_file(message.bot, message.photo[-1].file_id, "channel_avatars")
    await db.update_admin(admin["id"], channel_avatar_url=url)
    await message.answer("✅ Аватар канала обновлён!")
