"""
norm_service.py — Еженедельная проверка нормы администраторов.

Логика:
- Каждую неделю в настроенный день/час запускается check_norm()
- Администраторы у которых weekly_dialogs < norm И is_on_rest=False — увольняются
- Администратор на отдыхе (is_on_rest=True) пропускается
- После проверки weekly_dialogs обнуляется у всех
- В ADMIN_GROUP отправляется итоговый отчёт
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, date

from aiogram import Bot

import database as db
from config import settings

logger = logging.getLogger(__name__)


async def check_norm(bot: Bot) -> dict:
    """
    Основная функция проверки нормы.
    Возвращает словарь с результатами.
    """
    norm_enabled = await db.get_setting("norm_enabled", "true")
    if norm_enabled.lower() != "true":
        logger.info("Norm check is disabled, skipping.")
        return {"skipped": True}

    norm_value = int(await db.get_setting("weekly_norm", "10"))
    admins = await db.get_admins_for_norm_check()

    fired     = []
    passed    = []
    on_rest   = []
    details   = []

    for a in admins:
        entry = {
            "admin_id":      a["id"],
            "pseudonym":     a["pseudonym"],
            "weekly_dialogs": a["weekly_dialogs"],
            "is_on_rest":    a["is_on_rest"],
            "result":        "",
        }

        # Проверяем дату окончания отдыха
        if a["is_on_rest"] and a.get("rest_until"):
            if date.today() >= a["rest_until"]:
                # Отдых закончился — снимаем флаг
                await db.set_admin_rest(a["id"], False, None)
                a = dict(a)
                a["is_on_rest"] = False

        if a["is_on_rest"]:
            entry["result"] = "rest"
            on_rest.append(a)
        elif a["weekly_dialogs"] >= norm_value:
            entry["result"] = "passed"
            passed.append(a)
        else:
            entry["result"] = "fired"
            fired.append(a)

        details.append(entry)

    # Увольняем не прошедших норму
    for a in fired:
        try:
            tg_id = await db.delete_admin(a["id"])
            if tg_id:
                # Уведомляем администратора
                try:
                    await bot.send_message(
                        tg_id,
                        f"Добрый день.\n\n"
                        f"По результатам недельной проверки вы не выполнили норму "
                        f"({a['weekly_dialogs']} из {norm_value} диалогов).\n"
                        f"Ваши права администратора сняты.\n\n"
                        f"Если считаете это ошибкой — обратитесь к суперадминистратору.",
                    )
                except Exception:
                    pass
                # Кикаем из группы
                try:
                    await bot.ban_chat_member(settings.ADMIN_GROUP_ID, tg_id)
                    await bot.unban_chat_member(settings.ADMIN_GROUP_ID, tg_id)
                except Exception as e:
                    logger.warning("Could not kick %s from group: %s", tg_id, e)
        except Exception as e:
            logger.error("Error firing admin %s: %s", a["pseudonym"], e)

    # Сбрасываем счётчики у оставшихся
    await db.reset_all_weekly_dialogs()

    # Сохраняем лог
    await db.save_norm_check_log(norm_value, len(fired), details)

    # Отправляем отчёт суперадминам
    report_lines = [
        f"Проверка нормы завершена ({datetime.now().strftime('%d.%m.%Y %H:%M')})\n",
        f"Норма: {norm_value} диалогов/неделю\n",
        f"Прошли: {len(passed)}  |  Не прошли (уволены): {len(fired)}  |  На отдыхе: {len(on_rest)}\n",
    ]
    if fired:
        report_lines.append("\nУволены:")
        for a in fired:
            report_lines.append(f"  - {a['pseudonym']} ({a['weekly_dialogs']} диал.)")
    if on_rest:
        report_lines.append("\nНа отдыхе (пропущены):")
        for a in on_rest:
            report_lines.append(f"  - {a['pseudonym']}")

    report = "\n".join(report_lines)

    for sa_id in settings.SUPERADMIN_IDS:
        try:
            await bot.send_message(sa_id, report)
        except Exception as e:
            logger.warning("Could not notify superadmin %s: %s", sa_id, e)

    # В группу
    try:
        await bot.send_message(settings.ADMIN_GROUP_ID, report)
    except Exception as e:
        logger.warning("Could not send norm report to group: %s", e)

    return {
        "fired":   len(fired),
        "passed":  len(passed),
        "on_rest": len(on_rest),
        "norm":    norm_value,
    }


async def norm_scheduler(bot: Bot) -> None:
    """
    Фоновая задача. Каждую минуту проверяет не пора ли запустить norm check.
    Настройки читаются из БД (norm_check_weekday, norm_check_hour).
    """
    last_checked_date = None

    while True:
        await asyncio.sleep(60)
        try:
            norm_enabled = await db.get_setting("norm_enabled", "true")
            if norm_enabled.lower() != "true":
                continue

            weekday = int(await db.get_setting("norm_check_weekday", "0"))  # 0=Пн
            hour    = int(await db.get_setting("norm_check_hour",    "10"))

            now = datetime.now()
            if now.weekday() == weekday and now.hour == hour:
                today = now.date()
                if last_checked_date != today:
                    logger.info("Running weekly norm check...")
                    last_checked_date = today
                    await check_norm(bot)
        except Exception as e:
            logger.error("norm_scheduler error: %s", e)
