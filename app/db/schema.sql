PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    username TEXT,
    name TEXT,
    description TEXT,
    verified INTEGER DEFAULT 0,
    profile_image_url TEXT,
    raw_json TEXT,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS posts (
    id TEXT PRIMARY KEY,
    author_id TEXT,
    text TEXT,
    full_text TEXT,
    created_at TEXT,
    lang TEXT,
    possibly_sensitive INTEGER DEFAULT 0,
    public_metrics_json TEXT,
    entities_json TEXT,
    attachments_json TEXT,
    referenced_tweets_json TEXT,
    conversation_id TEXT,
    raw_json TEXT,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(author_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS media (
    media_key TEXT PRIMARY KEY,
    post_id TEXT,
    type TEXT,
    url TEXT,
    preview_image_url TEXT,
    alt_text TEXT,
    width INTEGER,
    height INTEGER,
    raw_json TEXT,
    FOREIGN KEY(post_id) REFERENCES posts(id)
);

CREATE TABLE IF NOT EXISTS bookmarks (
    post_id TEXT PRIMARY KEY,
    is_bookmarked INTEGER NOT NULL DEFAULT 1,
    first_seen_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL,
    inactive_at TEXT,
    last_sync_run_id INTEGER,
    FOREIGN KEY(post_id) REFERENCES posts(id)
);

CREATE TABLE IF NOT EXISTS tokens (
    provider TEXT PRIMARY KEY,
    access_token TEXT NOT NULL,
    refresh_token TEXT,
    token_type TEXT,
    scope TEXT,
    expires_at TEXT,
    user_id TEXT,
    username TEXT,
    name TEXT,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS oauth_states (
    state TEXT PRIMARY KEY,
    code_verifier TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sync_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    status TEXT NOT NULL,
    pages_fetched INTEGER NOT NULL DEFAULT 0,
    posts_seen INTEGER NOT NULL DEFAULT 0,
    posts_inserted INTEGER NOT NULL DEFAULT 0,
    posts_updated INTEGER NOT NULL DEFAULT 0,
    posts_deactivated INTEGER NOT NULL DEFAULT 0,
    error_message TEXT,
    mode TEXT NOT NULL DEFAULT 'full'
);

CREATE TABLE IF NOT EXISTS app_state (
    key TEXT PRIMARY KEY,
    value TEXT
);

CREATE VIRTUAL TABLE IF NOT EXISTS post_search USING fts5(
    post_id UNINDEXED,
    full_text,
    author_username,
    author_name,
    hashtags,
    mentions,
    urls
);

CREATE INDEX IF NOT EXISTS idx_posts_author_id ON posts(author_id);
CREATE INDEX IF NOT EXISTS idx_posts_created_at ON posts(created_at);
CREATE INDEX IF NOT EXISTS idx_bookmarks_is_bookmarked ON bookmarks(is_bookmarked);
CREATE INDEX IF NOT EXISTS idx_bookmarks_last_seen_at ON bookmarks(last_seen_at);
CREATE INDEX IF NOT EXISTS idx_media_post_id ON media(post_id);
