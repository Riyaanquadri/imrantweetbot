"""
Utility Functions
Helper functions for the Tweepy client.
"""


def validate_tweet_text(text: str, max_length: int = 280) -> bool:
    """
    Validate tweet text.

    Args:
        text: Tweet text to validate
        max_length: Maximum allowed length

    Returns:
        True if valid, False otherwise
    """
    if not isinstance(text, str):
        return False
    if len(text) == 0 or len(text) > max_length:
        return False
    return True


def format_tweet(text: str) -> str:
    """
    Format tweet text.

    Args:
        text: Raw tweet text

    Returns:
        Formatted tweet text
    """
    return text.strip()
