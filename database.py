"""
database.py — Полный слой доступа к БД через asyncpg.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

import asyncpg

pool: asyncpg.Pool = None  # type: ignore


# ─────────────────────────────────────────────
# INIT
# ─────────────────────────────────────────────

async def init_pool(dsn: str) -> None:
    global pool
    pool = await asyncpg.create_pool(dsn, min_size=5, max_size=20)
    await _run_migrations()


async def _run_migrations() -> None:
    with open("migrations/schema.sql", "r", encoding="utf-8") as f:
        sql = f.read()
    async with pool.acquire() as conn:
        await conn.execute(sql)


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

def _row(r: Optional[asyncpg.Record]) -> Optional[Dict[str, Any]]:
    return dict(r) if r else None


def _rows(rs: List[asyncpg.Record]) -> List[Dict[str, Any]]:
    return [dict(r) for r in rs]


# ─────────────────────────────────────────────
# USERS
# ─────────────────────────────────────────────

async def get_user(telegram_id: int) -> Optional[Dict]:
    async with pool.acquire() as c:
        return _row(await c.fetchrow("SELECT * FROM users WHERE telegram_id=$1", telegram_id))


async def upsert_user(telegram_id: int, username: Optional[str] = None) -> Dict:
    async with pool.acquire() as c:
        r = await c.fetchrow(
            """INSERT INTO users (telegram_id, username)
               VALUES ($1, $2)
               ON CONFLICT (telegram_id) DO UPDATE SET username = EXCLUDED.username
               RETURNING *""",
            telegram_id, username,
        )
        return dict(r)


async def update_user(telegram_id: int, **kwargs) -> Optional[Dict]:
    if not kwargs:
        return await get_user(telegram_id)
    cols = ", ".join(f"{k}=${i+2}" for i, k in enumerate(kwargs))
    cols += ", updated_at=NOW()"
    sql = f"UPDATE users SET {cols} WHERE telegram_id=$1 RETURNING *"
    async with pool.acquire() as c:
        return _row(await c.fetchrow(sql, telegram_id, *kwargs.values()))


async def get_all_users() -> List[Dict]:
    async with pool.acquire() as c:
        return _rows(await c.fetch("SELECT * FROM users ORDER BY created_at DESC"))


async def get_active_users() -> List[Dict]:
    async with pool.acquire() as c:
        return _rows(await c.fetch("SELECT * FROM users WHERE is_banned=FALSE AND is_registered=TRUE"))


async def ban_user(telegram_id: int, reason: str, issued_by: int) -> None:
    async with pool.acquire() as c:
        await c.execute("UPDATE users SET is_banned=TRUE WHERE telegram_id=$1", telegram_id)
        await c.execute(
            "INSERT INTO bans_log(user_id,action,reason,issued_by) VALUES($1,'ban',$2,$3)",
            telegram_id, reason, issued_by,
        )


async def unban_user(telegram_id: int, issued_by: int) -> None:
    async with pool.acquire() as c:
        await c.execute("UPDATE users SET is_banned=FALSE WHERE telegram_id=$1", telegram_id)
        await c.execute(
            "INSERT INTO bans_log(user_id,action,issued_by) VALUES($1,'unban',$2)",
            telegram_id, issued_by,
        )


async def warn_user(telegram_id: int, issued_by: int) -> int:
    async with pool.acquire() as c:
        r = await c.fetchrow(
            "UPDATE users SET warn_count=warn_count+1 WHERE telegram_id=$1 RETURNING warn_count",
            telegram_id,
        )
        await c.execute(
            "INSERT INTO bans_log(user_id,action,issued_by) VALUES($1,'warn',$2)",
            telegram_id, issued_by,
        )
        return r["warn_count"] if r else 0


async def unwarn_user(telegram_id: int, issued_by: int) -> int:
    async with pool.acquire() as c:
        r = await c.fetchrow(
            "UPDATE users SET warn_count=GREATEST(warn_count-1,0) WHERE telegram_id=$1 RETURNING warn_count",
            telegram_id,
        )
        await c.execute(
            "INSERT INTO bans_log(user_id,action,issued_by) VALUES($1,'unwarn',$2)",
            telegram_id, issued_by,
        )
        return r["warn_count"] if r else 0


# ─────────────────────────────────────────────
# ADMINS
# ─────────────────────────────────────────────

async def get_admin_by_tg(telegram_id: int) -> Optional[Dict]:
    async with pool.acquire() as c:
        return _row(await c.fetchrow("SELECT * FROM admins WHERE telegram_id=$1", telegram_id))


async def get_admin_by_id(admin_id: int) -> Optional[Dict]:
    async with pool.acquire() as c:
        return _row(await c.fetchrow("SELECT * FROM admins WHERE id=$1", admin_id))


async def get_admin_by_pseudonym(pseudonym: str) -> Optional[Dict]:
    async with pool.acquire() as c:
        return _row(await c.fetchrow("SELECT * FROM admins WHERE pseudonym=$1", pseudonym))


async def get_all_admins() -> List[Dict]:
    async with pool.acquire() as c:
        return _rows(await c.fetch(
            """SELECT a.*,
                      COALESCE(AVG(r.rating),0)::FLOAT as avg_rating,
                      COUNT(DISTINCT r.id) as reviews_count
               FROM admins a
               LEFT JOIN reviews r ON r.admin_id = a.id
               GROUP BY a.id
               ORDER BY a.is_online DESC, a.pseudonym"""
        ))


async def create_admin(telegram_id: int, username: str, pseudonym: str, password_hash: str) -> Dict:
    async with pool.acquire() as c:
        r = await c.fetchrow(
            """INSERT INTO admins (telegram_id, username, pseudonym, password_hash, channel_title)
               VALUES ($1,$2,$3,$4,$5) RETURNING *""",
            telegram_id, username, pseudonym, password_hash,
            f"Канал {pseudonym}",
        )
        return dict(r)


async def update_admin(admin_id: int, **kwargs) -> Optional[Dict]:
    if not kwargs:
        return await get_admin_by_id(admin_id)
    cols = ", ".join(f"{k}=${i+2}" for i, k in enumerate(kwargs))
    sql = f"UPDATE admins SET {cols} WHERE id=$1 RETURNING *"
    async with pool.acquire() as c:
        return _row(await c.fetchrow(sql, admin_id, *kwargs.values()))


async def delete_admin(admin_id: int) -> None:
    async with pool.acquire() as c:
        await c.execute("DELETE FROM admins WHERE id=$1", admin_id)


async def set_admin_online(telegram_id: int, is_online: bool) -> None:
    async with pool.acquire() as c:
        await c.execute(
            "UPDATE admins SET is_online=$1, last_seen=NOW() WHERE telegram_id=$2",
            is_online, telegram_id,
        )


# ─────────────────────────────────────────────
# DIALOGS
# ─────────────────────────────────────────────

async def create_dialog(user_id: int, admin_id: Optional[int], is_anonymous: bool) -> Dict:
    async with pool.acquire() as c:
        r = await c.fetchrow(
            """INSERT INTO dialogs (user_id, admin_id, is_anonymous, status)
               VALUES ($1,$2,$3,'pending') RETURNING *""",
            user_id, admin_id, is_anonymous,
        )
        return dict(r)


async def get_dialog(dialog_id: int) -> Optional[Dict]:
    async with pool.acquire() as c:
        return _row(await c.fetchrow("SELECT * FROM dialogs WHERE id=$1", dialog_id))


async def get_active_dialog_by_user(user_id: int) -> Optional[Dict]:
    async with pool.acquire() as c:
        return _row(await c.fetchrow(
            "SELECT * FROM dialogs WHERE user_id=$1 AND status IN ('pending','active') ORDER BY created_at DESC LIMIT 1",
            user_id,
        ))


async def get_admin_active_dialogs(admin_id: int) -> List[Dict]:
    async with pool.acquire() as c:
        return _rows(await c.fetch(
            """SELECT d.*,
                      COUNT(m.id) FILTER (WHERE m.is_read=FALSE AND m.sender_type='user') AS unread
               FROM dialogs d
               LEFT JOIN messages m ON m.dialog_id=d.id
               WHERE d.admin_id=$1 AND d.status='active'
               GROUP BY d.id
               ORDER BY d.created_at DESC""",
            admin_id,
        ))


async def get_all_dialogs(limit: int = 50, offset: int = 0) -> List[Dict]:
    """For superadmin moderation view"""
    async with pool.acquire() as c:
        return _rows(await c.fetch(
            """SELECT d.*, a.pseudonym as admin_pseudonym, u.pseudonym as user_pseudonym
               FROM dialogs d
               LEFT JOIN admins a ON d.admin_id=a.id
               LEFT JOIN users u ON d.user_id=u.telegram_id
               ORDER BY d.created_at DESC LIMIT $1 OFFSET $2""",
            limit, offset,
        ))


async def accept_dialog(dialog_id: int, admin_id: int) -> bool:
    async with pool.acquire() as c:
        existing = await c.fetchrow(
            "SELECT status FROM dialogs WHERE id=$1", dialog_id
        )
        if not existing or existing["status"] != "pending":
            return False
        await c.execute(
            "UPDATE dialogs SET status='active', admin_id=$1 WHERE id=$2",
            admin_id, dialog_id,
        )
        return True


async def close_dialog(dialog_id: int) -> None:
    async with pool.acquire() as c:
        await c.execute(
            "UPDATE dialogs SET status='closed', closed_at=NOW() WHERE id=$1", dialog_id
        )


async def update_dialog_group_msg(dialog_id: int, message_id: int) -> None:
    async with pool.acquire() as c:
        await c.execute(
            "UPDATE dialogs SET group_message_id=$1 WHERE id=$2", message_id, dialog_id
        )


async def user_had_dialog_with_admin(user_id: int, admin_id: int) -> bool:
    async with pool.acquire() as c:
        r = await c.fetchrow(
            "SELECT id FROM dialogs WHERE user_id=$1 AND admin_id=$2 AND status='closed' LIMIT 1",
            user_id, admin_id,
        )
        return r is not None


async def get_user_closed_dialogs(user_id: int) -> List[Dict]:
    """Returns closed dialogs with admin info for review eligibility"""
    async with pool.acquire() as c:
        return _rows(await c.fetch(
            """SELECT d.id, d.admin_id, d.closed_at, a.pseudonym as admin_pseudonym
               FROM dialogs d
               JOIN admins a ON d.admin_id=a.id
               WHERE d.user_id=$1 AND d.status='closed'
               ORDER BY d.closed_at DESC""",
            user_id,
        ))


# ─────────────────────────────────────────────
# MESSAGES
# ─────────────────────────────────────────────

async def save_message(
    dialog_id: int,
    sender_type: str,
    content: Optional[str] = None,
    media_url: Optional[str] = None,
    media_type: Optional[str] = None,
    telegram_message_id: Optional[int] = None,
) -> Dict:
    async with pool.acquire() as c:
        r = await c.fetchrow(
            """INSERT INTO messages (dialog_id, sender_type, content, media_url, media_type, telegram_message_id)
               VALUES ($1,$2,$3,$4,$5,$6) RETURNING *""",
            dialog_id, sender_type, content, media_url, media_type, telegram_message_id,
        )
        return dict(r)


async def get_dialog_messages(dialog_id: int, limit: int = 100) -> List[Dict]:
    async with pool.acquire() as c:
        return _rows(await c.fetch(
            "SELECT * FROM messages WHERE dialog_id=$1 ORDER BY created_at ASC LIMIT $2",
            dialog_id, limit,
        ))


async def get_dialog_text_for_ai(dialog_id: int) -> str:
    async with pool.acquire() as c:
        rows = await c.fetch(
            "SELECT sender_type, content FROM messages WHERE dialog_id=$1 AND content IS NOT NULL ORDER BY created_at",
            dialog_id,
        )
        return "\n".join(f"[{r['sender_type']}]: {r['content']}" for r in rows)


async def mark_messages_read(dialog_id: int, reader: str) -> None:
    sender = "user" if reader == "admin" else "admin"
    async with pool.acquire() as c:
        await c.execute(
            "UPDATE messages SET is_read=TRUE WHERE dialog_id=$1 AND sender_type=$2",
            dialog_id, sender,
        )


# ─────────────────────────────────────────────
# REVIEWS
# ─────────────────────────────────────────────

async def upsert_review(
    user_id: int, admin_id: int, dialog_id: int,
    text: str, rating: int, media_urls: Optional[list] = None,
) -> Dict:
    async with pool.acquire() as c:
        r = await c.fetchrow(
            """INSERT INTO reviews (user_id, admin_id, dialog_id, text, rating, media_urls)
               VALUES ($1,$2,$3,$4,$5,$6)
               ON CONFLICT (user_id, dialog_id) DO UPDATE
               SET text=$4, rating=$5, media_urls=$6, updated_at=NOW()
               RETURNING *""",
            user_id, admin_id, dialog_id, text, rating,
            json.dumps(media_urls or []),
        )
        return dict(r)


async def get_admin_reviews(admin_id: int) -> List[Dict]:
    async with pool.acquire() as c:
        return _rows(await c.fetch(
            """SELECT r.*, u.pseudonym AS user_pseudonym
               FROM reviews r JOIN users u ON r.user_id=u.telegram_id
               WHERE r.admin_id=$1 ORDER BY r.created_at DESC""",
            admin_id,
        ))


async def get_user_reviews(user_id: int) -> List[Dict]:
    async with pool.acquire() as c:
        return _rows(await c.fetch(
            """SELECT r.*, a.pseudonym AS admin_pseudonym
               FROM reviews r JOIN admins a ON r.admin_id=a.id
               WHERE r.user_id=$1 ORDER BY r.created_at DESC""",
            user_id,
        ))


async def get_all_reviews(limit: int = 50) -> List[Dict]:
    async with pool.acquire() as c:
        return _rows(await c.fetch(
            """SELECT r.*, a.pseudonym AS admin_pseudonym, u.pseudonym AS user_pseudonym
               FROM reviews r
               JOIN admins a ON r.admin_id=a.id
               JOIN users u ON r.user_id=u.telegram_id
               ORDER BY r.created_at DESC LIMIT $1""",
            limit,
        ))


# ─────────────────────────────────────────────
# CHANNEL POSTS
# ─────────────────────────────────────────────

async def create_channel_post(admin_id: int, content: Optional[str], media_urls: Optional[list] = None) -> Dict:
    async with pool.acquire() as c:
        r = await c.fetchrow(
            "INSERT INTO channel_posts (admin_id, content, media_urls) VALUES ($1,$2,$3) RETURNING *",
            admin_id, content, json.dumps(media_urls or []),
        )
        return dict(r)


async def get_admin_posts(admin_id: int, limit: int = 20, offset: int = 0) -> List[Dict]:
    async with pool.acquire() as c:
        return _rows(await c.fetch(
            "SELECT * FROM channel_posts WHERE admin_id=$1 ORDER BY created_at DESC LIMIT $2 OFFSET $3",
            admin_id, limit, offset,
        ))


async def delete_channel_post(post_id: int, admin_id: int) -> None:
    async with pool.acquire() as c:
        await c.execute("DELETE FROM channel_posts WHERE id=$1 AND admin_id=$2", post_id, admin_id)


async def increment_post_views(post_id: int) -> None:
    async with pool.acquire() as c:
        await c.execute("UPDATE channel_posts SET views=views+1 WHERE id=$1", post_id)


# ─────────────────────────────────────────────
# SUBSCRIPTIONS
# ─────────────────────────────────────────────

async def subscribe(user_id: int, admin_id: int) -> None:
    async with pool.acquire() as c:
        await c.execute(
            "INSERT INTO channel_subscriptions (user_id, admin_id) VALUES ($1,$2) ON CONFLICT DO NOTHING",
            user_id, admin_id,
        )


async def unsubscribe(user_id: int, admin_id: int) -> None:
    async with pool.acquire() as c:
        await c.execute(
            "DELETE FROM channel_subscriptions WHERE user_id=$1 AND admin_id=$2",
            user_id, admin_id,
        )


async def is_subscribed(user_id: int, admin_id: int) -> bool:
    async with pool.acquire() as c:
        r = await c.fetchrow(
            "SELECT 1 FROM channel_subscriptions WHERE user_id=$1 AND admin_id=$2",
            user_id, admin_id,
        )
        return r is not None


async def get_admin_subscribers(admin_id: int) -> List[int]:
    async with pool.acquire() as c:
        rows = await c.fetch(
            "SELECT user_id FROM channel_subscriptions WHERE admin_id=$1", admin_id
        )
        return [r["user_id"] for r in rows]


async def get_user_subscriptions(user_id: int) -> List[int]:
    async with pool.acquire() as c:
        rows = await c.fetch(
            "SELECT admin_id FROM channel_subscriptions WHERE user_id=$1", user_id
        )
        return [r["admin_id"] for r in rows]


# ─────────────────────────────────────────────
# AI RECOMMENDATIONS
# ─────────────────────────────────────────────

async def save_recommendation(user_id: int, dialog_id: int, recommendation: str,
                               keywords: list, emotional_tone: str = "") -> Dict:
    async with pool.acquire() as c:
        r = await c.fetchrow(
            """INSERT INTO ai_recommendations (user_id, dialog_id, recommendation, keywords, emotional_tone)
               VALUES ($1,$2,$3,$4,$5) RETURNING *""",
            user_id, dialog_id, recommendation,
            json.dumps(keywords), emotional_tone,
        )
        return dict(r)


async def get_user_recommendations(user_id: int, limit: int = 10) -> List[Dict]:
    async with pool.acquire() as c:
        return _rows(await c.fetch(
            "SELECT * FROM ai_recommendations WHERE user_id=$1 ORDER BY created_at DESC LIMIT $2",
            user_id, limit,
        ))


# ─────────────────────────────────────────────
# STATISTICS
# ─────────────────────────────────────────────

async def get_stats() -> Dict:
    async with pool.acquire() as c:
        users_count    = await c.fetchval("SELECT COUNT(*) FROM users")
        admins_count   = await c.fetchval("SELECT COUNT(*) FROM admins")
        active_dialogs = await c.fetchval("SELECT COUNT(*) FROM dialogs WHERE status='active'")
        total_dialogs  = await c.fetchval("SELECT COUNT(*) FROM dialogs")
        total_messages = await c.fetchval("SELECT COUNT(*) FROM messages")
        reviews_count  = await c.fetchval("SELECT COUNT(*) FROM reviews")
        avg_rating_raw = await c.fetchval("SELECT ROUND(AVG(rating)::numeric,2) FROM reviews")
        banned_users   = await c.fetchval("SELECT COUNT(*) FROM users WHERE is_banned=TRUE")
        online_admins  = await c.fetchval("SELECT COUNT(*) FROM admins WHERE is_online=TRUE")

        daily = await c.fetch(
            """SELECT DATE(created_at) AS d, COUNT(*) AS cnt
               FROM messages WHERE created_at > NOW() - INTERVAL '7 days'
               GROUP BY d ORDER BY d"""
        )
        return {
            "users_count":    int(users_count),
            "admins_count":   int(admins_count),
            "active_dialogs": int(active_dialogs),
            "total_dialogs":  int(total_dialogs),
            "total_messages": int(total_messages),
            "reviews_count":  int(reviews_count),
            "avg_rating":     float(avg_rating_raw) if avg_rating_raw else 0.0,
            "banned_users":   int(banned_users),
            "online_admins":  int(online_admins),
            "daily_messages": [{"date": str(r["d"]), "count": int(r["cnt"])} for r in daily],
        }


# ─────────────────────────────────────────────
# BROADCASTS
# ─────────────────────────────────────────────

async def save_broadcast(content: str, sent_by: int, recipients: int, media_url: Optional[str] = None) -> Dict:
    async with pool.acquire() as c:
        r = await c.fetchrow(
            "INSERT INTO broadcasts (content, sent_by, recipients_count, media_url) VALUES ($1,$2,$3,$4) RETURNING *",
            content, sent_by, recipients, media_url,
        )
        return dict(r)
