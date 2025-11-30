"""
OAuth2 Twitter API v2 Client using bearer token authentication.

Provides a wrapper around Twitter API v2 endpoints for posting, replying, and fetching mentions.
Uses direct HTTP requests instead of Tweepy (which requires OAuth1 consumer/access credentials).
"""
import requests
from typing import Optional, Dict, Any
import time
from app.logger import logger

class OAuth2Client:
    """Wrapper for Twitter API v2 using OAuth2 bearer token."""
    
    def __init__(self, bearer_token: str):
        """Initialize with OAuth2 bearer token."""
        self.bearer_token = bearer_token
        self.headers = {"Authorization": f"Bearer {bearer_token}"}
        self.base_url = "https://api.twitter.com/2"
        self.user_id = None  # Cache authenticated user ID
    
    def get_me(self) -> Dict[str, Any]:
        """Get authenticated user info."""
        response = requests.get(f"{self.base_url}/users/me", headers=self.headers)
        response.raise_for_status()
        data = response.json()
        self.user_id = data['data']['id']
        return data
    
    def create_tweet(self, text: str, reply_settings: Optional[str] = None) -> Dict[str, Any]:
        """Create a new tweet.
        
        Args:
            text: Tweet text (max 280 characters)
            reply_settings: "everyone", "following", or "mentionedUsers"
        
        Returns:
            Response with created tweet ID and data
        """
        payload = {"text": text}
        if reply_settings:
            payload["reply_settings"] = reply_settings
        
        response = requests.post(
            f"{self.base_url}/tweets",
            json=payload,
            headers=self.headers
        )
        response.raise_for_status()
        return response.json()
    
    def create_reply(self, text: str, in_reply_to_tweet_id: str) -> Dict[str, Any]:
        """Create a reply to a tweet.
        
        Args:
            text: Reply text (max 280 characters)
            in_reply_to_tweet_id: ID of tweet to reply to
        
        Returns:
            Response with created tweet ID and data
        """
        payload = {
            "text": text,
            "reply": {
                "in_reply_to_tweet_id": in_reply_to_tweet_id
            }
        }
        
        response = requests.post(
            f"{self.base_url}/tweets",
            json=payload,
            headers=self.headers
        )
        response.raise_for_status()
        return response.json()
    
    def get_mentions(self, max_results: int = 10, user_id: Optional[str] = None, 
                     start_time: Optional[str] = None, pagination_token: Optional[str] = None) -> Dict[str, Any]:
        """Get mentions for the authenticated user.
        
        Args:
            max_results: Number of results (10-100)
            user_id: User ID to get mentions for (default: authenticated user)
            start_time: ISO 8601 timestamp to start from (e.g., "2023-01-01T00:00:00Z")
            pagination_token: Token for pagination
        
        Returns:
            Response with mentions data and metadata
        """
        if not user_id:
            if not self.user_id:
                me = self.get_me()
                user_id = me['data']['id']
            else:
                user_id = self.user_id
        
        params = {
            'max_results': min(max_results, 100),  # API max is 100
            'expansions': 'author_id,in_reply_to_user_id',
            'tweet.fields': 'created_at,public_metrics,author_id,conversation_id',
            'user.fields': 'username,public_metrics,verified'
        }
        
        if start_time:
            params['start_time'] = start_time
        if pagination_token:
            params['pagination_token'] = pagination_token
        
        response = requests.get(
            f"{self.base_url}/users/{user_id}/mentions",
            headers=self.headers,
            params=params
        )
        response.raise_for_status()
        return response.json()
    
    def get_tweet(self, tweet_id: str) -> Dict[str, Any]:
        """Get a specific tweet.
        
        Args:
            tweet_id: Tweet ID
        
        Returns:
            Response with tweet data
        """
        params = {
            'expansions': 'author_id,in_reply_to_user_id',
            'tweet.fields': 'created_at,public_metrics,author_id,conversation_id',
            'user.fields': 'username,public_metrics,verified'
        }
        
        response = requests.get(
            f"{self.base_url}/tweets/{tweet_id}",
            headers=self.headers,
            params=params
        )
        response.raise_for_status()
        return response.json()
    
    def get_user(self, username: str) -> Dict[str, Any]:
        """Get user info by username.
        
        Args:
            username: Twitter username (without @)
        
        Returns:
            Response with user data
        """
        params = {
            'user.fields': 'username,public_metrics,verified,created_at'
        }
        
        response = requests.get(
            f"{self.base_url}/users/by/username/{username}",
            headers=self.headers,
            params=params
        )
        response.raise_for_status()
        return response.json()
    
    def delete_tweet(self, tweet_id: str) -> Dict[str, Any]:
        """Delete a tweet.
        
        Args:
            tweet_id: Tweet ID to delete
        
        Returns:
            Response with deletion confirmation
        """
        response = requests.delete(
            f"{self.base_url}/tweets/{tweet_id}",
            headers=self.headers
        )
        response.raise_for_status()
        return response.json()
    
    def like_tweet(self, tweet_id: str) -> Dict[str, Any]:
        """Like a tweet.
        
        Args:
            tweet_id: Tweet ID to like
        
        Returns:
            Response with like confirmation
        """
        if not self.user_id:
            me = self.get_me()
        
        payload = {"tweet_id": tweet_id}
        response = requests.post(
            f"{self.base_url}/users/{self.user_id}/likes",
            json=payload,
            headers=self.headers
        )
        response.raise_for_status()
        return response.json()
    
    def retweet(self, tweet_id: str) -> Dict[str, Any]:
        """Retweet a tweet.
        
        Args:
            tweet_id: Tweet ID to retweet
        
        Returns:
            Response with retweet confirmation
        """
        if not self.user_id:
            me = self.get_me()
        
        payload = {"tweet_id": tweet_id}
        response = requests.post(
            f"{self.base_url}/users/{self.user_id}/retweets",
            json=payload,
            headers=self.headers
        )
        response.raise_for_status()
        return response.json()
