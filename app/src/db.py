"""Tiny SQLite audit DB for drafts & posts."""
import sqlite3
from datetime import datetime
from typing import Optional

DB_PATH = "bot_audit.db"

CREATE_SQL = """
CREATE TABLE IF NOT EXISTS drafts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    text TEXT NOT NULL,
    context TEXT,
    status TEXT NOT NULL,
    safety_flags TEXT,
    created_at TEXT,
    posted_tweet_id TEXT,
    posted_at TEXT
);
"""


def get_conn():
    conn = sqlite3.connect(DB_PATH, isolation_level=None, check_same_thread=False)
    return conn


def init_db():
    conn = get_conn()
    conn.execute(CREATE_SQL)
    conn.close()


def save_draft(
    text: str,
    context: Optional[str],
    status: str = "queued",
    safety_flags: Optional[str] = None
) -> int:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO drafts (text, context, status, safety_flags, created_at) VALUES (?, ?, ?, ?, ?)",
        (text, context, status, safety_flags or "", datetime.utcnow().isoformat()),
    )
    draft_id = cur.lastrowid
    conn.close()
    return draft_id


def mark_posted(draft_id: int, tweet_id: str):
    conn = get_conn()
    conn.execute(
        "UPDATE drafts SET status = ?, posted_tweet_id = ?, posted_at = ? WHERE id = ?",
        ("posted", tweet_id, datetime.utcnow().isoformat(), draft_id)
    )
    conn.close()


def mark_failed(draft_id: int, reason: str):
    conn = get_conn()
    conn.execute(
        "UPDATE drafts SET status = ?, safety_flags = ? WHERE id = ?",
        ("failed", reason, draft_id)
    )
    conn.close()
