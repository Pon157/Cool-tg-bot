
"""
profile_card.py — Генерация карточки-анкеты через Pillow.

Ключевые фиксы v2:
- Изображение создаётся в режиме RGB (не RGBA) — иначе paste/save ломается
- Все emoji убраны из draw.text() — Pillow не рендерит emoji, крашится
- Шрифты ищутся в реальных путях Ubuntu + fallback на load_default()
- Запуск через asyncio.to_thread чтобы не блокировать event loop
"""
from __future__ import annotations

import asyncio
import glob
import io
import logging
import textwrap
from typing import Optional

import httpx
from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)

# ── Размеры ──────────────────────────────────────────
W, H        = 700, 440
PADDING     = 38
AVATAR_SIZE = 112
AVATAR_X    = PADDING
AVATAR_Y    = PADDING

# ── Цвета ────────────────────────────────────────────
BG_TOP   = (15,  20,  48)
BG_BOT   = (30,  44, 100)
ACCENT   = (90, 138, 255)
TEXT_PRI = (230, 236, 255)
TEXT_SEC = (150, 170, 220)
TEXT_MUT = (90,  110, 165)
WHITE    = (255, 255, 255)


# ── Поиск шрифтов ────────────────────────────────────

def _find_fonts() -> tuple[list[str], list[str]]:
    """Возвращает (bold_paths, regular_paths) — ищем по всей системе."""
    bold_globs = [
        "/usr/share/fonts/**/*Bold*.ttf",
        "/usr/share/fonts/**/*bold*.ttf",
        "/usr/share/fonts/**/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/**/LiberationSans-Bold.ttf",
        "/usr/local/share/fonts/**/*Bold*.ttf",
    ]
    reg_globs = [
        "/usr/share/fonts/**/DejaVuSans.ttf",
        "/usr/share/fonts/**/LiberationSans-Regular.ttf",
        "/usr/share/fonts/**/*Regular*.ttf",
        "/usr/local/share/fonts/**/*Regular*.ttf",
    ]
    bold = []
    for g in bold_globs:
        bold.extend(glob.glob(g, recursive=True))
    reg = []
    for g in reg_globs:
        reg.extend(glob.glob(g, recursive=True))
    return bold, reg


_BOLD_PATHS, _REG_PATHS = _find_fonts()


def _font(paths: list[str], size: int) -> ImageFont.FreeTypeFont:
    for p in paths:
        try:
            return ImageFont.truetype(p, size)
        except Exception:
            continue
    # Последний резерв: встроенный bitmap-шрифт
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


# ── Helpers ──────────────────────────────────────────

def _gradient(w: int, h: int) -> Image.Image:
    img  = Image.new("RGB", (w, h))
    draw = ImageDraw.Draw(img)
    for y in range(h):
        t = y / h
        r = int(BG_TOP[0] + (BG_BOT[0] - BG_TOP[0]) * t)
        g = int(BG_TOP[1] + (BG_BOT[1] - BG_TOP[1]) * t)
        b = int(BG_TOP[2] + (BG_BOT[2] - BG_TOP[2]) * t)
        draw.line([(0, y), (w, y)], fill=(r, g, b))
    return img


def _circle_crop(img: Image.Image, size: int) -> Image.Image:
    img    = img.resize((size, size), Image.LANCZOS).convert("RGBA")
    mask   = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, size - 1, size - 1), fill=255)
    result = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    result.paste(img, (0, 0), mask)
    return result


def _wrap(text: str, max_chars: int, max_lines: int = 3) -> list[str]:
    lines = textwrap.wrap(text or "", max_chars)
    return lines[:max_lines] if lines else ["-"]


def _strip_emoji(text: str) -> str:
    """Убираем emoji — Pillow их не рендерит и падает."""
    import re
    emoji_pattern = re.compile(
        "["
        "\U0001F600-\U0001F64F"
        "\U0001F300-\U0001F5FF"
        "\U0001F680-\U0001F6FF"
        "\U0001F1E0-\U0001F1FF"
        "\U00002702-\U000027B0"
        "\U000024C2-\U0001F251"
        "]+", flags=re.UNICODE
    )
    return emoji_pattern.sub("", text).strip()


# ── Синхронная генерация (запускается в thread) ──────

def _generate_sync(
    pseudonym: str,
    age: str,
    characteristics: str,
    hobbies: str,
    avatar_bytes: Optional[bytes],
) -> bytes:
    img  = _gradient(W, H)
    draw = ImageDraw.Draw(img)

    # Акцентные полоски
    draw.rectangle([0, 0, W, 4], fill=ACCENT)
    draw.rectangle([0, H - 4, W, H], fill=ACCENT)

    # Шрифты
    fn_name  = _font(_BOLD_PATHS, 26)
    fn_label = _font(_BOLD_PATHS, 15)
    fn_body  = _font(_REG_PATHS,  14)
    fn_tiny  = _font(_REG_PATHS,  12)

    # ── Аватар ──
    av_rgb = None
    if avatar_bytes:
        try:
            av_raw = Image.open(io.BytesIO(avatar_bytes))
            av_rgb = _circle_crop(av_raw, AVATAR_SIZE)
        except Exception as e:
            logger.debug("avatar open error: %s", e)

    if av_rgb:
        # Кольцо вокруг аватара
        ring_size = AVATAR_SIZE + 6
        ring = Image.new("RGBA", (ring_size, ring_size), (0, 0, 0, 0))
        ImageDraw.Draw(ring).ellipse(
            (0, 0, ring_size - 1, ring_size - 1),
            outline=ACCENT, width=3,
        )
        # paste RGBA на RGB через маску
        img.paste(ring.convert("RGB"), (AVATAR_X - 3, AVATAR_Y - 3),
                  ring.split()[3])
        img.paste(av_rgb.convert("RGB"), (AVATAR_X, AVATAR_Y),
                  av_rgb.split()[3])
    else:
        # Цветной круг с буквой
        draw.ellipse(
            (AVATAR_X, AVATAR_Y, AVATAR_X + AVATAR_SIZE, AVATAR_Y + AVATAR_SIZE),
            fill=ACCENT,
        )
        letter = (pseudonym[0].upper() if pseudonym else "?")
        fn_big = _font(_BOLD_PATHS, 40)
        bb = draw.textbbox((0, 0), letter, font=fn_big)
        lw, lh = bb[2] - bb[0], bb[3] - bb[1]
        draw.text(
            (AVATAR_X + (AVATAR_SIZE - lw) // 2,
             AVATAR_Y + (AVATAR_SIZE - lh) // 2 - 2),
            letter, font=fn_big, fill=WHITE,
        )

    # ── Имя и возраст ──
    name_x = AVATAR_X + AVATAR_SIZE + 22
    name_y = AVATAR_Y + 10
    draw.text((name_x, name_y), _strip_emoji(pseudonym)[:30],
              font=fn_name, fill=TEXT_PRI)
    draw.text((name_x, name_y + 36), f"Возраст: {_strip_emoji(age)}",
              font=fn_body, fill=TEXT_SEC)

    # ── Разделитель ──
    sep_y = AVATAR_Y + AVATAR_SIZE + 18
    draw.line([(PADDING, sep_y), (W - PADDING, sep_y)],
              fill=(*ACCENT, 100), width=1)

    # ── Блоки информации ──
    y = sep_y + 16

    def info_block(label: str, content: str) -> int:
        nonlocal y
        draw.text((PADDING, y), label, font=fn_label, fill=ACCENT)
        y += 22
        for line in _wrap(_strip_emoji(content), 60):
            draw.text((PADDING + 4, y), line, font=fn_body, fill=TEXT_PRI)
            y += 19
        y += 8
        return y

    info_block("Характеристики", characteristics)
    info_block("Увлечения", hobbies)

    # ── Водяной знак ──
    draw.text((W - 170, H - 20), "Anon Support Bot",
              font=fn_tiny, fill=TEXT_MUT)

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


# ── Публичная async функция ──────────────────────────

async def generate_profile_card(
    pseudonym: str,
    age: str,
    characteristics: str,
    hobbies: str,
    avatar_url: Optional[str] = None,
) -> bytes:
    avatar_bytes: Optional[bytes] = None
    if avatar_url:
        try:
            async with httpx.AsyncClient(timeout=8) as c:
                resp = await c.get(avatar_url)
                resp.raise_for_status()
                avatar_bytes = resp.content
        except Exception as e:
            logger.debug("avatar download failed: %s", e)

    # CPU-bound работу выносим в thread
    return await asyncio.to_thread(
        _generate_sync,
        pseudonym or "Аноним",
        age or "не указан",
        characteristics or "",
        hobbies or "",
        avatar_bytes,
    )
