# app/src/posting.py
"""Unified posting wrapper: safety -> audit -> backoff -> post."""
import time
import random
from typing import Optional
from .safety import passes_safety
from .db import save_draft, mark_posted, mark_failed
from .config import Config
from .logger import logger

# Expect you have a `twitter_client` instance available from your existing code:
# from your_client_module import twitter_client

def _backoff_try(func, *args, max_retries=5, base=1.5, **kwargs):
    backoff = base
    for attempt in range(max_retries):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logger.warning("Post attempt %s failed: %s", attempt + 1, str(e))
            if attempt == max_retries - 1:
                raise
            time.sleep(backoff + random.random())
            backoff *= base

def post_safe(
    text: str,
    context: Optional[str] = None,
    twitter_client=None,
    in_reply_to_tweet_id: Optional[str] = None
) -> Optional[str]:
    """Run safety checks, audit, and post (or reply) if allowed. Returns tweet_id or None."""
    ok, reason = passes_safety(text)
    draft_id = save_draft(text, context, status="queued", safety_flags=(reason if not ok else ""))
    if not ok:
        mark_failed(draft_id, reason)
        logger.info("Draft %s blocked by safety: %s", draft_id, reason)
        return None

    # Dry run guard
    if Config.DRY_RUN:
        logger.info("[DRY_RUN] Would post draft %s: %s", draft_id, text)
        return None

    if twitter_client is None:
        raise RuntimeError("twitter_client is required for real posts")

    # Do the post with backoff
    tweet_kwargs = {'text': text}
    if in_reply_to_tweet_id:
        tweet_kwargs['in_reply_to_tweet_id'] = in_reply_to_tweet_id

    try:
        resp = _backoff_try(twitter_client.create_tweet, **tweet_kwargs)
        tweet_id = getattr(resp.data, "id", None) if resp and hasattr(resp, "data") else (resp.get("id") if isinstance(resp, dict) else None)
        if tweet_id:
            mark_posted(draft_id, str(tweet_id))
            logger.info("Posted draft %s => tweet %s", draft_id, tweet_id)
            return str(tweet_id)
        else:
            mark_failed(draft_id, "no_tweet_id")
            return None
    except Exception as e:
        logger.exception("Final posting failed: %s", str(e))
        mark_failed(draft_id, "exception:"+str(e))
        return None
