from __future__ import annotations

from typing import List, Optional

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    WebAppInfo,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder

from config import settings

WU = settings.WEBAPP_URL   # short alias


# ──────────────────────────────────────────────────────
#  MAIN MENU
# ──────────────────────────────────────────────────────

def main_menu(is_admin: bool = False, is_superadmin: bool = False) -> ReplyKeyboardMarkup:
    b = ReplyKeyboardBuilder()
    b.row(KeyboardButton(text="✍️ Написать"),
          KeyboardButton(text="👤 Мой профиль"))
    b.row(
        KeyboardButton(text="👥 Администраторы",
                       web_app=WebAppInfo(url=f"{WU}/admins.html")),
        KeyboardButton(text="⭐ Отзывы",
                       web_app=WebAppInfo(url=f"{WU}/reviews.html")),
    )
    b.row(KeyboardButton(text="📺 Каналы",
                         web_app=WebAppInfo(url=f"{WU}/channels.html")))
    if is_admin:
        b.row(KeyboardButton(text="🛠 Панель администратора",
                             web_app=WebAppInfo(url=f"{WU}/admin_panel.html")))
    if is_superadmin:
        b.row(KeyboardButton(text="⚡ Суперадмин",
                             web_app=WebAppInfo(url=f"{WU}/superadmin.html")))
    return b.as_markup(resize_keyboard=True)


# ──────────────────────────────────────────────────────
#  PROFILE
# ──────────────────────────────────────────────────────

def profile_menu() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text="🖼 Посмотреть анкету", callback_data="view_card"))
    b.row(InlineKeyboardButton(text="✏️ Редактировать", callback_data="edit_profile"))
    b.row(InlineKeyboardButton(text="⭐ Мои отзывы", callback_data="my_reviews"))
    b.row(InlineKeyboardButton(text="🤖 Рекомендации ИИ", callback_data="ai_recs"))
    return b.as_markup()


def edit_profile_menu() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for text, cb in [
        ("👤 Псевдоним",      "ep_pseudonym"),
        ("🎂 Возраст",         "ep_age"),
        ("✨ Характеристики", "ep_characteristics"),
        ("🎯 Увлечения",      "ep_hobbies"),
    ]:
        b.row(InlineKeyboardButton(text=text, callback_data=cb))
    b.row(InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_profile"))
    return b.as_markup()


# ──────────────────────────────────────────────────────
#  DIALOGS
# ──────────────────────────────────────────────────────

def dialog_mode_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text="👤 С профилем",             callback_data="dlg_mode:profile"))
    b.row(InlineKeyboardButton(text="🎭 Полностью анонимно",    callback_data="dlg_mode:anon"))
    b.row(InlineKeyboardButton(text="❌ Отмена",                 callback_data="dlg_cancel"))
    return b.as_markup()


def choose_admin_kb(admins: List[dict], mode: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(
        text="🎲 Любой подходящий (ИИ подберёт)",
        callback_data=f"pick_admin:any:{mode}",
    ))
    for a in admins:
        dot = "🟢" if a["is_online"] else "🔴"
        stars = ""
        if a.get("avg_rating"):
            stars = f" ★{a['avg_rating']:.1f}"
        b.row(InlineKeyboardButton(
            text=f"{dot} {a['pseudonym']}{stars}",
            callback_data=f"pick_admin:{a['id']}:{mode}",
        ))
    b.row(InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_mode"))
    return b.as_markup()


def accept_dialog_kb(dialog_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(
        text="✅ Принять обращение",
        callback_data=f"accept_dlg:{dialog_id}",
    ))
    return b.as_markup()


def user_in_dialog_kb(dialog_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text="🔚 Закрыть диалог", callback_data=f"user_close:{dialog_id}"))
    return b.as_markup()


def admin_in_dialog_kb(dialog_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(
        InlineKeyboardButton(text="🔚 Закрыть",       callback_data=f"admin_close:{dialog_id}"),
        InlineKeyboardButton(text="🚫 Забанить юзера", callback_data=f"admin_ban:{dialog_id}"),
    )
    return b.as_markup()


# ──────────────────────────────────────────────────────
#  REVIEWS
# ──────────────────────────────────────────────────────

def choose_admin_for_review_kb(dialogs: List[dict]) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    seen = set()
    for d in dialogs:
        key = d["admin_id"]
        if key in seen:
            continue
        seen.add(key)
        b.row(InlineKeyboardButton(
            text=f"⭐ {d['admin_pseudonym']}",
            callback_data=f"rev_admin:{d['admin_id']}:{d['id']}",
        ))
    b.row(InlineKeyboardButton(text="❌ Отмена", callback_data="rev_cancel"))
    return b.as_markup()


def rating_kb(admin_id: int, dialog_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for i in range(1, 6):
        b.add(InlineKeyboardButton(
            text="⭐" * i,
            callback_data=f"rev_rate:{admin_id}:{dialog_id}:{i}",
        ))
    b.adjust(5)
    return b.as_markup()


def skip_media_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text="➡️ Пропустить медиа", callback_data="rev_skip_media"))
    return b.as_markup()


# ──────────────────────────────────────────────────────
#  ADMIN PANEL
# ──────────────────────────────────────────────────────

def admin_panel_menu_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text="💬 Мои диалоги",   callback_data="adm_my_dialogs"))
    b.row(InlineKeyboardButton(text="📺 Мой канал",      callback_data="adm_my_channel"))
    b.row(InlineKeyboardButton(text="📝 Заполнить профиль", callback_data="adm_fill_profile"))
    b.row(InlineKeyboardButton(
        text="🌐 Веб-панель",
        web_app=WebAppInfo(url=f"{WU}/admin_panel.html"),
    ))
    return b.as_markup()


def channel_manage_kb(admin_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text="📝 Написать пост",       callback_data="ch_new_post"))
    b.row(InlineKeyboardButton(text="✏️ Изменить название",   callback_data="ch_edit:title"))
    b.row(InlineKeyboardButton(text="📄 Изменить описание",   callback_data="ch_edit:description"))
    b.row(InlineKeyboardButton(text="🖼 Изменить аватарку",   callback_data="ch_edit:avatar"))
    return b.as_markup()


# ──────────────────────────────────────────────────────
#  SUPERADMIN
# ──────────────────────────────────────────────────────

def superadmin_menu_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text="📊 Статистика",          callback_data="sa_stats"))
    b.row(
        InlineKeyboardButton(text="➕ Добавить админа",  callback_data="sa_add_admin"),
        InlineKeyboardButton(text="➖ Удалить админа",   callback_data="sa_del_admin"),
    )
    b.row(
        InlineKeyboardButton(text="🚫 Бан",     callback_data="sa_ban"),
        InlineKeyboardButton(text="✅ Разбан",   callback_data="sa_unban"),
    )
    b.row(
        InlineKeyboardButton(text="⚠️ Варн",    callback_data="sa_warn"),
        InlineKeyboardButton(text="↩️ Анварн",  callback_data="sa_unwarn"),
    )
    b.row(InlineKeyboardButton(text="📣 Рассылка",            callback_data="sa_broadcast"))
    b.row(InlineKeyboardButton(
        text="🌐 Веб-панель статистики",
        web_app=WebAppInfo(url=f"{WU}/superadmin.html"),
    ))
    return b.as_markup()


def confirm_kb(yes_cb: str, no_cb: str = "cancel") -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(
        InlineKeyboardButton(text="✅ Да",    callback_data=yes_cb),
        InlineKeyboardButton(text="❌ Нет",   callback_data=no_cb),
    )
    return b.as_markup()


def cancel_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text="❌ Отмена", callback_data="cancel"))
    return b.as_markup()
