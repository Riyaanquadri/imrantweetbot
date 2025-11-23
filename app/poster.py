from tweepy import Client
from .config import Config
from .logger import logger
from .safety import passes_safety

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
        if not passes_safety(text):
            logger.warning('Not posting: failed safety checks')
            return None
        if Config.DRY_RUN:
            logger.info('[DRY_RUN] Would post: %s', text)
            return None
        try:
            resp = self.client.create_tweet(text=text)
            tid = resp.data.get('id')
            logger.info('Posted tweet id=%s', tid)
            return tid
        except Exception as e:
            logger.exception('Error posting tweet')
            return None

    def reply(self, text: str, in_reply_to_tweet_id: str):
        if not passes_safety(text):
            logger.warning('Not replying: failed safety checks')
            return None
        if Config.DRY_RUN:
            logger.info('[DRY_RUN] Would reply: %s -> %s', text, in_reply_to_tweet_id)
            return None
        try:
            resp = self.client.create_tweet(text=text, in_reply_to_tweet_id=in_reply_to_tweet_id)
            logger.info('Posted reply id=%s', resp.data.get('id'))
            return resp.data.get('id')
        except Exception:
            logger.exception('Reply failed')
            return None
