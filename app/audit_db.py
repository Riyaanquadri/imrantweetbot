"""Concurrency-safe SQLite audit log helper."""
from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from .config import Config
from .logger import logger

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, 'bot_audit.db')
_write_lock = threading.Lock()


def _connect(db_path: str = DB_PATH) -> sqlite3.Connection:
    """Create SQLite connection with WAL + busy timeout ready."""
    conn = sqlite3.connect(db_path, timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    # Defensive PRAGMAs (no-op if already set globally)
    try:
        conn.execute('PRAGMA journal_mode=WAL;')
    except sqlite3.OperationalError:
        pass
    conn.execute('PRAGMA busy_timeout=5000;')
    return conn


def _column_exists(conn: sqlite3.Connection, table: str, column: str) -> bool:
    cur = conn.cursor()
    cur.execute(f"PRAGMA table_info({table})")
    return any(row[1] == column for row in cur.fetchall())


def _with_retry(fn, max_retries: int = 6, base_delay: float = 0.05):
    """Retry helper to survive short write contentions."""
    for attempt in range(max_retries):
        try:
            return fn()
        except sqlite3.OperationalError as exc:
            msg = str(exc).lower()
            if 'database is locked' in msg or 'database table is locked' in msg:
                sleep_for = base_delay * (2 ** attempt)
                time.sleep(sleep_for)
                continue
            raise
    return fn()


class AuditDB:
    """SQLite-based audit log and manual review queue with locking."""

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._init_db()

    def _get_connection(self):
        """Backward-compatible accessor for legacy callers."""
        return _connect(self.db_path)

    def _init_db(self):
        conn = _connect(self.db_path)
        cur = conn.cursor()
        cur.execute('''
            CREATE TABLE IF NOT EXISTS drafts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                text TEXT NOT NULL,
                context TEXT,
                generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status TEXT DEFAULT 'generated',
                safety_passed BOOLEAN DEFAULT 0,
                safety_flags TEXT,
                posted_tweet_id TEXT,
                posted_at TIMESTAMP,
                error_message TEXT,
                manual_review_notes TEXT,
                reviewed_by TEXT,
                reviewed_at TIMESTAMP
            )
        ''')
        if not _column_exists(conn, 'drafts', 'ab_variant'):
            cur.execute("ALTER TABLE drafts ADD COLUMN ab_variant TEXT")
        cur.execute('''
            CREATE TABLE IF NOT EXISTS safety_checks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                draft_id INTEGER NOT NULL,
                check_name TEXT NOT NULL,
                passed BOOLEAN NOT NULL,
                details TEXT,
                checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (draft_id) REFERENCES drafts(id)
            )
        ''')
        cur.execute('''
            CREATE TABLE IF NOT EXISTS review_queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                draft_id INTEGER NOT NULL UNIQUE,
                reason TEXT,
                priority TEXT DEFAULT 'normal',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                reviewed BOOLEAN DEFAULT 0,
                reviewed_at TIMESTAMP,
                reviewer_decision TEXT,
                reviewer_notes TEXT,
                FOREIGN KEY (draft_id) REFERENCES drafts(id)
            )
        ''')
        cur.execute('''
            CREATE TABLE IF NOT EXISTS posts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                draft_id INTEGER NOT NULL,
                tweet_id TEXT NOT NULL,
                text TEXT NOT NULL,
                posted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                replies_count INTEGER DEFAULT 0,
                likes_count INTEGER DEFAULT 0,
                retweets_count INTEGER DEFAULT 0,
                last_updated TIMESTAMP
            )
        ''')
        conn.commit()
        conn.close()
        logger.info('Initialized audit database at %s', self.db_path)

    def _write(self, handler):
        def run():
            with _write_lock:
                conn = _connect(self.db_path)
                try:
                    result = handler(conn)
                    conn.commit()
                    return result
                finally:
                    conn.close()
        return _with_retry(run)

    def _read(self, handler):
        conn = _connect(self.db_path)
        try:
            return handler(conn)
        finally:
            conn.close()
    
    def log_draft(
        self,
        text: str,
        context: Optional[str] = None,
        safety_passed: bool = False,
        safety_flags: Optional[List[str]] = None,
        ab_variant: Optional[str] = None
    ) -> int:
        """Log a generated draft."""
        flags_json = json.dumps(safety_flags or [])
        status_val = 'pending_approval' if Config.REQUIRE_POST_APPROVAL else 'queued'

        def handler(conn):
            cur = conn.cursor()
            cur.execute(
                '''
                INSERT INTO drafts (text, context, status, safety_passed, safety_flags, ab_variant)
                VALUES (?, ?, ?, ?, ?, ?)
                ''',
                (text, context, status_val, int(bool(safety_passed)), flags_json, ab_variant)
            )
            draft_id = cur.lastrowid
            logger.debug('Logged draft %s: status=%s safety_passed=%s', draft_id, status_val, safety_passed)
            return draft_id

        return self._write(handler)
    
    def log_safety_check(
        self,
        draft_id: int,
        check_name: str,
        passed: bool,
        details: Optional[str] = None
    ):
        """Log individual safety check result."""
        def handler(conn):
            cur = conn.cursor()
            cur.execute(
                '''
                INSERT INTO safety_checks (draft_id, check_name, passed, details)
                VALUES (?, ?, ?, ?)
                ''',
                (draft_id, check_name, int(bool(passed)), details)
            )

        self._write(handler)
    
    def queue_for_review(
        self,
        draft_id: int,
        reason: str = 'safety_check_failed',
        priority: str = 'normal'
    ):
        """Queue a draft for manual review."""
        def handler(conn):
            cur = conn.cursor()
            cur.execute(
                '''
                INSERT INTO review_queue (draft_id, reason, priority)
                VALUES (?, ?, ?)
                ON CONFLICT(draft_id) DO UPDATE SET priority = excluded.priority
                ''',
                (draft_id, reason, priority)
            )

        self._write(handler)
        logger.info('Queued draft %s for review (reason=%s, priority=%s)', draft_id, reason, priority)
    
    def get_review_queue(self, only_unreviewed: bool = True) -> List[Dict[str, Any]]:
        """Get drafts pending manual review."""
        def handler(conn):
            where = "WHERE reviewed = 0" if only_unreviewed else ""
            cur = conn.cursor()
            cur.execute(
                f'''
                SELECT rq.*, d.text, d.safety_flags
                FROM review_queue rq
                JOIN drafts d ON rq.draft_id = d.id
                {where}
                ORDER BY rq.priority DESC, rq.created_at ASC
                '''
            )
            return [dict(row) for row in cur.fetchall()]

        return self._read(handler)
    
    def approve_for_posting(
        self,
        draft_id: int,
        reviewer: str,
        notes: Optional[str] = None
    ):
        """Approve a draft for posting."""
        def handler(conn):
            cur = conn.cursor()
            cur.execute(
                '''
                UPDATE drafts SET status = 'approved', reviewed_by = ?, reviewed_at = CURRENT_TIMESTAMP
                WHERE id = ?
                ''',
                (reviewer, draft_id)
            )
            cur.execute(
                '''
                UPDATE review_queue SET reviewed = 1, reviewer_decision = 'approved', reviewer_notes = ?, reviewed_at = CURRENT_TIMESTAMP
                WHERE draft_id = ?
                ''',
                (notes, draft_id)
            )

        self._write(handler)
        logger.info('Approved draft %s for posting', draft_id)
    
    def reject_draft(
        self,
        draft_id: int,
        reviewer: str,
        reason: str,
        notes: Optional[str] = None
    ):
        """Reject a draft."""
        def handler(conn):
            cur = conn.cursor()
            cur.execute(
                '''
                UPDATE drafts SET status = 'rejected', reviewed_by = ?, reviewed_at = CURRENT_TIMESTAMP
                WHERE id = ?
                ''',
                (reviewer, draft_id)
            )
            cur.execute(
                '''
                UPDATE review_queue SET reviewed = 1, reviewer_decision = 'rejected', reviewer_notes = ?, reviewed_at = CURRENT_TIMESTAMP
                WHERE draft_id = ?
                ''',
                (notes, draft_id)
            )

        self._write(handler)
        logger.info('Rejected draft %s: %s', draft_id, reason)
    
    def log_posted_tweet(
        self,
        draft_id: int,
        tweet_id: str,
        text: str
    ):
        """Log a successfully posted tweet."""
        def handler(conn):
            cur = conn.cursor()
            cur.execute(
                '''
                UPDATE drafts SET status = 'posted', posted_tweet_id = ?, posted_at = CURRENT_TIMESTAMP
                WHERE id = ?
                ''',
                (tweet_id, draft_id)
            )
            cur.execute(
                '''
                INSERT INTO posts (draft_id, tweet_id, text)
                VALUES (?, ?, ?)
                ''',
                (draft_id, tweet_id, text)
            )

        self._write(handler)
        logger.info('Logged posted tweet %s (draft=%s)', tweet_id, draft_id)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get audit log statistics."""
        def handler(conn):
            cur = conn.cursor()
            stats: Dict[str, Any] = {}
            cur.execute('SELECT COUNT(*) FROM drafts')
            stats['total_drafts'] = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM drafts WHERE status = 'posted'")
            stats['posted_tweets'] = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM drafts WHERE status = 'rejected'")
            stats['rejected_drafts'] = cur.fetchone()[0]
            cur.execute('SELECT COUNT(*) FROM review_queue WHERE reviewed = 0')
            stats['pending_reviews'] = cur.fetchone()[0]
            return stats

        return self._read(handler)
    
    def export_audit_log(self, output_path: str = 'audit_export.json'):
        """Export audit log for compliance."""
        def handler(conn):
            cur = conn.cursor()
            cur.execute('SELECT * FROM drafts ORDER BY generated_at DESC')
            drafts = [dict(row) for row in cur.fetchall()]
            cur.execute('SELECT * FROM posts ORDER BY posted_at DESC')
            posts = [dict(row) for row in cur.fetchall()]
            return drafts, posts

        drafts, posts = self._read(handler)
        export = {
            'exported_at': datetime.now().isoformat(),
            'drafts': drafts,
            'posts': posts,
            'stats': self.get_stats()
        }
        with open(output_path, 'w', encoding='utf-8') as file:
            json.dump(export, file, indent=2, default=str)
        logger.info('Exported audit log to %s', output_path)


# Global audit DB instance
_audit_db = None


def get_audit_db() -> AuditDB:
    """Get or create global audit database instance."""
    global _audit_db
    if _audit_db is None:
        _audit_db = AuditDB()
    return _audit_db
