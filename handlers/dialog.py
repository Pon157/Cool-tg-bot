"""
handlers/dialog.py — Создание обращения, роутинг сообщений между пользователем и администратором.
"""
from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

import database as db
from config import settings
from keyboards import (
    accept_dialog_kb,
    admin_in_dialog_kb,
    cancel_kb,
    choose_admin_kb,
    dialog_mode_kb,
    user_in_dialog_kb,
)
from services.ai_service import analyze_dialog, match_admins
from services.s3_service import upload_telegram_file
from states import ActiveDialog, CreateDialog

logger = logging.getLogger(__name__)
router = Router(name="dialog")


# ──────────────────────────────────────────────────────
#  Старт обращения
# ──────────────────────────────────────────────────────

@router.message(F.text == "✍️ Написать")
async def start_dialog(message: Message, state: FSMContext) -> None:
    user = await db.get_user(message.from_user.id)
    if not user or not user.get("is_registered"):
        await message.answer("Пройди регистрацию — нажми /start")
        return
    if user.get("is_banned"):
        await message.answer("🚫 Ты заблокирован в этой системе.")
        return

    active = await db.get_active_dialog_by_user(message.from_user.id)
    if active:
        await message.answer(
            f"У тебя уже есть {'активный' if active['status']=='active' else 'ожидающий'} диалог #{active['id']}.\n"
            "Продолжай писать здесь!",
            reply_markup=user_in_dialog_kb(active["id"]),
        )
        await state.set_state(ActiveDialog.chatting)
        await state.update_data(dialog_id=active["id"], role="user")
        return

    await message.answer(
        "Выбери режим общения:",
        reply_markup=dialog_mode_kb(),
    )
    await state.set_state(CreateDialog.choose_mode)


@router.callback_query(CreateDialog.choose_mode, F.data == "dlg_cancel")
async def dlg_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text("Отменено.")
    await callback.answer()


@router.callback_query(CreateDialog.choose_mode, F.data.startswith("dlg_mode:"))
async def choose_mode(callback: CallbackQuery, state: FSMContext) -> None:
    mode = callback.data.split(":")[1]  # "profile" | "anon"
    await state.update_data(mode=mode)

    admins = await db.get_all_admins()

    if mode == "profile":
        user = await db.get_user(callback.from_user.id)
        admins = await match_admins(user, admins)

    await callback.message.edit_text(
        "👥 Выбери администратора:",
        reply_markup=choose_admin_kb(admins, mode),
    )
    await state.set_state(CreateDialog.choose_admin)
    await callback.answer()


@router.callback_query(CreateDialog.choose_admin, F.data == "back_to_mode")
async def back_to_mode(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.message.edit_text("Выбери режим общения:", reply_markup=dialog_mode_kb())
    await state.set_state(CreateDialog.choose_mode)
    await callback.answer()


@router.callback_query(CreateDialog.choose_admin, F.data.startswith("pick_admin:"))
async def pick_admin(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    _, admin_id_str, mode = callback.data.split(":")
    is_anon = mode == "anon"
    admin_id = None if admin_id_str == "any" else int(admin_id_str)

    dialog = await db.create_dialog(callback.from_user.id, admin_id, is_anon)
    dialog_id = dialog["id"]

    await state.update_data(dialog_id=dialog_id, role="user")
    await state.set_state(ActiveDialog.chatting)

    user = await db.get_user(callback.from_user.id)
    await _notify_admin_group(bot, dialog_id, user, admin_id, is_anon)

    await callback.message.edit_text(
        "✅ Обращение создано!\n\n"
        "⏳ Ожидай ответа администратора.\n"
        "Можешь уже писать — администратор получит все сообщения.",
        reply_markup=user_in_dialog_kb(dialog_id),
    )
    await callback.answer()


async def _notify_admin_group(
    bot: Bot, dialog_id: int, user: dict,
    preferred_admin_id: int | None, is_anon: bool,
) -> None:
    """Send new request notification to admin group."""
    if is_anon:
        user_block = f"🎭 <b>Анонимный пользователь</b> #{user['telegram_id'] % 99999}"
    else:
        user_block = (
            f"👤 <b>{user.get('pseudonym','—')}</b>\n"
            f"🎂 Возраст: {user.get('age','—')}\n"
            f"✨ {user.get('characteristics','—')}\n"
            f"🎯 {user.get('hobbies','—')}"
        )

    if preferred_admin_id:
        adm = await db.get_admin_by_id(preferred_admin_id)
        mention = f"@{adm['username']}" if adm and adm.get("username") else f"(id={preferred_admin_id})"
        title = f"🔔 Новое обращение к {mention}!"
    else:
        title = "🔔 Новое обращение! (любой администратор)"

    text = f"{title}\n\n{user_block}\n\n<code>#{dialog_id}</code>"

    msg = await bot.send_message(
        settings.ADMIN_GROUP_ID,
        text,
        reply_markup=accept_dialog_kb(dialog_id),
        parse_mode="HTML",
    )
    await db.update_dialog_group_msg(dialog_id, msg.message_id)


# ──────────────────────────────────────────────────────
#  Принятие диалога администратором
# ──────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("accept_dlg:"))
async def accept_dialog_cb(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    dialog_id = int(callback.data.split(":")[1])
    admin = await db.get_admin_by_tg(callback.from_user.id)

    if not admin:
        await callback.answer("❌ У вас нет прав администратора.", show_alert=True)
        return

    success = await db.accept_dialog(dialog_id, admin["id"])
    if not success:
        await callback.answer("⚠️ Диалог уже принят или не существует.", show_alert=True)
        return

    dialog = await db.get_dialog(dialog_id)

    # Put admin into ActiveDialog state
    await state.set_state(ActiveDialog.chatting)
    await state.update_data(dialog_id=dialog_id, role="admin")

    # Edit group message
    try:
        await callback.message.edit_text(
            callback.message.html_text + f"\n\n✅ Принял: @{callback.from_user.username or callback.from_user.first_name}",
            reply_markup=None,
            parse_mode="HTML",
        )
    except Exception:
        pass

    # Notify user
    await bot.send_message(
        dialog["user_id"],
        "✅ Администратор принял ваше обращение! Начинайте общение.",
        reply_markup=user_in_dialog_kb(dialog_id),
    )

    # Notify admin in private
    await bot.send_message(
        callback.from_user.id,
        f"✅ Вы приняли обращение <b>#{dialog_id}</b>\n\n"
        "Пишите сообщения прямо здесь — они будут переданы пользователю.\n"
        "Поддерживаются: текст, фото, видео, голосовые, файлы, аудио.",
        reply_markup=admin_in_dialog_kb(dialog_id),
        parse_mode="HTML",
    )
    await callback.answer("✅ Принято!")


# ──────────────────────────────────────────────────────
#  Пересылка сообщений в активном диалоге
# ──────────────────────────────────────────────────────

@router.message(ActiveDialog.chatting)
async def relay_message(message: Message, state: FSMContext, bot: Bot) -> None:
    data = await state.get_data()
    dialog_id: int | None = data.get("dialog_id")
    role: str = data.get("role", "user")

    if not dialog_id:
        await message.answer("Нет активного диалога. Нажми '✍️ Написать'.")
        await state.clear()
        return

    dialog = await db.get_dialog(dialog_id)
    if not dialog or dialog["status"] == "closed":
        await message.answer("❌ Диалог закрыт.")
        await state.clear()
        return

    # Prepare media
    media_url, media_type, content = None, None, message.text or message.caption

    if message.photo:
        media_url = await _safe_upload(bot, message.photo[-1].file_id, "dialog")
        media_type = "photo"
    elif message.video:
        media_url = await _safe_upload(bot, message.video.file_id, "dialog")
        media_type = "video"
    elif message.voice:
        media_url = await _safe_upload(bot, message.voice.file_id, "dialog")
        media_type = "voice"
    elif message.audio:
        media_url = await _safe_upload(bot, message.audio.file_id, "dialog")
        media_type = "audio"
    elif message.document:
        media_url = await _safe_upload(bot, message.document.file_id, "dialog")
        media_type = "document"
    elif message.sticker:
        media_type = "sticker"
        content = f"[🎭 стикер {message.sticker.emoji or ''}]"
    elif message.video_note:
        media_url = await _safe_upload(bot, message.video_note.file_id, "dialog")
        media_type = "video_note"
    elif message.animation:
        media_url = await _safe_upload(bot, message.animation.file_id, "dialog")
        media_type = "animation"

    await db.save_message(dialog_id, role, content, media_url, media_type, message.message_id)

    if role == "user":
        if dialog["status"] != "active":
            # Still pending — messages queued
            return
        admin = await db.get_admin_by_id(dialog["admin_id"])
        if not admin:
            return
        prefix = (
            "🎭 <b>Аноним:</b>" if dialog["is_anonymous"] else "👤 <b>Пользователь:</b>"
        )
        await _forward(bot, admin["telegram_id"], message, prefix, admin_in_dialog_kb(dialog_id))
    else:
        # Admin → User
        await _forward(bot, dialog["user_id"], message, "🛠 <b>Администратор:</b>", user_in_dialog_kb(dialog_id))


async def _safe_upload(bot: Bot, file_id: str, folder: str) -> str | None:
    try:
        return await upload_telegram_file(bot, file_id, folder)
    except Exception as e:
        logger.warning("upload error: %s", e)
        return None


async def _forward(bot: Bot, to_id: int, message: Message, prefix: str, kb) -> None:
    try:
        if message.text:
            await bot.send_message(to_id, f"{prefix}\n{message.text}", reply_markup=kb, parse_mode="HTML")
        elif message.photo:
            await bot.send_photo(to_id, message.photo[-1].file_id,
                                 caption=f"{prefix}\n{message.caption or ''}", reply_markup=kb, parse_mode="HTML")
        elif message.video:
            await bot.send_video(to_id, message.video.file_id,
                                 caption=f"{prefix}\n{message.caption or ''}", reply_markup=kb, parse_mode="HTML")
        elif message.voice:
            await bot.send_voice(to_id, message.voice.file_id,
                                 caption=prefix, reply_markup=kb, parse_mode="HTML")
        elif message.audio:
            await bot.send_audio(to_id, message.audio.file_id,
                                 caption=f"{prefix}\n{message.caption or ''}", reply_markup=kb, parse_mode="HTML")
        elif message.document:
            await bot.send_document(to_id, message.document.file_id,
                                    caption=f"{prefix}\n{message.caption or ''}", reply_markup=kb, parse_mode="HTML")
        elif message.sticker:
            await bot.send_message(to_id, f"{prefix} прислал стикер:", parse_mode="HTML")
            await bot.send_sticker(to_id, message.sticker.file_id)
        elif message.video_note:
            await bot.send_message(to_id, prefix, parse_mode="HTML")
            await bot.send_video_note(to_id, message.video_note.file_id)
        elif message.animation:
            await bot.send_animation(to_id, message.animation.file_id,
                                     caption=prefix, reply_markup=kb, parse_mode="HTML")
    except Exception as e:
        logger.warning("forward error to %s: %s", to_id, e)


# ──────────────────────────────────────────────────────
#  Закрытие диалога
# ──────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("user_close:"))
async def user_close_dialog(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    dialog_id = int(callback.data.split(":")[1])
    await _close_dialog_flow(callback, state, bot, dialog_id, by_admin=False)


@router.callback_query(F.data.startswith("admin_close:"))
async def admin_close_dialog(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    dialog_id = int(callback.data.split(":")[1])
    admin = await db.get_admin_by_tg(callback.from_user.id)
    if not admin:
        await callback.answer("❌ Нет прав")
        return
    await _close_dialog_flow(callback, state, bot, dialog_id, by_admin=True)


async def _close_dialog_flow(
    callback: CallbackQuery, state: FSMContext, bot: Bot,
    dialog_id: int, by_admin: bool,
) -> None:
    dialog = await db.get_dialog(dialog_id)
    if not dialog:
        await callback.answer("Диалог не найден.")
        return

    await db.close_dialog(dialog_id)
    await state.clear()

    closer = "Администратор" if by_admin else "Пользователь"
    notify_id = dialog["user_id"] if by_admin else None
    if notify_id and dialog.get("admin_id"):
        admin = await db.get_admin_by_id(dialog["admin_id"])
        if admin:
            try:
                await bot.send_message(
                    dialog["user_id"],
                    "🔚 Диалог закрыт.\n\n"
                    "Ты можешь оставить отзыв администратору через раздел ⭐ Отзывы.",
                )
            except Exception:
                pass
            if by_admin:
                pass  # admin already knows
            else:
                try:
                    await bot.send_message(admin["telegram_id"], f"🔚 Пользователь закрыл диалог #{dialog_id}.")
                except Exception:
                    pass

    await callback.message.edit_text(f"✅ Диалог #{dialog_id} закрыт.", reply_markup=None)
    await callback.answer()

    # Background AI analysis
    asyncio.create_task(_ai_analyze(dialog_id, dialog["user_id"]))


async def _ai_analyze(dialog_id: int, user_id: int) -> None:
    try:
        text = await db.get_dialog_text_for_ai(dialog_id)
        if not text.strip():
            return
        user = await db.get_user(user_id)
        rec, kw, tone = await analyze_dialog(text, user)
        if rec:
            await db.save_recommendation(user_id, dialog_id, rec, kw, tone)
    except Exception as e:
        logger.warning("_ai_analyze: %s", e)


# ──────────────────────────────────────────────────────
#  Бан пользователя из диалога
# ──────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("admin_ban:"))
async def admin_ban_user(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    dialog_id = int(callback.data.split(":")[1])
    admin = await db.get_admin_by_tg(callback.from_user.id)
    if not admin:
        await callback.answer("❌ Нет прав")
        return
    dialog = await db.get_dialog(dialog_id)
    if not dialog:
        await callback.answer("Диалог не найден")
        return

    await db.ban_user(dialog["user_id"], "Забанен администратором", callback.from_user.id)
    await db.close_dialog(dialog_id)
    await state.clear()

    try:
        await bot.send_message(dialog["user_id"], "🚫 Ты заблокирован администратором.")
    except Exception:
        pass

    await callback.message.edit_text("✅ Пользователь заблокирован, диалог закрыт.")
    await callback.answer()
