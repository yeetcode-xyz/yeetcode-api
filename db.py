"""
SQLite database layer for YeetCode
Single source of truth — replaces DynamoDB + cache + WAL
"""

import sqlite3
import os

DB_PATH = os.environ.get("SQLITE_PATH", "/data/yeetcode.db")

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS users (
    username            TEXT PRIMARY KEY,
    email               TEXT UNIQUE NOT NULL,
    display_name        TEXT,
    university          TEXT,
    group_id            TEXT,
    easy                INTEGER DEFAULT 0,
    medium              INTEGER DEFAULT 0,
    hard                INTEGER DEFAULT 0,
    xp                  INTEGER DEFAULT 0,
    streak              INTEGER DEFAULT 0,
    last_completed_date TEXT,
    today               INTEGER DEFAULT 0,
    created_at          TEXT,
    updated_at          TEXT,
    leetcode_invalid    INTEGER DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_users_group ON users(group_id);
CREATE INDEX IF NOT EXISTS idx_users_university ON users(university);
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);

CREATE TABLE IF NOT EXISTS daily_problems (
    date        TEXT PRIMARY KEY,
    slug        TEXT NOT NULL,
    title       TEXT,
    frontend_id TEXT,
    difficulty  TEXT,
    tags        TEXT
);

CREATE TABLE IF NOT EXISTS daily_completions (
    username    TEXT NOT NULL,
    date        TEXT NOT NULL,
    PRIMARY KEY (username, date)
);
CREATE INDEX IF NOT EXISTS idx_completions_date ON daily_completions(date);
CREATE INDEX IF NOT EXISTS idx_completions_user ON daily_completions(username);

CREATE TABLE IF NOT EXISTS bounties (
    bounty_id   TEXT PRIMARY KEY,
    title       TEXT,
    description TEXT,
    slug        TEXT,
    metric      TEXT,
    count       INTEGER,
    start_date  INTEGER,
    expiry_date INTEGER,
    xp          INTEGER
);

CREATE TABLE IF NOT EXISTS bounty_progress (
    bounty_id   TEXT NOT NULL,
    username    TEXT NOT NULL,
    progress    INTEGER DEFAULT 0,
    PRIMARY KEY (bounty_id, username)
);

CREATE TABLE IF NOT EXISTS duels (
    duel_id               TEXT PRIMARY KEY,
    challenger            TEXT NOT NULL,
    challengee            TEXT NOT NULL,
    problem_slug          TEXT,
    problem_title         TEXT,
    problem_number        TEXT,
    difficulty            TEXT,
    status                TEXT DEFAULT 'PENDING',
    is_wager              INTEGER DEFAULT 0,
    challenger_wager      INTEGER DEFAULT 0,
    challengee_wager      INTEGER DEFAULT 0,
    challenger_time       INTEGER DEFAULT -1,
    challengee_time       INTEGER DEFAULT -1,
    challenger_start_time TEXT,
    challengee_start_time TEXT,
    start_time            TEXT,
    winner                TEXT,
    xp_awarded            INTEGER DEFAULT 0,
    created_at            TEXT,
    accepted_at           TEXT,
    completed_at          TEXT,
    expires_at            INTEGER
);
CREATE INDEX IF NOT EXISTS idx_duels_challenger ON duels(challenger);
CREATE INDEX IF NOT EXISTS idx_duels_challengee ON duels(challengee);
CREATE INDEX IF NOT EXISTS idx_duels_status ON duels(status);

CREATE TABLE IF NOT EXISTS verification_codes (
    email       TEXT PRIMARY KEY,
    code        TEXT NOT NULL,
    expires_at  INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS groups (
    group_id   TEXT PRIMARY KEY,
    name       TEXT,
    leader     TEXT NOT NULL,
    created_at TEXT
);

CREATE TABLE IF NOT EXISTS duel_invites (
    token       TEXT PRIMARY KEY,
    challenger  TEXT NOT NULL,
    email       TEXT,
    difficulty  TEXT,
    created_at  TEXT,
    expires_at  INTEGER
);
"""


def get_db() -> sqlite3.Connection:
    """Get a SQLite connection with WAL mode and row factory."""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def init_db():
    """Initialize database schema (idempotent — safe to call on every startup)."""
    # Ensure parent directory exists
    db_dir = os.path.dirname(DB_PATH)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir, exist_ok=True)

    conn = get_db()
    conn.executescript(SCHEMA_SQL)
    conn.commit()
    conn.close()
