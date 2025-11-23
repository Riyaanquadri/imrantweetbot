"""
Persistent audit log and manual review queue for generated tweets.

Stores all drafts, safety checks, and posting decisions in SQLite for:
- Debugging
- Compliance
- Manual review queuing
- Historical analysis

Schema:
- drafts: Generated tweet content
- safety_checks: Safety check results
- posts: Posted tweets
"""
import sqlite3
import json
from datetime import datetime
from typing import Optional, List, Dict, Any
from .logger import logger

DB_PATH = 'bot_audit.db'


class AuditDB:
    """SQLite-based audit log and manual review queue."""
    
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._init_db()
    
    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection with row factory."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def _init_db(self):
        """Initialize database schema."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Drafts table: Generated tweet content
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS drafts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                text TEXT NOT NULL,
                context TEXT,
                generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status TEXT DEFAULT 'generated',  -- generated, approved, rejected, posted
                safety_passed BOOLEAN DEFAULT 0,
                safety_flags TEXT,  -- JSON array of flags
                posted_tweet_id TEXT,
                posted_at TIMESTAMP,
                error_message TEXT,
                manual_review_notes TEXT,
                reviewed_by TEXT,
                reviewed_at TIMESTAMP
            )
        ''')
        
        # Safety checks table: Detailed safety check results
        cursor.execute('''
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
        
        # Manual review queue
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS review_queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                draft_id INTEGER NOT NULL UNIQUE,
                reason TEXT,  -- safety_check_failed, high_priority, etc.
                priority TEXT DEFAULT 'normal',  -- low, normal, high
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                reviewed BOOLEAN DEFAULT 0,
                reviewed_at TIMESTAMP,
                reviewer_decision TEXT,  -- approved, rejected
                reviewer_notes TEXT,
                FOREIGN KEY (draft_id) REFERENCES drafts(id)
            )
        ''')
        
        # Posts table: Posted tweets for tracking
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS posts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                draft_id INTEGER NOT NULL,
                tweet_id TEXT NOT NULL,
                text TEXT NOT NULL,
                posted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                replies_count INTEGER DEFAULT 0,
                likes_count INTEGER DEFAULT 0,
                retweets_count INTEGER DEFAULT 0,
                last_updated TIMESTAMP,
                FOREIGN KEY (draft_id) REFERENCES drafts(id)
            )
        ''')
        
        conn.commit()
        conn.close()
        logger.info(f'Initialized audit database at {self.db_path}')
    
    def log_draft(
        self,
        text: str,
        context: Optional[str] = None,
        safety_passed: bool = False,
        safety_flags: Optional[List[str]] = None
    ) -> int:
        """Log a generated draft."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        flags_json = json.dumps(safety_flags or [])
        cursor.execute('''
            INSERT INTO drafts (text, context, safety_passed, safety_flags)
            VALUES (?, ?, ?, ?)
        ''', (text, context, safety_passed, flags_json))
        
        draft_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        logger.debug(f'Logged draft {draft_id}: passed_safety={safety_passed}')
        return draft_id
    
    def log_safety_check(
        self,
        draft_id: int,
        check_name: str,
        passed: bool,
        details: Optional[str] = None
    ):
        """Log individual safety check result."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO safety_checks (draft_id, check_name, passed, details)
            VALUES (?, ?, ?, ?)
        ''', (draft_id, check_name, passed, details))
        
        conn.commit()
        conn.close()
    
    def queue_for_review(
        self,
        draft_id: int,
        reason: str = 'safety_check_failed',
        priority: str = 'normal'
    ):
        """Queue a draft for manual review."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO review_queue (draft_id, reason, priority)
            VALUES (?, ?, ?)
            ON CONFLICT(draft_id) DO UPDATE SET priority = ?
        ''', (draft_id, reason, priority, priority))
        
        conn.commit()
        conn.close()
        
        logger.info(f'Queued draft {draft_id} for review (reason: {reason}, priority: {priority})')
    
    def get_review_queue(self, only_unreviewed: bool = True) -> List[Dict[str, Any]]:
        """Get drafts pending manual review."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        where = "WHERE reviewed = 0" if only_unreviewed else ""
        cursor.execute(f'''
            SELECT rq.*, d.text, d.safety_flags
            FROM review_queue rq
            JOIN drafts d ON rq.draft_id = d.id
            {where}
            ORDER BY rq.priority DESC, rq.created_at ASC
        ''')
        
        rows = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return rows
    
    def approve_for_posting(
        self,
        draft_id: int,
        reviewer: str,
        notes: Optional[str] = None
    ):
        """Approve a draft for posting."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE drafts SET status = 'approved', reviewed_by = ?, reviewed_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (reviewer, draft_id))
        
        cursor.execute('''
            UPDATE review_queue SET reviewed = 1, reviewer_decision = 'approved', reviewer_notes = ?, reviewed_at = CURRENT_TIMESTAMP
            WHERE draft_id = ?
        ''', (notes, draft_id))
        
        conn.commit()
        conn.close()
        
        logger.info(f'Approved draft {draft_id} for posting')
    
    def reject_draft(
        self,
        draft_id: int,
        reviewer: str,
        reason: str,
        notes: Optional[str] = None
    ):
        """Reject a draft."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE drafts SET status = 'rejected', reviewed_by = ?, reviewed_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (reviewer, draft_id))
        
        cursor.execute('''
            UPDATE review_queue SET reviewed = 1, reviewer_decision = 'rejected', reviewer_notes = ?, reviewed_at = CURRENT_TIMESTAMP
            WHERE draft_id = ?
        ''', (notes, draft_id))
        
        conn.commit()
        conn.close()
        
        logger.info(f'Rejected draft {draft_id}: {reason}')
    
    def log_posted_tweet(
        self,
        draft_id: int,
        tweet_id: str,
        text: str
    ):
        """Log a successfully posted tweet."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE drafts SET status = 'posted', posted_tweet_id = ?, posted_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (tweet_id, draft_id))
        
        cursor.execute('''
            INSERT INTO posts (draft_id, tweet_id, text)
            VALUES (?, ?, ?)
        ''', (draft_id, tweet_id, text))
        
        conn.commit()
        conn.close()
        
        logger.info(f'Logged posted tweet {tweet_id} (draft: {draft_id})')
    
    def get_stats(self) -> Dict[str, Any]:
        """Get audit log statistics."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        stats = {}
        
        # Draft stats
        cursor.execute('SELECT COUNT(*) FROM drafts')
        stats['total_drafts'] = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM drafts WHERE status = ?', ('posted',))
        stats['posted_tweets'] = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM drafts WHERE status = ?', ('rejected',))
        stats['rejected_drafts'] = cursor.fetchone()[0]
        
        # Review queue
        cursor.execute('SELECT COUNT(*) FROM review_queue WHERE reviewed = 0')
        stats['pending_reviews'] = cursor.fetchone()[0]
        
        conn.close()
        return stats
    
    def export_audit_log(self, output_path: str = 'audit_export.json'):
        """Export audit log for compliance."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM drafts ORDER BY generated_at DESC')
        drafts = [dict(row) for row in cursor.fetchall()]
        
        cursor.execute('SELECT * FROM posts ORDER BY posted_at DESC')
        posts = [dict(row) for row in cursor.fetchall()]
        
        export = {
            'exported_at': datetime.now().isoformat(),
            'drafts': drafts,
            'posts': posts,
            'stats': self.get_stats()
        }
        
        with open(output_path, 'w') as f:
            json.dump(export, f, indent=2, default=str)
        
        conn.close()
        logger.info(f'Exported audit log to {output_path}')


# Global audit DB instance
_audit_db = None


def get_audit_db() -> AuditDB:
    """Get or create global audit database instance."""
    global _audit_db
    if _audit_db is None:
        _audit_db = AuditDB()
    return _audit_db
