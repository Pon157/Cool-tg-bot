"""
s3_service.py — Работа с S3-совместимым хранилищем через aioboto3.
"""
from __future__ import annotations

import logging
from typing import Optional

import aioboto3
import httpx

from config import settings

logger = logging.getLogger(__name__)

_session = aioboto3.Session(
    aws_access_key_id=settings.S3_ACCESS_KEY,
    aws_secret_access_key=settings.S3_SECRET_KEY,
)


def _client():
    return _session.client("s3", endpoint_url=settings.S3_ENDPOINT_URL)


async def upload_bytes(data: bytes, key: str, content_type: str = "application/octet-stream") -> str:
    """Upload raw bytes and return public URL."""
    async with _client() as s3:
        await s3.put_object(
            Bucket=settings.S3_BUCKET_NAME,
            Key=key,
            Body=data,
            ContentType=content_type,
            ACL="public-read",
        )
    return f"{settings.S3_PUBLIC_URL}/{settings.S3_BUCKET_NAME}/{key}"


async def upload_from_url(url: str, key: str) -> str:
    """Download from URL and upload to S3."""
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        ct = resp.headers.get("content-type", "application/octet-stream").split(";")[0]
    return await upload_bytes(resp.content, key, ct)


async def upload_telegram_file(bot, file_id: str, folder: str) -> str:
    """Download a Telegram file and upload to S3."""
    tg_file = await bot.get_file(file_id)
    ext = tg_file.file_path.rsplit(".", 1)[-1] if "." in tg_file.file_path else "bin"
    url = f"https://api.telegram.org/file/bot{settings.BOT_TOKEN}/{tg_file.file_path}"
    key = f"{folder}/{file_id}.{ext}"
    return await upload_from_url(url, key)


async def delete_file(key: str) -> None:
    async with _client() as s3:
        await s3.delete_object(Bucket=settings.S3_BUCKET_NAME, Key=key)
