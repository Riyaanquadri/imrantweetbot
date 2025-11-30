"""
Adapter to make OAuth2Client API compatible with Tweepy Client interface.
Allows scheduler to work with OAuth2 without major refactoring.
"""
from typing import Optional, NamedTuple
from app.oauth2_client import OAuth2Client
from app.logger import logger

class User(NamedTuple):
    """Mock Tweepy User object."""
    id: str
    username: str
    public_metrics: dict = {}
    verified: bool = False

class Tweet(NamedTuple):
    """Mock Tweepy Tweet object."""
    id: str
    text: str
    author_id: str = None
    created_at: str = None
    public_metrics: dict = None
    conversation_id: str = None

class Data(NamedTuple):
    """Mock Tweepy Response.data."""
    value: object
    
    def __getattr__(self, name):
        # For compatibility, allow direct attribute access
        if hasattr(self.value, name):
            return getattr(self.value, name)
        raise AttributeError(f"{name}")

class Response(NamedTuple):
    """Mock Tweepy Response object."""
    data: object

class OAuth2ClientAdapter:
    """Adapter to make OAuth2Client compatible with Tweepy Client interface."""
    
    def __init__(self, oauth2_client: OAuth2Client):
        """Initialize adapter with OAuth2Client."""
        self.oauth2 = oauth2_client
        self.data = None  # Last response data
    
    def get_me(self) -> Response:
        """Get authenticated user info - Tweepy compatible."""
        resp = self.oauth2.get_me()
        user_data = resp['data']
        user = User(
            id=user_data['id'],
            username=user_data['username']
        )
        return Response(data=user)
    
    def create_tweet(self, text: str, **kwargs) -> Response:
        """Create a tweet - Tweepy compatible."""
        try:
            resp = self.oauth2.create_tweet(text=text)
            tweet_data = resp['data']
            tweet = Tweet(
                id=tweet_data['id'],
                text=text
            )
            return Response(data=tweet)
        except Exception as e:
            logger.error(f"Failed to create tweet: {e}")
            raise
    
    def create_reply(self, text: str, in_reply_to_tweet_id: str, **kwargs) -> Response:
        """Create a reply - Tweepy compatible."""
        try:
            resp = self.oauth2.create_reply(text=text, in_reply_to_tweet_id=in_reply_to_tweet_id)
            tweet_data = resp['data']
            tweet = Tweet(
                id=tweet_data['id'],
                text=text,
                conversation_id=in_reply_to_tweet_id
            )
            return Response(data=tweet)
        except Exception as e:
            logger.error(f"Failed to create reply: {e}")
            raise
    
    def get_users(self, ids: list, **kwargs) -> Response:
        """Get multiple users by ID - Tweepy compatible."""
        # OAuth2 API requires individual calls, so batch them
        users = []
        for user_id in ids:
            try:
                # Get user by ID (not implemented in OAuth2Client, but we can work around)
                # For now, return mock data
                users.append(User(id=user_id, username=f"user_{user_id}"))
            except Exception as e:
                logger.warning(f"Failed to get user {user_id}: {e}")
        return Response(data=users)
    
    def get_search_recent_tweets(self, query: str, max_results: int = 10, 
                                 expansions: list = None, tweet_fields: list = None,
                                 user_fields: list = None, **kwargs) -> Response:
        """Search recent tweets - Tweepy compatible."""
        # This would require the search/recent_tweets endpoint
        # Not implemented in basic OAuth2Client yet
        logger.warning("get_search_recent_tweets not yet implemented for OAuth2")
        return Response(data=[])
    
    def get_liked_tweets(self, id: str, max_results: int = 10, **kwargs) -> Response:
        """Get user's liked tweets - Tweepy compatible."""
        logger.warning("get_liked_tweets not yet implemented for OAuth2")
        return Response(data=[])
    
    def like(self, tweet_id: str, **kwargs) -> Response:
        """Like a tweet - Tweepy compatible."""
        try:
            resp = self.oauth2.like_tweet(tweet_id)
            return Response(data={'liked': resp['data'].get('liked', True)})
        except Exception as e:
            logger.error(f"Failed to like tweet: {e}")
            raise
    
    def retweet(self, id: str, **kwargs) -> Response:
        """Retweet - Tweepy compatible."""
        try:
            resp = self.oauth2.retweet(id)
            return Response(data={'retweeted': resp['data'].get('retweeted', True)})
        except Exception as e:
            logger.error(f"Failed to retweet: {e}")
            raise
    
    def delete_tweet(self, id: str, **kwargs) -> Response:
        """Delete a tweet - Tweepy compatible."""
        try:
            resp = self.oauth2.delete_tweet(id)
            return Response(data={'deleted': resp['data'].get('deleted', True)})
        except Exception as e:
            logger.error(f"Failed to delete tweet: {e}")
            raise
