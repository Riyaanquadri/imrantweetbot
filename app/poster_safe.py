"""
Safety pipeline: Enhanced poster with rate limiting, safety checks, and audit logging.

Workflow:
1. Generate draft tweet
2. Run safety checks
3. If passes: post directly (or queue for review if DRY_RUN)
4. If fails: queue for manual review
5. Log everything to audit DB
"""
import difflib
from tweepy import Client
from typing import Optional, Tuple
from .config import Config
from .logger import logger
from .rate_limit import RateLimitWrapper, RateLimitException
from .safety_enhanced import passes_safety, get_safety_flags
from .audit_db import get_audit_db
from .quota import get_quota_manager

def _is_duplicate(text, window=20, thresh=0.85):
    """
    Check recent 'posted' tweets for high similarity. Returns (is_dup, ratio, matched_text).
    window: number of last posted drafts to compare
    thresh: similarity threshold (0.0-1.0) to consider a duplicate
    """
    try:
        conn = audit_db._get_connection()
        cur = conn.cursor()
        cur.execute("SELECT text FROM drafts WHERE status='posted' ORDER BY id DESC LIMIT ?", (window,))
        rows = [r[0] for r in cur.fetchall()]
        conn.close()
    except Exception:
        # if DB fails, don't block posting — be conservative and treat as non-duplicate
        return False, 0.0, None

    s1 = (text or "").strip().lower()
    for old in rows:
        s2 = (old or "").strip().lower()
        ratio = difflib.SequenceMatcher(None, s1, s2).ratio()
        if ratio >= thresh:
            return True, ratio, old
    return False, 0.0, None

def _extract_tweet_id(resp):
    """
    Normalize various client response shapes to extract the tweet id string.
    Accepts:
      - Tweepy-like Response (has .data which may be dict-like or object-like)
      - raw dict response {'data': {'id': ...}}
      - raw id string (already an id)
    Returns tweet id string or None.
    """
    if resp is None:
        return None

    # If Tweepy-like wrapper with .data attribute
    if hasattr(resp, "data"):
        data = resp.data
        # dict-like (has get)
        if hasattr(data, "get"):
            return data.get("id") or data.get("id_str") if isinstance(data, dict) else None
        # object-like with attribute 'id'
        return getattr(data, "id", None)

    # If it's a plain dict
    if isinstance(resp, dict):
        d = resp.get("data") or resp
        if isinstance(d, dict):
            return d.get("id") or d.get("id_str")
    # If resp is a raw id
    if isinstance(resp, (int, str)):
        return str(resp)

    return None
# --- end helper ---

audit_db = get_audit_db()
quota_manager = get_quota_manager()


class SafePoster:
    """Posts tweets with rate limiting, safety checks, and audit trail."""
    
    def __init__(self, twitter_client=None):
        if twitter_client:
            self.client = twitter_client
        else:
            self.client = Client(
                bearer_token=Config.X_BEARER_TOKEN,
                consumer_key=Config.X_API_KEY,
                consumer_secret=Config.X_API_SECRET,
                access_token=Config.X_ACCESS_TOKEN,
                access_token_secret=Config.X_ACCESS_SECRET,
                wait_on_rate_limit=True
            )
    
    def post(
        self,
        text: str,
        context: Optional[str] = None,
        force_review: bool = False,
        ab_variant: Optional[str] = None
    ) -> Tuple[Optional[str], bool]:
        """
        Post a tweet with full safety pipeline.
        
        Args:
            text: Tweet text
            context: Context for audit log
            force_review: Force manual review regardless of safety
            
        Returns:
            Tuple of (tweet_id, was_posted)
            - tweet_id: ID if posted, None if queued/rejected
            - was_posted: True only if actually posted to Twitter
        """
        # Step 1: Log draft
        draft_id = audit_db.log_draft(text, context, safety_passed=False, safety_flags=[], ab_variant=ab_variant)
        variant_label = ab_variant or 'default'
        logger.info(f'[Draft {draft_id}] Generated tweet (variant={variant_label}): {text[:50]}...')
        
        # Step 2: Run safety checks
        passed_safety = passes_safety(text)
        safety_flags = [] if passed_safety else get_safety_flags(text)
        
        logger.info(f'[Draft {draft_id}] Safety check: {"✓ PASSED" if passed_safety else "✗ FAILED"}')
        if not passed_safety:
            logger.warning(f'[Draft {draft_id}] Flags: {", ".join(safety_flags)}')
        
        # Update draft with safety results
        conn_audit = audit_db._get_connection()
        cursor = conn_audit.cursor()
        cursor.execute('''
            UPDATE drafts SET safety_passed = ?, safety_flags = ?
            WHERE id = ?
        ''', (passed_safety, str(safety_flags), draft_id))
        conn_audit.commit()
        conn_audit.close()
        
        # Step 3: Decide posting action
        if not passed_safety:
            audit_db.queue_for_review(draft_id, reason='safety_check_failed', priority='normal')
            logger.info(f'[Draft {draft_id}] Queued for manual review')
            return None, False

        can_post, quota_reason = quota_manager.can_post()
        if not can_post:
            audit_db.queue_for_review(draft_id, reason=quota_reason, priority='low')
            logger.info(f'[Draft {draft_id}] Post deferred: {quota_reason}')
            return None, False

        if force_review:
            audit_db.queue_for_review(draft_id, reason='owner_approval_required', priority='high')
            logger.info(f'[Draft {draft_id}] Awaiting manual approval before posting')
            return None, False
        
        dup, ratio, matched = _is_duplicate(text)
        if dup:
            logger.info(f'[Draft {draft_id}] Skipping post — duplicate of recent tweet (sim={ratio:.2f})')
            audit_db.queue_for_review(draft_id, reason='duplicate_recent', priority='low')
            return None, False
        # Step 4: Check DRY_RUN mode
        if Config.DRY_RUN:
            logger.info(f'[Draft {draft_id}] [DRY_RUN] Would post to Twitter')
            conn_audit = audit_db._get_connection()
            cursor = conn_audit.cursor()
            cursor.execute('UPDATE drafts SET status = ? WHERE id = ?', ('posted', draft_id))
            conn_audit.commit()
            conn_audit.close()
            return None, False
        
        # Step 5: Post with rate limiting
        try:
            resp = RateLimitWrapper.call_with_backoff(
                self.client.create_tweet,
                text=text
            )

            tweet_id = _extract_tweet_id(resp)

            # Log posted tweet
            audit_db.log_posted_tweet(draft_id, str(tweet_id), text)
            logger.info(f'[Draft {draft_id}] ✓ Posted to Twitter: {tweet_id}')
            quota_manager.record_post()
            
            return str(tweet_id), True
            
        except RateLimitException as e:
            logger.error(f'[Draft {draft_id}] Rate limit exceeded, queuing for retry: {e}')
            audit_db.queue_for_review(draft_id, reason='rate_limit_exceeded', priority='high')
            return None, False
            
        except Exception as e:
            logger.error(f'[Draft {draft_id}] Error posting tweet: {e}')
            
            # Store error in audit log
            conn_audit = audit_db._get_connection()
            cursor = conn_audit.cursor()
            cursor.execute('''
                UPDATE drafts SET status = ?, error_message = ?
                WHERE id = ?
            ''', ('error', str(e), draft_id))
            conn_audit.commit()
            conn_audit.close()
            
            audit_db.queue_for_review(draft_id, reason='posting_error', priority='high')
            return None, False
    
    def reply(
        self,
        text: str,
        in_reply_to_tweet_id: str,
        context: Optional[str] = None,
        force_review: bool = False,
        author_id: Optional[str] = None,
        priority: str = 'normal',
        ab_variant: Optional[str] = None
    ) -> Tuple[Optional[str], bool]:
        """
        Reply to a tweet with full safety pipeline.
        
        Same as post() but for replies.
        """
        # Step 1: Log draft
        draft_id = audit_db.log_draft(
            text,
            context=f'reply_to:{in_reply_to_tweet_id}',
            safety_passed=False,
            safety_flags=[],
            ab_variant=ab_variant
        )
        logger.info(f'[Draft {draft_id}] Generated reply: {text[:50]}...')
        
        # Step 2: Run safety checks
        passed_safety = passes_safety(text)
        safety_flags = [] if passed_safety else get_safety_flags(text)
        
        logger.info(f'[Draft {draft_id}] Safety check: {"✓ PASSED" if passed_safety else "✗ FAILED"}')
        
        # Update draft with safety results
        conn_audit = audit_db._get_connection()
        cursor = conn_audit.cursor()
        cursor.execute('''
            UPDATE drafts SET safety_passed = ?, safety_flags = ?
            WHERE id = ?
        ''', (passed_safety, str(safety_flags), draft_id))
        conn_audit.commit()
        conn_audit.close()
        
        # Step 3: Check if should queue for review
        if not passed_safety:
            audit_db.queue_for_review(draft_id, reason='safety_check_failed', priority='normal')
            logger.info(f'[Draft {draft_id}] Queued for manual review')
            return None, False

        if force_review:
            audit_db.queue_for_review(draft_id, reason='forced_review', priority='normal')
            logger.info(f'[Draft {draft_id}] Forced review requested')
            return None, False

        can_reply, quota_reason = quota_manager.can_reply(author_id)
        if not can_reply:
            logger.info(f'[Draft {draft_id}] Reply skipped due to quota: {quota_reason}')
            return None, False
        
        # Step 4: Check DRY_RUN mode
        if Config.DRY_RUN:
            logger.info(f'[Draft {draft_id}] [DRY_RUN] Would reply to {in_reply_to_tweet_id}')
            return None, False
        
        # Step 5: Post with rate limiting
        try:
            response = RateLimitWrapper.call_with_backoff(
                self.client.create_tweet,
                text=text,
                in_reply_to_tweet_id=in_reply_to_tweet_id
            )

            tweet_id = _extract_tweet_id(response)
            audit_db.log_posted_tweet(draft_id, str(tweet_id), text)
            logger.info(f'[Draft {draft_id}] ✓ Posted reply: {tweet_id}')
            quota_manager.record_reply(author_id)
            
            return str(tweet_id), True
            
        except RateLimitException as e:
            logger.error(f'[Draft {draft_id}] Rate limit exceeded: {e}')
            audit_db.queue_for_review(draft_id, reason='rate_limit_exceeded', priority='high')
            return None, False
            
        except Exception as e:
            logger.error(f'[Draft {draft_id}] Error posting reply: {e}')
            conn_audit = audit_db._get_connection()
            cursor = conn_audit.cursor()
            cursor.execute('''
                UPDATE drafts SET status = ?, error_message = ?
                WHERE id = ?
            ''', ('error', str(e), draft_id))
            conn_audit.commit()
            conn_audit.close()
            
            audit_db.queue_for_review(draft_id, reason='posting_error', priority='high')
            return None, False
