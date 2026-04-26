"""
tg_auth.py — Валидация Telegram WebApp initData.

Telegram подписывает initData HMAC-SHA256 с ключом derived от BOT_TOKEN.
Проверяем подпись, возвращаем user dict или None.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
from typing import Optional
from urllib.parse import parse_qsl, unquote

logger = logging.getLogger(__name__)


def validate_init_data(raw_init_data: str, bot_token: str) -> Optional[dict]:
    """
    Возвращает dict с полями пользователя если подпись верна, иначе None.
    raw_init_data — строка из window.Telegram.WebApp.initData
    """
    try:
        params = dict(parse_qsl(raw_init_data, keep_blank_values=True))
        received_hash = params.pop("hash", None)
        if not received_hash:
            return None

        # Строка для проверки: ключи отсортированы, разделены \n
        check_string = "\n".join(
            f"{k}={v}" for k, v in sorted(params.items())
        )

        # secret_key = HMAC-SHA256("WebAppData", bot_token)
        secret_key = hmac.new(
            b"WebAppData",
            bot_token.encode("utf-8"),
            hashlib.sha256,
        ).digest()

        computed = hmac.new(
            secret_key,
            check_string.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        if not hmac.compare_digest(computed, received_hash):
            logger.debug("initData hash mismatch")
            return None

        # Парсим user JSON
        user_raw = params.get("user", "{}")
        return json.loads(unquote(user_raw))
    except Exception as e:
        logger.warning("validate_init_data error: %s", e)
        return None
