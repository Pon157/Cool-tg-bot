"""
api/routes.py — REST API v3
Auth:
  POST /auth/tg      — вход через Telegram initData (приоритет)
  POST /auth/sa      — вход суперадмина по login+password из .env
  POST /auth/login   — вход администратора по pseudonym+password (запасной)
Balance:
  GET  /admin/balance
  POST /admin/withdraw
Withdrawals (superadmin):
  GET  /superadmin/withdrawals
  POST /superadmin/withdrawals/:id/approve
  POST /superadmin/withdrawals/:id/reject
Applications:
  POST /applications
  GET  /superadmin/applications
  POST /superadmin/applications/:id/approve
  POST /superadmin/applications/:id/reject
Norm settings:
  GET/PATCH /superadmin/norm/settings
  GET       /superadmin/norm/history
"""
from __future__ import annotations

import json
import logging
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel

import database as db
from config import settings
from services.s3_service import upload_bytes
from services.tg_auth import validate_init_data

logger = logging.getLogger(__name__)
router = APIRouter()
bearer = HTTPBearer(auto_error=False)
pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")

WU = settings.WEBAPP_URL.rstrip("/")


# ─── JWT ─────────────────────────────────────────────────────────────────────

def _make_token(payload: dict, hours: int = 168) -> str:
    data = {**payload, "exp": datetime.utcnow() + timedelta(hours=hours)}
    return jwt.encode(data, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)

def _decode_token(token: str) -> dict:
    return jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])

async def _get_token(cred: Optional[HTTPAuthorizationCredentials]) -> dict:
    exc = HTTPException(status_code=401, detail="Not authenticated")
    if not cred:
        raise exc
    try:
        return _decode_token(cred.credentials)
    except JWTError:
        raise exc

async def get_current_admin(
    cred: Optional[HTTPAuthorizationCredentials] = Depends(bearer),
) -> dict:
    payload = await _get_token(cred)
    admin_id = int(payload.get("sub", 0))
    if not admin_id:
        raise HTTPException(401, "Invalid token")
    admin = await db.get_admin_by_id(admin_id)
    if not admin:
        raise HTTPException(401, "Admin not found")
    return admin

async def get_current_superadmin(
    cred: Optional[HTTPAuthorizationCredentials] = Depends(bearer),
) -> dict:
    """Принимаем оба типа токенов: обычный admin + sa-токен суперадмина."""
    payload = await _get_token(cred)
    role = payload.get("role")
    tg_id = int(payload.get("tg_id", 0))

    if role == "superadmin":
        if tg_id not in settings.SUPERADMIN_IDS:
            raise HTTPException(403, "Superadmin only")
        # Возвращаем фиктивный словарь чтобы не ломать зависимости
        return {"id": 0, "telegram_id": tg_id, "pseudonym": "superadmin"}

    admin_id = int(payload.get("sub", 0))
    admin = await db.get_admin_by_id(admin_id)
    if not admin:
        raise HTTPException(401, "Not found")
    if admin["telegram_id"] not in settings.SUPERADMIN_IDS:
        raise HTTPException(403, "Superadmin only")
    return admin


# ─── AUTH ─────────────────────────────────────────────────────────────────────

class TgAuthRequest(BaseModel):
    init_data: str

@router.post("/auth/tg")
async def auth_via_telegram(body: TgAuthRequest) -> dict:
    """
    Основной вход для всех мини-приложений.
    Проверяет Telegram initData, возвращает JWT.
    Работает как для администраторов, так и для суперадминов.
    """
    user = validate_init_data(body.init_data, settings.BOT_TOKEN)
    if not user:
        raise HTTPException(401, "Invalid Telegram initData")

    tg_id = int(user.get("id", 0))
    if not tg_id:
        raise HTTPException(401, "No user id")

    is_sa = tg_id in settings.SUPERADMIN_IDS
    admin = await db.get_admin_by_tg(tg_id)

    if not admin and not is_sa:
        raise HTTPException(403, "Not an admin")

    if is_sa and not admin:
        # Суперадмин без записи в admins
        token = _make_token({"sub": "0", "tg_id": tg_id, "role": "superadmin"})
        return {
            "token": token,
            "user": {
                "id":           0,
                "pseudonym":    user.get("username") or "Суперадмин",
                "is_superadmin": True,
                "is_admin":     False,
                "telegram_id":  tg_id,
            },
        }

    await db.set_admin_online(tg_id, True)
    token = _make_token({"sub": str(admin["id"]), "tg_id": tg_id, "role": "admin"})
    return {
        "token": token,
        "user": {
            "id":           admin["id"],
            "pseudonym":    admin["pseudonym"],
            "is_superadmin": is_sa,
            "is_admin":     True,
            "telegram_id":  tg_id,
        },
    }


class SaLoginRequest(BaseModel):
    login: str
    password: str

@router.post("/auth/sa")
async def superadmin_login(body: SaLoginRequest) -> dict:
    """
    Вход суперадмина по логину/паролю из .env (SUPERADMIN_CREDENTIALS).
    Используется если суперадмин не является зарегистрированным администратором.
    """
    creds = settings.get_superadmin_credentials()
    if body.login not in creds or creds[body.login] != body.password:
        raise HTTPException(401, "Invalid credentials")
    # Ищем telegram_id по логину в admins или ставим 0
    admin = await db.get_admin_by_pseudonym(body.login)
    tg_id = admin["telegram_id"] if admin else 0
    token = _make_token({"sub": str(admin["id"]) if admin else "0",
                         "tg_id": tg_id, "role": "superadmin"})
    return {
        "token": token,
        "user": {
            "id":           admin["id"] if admin else 0,
            "pseudonym":    body.login,
            "is_superadmin": True,
            "is_admin":     admin is not None,
        },
    }


class LoginRequest(BaseModel):
    pseudonym: str
    password: str

@router.post("/auth/login")
async def admin_login(body: LoginRequest) -> dict:
    """Запасной вход администратора по паролю."""
    admin = await db.get_admin_by_pseudonym(body.pseudonym)
    if not admin or not pwd_ctx.verify(body.password, admin["password_hash"]):
        raise HTTPException(401, "Invalid credentials")
    await db.set_admin_online(admin["telegram_id"], True)
    is_sa = admin["telegram_id"] in settings.SUPERADMIN_IDS
    token = _make_token({"sub": str(admin["id"]), "tg_id": admin["telegram_id"], "role": "admin"})
    return {
        "token": token,
        "user": {"id": admin["id"], "pseudonym": admin["pseudonym"],
                 "is_superadmin": is_sa, "is_admin": True},
    }

@router.post("/auth/logout")
async def admin_logout(admin: dict = Depends(get_current_admin)) -> dict:
    await db.set_admin_online(admin["telegram_id"], False)
    return {"ok": True}


# ─── PUBLIC — ADMINS ──────────────────────────────────────────────────────────

def _pub_admin(a: dict) -> dict:
    return {
        "id":           a["id"],
        "pseudonym":    a["pseudonym"],
        "age":          a.get("age"),
        "description":  a.get("description"),
        "hobbies":      a.get("hobbies"),
        "avatar_url":   a.get("avatar_url"),
        "is_online":    a["is_online"],
        "is_on_rest":   a.get("is_on_rest", False),
        "last_seen":    a["last_seen"].isoformat() if a.get("last_seen") else None,
        "avg_rating":   round(float(a.get("avg_rating") or 0), 2),
        "reviews_count": int(a.get("reviews_count") or 0),
    }

@router.get("/admins")
async def list_admins() -> List[dict]:
    return [_pub_admin(a) for a in await db.get_all_admins()]

@router.get("/admins/{admin_id}")
async def get_admin_detail(admin_id: int) -> dict:
    a = await db.get_admin_by_id(admin_id)
    if not a:
        raise HTTPException(404, "Not found")
    return {
        "id":                  a["id"],
        "pseudonym":           a["pseudonym"],
        "age":                 a.get("age"),
        "description":         a.get("description"),
        "hobbies":             a.get("hobbies"),
        "characteristics":     a.get("characteristics"),
        "avatar_url":          a.get("avatar_url"),
        "channel_title":       a.get("channel_title"),
        "channel_description": a.get("channel_description"),
        "channel_avatar_url":  a.get("channel_avatar_url"),
        "is_online":           a["is_online"],
        "is_on_rest":          a.get("is_on_rest", False),
        "last_seen":           a["last_seen"].isoformat() if a.get("last_seen") else None,
    }


# ─── PUBLIC — REVIEWS ─────────────────────────────────────────────────────────

def _ser_review(r: dict) -> dict:
    media = r.get("media_urls") or []
    if isinstance(media, str):
        try: media = json.loads(media)
        except: media = []
    return {
        "id":              r["id"],
        "user_pseudonym":  r.get("user_pseudonym", "Аноним"),
        "admin_pseudonym": r.get("admin_pseudonym"),
        "text":            r.get("text"),
        "rating":          r["rating"],
        "media_urls":      media,
        "created_at":      r["created_at"].isoformat(),
    }

@router.get("/reviews")
async def all_reviews(limit: int = Query(50, le=100)) -> List[dict]:
    return [_ser_review(r) for r in await db.get_all_reviews(limit)]

@router.get("/reviews/admin/{admin_id}")
async def admin_reviews(admin_id: int) -> List[dict]:
    return [_ser_review(r) for r in await db.get_admin_reviews(admin_id)]

@router.get("/reviews/user/{user_id}")
async def user_reviews(user_id: int) -> List[dict]:
    return [_ser_review(r) for r in await db.get_user_reviews(user_id)]

class ReviewBody(BaseModel):
    user_id: int
    admin_id: int
    dialog_id: int
    text: Optional[str] = None
    rating: int

@router.post("/reviews")
async def create_review(body: ReviewBody) -> dict:
    if not await db.user_had_dialog_with_admin(body.user_id, body.admin_id):
        raise HTTPException(403, "No completed dialog with this admin")
    r = await db.upsert_review(body.user_id, body.admin_id, body.dialog_id,
                                body.text or "", body.rating, [])
    return {"ok": True, "review_id": r["id"]}

@router.post("/reviews/media")
async def upload_review_media(file: UploadFile = File(...)) -> dict:
    data = await file.read()
    url = await upload_bytes(data, f"review_media/{file.filename}",
                             file.content_type or "application/octet-stream")
    return {"url": url}


# ─── PUBLIC — CHANNELS ────────────────────────────────────────────────────────

@router.get("/channels")
async def list_channels() -> List[dict]:
    return [
        {
            "admin_id":    a["id"],
            "title":       a.get("channel_title") or f"Канал {a['pseudonym']}",
            "description": a.get("channel_description"),
            "avatar_url":  a.get("channel_avatar_url"),
            "pseudonym":   a["pseudonym"],
            "is_online":   a["is_online"],
        }
        for a in await db.get_all_admins()
    ]

def _ser_media(raw) -> list:
    if not raw:
        return []
    if isinstance(raw, str):
        try: raw = json.loads(raw)
        except: return []
    return raw

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
            "media_urls": _ser_media(p.get("media_urls")),
            "views":      p["views"],
            "created_at": p["created_at"].isoformat(),
        })
        await db.increment_post_views(p["id"])
    return result

@router.post("/channels/{admin_id}/subscribe")
async def subscribe_channel(admin_id: int, user_id: int = Query(...)) -> dict:
    await db.subscribe(user_id, admin_id); return {"ok": True}

@router.delete("/channels/{admin_id}/subscribe")
async def unsubscribe_channel(admin_id: int, user_id: int = Query(...)) -> dict:
    await db.unsubscribe(user_id, admin_id); return {"ok": True}

@router.get("/channels/{admin_id}/subscribed")
async def check_subscribed(admin_id: int, user_id: int = Query(...)) -> dict:
    return {"subscribed": await db.is_subscribed(user_id, admin_id)}


# ─── ADMIN PANEL ─────────────────────────────────────────────────────────────

def _ser_msg(m: dict) -> dict:
    return {
        "id":          m["id"],
        "sender_type": m["sender_type"],
        "content":     m.get("content"),
        "media_url":   m.get("media_url"),
        "media_type":  m.get("media_type"),
        "is_read":     m["is_read"],
        "created_at":  m["created_at"].isoformat(),
    }

@router.get("/admin/me")
async def admin_me(admin: dict = Depends(get_current_admin)) -> dict:
    return {
        "id":                  admin["id"],
        "pseudonym":           admin["pseudonym"],
        "telegram_id":         admin["telegram_id"],
        "age":                 admin.get("age"),
        "characteristics":     admin.get("characteristics"),
        "hobbies":             admin.get("hobbies"),
        "description":         admin.get("description"),
        "channel_title":       admin.get("channel_title"),
        "channel_description": admin.get("channel_description"),
        "channel_avatar_url":  admin.get("channel_avatar_url"),
        "is_online":           admin["is_online"],
        "is_profile_filled":   admin["is_profile_filled"],
        "is_on_rest":          admin.get("is_on_rest", False),
        "rest_until":          str(admin["rest_until"]) if admin.get("rest_until") else None,
        "weekly_dialogs":      admin.get("weekly_dialogs", 0),
        "balance_messages":    admin.get("balance_messages", 0),
        "balance_rub":         float(admin.get("balance_rub") or 0),
    }

@router.get("/admin/dialogs")
async def admin_dialogs(admin: dict = Depends(get_current_admin)) -> List[dict]:
    return [
        {
            "id":           d["id"],
            "status":       d["status"],
            "is_anonymous": d["is_anonymous"],
            "unread":       int(d.get("unread") or 0),
            "created_at":   d["created_at"].isoformat(),
        }
        for d in await db.get_admin_active_dialogs(admin["id"])
    ]

@router.get("/admin/dialogs/{dialog_id}/messages")
async def dialog_messages(dialog_id: int, admin: dict = Depends(get_current_admin)) -> List[dict]:
    dialog = await db.get_dialog(dialog_id)
    if not dialog or dialog["admin_id"] != admin["id"]:
        raise HTTPException(403, "Access denied")
    await db.mark_messages_read(dialog_id, "admin")
    return [_ser_msg(m) for m in await db.get_dialog_messages(dialog_id)]

class UpdateChannelBody(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None

@router.patch("/admin/channel")
async def update_channel(body: UpdateChannelBody, admin: dict = Depends(get_current_admin)) -> dict:
    kw: dict = {}
    if body.title is not None:       kw["channel_title"]       = body.title[:200]
    if body.description is not None: kw["channel_description"] = body.description[:500]
    if kw: await db.update_admin(admin["id"], **kw)
    return {"ok": True}

@router.post("/admin/channel/avatar")
async def update_channel_avatar(file: UploadFile = File(...), admin: dict = Depends(get_current_admin)) -> dict:
    data = await file.read()
    url = await upload_bytes(data, f"channel_avatars/{admin['id']}.jpg",
                             file.content_type or "image/jpeg")
    await db.update_admin(admin["id"], channel_avatar_url=url)
    return {"url": url}

class NewPostBody(BaseModel):
    content: Optional[str] = None
    media_urls: Optional[list] = None

@router.post("/admin/channel/posts")
async def create_post(body: NewPostBody, admin: dict = Depends(get_current_admin)) -> dict:
    post = await db.create_channel_post(admin["id"], body.content, body.media_urls or [])
    return {"ok": True, "post_id": post["id"]}

@router.delete("/admin/channel/posts/{post_id}")
async def delete_post(post_id: int, admin: dict = Depends(get_current_admin)) -> dict:
    await db.delete_channel_post(post_id, admin["id"]); return {"ok": True}

@router.post("/admin/channel/posts/media")
async def upload_post_media(file: UploadFile = File(...), admin: dict = Depends(get_current_admin)) -> dict:
    data = await file.read()
    url = await upload_bytes(data, f"channel_media/{admin['id']}_{file.filename}",
                             file.content_type or "application/octet-stream")
    return {"url": url}


# ─── ADMIN BALANCE ────────────────────────────────────────────────────────────

@router.get("/admin/balance")
async def admin_balance(admin: dict = Depends(get_current_admin)) -> dict:
    rate = float(await db.get_setting("message_rate", str(settings.MESSAGE_RATE)))
    return {
        "balance_messages": admin.get("balance_messages", 0),
        "balance_rub":      float(admin.get("balance_rub") or 0),
        "message_rate":     rate,
    }

class WithdrawBody(BaseModel):
    amount_rub: float
    details: str      # реквизиты (номер карты, кошелёк, телефон и тп)

@router.post("/admin/withdraw")
async def request_withdrawal(body: WithdrawBody, admin: dict = Depends(get_current_admin)) -> dict:
    balance = float(admin.get("balance_rub") or 0)
    if body.amount_rub <= 0:
        raise HTTPException(400, "Amount must be positive")
    if body.amount_rub > balance:
        raise HTTPException(400, f"Insufficient balance: {balance:.2f} RUB")
    if not body.details.strip():
        raise HTTPException(400, "Payment details required")
    # Проверяем нет ли уже pending-заявки
    existing = await db.get_withdrawals(status="pending", admin_id=admin["id"])
    if existing:
        raise HTTPException(400, "You already have a pending withdrawal request")
    w = await db.create_withdrawal(admin["id"], body.amount_rub, body.details.strip())
    return {"ok": True, "withdrawal_id": w["id"]}

@router.get("/admin/withdrawals")
async def admin_withdrawals(admin: dict = Depends(get_current_admin)) -> List[dict]:
    return [_ser_w(w) for w in await db.get_withdrawals(admin_id=admin["id"])]

def _ser_w(w: dict) -> dict:
    return {
        "id":          w["id"],
        "amount_rub":  float(w["amount_rub"]),
        "details":     w["details"],
        "status":      w["status"],
        "comment":     w.get("comment"),
        "created_at":  w["created_at"].isoformat(),
        "reviewed_at": w["reviewed_at"].isoformat() if w.get("reviewed_at") else None,
        "admin_pseudonym": w.get("admin_pseudonym"),
    }


# ─── APPLICATIONS ─────────────────────────────────────────────────────────────

class ApplicationBody(BaseModel):
    telegram_id: int
    username: Optional[str] = None
    age: str
    characteristics: str
    hobbies: str
    test_answers: list
    detailed_answers: list

@router.post("/applications")
async def submit_application(body: ApplicationBody) -> dict:
    app = await db.create_application(
        body.telegram_id, body.username, body.age,
        body.characteristics, body.hobbies,
        body.test_answers, body.detailed_answers,
    )
    return {"ok": True, "application_id": app["id"]}

def _ser_app(a: dict) -> dict:
    def _j(v):
        if isinstance(v, str):
            try: return json.loads(v)
            except: return []
        return v or []
    return {
        "id":               a["id"],
        "telegram_id":      a["telegram_id"],
        "username":         a.get("username"),
        "age":              a.get("age"),
        "characteristics":  a.get("characteristics"),
        "hobbies":          a.get("hobbies"),
        "test_answers":     _j(a.get("test_answers")),
        "detailed_answers": _j(a.get("detailed_answers")),
        "status":           a["status"],
        "created_at":       a["created_at"].isoformat(),
    }


# ─── SUPERADMIN ───────────────────────────────────────────────────────────────

@router.get("/superadmin/stats")
async def superadmin_stats(sa: dict = Depends(get_current_superadmin)) -> dict:
    return await db.get_stats()

@router.get("/superadmin/users")
async def superadmin_users(
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    sa: dict = Depends(get_current_superadmin),
) -> List[dict]:
    users = await db.get_all_users()
    return [
        {
            "telegram_id":   u["telegram_id"],
            "username":      u.get("username"),
            "pseudonym":     u.get("pseudonym"),
            "is_banned":     u["is_banned"],
            "warn_count":    u["warn_count"],
            "is_registered": u["is_registered"],
            "created_at":    u["created_at"].isoformat(),
        }
        for u in users[offset: offset + limit]
    ]

@router.get("/superadmin/dialogs")
async def superadmin_dialogs(
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    sa: dict = Depends(get_current_superadmin),
) -> List[dict]:
    return [
        {
            "id":              d["id"],
            "status":          d["status"],
            "is_anonymous":    d["is_anonymous"],
            "admin_pseudonym": d.get("admin_pseudonym"),
            "user_pseudonym":  d.get("user_pseudonym"),
            "created_at":      d["created_at"].isoformat(),
            "closed_at":       d["closed_at"].isoformat() if d.get("closed_at") else None,
        }
        for d in await db.get_all_dialogs(limit, offset)
    ]

@router.get("/superadmin/dialogs/{dialog_id}/messages")
async def superadmin_dialog_messages(dialog_id: int, sa: dict = Depends(get_current_superadmin)) -> List[dict]:
    return [_ser_msg(m) for m in await db.get_dialog_messages(dialog_id, limit=500)]

class BanBody(BaseModel):
    user_id: int
    reason: Optional[str] = None

@router.post("/superadmin/ban")
async def superadmin_ban(body: BanBody, sa: dict = Depends(get_current_superadmin)) -> dict:
    await db.ban_user(body.user_id, body.reason or "", sa["telegram_id"]); return {"ok": True}

@router.post("/superadmin/unban")
async def superadmin_unban(body: BanBody, sa: dict = Depends(get_current_superadmin)) -> dict:
    await db.unban_user(body.user_id, sa["telegram_id"]); return {"ok": True}

@router.post("/superadmin/warn")
async def superadmin_warn(body: BanBody, sa: dict = Depends(get_current_superadmin)) -> dict:
    warns = await db.warn_user(body.user_id, sa["telegram_id"])
    return {"ok": True, "warn_count": warns}

@router.get("/superadmin/admins")
async def superadmin_admins(sa: dict = Depends(get_current_superadmin)) -> List[dict]:
    return [
        {
            "id":                a["id"],
            "telegram_id":       a["telegram_id"],
            "pseudonym":         a["pseudonym"],
            "username":          a.get("username"),
            "is_online":         a["is_online"],
            "is_profile_filled": a["is_profile_filled"],
            "is_on_rest":        a.get("is_on_rest", False),
            "rest_until":        str(a["rest_until"]) if a.get("rest_until") else None,
            "weekly_dialogs":    a.get("weekly_dialogs", 0),
            "avg_rating":        round(float(a.get("avg_rating") or 0), 2),
            "reviews_count":     int(a.get("reviews_count") or 0),
            "balance_messages":  a.get("balance_messages", 0),
            "balance_rub":       float(a.get("balance_rub") or 0),
        }
        for a in await db.get_all_admins()
    ]

class RestBody(BaseModel):
    is_on_rest: bool
    rest_until: Optional[str] = None

@router.post("/superadmin/admins/{admin_id}/rest")
async def toggle_admin_rest(admin_id: int, body: RestBody, sa: dict = Depends(get_current_superadmin)) -> dict:
    rest_until = None
    if body.rest_until:
        try: rest_until = date.fromisoformat(body.rest_until)
        except ValueError: raise HTTPException(400, "Invalid date")
    await db.set_admin_rest(admin_id, body.is_on_rest, rest_until)
    return {"ok": True}

# Withdrawals (superadmin)
@router.get("/superadmin/withdrawals")
async def sa_withdrawals(
    status: Optional[str] = Query(None),
    sa: dict = Depends(get_current_superadmin),
) -> List[dict]:
    return [_ser_w(w) for w in await db.get_withdrawals(status=status)]

class ReviewWithdrawBody(BaseModel):
    comment: Optional[str] = None

@router.post("/superadmin/withdrawals/{wid}/approve")
async def sa_approve_withdrawal(wid: int, sa: dict = Depends(get_current_superadmin)) -> dict:
    w = await db.review_withdrawal(wid, "approved", sa["telegram_id"])
    if not w:
        raise HTTPException(404, "Not found")
    # Списываем баланс
    ok = await db.deduct_admin_balance(w["admin_id"], float(w["amount_rub"]))
    if not ok:
        # Если баланс уже не сходится — всё равно помечаем одобренной, суперадмин разберётся
        logger.warning("deduct_admin_balance failed for withdrawal %s", wid)
    return {"ok": True}

@router.post("/superadmin/withdrawals/{wid}/reject")
async def sa_reject_withdrawal(wid: int, body: ReviewWithdrawBody, sa: dict = Depends(get_current_superadmin)) -> dict:
    w = await db.review_withdrawal(wid, "rejected", sa["telegram_id"], body.comment)
    if not w:
        raise HTTPException(404, "Not found")
    return {"ok": True}

# Applications
@router.get("/superadmin/applications")
async def sa_applications(sa: dict = Depends(get_current_superadmin)) -> List[dict]:
    return [_ser_app(a) for a in await db.get_pending_applications()]

@router.post("/superadmin/applications/{app_id}/approve")
async def sa_approve_app(app_id: int, sa: dict = Depends(get_current_superadmin)) -> dict:
    a = await db.update_application_status(app_id, "approved")
    if not a: raise HTTPException(404, "Not found")
    return {"ok": True}

@router.post("/superadmin/applications/{app_id}/reject")
async def sa_reject_app(app_id: int, sa: dict = Depends(get_current_superadmin)) -> dict:
    a = await db.update_application_status(app_id, "rejected")
    if not a: raise HTTPException(404, "Not found")
    return {"ok": True}

# Norm
@router.get("/superadmin/norm/settings")
async def get_norm_settings(sa: dict = Depends(get_current_superadmin)) -> dict:
    return await db.get_all_settings()

class NormSettingsBody(BaseModel):
    weekly_norm:        Optional[int]   = None
    norm_check_weekday: Optional[int]   = None
    norm_check_hour:    Optional[int]   = None
    norm_enabled:       Optional[bool]  = None
    message_rate:       Optional[float] = None

@router.patch("/superadmin/norm/settings")
async def update_norm_settings(body: NormSettingsBody, sa: dict = Depends(get_current_superadmin)) -> dict:
    if body.weekly_norm        is not None: await db.set_setting("weekly_norm",        str(body.weekly_norm))
    if body.norm_check_weekday is not None: await db.set_setting("norm_check_weekday", str(body.norm_check_weekday))
    if body.norm_check_hour    is not None: await db.set_setting("norm_check_hour",    str(body.norm_check_hour))
    if body.norm_enabled       is not None: await db.set_setting("norm_enabled",       "true" if body.norm_enabled else "false")
    if body.message_rate       is not None: await db.set_setting("message_rate",       str(body.message_rate))
    return {"ok": True}

@router.get("/superadmin/norm/history")
async def norm_history(sa: dict = Depends(get_current_superadmin)) -> List[dict]:
    logs = await db.get_last_norm_checks(10)
    result = []
    for l in logs:
        details = l.get("details") or []
        if isinstance(details, str):
            try: details = json.loads(details)
            except: details = []
        result.append({
            "checked_at":  l["checked_at"].isoformat(),
            "norm_value":  l["norm_value"],
            "fired_count": l["fired_count"],
            "details":     details,
        })
    return result
