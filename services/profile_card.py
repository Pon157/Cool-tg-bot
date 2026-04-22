"""
profile_card.py — Генерация красивой карточки-анкеты через Pillow.
"""
from __future__ import annotations

import io
import textwrap
from typing import Optional

import httpx
from PIL import Image, ImageDraw, ImageFilter, ImageFont

# ──────────────────────────────────────────────────────
#  Константы
# ──────────────────────────────────────────────────────

W, H = 680, 420
PADDING = 36
AVATAR_SIZE = 110
AVATAR_X, AVATAR_Y = PADDING, PADDING

# Цветовая схема
BG_TOP    = (18,  24,  54)
BG_BOT    = (34,  48, 110)
ACCENT    = (99, 143, 255)
TEXT_PRI  = (235, 240, 255)
TEXT_SEC  = (160, 180, 230)
TEXT_MUT  = (100, 120, 175)
WHITE     = (255, 255, 255)

FONT_PATHS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
]
FONT_PATHS_REG = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
]


def _load_font(paths: list, size: int) -> ImageFont.FreeTypeFont:
    for p in paths:
        try:
            return ImageFont.truetype(p, size)
        except (IOError, OSError):
            continue
    return ImageFont.load_default()


# ──────────────────────────────────────────────────────
#  Вспомогательные функции
# ──────────────────────────────────────────────────────

def _gradient(w: int, h: int) -> Image.Image:
    base = Image.new("RGB", (w, h))
    draw = ImageDraw.Draw(base)
    for y in range(h):
        t = y / h
        r = int(BG_TOP[0] + (BG_BOT[0] - BG_TOP[0]) * t)
        g = int(BG_TOP[1] + (BG_BOT[1] - BG_TOP[1]) * t)
        b = int(BG_TOP[2] + (BG_BOT[2] - BG_TOP[2]) * t)
        draw.line([(0, y), (w, y)], fill=(r, g, b))
    return base


def _circle_mask(size: int) -> Image.Image:
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, size, size), fill=255)
    return mask


def _round_rect(draw: ImageDraw.ImageDraw, xy, radius: int, fill, outline=None, width: int = 1):
    x1, y1, x2, y2 = xy
    draw.rounded_rectangle([x1, y1, x2, y2], radius=radius, fill=fill, outline=outline, width=width)


def _wrap(text: str, max_chars: int) -> list[str]:
    return textwrap.wrap(text or "", max_chars) or ["—"]


# ──────────────────────────────────────────────────────
#  Основная функция генерации
# ──────────────────────────────────────────────────────

async def generate_profile_card(
    pseudonym: str,
    age: str,
    characteristics: str,
    hobbies: str,
    avatar_url: Optional[str] = None,
) -> bytes:
    # ---- фон ----
    img = _gradient(W, H)
    draw = ImageDraw.Draw(img, "RGBA")

    # ---- декоративный блок ----
    # Верхняя полоска
    draw.rectangle([0, 0, W, 4], fill=ACCENT)
    # Нижняя полоска
    draw.rectangle([0, H - 4, W, H], fill=ACCENT)
    # Полупрозрачный прямоугольник под аватаром
    _round_rect(draw, (PADDING - 8, PADDING - 8, PADDING + AVATAR_SIZE + 8, PADDING + AVATAR_SIZE + 8),
                radius=16, fill=(255, 255, 255, 20))

    # ---- шрифты ----
    fn_big   = _load_font(FONT_PATHS,     28)
    fn_med   = _load_font(FONT_PATHS,     18)
    fn_small = _load_font(FONT_PATHS_REG, 15)
    fn_tiny  = _load_font(FONT_PATHS_REG, 13)

    # ---- аватар ----
    if avatar_url:
        try:
            async with httpx.AsyncClient(timeout=8) as c:
                resp = await c.get(avatar_url)
                resp.raise_for_status()
            av = Image.open(io.BytesIO(resp.content)).convert("RGBA")
            av = av.resize((AVATAR_SIZE, AVATAR_SIZE), Image.LANCZOS)
            mask = _circle_mask(AVATAR_SIZE)
            # glow ring
            ring = Image.new("RGBA", (AVATAR_SIZE + 8, AVATAR_SIZE + 8), (0, 0, 0, 0))
            ImageDraw.Draw(ring).ellipse((0, 0, AVATAR_SIZE + 8, AVATAR_SIZE + 8),
                                         outline=ACCENT, width=3)
            img.paste(ring, (AVATAR_X - 4, AVATAR_Y - 4), ring)
            img.paste(av, (AVATAR_X, AVATAR_Y), mask)
        except Exception:
            _draw_default_avatar(draw, AVATAR_X, AVATAR_Y, AVATAR_SIZE, pseudonym)
    else:
        _draw_default_avatar(draw, AVATAR_X, AVATAR_Y, AVATAR_SIZE, pseudonym)

    # ---- имя и возраст ----
    name_x = AVATAR_X + AVATAR_SIZE + 24
    draw.text((name_x, AVATAR_Y + 10), pseudonym[:30], font=fn_big, fill=TEXT_PRI)
    draw.text((name_x, AVATAR_Y + 48), f"🎂 Возраст: {age}", font=fn_small, fill=TEXT_SEC)

    # ---- горизонтальный разделитель ----
    sep_y = AVATAR_Y + AVATAR_SIZE + 20
    draw.line([(PADDING, sep_y), (W - PADDING, sep_y)], fill=(*ACCENT, 120), width=1)

    # ---- блоки с информацией ----
    y = sep_y + 18
    y = _info_block(draw, y, "✨ Характеристики", characteristics,
                    fn_med, fn_small, max_chars=55, max_lines=3)
    y = _info_block(draw, y, "🎯 Увлечения", hobbies,
                    fn_med, fn_small, max_chars=55, max_lines=3)

    # ---- водяной знак ----
    draw.text((W - 180, H - 22), "Anon Support Bot", font=fn_tiny, fill=TEXT_MUT)

    # ---- export ----
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def _draw_default_avatar(draw: ImageDraw.ImageDraw, x: int, y: int, size: int, name: str) -> None:
    draw.ellipse((x, y, x + size, y + size), fill=ACCENT)
    font = _load_font(FONT_PATHS, 36)
    letter = (name[0].upper() if name else "?")
    bbox = draw.textbbox((0, 0), letter, font=font)
    lw, lh = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text((x + (size - lw) // 2, y + (size - lh) // 2 - 4), letter, font=font, fill=WHITE)


def _info_block(draw, y, title, content, fn_title, fn_body, max_chars=55, max_lines=3) -> int:
    draw.text((PADDING, y), title, font=fn_title, fill=ACCENT)
    y += 26
    lines = _wrap(content, max_chars)[:max_lines]
    for line in lines:
        draw.text((PADDING + 6, y), line, font=fn_body, fill=TEXT_PRI)
        y += 20
    y += 10
    return y
