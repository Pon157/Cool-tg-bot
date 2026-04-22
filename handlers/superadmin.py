"""
handlers/superadmin.py — Суперадмин: статистика, добавление/удаление администраторов,
бан/варн/рассылка.
"""
from __future__ import annotations

import logging
import secrets
import string

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from passlib.context import CryptContext

import database as db
from config import settings
from keyboards import (
    cancel_kb,
    confirm_kb,
    superadmin_menu_kb,
)
from states import (
    SuperAdminAddAdmin,
    SuperAdminBan,
    SuperAdminBroadcast,
    SuperAdminUnban,
    SuperAdminWarn,
)

logger = logging.getLogger(__name__)
router = Router(name="superadmin")
pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")


def _is_superadmin(message: Message) -> bool:
    return message.from_user.id in settings.SUPERADMIN_IDS


def _is_superadmin_cb(callback: CallbackQuery) -> bool:
    return callback.from_user.id in settings.SUPERADMIN_IDS


def _gen_password(length: int = 12) -> str:
    alphabet = string.ascii_letters + string.digits + "!@#$%"
    return "".join(secrets.choice(alphabet) for _ in range(length))


# ──────────────────────────────────────────────────────
#  Вход + меню
# ──────────────────────────────────────────────────────

@router.message(F.text == "⚡ Суперадмин")
async def superadmin_menu(message: Message) -> None:
    if not _is_superadmin(message):
        return
    stats = await db.get_stats()
    await message.answer(
        f"⚡ <b>Суперадмин-панель</b>\n\n"
        f"👥 Пользователей: {stats['users_count']}\n"
        f"🛡 Администраторов: {stats['admins_count']} (онлайн: {stats['online_admins']})\n"
        f"💬 Диалогов: {stats['total_dialogs']} (активных: {stats['active_dialogs']})\n"
        f"📨 Сообщений: {stats['total_messages']}\n"
        f"⭐ Отзывов: {stats['reviews_count']} (рейтинг: {stats['avg_rating']})\n"
        f"🚫 Забанено: {stats['banned_users']}",
        reply_markup=superadmin_menu_kb(),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "sa_stats")
async def sa_stats_cb(callback: CallbackQuery) -> None:
    if not _is_superadmin_cb(callback):
        await callback.answer("Нет доступа")
        return
    stats = await db.get_stats()
    daily = "\n".join(f"  {d['date']}: {d['count']} сообщений" for d in stats["daily_messages"])
    await callback.message.answer(
        f"📊 <b>Подробная статистика</b>\n\n"
        f"👥 Пользователи: {stats['users_count']}\n"
        f"🛡 Администраторы: {stats['admins_count']}\n"
        f"💬 Все диалоги: {stats['total_dialogs']}\n"
        f"💬 Активные: {stats['active_dialogs']}\n"
        f"📨 Сообщения: {stats['total_messages']}\n"
        f"⭐ Отзывы: {stats['reviews_count']}\n"
        f"★ Средний рейтинг: {stats['avg_rating']}\n"
        f"🚫 Забанено: {stats['banned_users']}\n\n"
        f"📆 <b>Сообщений по дням:</b>\n{daily or 'нет данных'}",
        parse_mode="HTML",
    )
    await callback.answer()


# ──────────────────────────────────────────────────────
#  Добавить администратора
# ──────────────────────────────────────────────────────

@router.callback_query(F.data == "sa_add_admin")
async def sa_add_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_superadmin_cb(callback):
        await callback.answer("Нет доступа")
        return
    await callback.message.answer(
        "➕ <b>Добавление администратора</b>\n\n"
        "Введите Telegram ID нового администратора:",
        reply_markup=cancel_kb(),
        parse_mode="HTML",
    )
    await state.set_state(SuperAdminAddAdmin.telegram_id)
    await callback.answer()


@router.message(SuperAdminAddAdmin.telegram_id)
async def sa_add_tgid(message: Message, state: FSMContext) -> None:
    if not _is_superadmin(message):
        return
    try:
        tg_id = int(message.text.strip())
    except ValueError:
        await message.answer("Telegram ID должен быть числом. Попробуй ещё раз:")
        return
    # Check if already admin
    existing = await db.get_admin_by_tg(tg_id)
    if existing:
        await message.answer("❌ Этот пользователь уже является администратором.")
        await state.clear()
        return
    await state.update_data(telegram_id=tg_id)
    await message.answer("Введите @username (без @) нового администратора:")
    await state.set_state(SuperAdminAddAdmin.username)


@router.message(SuperAdminAddAdmin.username)
async def sa_add_username(message: Message, state: FSMContext) -> None:
    if not _is_superadmin(message):
        return
    username = message.text.strip().lstrip("@")
    await state.update_data(username=username)
    await message.answer(
        "Введите псевдоним (логин) для администратора.\n"
        "<i>Он будет отображаться пользователям как имя администратора.</i>",
        parse_mode="HTML",
    )
    await state.set_state(SuperAdminAddAdmin.pseudonym)


@router.message(SuperAdminAddAdmin.pseudonym)
async def sa_add_pseudo(message: Message, state: FSMContext) -> None:
    if not _is_superadmin(message):
        return
    pseudo = message.text.strip()[:50]
    existing = await db.get_admin_by_pseudonym(pseudo)
    if existing:
        await message.answer("Такой псевдоним уже занят. Введите другой:")
        return
    await state.update_data(pseudonym=pseudo)
    data = await state.get_data()
    await message.answer(
        f"🔎 Проверьте данные:\n\n"
        f"TG ID: <code>{data['telegram_id']}</code>\n"
        f"Username: @{data['username']}\n"
        f"Псевдоним: <b>{pseudo}</b>\n\n"
        f"Создать администратора?",
        reply_markup=confirm_kb("sa_add_confirm", "cancel"),
        parse_mode="HTML",
    )
    await state.set_state(SuperAdminAddAdmin.confirm)


@router.callback_query(SuperAdminAddAdmin.confirm, F.data == "sa_add_confirm")
async def sa_add_confirm(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    await state.clear()

    password = _gen_password()
    pwd_hash = pwd_ctx.hash(password)

    admin = await db.create_admin(
        telegram_id=data["telegram_id"],
        username=data["username"],
        pseudonym=data["pseudonym"],
        password_hash=pwd_hash,
    )

    # Also create user entry if not exists
    await db.upsert_user(data["telegram_id"], data["username"])

    # Notify new admin
    try:
        await callback.bot.send_message(
            data["telegram_id"],
            f"🎉 Вас назначили администратором!\n\n"
            f"🔑 Ваш пароль для веб-панели: <code>{password}</code>\n"
            f"👤 Логин: <code>{data['pseudonym']}</code>\n\n"
            f"⚠️ Сохраните пароль — он показывается один раз!\n\n"
            f"Нажмите /start для активации аккаунта.",
            parse_mode="HTML",
        )
    except Exception as e:
        logger.warning("notify new admin: %s", e)

    await callback.message.edit_text(
        f"✅ Администратор <b>{data['pseudonym']}</b> создан!\n"
        f"Канал «Канал {data['pseudonym']}» создан автоматически.\n"
        f"Уведомление отправлено пользователю.",
        parse_mode="HTML",
    )
    await callback.answer()


# ──────────────────────────────────────────────────────
#  Удалить администратора
# ──────────────────────────────────────────────────────

@router.callback_query(F.data == "sa_del_admin")
async def sa_del_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_superadmin_cb(callback):
        await callback.answer("Нет доступа")
        return
    admins = await db.get_all_admins()
    if not admins:
        await callback.message.answer("Администраторов нет.")
        await callback.answer()
        return
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton
    b = InlineKeyboardBuilder()
    for a in admins:
        b.row(InlineKeyboardButton(
            text=f"❌ {a['pseudonym']}",
            callback_data=f"sa_del_confirm:{a['id']}",
        ))
    b.row(InlineKeyboardButton(text="◀️ Отмена", callback_data="cancel"))
    await callback.message.answer("Выберите администратора для удаления:", reply_markup=b.as_markup())
    await callback.answer()


@router.callback_query(F.data.startswith("sa_del_confirm:"))
async def sa_del_confirm(callback: CallbackQuery) -> None:
    if not _is_superadmin_cb(callback):
        await callback.answer("Нет доступа")
        return
    admin_id = int(callback.data.split(":")[1])
    admin = await db.get_admin_by_id(admin_id)
    if not admin:
        await callback.answer("Не найден")
        return
    await db.delete_admin(admin_id)
    await callback.message.edit_text(f"✅ Администратор <b>{admin['pseudonym']}</b> удалён.", parse_mode="HTML")
    try:
        await callback.bot.send_message(admin["telegram_id"], "⚠️ Ваши права администратора отозваны.")
    except Exception:
        pass
    await callback.answer()


# ──────────────────────────────────────────────────────
#  Бан / Разбан / Варн
# ──────────────────────────────────────────────────────

@router.callback_query(F.data == "sa_ban")
async def sa_ban_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_superadmin_cb(callback):
        await callback.answer()
        return
    await callback.message.answer("🚫 Введите Telegram ID пользователя для бана:", reply_markup=cancel_kb())
    await state.set_state(SuperAdminBan.user_id)
    await callback.answer()


@router.message(SuperAdminBan.user_id)
async def sa_ban_userid(message: Message, state: FSMContext) -> None:
    if not _is_superadmin(message):
        return
    try:
        uid = int(message.text.strip())
    except ValueError:
        await message.answer("Введи числовой Telegram ID:")
        return
    await state.update_data(user_id=uid)
    await message.answer("Введите причину бана:", reply_markup=cancel_kb())
    from states import SuperAdminBan
    await state.set_state(SuperAdminBan.reason)


@router.message(SuperAdminBan.reason)
async def sa_ban_reason(message: Message, state: FSMContext) -> None:
    if not _is_superadmin(message):
        return
    data = await state.get_data()
    await state.clear()
    await db.ban_user(data["user_id"], message.text.strip(), message.from_user.id)
    try:
        await message.bot.send_message(data["user_id"], f"🚫 Вы заблокированы.\nПричина: {message.text}")
    except Exception:
        pass
    await message.answer(f"✅ Пользователь {data['user_id']} заблокирован.")


@router.callback_query(F.data == "sa_unban")
async def sa_unban_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_superadmin_cb(callback):
        await callback.answer()
        return
    await callback.message.answer("✅ Введите Telegram ID для разбана:", reply_markup=cancel_kb())
    await state.set_state(SuperAdminUnban.user_id)
    await callback.answer()


@router.message(SuperAdminUnban.user_id)
async def sa_unban_do(message: Message, state: FSMContext) -> None:
    if not _is_superadmin(message):
        return
    await state.clear()
    try:
        uid = int(message.text.strip())
    except ValueError:
        await message.answer("Неверный ID")
        return
    await db.unban_user(uid, message.from_user.id)
    try:
        await message.bot.send_message(uid, "✅ Ваша блокировка снята.")
    except Exception:
        pass
    await message.answer(f"✅ Пользователь {uid} разблокирован.")


@router.callback_query(F.data == "sa_warn")
async def sa_warn_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_superadmin_cb(callback):
        await callback.answer()
        return
    await callback.message.answer("⚠️ Введите Telegram ID для варна:", reply_markup=cancel_kb())
    await state.set_state(SuperAdminWarn.user_id)
    await callback.answer()


@router.message(SuperAdminWarn.user_id)
async def sa_warn_do(message: Message, state: FSMContext) -> None:
    if not _is_superadmin(message):
        return
    await state.clear()
    try:
        uid = int(message.text.strip())
    except ValueError:
        await message.answer("Неверный ID")
        return
    warns = await db.warn_user(uid, message.from_user.id)
    try:
        await message.bot.send_message(uid, f"⚠️ Вам выдано предупреждение ({warns}/3).")
    except Exception:
        pass
    await message.answer(f"✅ Предупреждение выдано. Всего варнов: {warns}")


@router.callback_query(F.data == "sa_unwarn")
async def sa_unwarn_do(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_superadmin_cb(callback):
        await callback.answer()
        return
    await callback.message.answer("↩️ Введите Telegram ID для снятия варна:", reply_markup=cancel_kb())
    from states import SuperAdminWarn
    await state.set_state(SuperAdminWarn.user_id)
    await callback.answer()


# ──────────────────────────────────────────────────────
#  Рассылка
# ──────────────────────────────────────────────────────

@router.callback_query(F.data == "sa_broadcast")
async def sa_broadcast_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_superadmin_cb(callback):
        await callback.answer()
        return
    await callback.message.answer(
        "📣 <b>Рассылка</b>\n\nВведите текст сообщения (можно с фото/медиа — отправьте сообщение с подписью):",
        reply_markup=cancel_kb(),
        parse_mode="HTML",
    )
    await state.set_state(SuperAdminBroadcast.content)
    await callback.answer()


@router.message(SuperAdminBroadcast.content)
async def sa_broadcast_content(message: Message, state: FSMContext) -> None:
    if not _is_superadmin(message):
        return
    await state.update_data(
        content=message.text or message.caption or "",
        photo_id=message.photo[-1].file_id if message.photo else None,
    )
    users = await db.get_active_users()
    await message.answer(
        f"Сообщение будет отправлено <b>{len(users)}</b> пользователям.\n\nПодтвердить?",
        reply_markup=confirm_kb("sa_broadcast_confirm", "cancel"),
        parse_mode="HTML",
    )
    await state.set_state(SuperAdminBroadcast.confirm)


@router.callback_query(SuperAdminBroadcast.confirm, F.data == "sa_broadcast_confirm")
async def sa_broadcast_send(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    await state.clear()

    users = await db.get_active_users()
    sent = 0
    failed = 0

    for user in users:
        try:
            if data.get("photo_id"):
                await callback.bot.send_photo(
                    user["telegram_id"],
                    data["photo_id"],
                    caption=data["content"],
                )
            else:
                await callback.bot.send_message(user["telegram_id"], data["content"])
            sent += 1
        except Exception:
            failed += 1

    await db.save_broadcast(data["content"], callback.from_user.id, sent)
    await callback.message.edit_text(
        f"📣 Рассылка завершена!\n✅ Отправлено: {sent}\n❌ Ошибок: {failed}"
    )
    await callback.answer()


# ──────────────────────────────────────────────────────
#  Общий отмена
# ──────────────────────────────────────────────────────

@router.callback_query(F.data == "cancel")
async def cancel_cb(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text("Отменено.")
    await callback.answer()
