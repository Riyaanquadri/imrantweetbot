"""
Authentication Module
Handle Twitter API authentication.
"""

import os
from typing import Optional


class Auth:
    """Handle Twitter API authentication."""

    def __init__(self, api_key: Optional[str] = None, api_secret: Optional[str] = None,
                 access_token: Optional[str] = None, access_secret: Optional[str] = None):
        """
        Initialize authentication.

        Args:
            api_key: Twitter API Key (or from env TWITTER_API_KEY)
            api_secret: Twitter API Secret (or from env TWITTER_API_SECRET)
            access_token: Twitter Access Token (or from env TWITTER_ACCESS_TOKEN)
            access_secret: Twitter Access Secret (or from env TWITTER_ACCESS_SECRET)
        """
        self.api_key = api_key or os.getenv("TWITTER_API_KEY")
        self.api_secret = api_secret or os.getenv("TWITTER_API_SECRET")
        self.access_token = access_token or os.getenv("TWITTER_ACCESS_TOKEN")
        self.access_secret = access_secret or os.getenv("TWITTER_ACCESS_SECRET")

        if not all([self.api_key, self.api_secret, self.access_token, self.access_secret]):
            raise ValueError("Missing required authentication credentials")

    def get_credentials(self) -> dict:
        """Get authentication credentials."""
        return {
            "api_key": self.api_key,
            "api_secret": self.api_secret,
            "access_token": self.access_token,
            "access_secret": self.access_secret,
        }
