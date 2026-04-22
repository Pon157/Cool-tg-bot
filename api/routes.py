"""
api/routes.py — Все REST эндпоинты для мини-приложений.
JWT аутентификация для администраторов, открытые эндпоинты для пользователей.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel

import database as db
from config import settings
from services.s3_service import upload_bytes

logger = logging.getLogger(__name__)
router = APIRouter()
bearer = HTTPBearer(auto_error=False)
pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ──────────────────────────────────────────────────────
#  JWT helpers
# ──────────────────────────────────────────────────────

def _make_token(payload: dict, expires_hours: int = 72) -> str:
    data = {**payload, "exp": datetime.utcnow() + timedelta(hours=expires_hours)}
    return jwt.encode(data, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def _decode_token(token: str) -> dict:
    return jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])


async def get_current_admin(
    cred: Optional[HTTPAuthorizationCredentials] = Depends(bearer),
) -> dict:
    exc = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    if not cred:
        raise exc
    try:
        payload = _decode_token(cred.credentials)
        admin_id = int(payload["sub"])
    except (JWTError, KeyError, ValueError):
        raise exc
    admin = await db.get_admin_by_id(admin_id)
    if not admin:
        raise exc
    return admin


async def get_current_superadmin(admin: dict = Depends(get_current_admin)) -> dict:
    if admin["telegram_id"] not in settings.SUPERADMIN_IDS:
        raise HTTPException(status_code=403, detail="Superadmin only")
    return admin


# ──────────────────────────────────────────────────────
#  Auth
# ──────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    pseudonym: str
    password: str


@router.post("/auth/login")
async def admin_login(body: LoginRequest) -> dict:
    admin = await db.get_admin_by_pseudonym(body.pseudonym)
    if not admin or not pwd_ctx.verify(body.password, admin["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = _make_token({"sub": str(admin["id"]), "role": "admin"})
    await db.set_admin_online(admin["telegram_id"], True)
    return {
        "token": token,
        "admin": {
            "id": admin["id"],
            "pseudonym": admin["pseudonym"],
            "is_superadmin": admin["telegram_id"] in settings.SUPERADMIN_IDS,
        },
    }


@router.post("/auth/logout")
async def admin_logout(admin: dict = Depends(get_current_admin)) -> dict:
    await db.set_admin_online(admin["telegram_id"], False)
    return {"ok": True}


# ──────────────────────────────────────────────────────
#  Admins (public — for mini-app users)
# ──────────────────────────────────────────────────────

@router.get("/admins")
async def list_admins() -> List[dict]:
    admins = await db.get_all_admins()
    result = []
    for a in admins:
        result.append({
            "id":          a["id"],
            "pseudonym":   a["pseudonym"],
            "age":         a.get("age"),
            "description": a.get("description"),
            "hobbies":     a.get("hobbies"),
            "avatar_url":  a.get("avatar_url"),
            "is_online":   a["is_online"],
            "last_seen":   a["last_seen"].isoformat() if a.get("last_seen") else None,
            "avg_rating":  round(float(a.get("avg_rating") or 0), 2),
            "reviews_count": int(a.get("reviews_count") or 0),
        })
    return result


@router.get("/admins/{admin_id}")
async def get_admin_detail(admin_id: int) -> dict:
    admin = await db.get_admin_by_id(admin_id)
    if not admin:
        raise HTTPException(404, "Not found")
    return {
        "id":                  admin["id"],
        "pseudonym":           admin["pseudonym"],
        "age":                 admin.get("age"),
        "description":         admin.get("description"),
        "hobbies":             admin.get("hobbies"),
        "characteristics":     admin.get("characteristics"),
        "avatar_url":          admin.get("avatar_url"),
        "channel_title":       admin.get("channel_title"),
        "channel_description": admin.get("channel_description"),
        "channel_avatar_url":  admin.get("channel_avatar_url"),
        "is_online":           admin["is_online"],
        "last_seen":           admin["last_seen"].isoformat() if admin.get("last_seen") else None,
    }


# ──────────────────────────────────────────────────────
#  Reviews (public read, auth write)
# ──────────────────────────────────────────────────────

@router.get("/reviews")
async def all_reviews(limit: int = Query(50, le=100)) -> List[dict]:
    reviews = await db.get_all_reviews(limit)
    return [_serialize_review(r) for r in reviews]


@router.get("/reviews/admin/{admin_id}")
async def admin_reviews(admin_id: int) -> List[dict]:
    reviews = await db.get_admin_reviews(admin_id)
    return [_serialize_review(r) for r in reviews]


@router.get("/reviews/user/{user_id}")
async def user_reviews(user_id: int) -> List[dict]:
    reviews = await db.get_user_reviews(user_id)
    return [_serialize_review(r) for r in reviews]


def _serialize_review(r: dict) -> dict:
    return {
        "id":              r["id"],
        "user_pseudonym":  r.get("user_pseudonym", "Аноним"),
        "admin_pseudonym": r.get("admin_pseudonym"),
        "text":            r.get("text"),
        "rating":          r["rating"],
        "media_urls":      r.get("media_urls") or [],
        "created_at":      r["created_at"].isoformat(),
    }


class ReviewBody(BaseModel):
    user_id: int
    admin_id: int
    dialog_id: int
    text: Optional[str] = None
    rating: int


@router.post("/reviews")
async def create_review(body: ReviewBody) -> dict:
    # Verify user had a dialog with this admin
    had = await db.user_had_dialog_with_admin(body.user_id, body.admin_id)
    if not had:
        raise HTTPException(403, "No completed dialog with this admin")
    r = await db.upsert_review(body.user_id, body.admin_id, body.dialog_id,
                                body.text or "", body.rating, [])
    return {"ok": True, "review_id": r["id"]}


@router.post("/reviews/media")
async def upload_review_media(file: UploadFile = File(...)) -> dict:
    data = await file.read()
    ct = file.content_type or "application/octet-stream"
    key = f"review_media/{file.filename}"
    url = await upload_bytes(data, key, ct)
    return {"url": url}


# ──────────────────────────────────────────────────────
#  Channels
# ──────────────────────────────────────────────────────

@router.get("/channels")
async def list_channels() -> List[dict]:
    admins = await db.get_all_admins()
    return [
        {
            "admin_id":    a["id"],
            "title":       a.get("channel_title") or f"Канал {a['pseudonym']}",
            "description": a.get("channel_description"),
            "avatar_url":  a.get("channel_avatar_url"),
            "pseudonym":   a["pseudonym"],
            "is_online":   a["is_online"],
        }
        for a in admins
    ]


@router.get("/channels/{admin_id}/posts")
async def channel_posts(
    admin_id: int,
    limit: int = Query(20, le=50),
    offset: int = Query(0, ge=0),
) -> List[dict]:
    posts = await db.get_admin_posts(admin_id, limit, offset)
    result = []
    for p in posts:
        result.append({
            "id":         p["id"],
            "content":    p.get("content"),
            "media_urls": p.get("media_urls") or [],
            "views":      p["views"],
            "created_at": p["created_at"].isoformat(),
        })
        await db.increment_post_views(p["id"])
    return result


@router.post("/channels/{admin_id}/subscribe")
async def subscribe_channel(admin_id: int, user_id: int = Query(...)) -> dict:
    await db.subscribe(user_id, admin_id)
    return {"ok": True}


@router.delete("/channels/{admin_id}/subscribe")
async def unsubscribe_channel(admin_id: int, user_id: int = Query(...)) -> dict:
    await db.unsubscribe(user_id, admin_id)
    return {"ok": True}


@router.get("/channels/{admin_id}/subscribed")
async def check_subscribed(admin_id: int, user_id: int = Query(...)) -> dict:
    return {"subscribed": await db.is_subscribed(user_id, admin_id)}


# ──────────────────────────────────────────────────────
#  Admin panel (auth required)
# ──────────────────────────────────────────────────────

@router.get("/admin/me")
async def admin_me(admin: dict = Depends(get_current_admin)) -> dict:
    return {
        "id":                  admin["id"],
        "pseudonym":           admin["pseudonym"],
        "age":                 admin.get("age"),
        "characteristics":     admin.get("characteristics"),
        "hobbies":             admin.get("hobbies"),
        "description":         admin.get("description"),
        "channel_title":       admin.get("channel_title"),
        "channel_description": admin.get("channel_description"),
        "channel_avatar_url":  admin.get("channel_avatar_url"),
        "is_online":           admin["is_online"],
        "is_profile_filled":   admin["is_profile_filled"],
    }


@router.get("/admin/dialogs")
async def admin_dialogs(admin: dict = Depends(get_current_admin)) -> List[dict]:
    dialogs = await db.get_admin_active_dialogs(admin["id"])
    result = []
    for d in dialogs:
        result.append({
            "id":           d["id"],
            "status":       d["status"],
            "is_anonymous": d["is_anonymous"],
            "unread":       int(d.get("unread") or 0),
            "created_at":   d["created_at"].isoformat(),
        })
    return result


@router.get("/admin/dialogs/{dialog_id}/messages")
async def dialog_messages(
    dialog_id: int,
    admin: dict = Depends(get_current_admin),
) -> List[dict]:
    dialog = await db.get_dialog(dialog_id)
    if not dialog or dialog["admin_id"] != admin["id"]:
        raise HTTPException(403, "Access denied")
    await db.mark_messages_read(dialog_id, "admin")
    msgs = await db.get_dialog_messages(dialog_id)
    return [
        {
            "id":           m["id"],
            "sender_type":  m["sender_type"],
            "content":      m.get("content"),
            "media_url":    m.get("media_url"),
            "media_type":   m.get("media_type"),
            "is_read":      m["is_read"],
            "created_at":   m["created_at"].isoformat(),
        }
        for m in msgs
    ]


class UpdateChannelBody(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None


@router.patch("/admin/channel")
async def update_channel(
    body: UpdateChannelBody,
    admin: dict = Depends(get_current_admin),
) -> dict:
    kwargs: dict = {}
    if body.title:
        kwargs["channel_title"] = body.title[:200]
    if body.description:
        kwargs["channel_description"] = body.description[:500]
    if kwargs:
        await db.update_admin(admin["id"], **kwargs)
    return {"ok": True}


@router.post("/admin/channel/avatar")
async def update_channel_avatar(
    file: UploadFile = File(...),
    admin: dict = Depends(get_current_admin),
) -> dict:
    data = await file.read()
    ct = file.content_type or "image/jpeg"
    url = await upload_bytes(data, f"channel_avatars/{admin['id']}.jpg", ct)
    await db.update_admin(admin["id"], channel_avatar_url=url)
    return {"url": url}


class NewPostBody(BaseModel):
    content: Optional[str] = None
    media_urls: Optional[list] = None


@router.post("/admin/channel/posts")
async def create_post(
    body: NewPostBody,
    admin: dict = Depends(get_current_admin),
) -> dict:
    post = await db.create_channel_post(admin["id"], body.content, body.media_urls or [])
    return {"ok": True, "post_id": post["id"]}


@router.delete("/admin/channel/posts/{post_id}")
async def delete_post(
    post_id: int,
    admin: dict = Depends(get_current_admin),
) -> dict:
    await db.delete_channel_post(post_id, admin["id"])
    return {"ok": True}


@router.post("/admin/channel/posts/media")
async def upload_post_media(
    file: UploadFile = File(...),
    admin: dict = Depends(get_current_admin),
) -> dict:
    data = await file.read()
    ct = file.content_type or "application/octet-stream"
    key = f"channel_media/{admin['id']}_{file.filename}"
    url = await upload_bytes(data, key, ct)
    return {"url": url}


# ──────────────────────────────────────────────────────
#  Superadmin
# ──────────────────────────────────────────────────────

@router.get("/superadmin/stats")
async def superadmin_stats(admin: dict = Depends(get_current_superadmin)) -> dict:
    return await db.get_stats()


@router.get("/superadmin/users")
async def superadmin_users(
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    admin: dict = Depends(get_current_superadmin),
) -> List[dict]:
    users = await db.get_all_users()
    result = []
    for u in users[offset: offset + limit]:
        result.append({
            "telegram_id":  u["telegram_id"],
            "username":     u.get("username"),
            "pseudonym":    u.get("pseudonym"),
            "is_banned":    u["is_banned"],
            "warn_count":   u["warn_count"],
            "is_registered": u["is_registered"],
            "created_at":   u["created_at"].isoformat(),
        })
    return result


@router.get("/superadmin/dialogs")
async def superadmin_dialogs(
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    admin: dict = Depends(get_current_superadmin),
) -> List[dict]:
    dialogs = await db.get_all_dialogs(limit, offset)
    return [
        {
            "id":               d["id"],
            "status":           d["status"],
            "is_anonymous":     d["is_anonymous"],
            "admin_pseudonym":  d.get("admin_pseudonym"),
            "user_pseudonym":   d.get("user_pseudonym"),
            "created_at":       d["created_at"].isoformat(),
            "closed_at":        d["closed_at"].isoformat() if d.get("closed_at") else None,
        }
        for d in dialogs
    ]


@router.get("/superadmin/dialogs/{dialog_id}/messages")
async def superadmin_dialog_messages(
    dialog_id: int,
    admin: dict = Depends(get_current_superadmin),
) -> List[dict]:
    msgs = await db.get_dialog_messages(dialog_id, limit=500)
    return [
        {
            "id":           m["id"],
            "sender_type":  m["sender_type"],
            "content":      m.get("content"),
            "media_url":    m.get("media_url"),
            "media_type":   m.get("media_type"),
            "created_at":   m["created_at"].isoformat(),
        }
        for m in msgs
    ]


class BanBody(BaseModel):
    user_id: int
    reason: Optional[str] = None


@router.post("/superadmin/ban")
async def superadmin_ban(body: BanBody, admin: dict = Depends(get_current_superadmin)) -> dict:
    await db.ban_user(body.user_id, body.reason or "", admin["telegram_id"])
    return {"ok": True}


@router.post("/superadmin/unban")
async def superadmin_unban(body: BanBody, admin: dict = Depends(get_current_superadmin)) -> dict:
    await db.unban_user(body.user_id, admin["telegram_id"])
    return {"ok": True}


@router.post("/superadmin/warn")
async def superadmin_warn(body: BanBody, admin: dict = Depends(get_current_superadmin)) -> dict:
    warns = await db.warn_user(body.user_id, admin["telegram_id"])
    return {"ok": True, "warn_count": warns}


@router.get("/superadmin/admins")
async def superadmin_admins(admin: dict = Depends(get_current_superadmin)) -> List[dict]:
    admins = await db.get_all_admins()
    return [
        {
            "id":               a["id"],
            "telegram_id":      a["telegram_id"],
            "pseudonym":        a["pseudonym"],
            "username":         a.get("username"),
            "is_online":        a["is_online"],
            "is_profile_filled": a["is_profile_filled"],
            "avg_rating":       round(float(a.get("avg_rating") or 0), 2),
            "reviews_count":    int(a.get("reviews_count") or 0),
        }
        for a in admins
    ]
