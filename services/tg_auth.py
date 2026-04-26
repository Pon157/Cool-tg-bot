"""
tg_auth.py — Валидация Telegram WebApp initData + проверка суперадмина по паролю.
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
    Проверяет подпись Telegram WebApp initData.
    Возвращает dict пользователя при успехе, иначе None.
    """
    if not raw_init_data:
        return None
    try:
        params = dict(parse_qsl(raw_init_data, keep_blank_values=True))
        received_hash = params.pop("hash", None)
        if not received_hash:
            return None

        check_string = "\n".join(f"{k}={v}" for k, v in sorted(params.items()))

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

        user_raw = params.get("user", "{}")
        return json.loads(unquote(user_raw))
    except Exception as e:
        logger.warning("validate_init_data error: %s", e)
        return None
