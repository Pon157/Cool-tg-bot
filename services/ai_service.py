"""
ai_service.py — Интеграция с Qwen (OpenAI-совместимый API).
"""
from __future__ import annotations

import json
import logging
from typing import List, Optional, Tuple

import httpx

from config import settings

logger = logging.getLogger(__name__)

HEADERS = {
    "Authorization": f"Bearer {settings.QWEN_API_KEY}",
    "Content-Type":  "application/json",
}


async def _chat(messages: list, max_tokens: int = 1000, json_mode: bool = False) -> str:
    body: dict = {
        "model":      settings.QWEN_MODEL,
        "messages":   messages,
        "max_tokens": max_tokens,
    }
    if json_mode:
        body["response_format"] = {"type": "json_object"}

    async with httpx.AsyncClient(timeout=40) as client:
        r = await client.post(
            f"{settings.QWEN_API_URL}/chat/completions",
            headers=HEADERS,
            json=body,
        )
        r.raise_for_status()
        data = r.json()
        return data["choices"][0]["message"]["content"]


# ──────────────────────────────────────────────────────
#  Анализ диалога
# ──────────────────────────────────────────────────────

async def analyze_dialog(
    messages_text: str,
    user_profile: Optional[dict] = None,
) -> Tuple[str, List[str], str]:
    """
    Returns (recommendation, keywords, emotional_tone).
    """
    system = (
        "Ты ИИ-аналитик системы поддержки. Анализируй диалог пользователя с администратором. "
        "Определи эмоциональный тон, ключевые темы и дай короткую рекомендацию пользователю. "
        "Отвечай ТОЛЬКО валидным JSON без лишнего текста:\n"
        '{"keywords":["..."],"recommendation":"...","emotional_tone":"позитивный|нейтральный|тревожный|грустный"}'
    )
    user_content = f"Диалог:\n{messages_text}"
    if user_profile:
        user_content += (
            f"\n\nПрофиль пользователя: возраст={user_profile.get('age')}, "
            f"увлечения={user_profile.get('hobbies')}, "
            f"характеристики={user_profile.get('characteristics')}"
        )

    try:
        raw = await _chat(
            [{"role": "system", "content": system},
             {"role": "user", "content": user_content}],
            max_tokens=800,
            json_mode=True,
        )
        parsed = json.loads(raw)
        return (
            parsed.get("recommendation", ""),
            parsed.get("keywords", []),
            parsed.get("emotional_tone", "нейтральный"),
        )
    except Exception as e:
        logger.warning("AI analyze_dialog error: %s", e)
        return "Анализ временно недоступен.", [], "нейтральный"


# ──────────────────────────────────────────────────────
#  Подбор администратора
# ──────────────────────────────────────────────────────

async def match_admins(user_profile: dict, admins: List[dict]) -> List[dict]:
    """
    Returns re-sorted list of admins: best matches first (max 3 recommendations).
    """
    if not admins:
        return []

    lines = []
    for i, a in enumerate(admins):
        lines.append(
            f"{i}. {a['pseudonym']}: "
            f"возраст={a.get('age','?')}, "
            f"увлечения={a.get('hobbies','?')}, "
            f"характеристики={a.get('characteristics','?')}"
        )

    prompt = (
        f"Пользователь ищет подходящего администратора.\n"
        f"Профиль: возраст={user_profile.get('age')}, "
        f"увлечения={user_profile.get('hobbies')}, "
        f"характеристики={user_profile.get('characteristics')}\n\n"
        f"Администраторы (0-based index):\n"
        + "\n".join(lines)
        + '\n\nВерни JSON: {"recommended":[indices, max 3]}'
    )

    try:
        raw = await _chat(
            [{"role": "user", "content": prompt}],
            max_tokens=200,
            json_mode=True,
        )
        parsed = json.loads(raw)
        indices = [int(i) for i in parsed.get("recommended", []) if int(i) < len(admins)]
        recommended = [admins[i] for i in indices]
        rest = [a for j, a in enumerate(admins) if j not in indices]
        return recommended + rest
    except Exception as e:
        logger.warning("AI match_admins error: %s", e)
        return admins
