from tweepy import Client
from .logger import logger
from app.src.posting import post_safe

class Poster:
    def __init__(self):
        self.client = Client(
            bearer_token=Config.X_BEARER_TOKEN,
            consumer_key=Config.X_API_KEY,
            consumer_secret=Config.X_API_SECRET,
            access_token=Config.X_ACCESS_TOKEN,
            access_token_secret=Config.X_ACCESS_SECRET,
            wait_on_rate_limit=True
        )

    def post(self, text: str):
        tweet_id = post_safe(
            text=text,
            context='bot_post',
            twitter_client=self.client
        )
        if tweet_id:
            logger.info('Posted tweet id=%s via post_safe', tweet_id)
        return tweet_id

    def reply(self, text: str, in_reply_to_tweet_id: str):
        tweet_id = post_safe(
            text=text,
            context=f'reply_to:{in_reply_to_tweet_id}',
            twitter_client=self.client,
            in_reply_to_tweet_id=in_reply_to_tweet_id
        )
        if tweet_id:
            logger.info('Posted reply id=%s via post_safe', tweet_id)
        return tweet_id
