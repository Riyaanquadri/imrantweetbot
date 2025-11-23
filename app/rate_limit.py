"""
Rate-limiting wrapper with exponential backoff for Tweepy API calls.

Handles 429 (rate limit) responses and retries with exponential backoff.
Respects X-Rate-Limit-Reset header for intelligent backoff timing.
"""
import time
import logging
from typing import Callable, Any, Optional

logger = logging.getLogger('crypto_ai_bot')

class RateLimitException(Exception):
    """Raised when rate limit is hit and max retries exceeded."""
    pass


class RateLimitWrapper:
    """Wraps Tweepy client calls with automatic retry logic."""
    
    MAX_RETRIES = 6
    INITIAL_BACKOFF = 1  # seconds
    MAX_BACKOFF = 300  # 5 minutes
    
    @staticmethod
    def _get_retry_after(exception: Exception) -> Optional[int]:
        """Extract Retry-After header or X-Rate-Limit-Reset from exception."""
        try:
            if hasattr(exception, 'response'):
                headers = getattr(exception.response, 'headers', {})
                if 'retry-after' in headers:
                    return int(headers['retry-after'])
                if 'x-rate-limit-reset' in headers:
                    reset_time = int(headers['x-rate-limit-reset'])
                    return max(1, reset_time - int(time.time()))
            return None
        except Exception:
            return None
    
    @staticmethod
    def _is_rate_limit_error(exception: Exception) -> bool:
        """Check if exception is a 429 rate limit error."""
        try:
            if hasattr(exception, 'response'):
                status_code = getattr(exception.response, 'status_code', None)
                return status_code == 429
            return False
        except Exception:
            return False
    
    @staticmethod
    def call_with_backoff(
        func: Callable,
        *args,
        max_retries: int = MAX_RETRIES,
        initial_backoff: int = INITIAL_BACKOFF,
        **kwargs
    ) -> Any:
        """
        Execute a function with exponential backoff on rate limits.
        
        Args:
            func: Callable to execute (e.g., client.create_tweet)
            *args: Positional arguments for func
            max_retries: Number of retry attempts
            initial_backoff: Initial backoff time in seconds
            **kwargs: Keyword arguments for func
            
        Returns:
            Result of func(*args, **kwargs)
            
        Raises:
            RateLimitException: If rate limit persists after max retries
            Original exception: If not a rate limit error
        """
        backoff = initial_backoff
        
        for attempt in range(max_retries + 1):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                if not RateLimitWrapper._is_rate_limit_error(e):
                    # Not a rate limit error, raise immediately
                    raise
                
                if attempt >= max_retries:
                    logger.error(f'Rate limit exceeded after {max_retries} retries')
                    raise RateLimitException(f'Rate limit not recovered after {max_retries} attempts') from e
                
                # Calculate backoff time
                retry_after = RateLimitWrapper._get_retry_after(e)
                sleep_time = retry_after if retry_after else min(backoff, RateLimitWrapper.MAX_BACKOFF)
                
                logger.warning(
                    f'Rate limit hit (attempt {attempt + 1}/{max_retries}). '
                    f'Backing off for {sleep_time}s'
                )
                time.sleep(sleep_time)
                backoff = min(backoff * 2, RateLimitWrapper.MAX_BACKOFF)
        
        # Shouldn't reach here
        raise RateLimitException('Unexpected rate limit retry exhaustion')


# Convenience decorators for common Tweepy operations
def with_rate_limit_backoff(max_retries: int = RateLimitWrapper.MAX_RETRIES):
    """Decorator to add rate limit handling to any function."""
    def decorator(func: Callable) -> Callable:
        def wrapper(*args, **kwargs):
            return RateLimitWrapper.call_with_backoff(func, *args, max_retries=max_retries, **kwargs)
        return wrapper
    return decorator
