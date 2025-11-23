"""
Tweepy - Twitter API Client
A Python client for interacting with Twitter's REST and Stream APIs.
"""

__version__ = "0.1.0"
__author__ = "Developer"

from .client import TwitterClient
from .auth import Auth

__all__ = ["TwitterClient", "Auth"]
