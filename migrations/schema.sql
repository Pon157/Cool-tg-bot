-- =============================================
-- Anon Support Bot — Database Schema
-- =============================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- USERS
CREATE TABLE IF NOT EXISTS users (
    telegram_id     BIGINT PRIMARY KEY,
    username        VARCHAR(100),
    pseudonym       VARCHAR(100),
    age             VARCHAR(30),
    characteristics TEXT,
    hobbies         TEXT,
    avatar_url      TEXT,
    profile_card_url TEXT,
    is_banned       BOOLEAN NOT NULL DEFAULT FALSE,
    warn_count      INT NOT NULL DEFAULT 0,
    is_registered   BOOLEAN NOT NULL DEFAULT FALSE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ADMINS
CREATE TABLE IF NOT EXISTS admins (
    id              SERIAL PRIMARY KEY,
    telegram_id     BIGINT UNIQUE NOT NULL,
    username        VARCHAR(100),
    pseudonym       VARCHAR(100) UNIQUE NOT NULL,
    password_hash   TEXT NOT NULL,
    age             VARCHAR(30),
    characteristics TEXT,
    hobbies         TEXT,
    description     TEXT,
    avatar_url      TEXT,
    -- Channel info
    channel_title       VARCHAR(200),
    channel_description TEXT,
    channel_avatar_url  TEXT,
    -- Status
    is_online       BOOLEAN NOT NULL DEFAULT FALSE,
    last_seen       TIMESTAMPTZ,
    is_profile_filled BOOLEAN NOT NULL DEFAULT FALSE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- DIALOGS
CREATE TABLE IF NOT EXISTS dialogs (
    id              SERIAL PRIMARY KEY,
    user_id         BIGINT NOT NULL REFERENCES users(telegram_id) ON DELETE CASCADE,
    admin_id        INT REFERENCES admins(id) ON DELETE SET NULL,
    status          VARCHAR(20) NOT NULL DEFAULT 'pending'
                        CHECK (status IN ('pending','active','closed')),
    is_anonymous    BOOLEAN NOT NULL DEFAULT FALSE,
    group_message_id BIGINT,    -- message_id in admin group for editing
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    closed_at       TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_dialogs_user   ON dialogs(user_id);
CREATE INDEX IF NOT EXISTS idx_dialogs_admin  ON dialogs(admin_id);
CREATE INDEX IF NOT EXISTS idx_dialogs_status ON dialogs(status);

-- MESSAGES
CREATE TABLE IF NOT EXISTS messages (
    id                  SERIAL PRIMARY KEY,
    dialog_id           INT NOT NULL REFERENCES dialogs(id) ON DELETE CASCADE,
    sender_type         VARCHAR(10) NOT NULL CHECK (sender_type IN ('user','admin')),
    content             TEXT,
    media_url           TEXT,
    media_type          VARCHAR(30),
    telegram_message_id BIGINT,
    is_read             BOOLEAN NOT NULL DEFAULT FALSE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_messages_dialog ON messages(dialog_id);

-- REVIEWS
CREATE TABLE IF NOT EXISTS reviews (
    id          SERIAL PRIMARY KEY,
    user_id     BIGINT NOT NULL REFERENCES users(telegram_id) ON DELETE CASCADE,
    admin_id    INT NOT NULL REFERENCES admins(id) ON DELETE CASCADE,
    dialog_id   INT NOT NULL REFERENCES dialogs(id) ON DELETE CASCADE,
    text        TEXT,
    rating      INT NOT NULL CHECK (rating BETWEEN 1 AND 5),
    media_urls  JSONB NOT NULL DEFAULT '[]',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(user_id, dialog_id)
);

-- CHANNEL POSTS
CREATE TABLE IF NOT EXISTS channel_posts (
    id          SERIAL PRIMARY KEY,
    admin_id    INT NOT NULL REFERENCES admins(id) ON DELETE CASCADE,
    content     TEXT,
    media_urls  JSONB NOT NULL DEFAULT '[]',
    views       INT NOT NULL DEFAULT 0,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_channel_posts_admin ON channel_posts(admin_id);

-- CHANNEL SUBSCRIPTIONS
CREATE TABLE IF NOT EXISTS channel_subscriptions (
    user_id     BIGINT NOT NULL REFERENCES users(telegram_id) ON DELETE CASCADE,
    admin_id    INT NOT NULL REFERENCES admins(id) ON DELETE CASCADE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (user_id, admin_id)
);

-- AI RECOMMENDATIONS
CREATE TABLE IF NOT EXISTS ai_recommendations (
    id              SERIAL PRIMARY KEY,
    user_id         BIGINT NOT NULL REFERENCES users(telegram_id) ON DELETE CASCADE,
    dialog_id       INT REFERENCES dialogs(id) ON DELETE SET NULL,
    recommendation  TEXT NOT NULL,
    keywords        JSONB NOT NULL DEFAULT '[]',
    emotional_tone  VARCHAR(50),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_ai_recs_user ON ai_recommendations(user_id);

-- BROADCASTS
CREATE TABLE IF NOT EXISTS broadcasts (
    id              SERIAL PRIMARY KEY,
    content         TEXT NOT NULL,
    media_url       TEXT,
    sent_by         BIGINT NOT NULL,
    recipients_count INT NOT NULL DEFAULT 0,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- BANS LOG
CREATE TABLE IF NOT EXISTS bans_log (
    id          SERIAL PRIMARY KEY,
    user_id     BIGINT NOT NULL,
    action      VARCHAR(20) NOT NULL,  -- ban / unban / warn / unwarn
    reason      TEXT,
    issued_by   BIGINT NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
