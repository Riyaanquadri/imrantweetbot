"""
Safety pipeline: Enhanced poster with rate limiting, safety checks, and audit logging.

Workflow:
1. Generate draft tweet
2. Run safety checks
3. If passes: post directly (or queue for review if DRY_RUN)
4. If fails: queue for manual review
5. Log everything to audit DB
"""
from tweepy import Client
from typing import Optional, Tuple
from .config import Config
from .logger import logger
from .rate_limit import RateLimitWrapper, RateLimitException
from .safety_enhanced import passes_safety, get_safety_flags
from .audit_db import get_audit_db

audit_db = get_audit_db()


class SafePoster:
    """Posts tweets with rate limiting, safety checks, and audit trail."""
    
    def __init__(self):
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
        force_review: bool = False
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
        draft_id = audit_db.log_draft(text, context, safety_passed=False, safety_flags=[])
        logger.info(f'[Draft {draft_id}] Generated tweet: {text[:50]}...')
        
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
        if not passed_safety or force_review:
            reason = 'safety_check_failed' if not passed_safety else 'forced_review'
            audit_db.queue_for_review(draft_id, reason=reason, priority='normal')
            logger.info(f'[Draft {draft_id}] Queued for manual review')
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
            tweet_id = RateLimitWrapper.call_with_backoff(
                self.client.create_tweet,
                text=text
            )
            
            # Extract ID from response
            if hasattr(tweet_id, 'data'):
                tweet_id = tweet_id.data.get('id')
            
            # Log posted tweet
            audit_db.log_posted_tweet(draft_id, str(tweet_id), text)
            logger.info(f'[Draft {draft_id}] ✓ Posted to Twitter: {tweet_id}')
            
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
        force_review: bool = False
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
            safety_flags=[]
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
        if not passed_safety or force_review:
            reason = 'safety_check_failed' if not passed_safety else 'forced_review'
            audit_db.queue_for_review(draft_id, reason=reason, priority='normal')
            logger.info(f'[Draft {draft_id}] Queued for manual review')
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
            
            tweet_id = response.data.get('id') if hasattr(response, 'data') else response
            audit_db.log_posted_tweet(draft_id, str(tweet_id), text)
            logger.info(f'[Draft {draft_id}] ✓ Posted reply: {tweet_id}')
            
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
