from apscheduler.schedulers.background import BackgroundScheduler
from .logger import logger
from .llm_provider import LLMProvider
from .poster_safe import SafePoster
from .config import Config
import time

class BotScheduler:
    def __init__(self):
        self.llm = LLMProvider()
        self.poster = SafePoster()
        self.scheduler = BackgroundScheduler()

    def start(self):
        # Post job
        self.scheduler.add_job(self.post_job, 'interval', hours=Config.POST_INTERVAL_HOURS, id='post_job')
        # Mention poll job
        self.scheduler.add_job(self.mention_job, 'interval', minutes=Config.MENTION_POLL_MINUTES, id='mention_job')
        self.scheduler.start()
        logger.info('Scheduler started')

    def post_job(self):
        # Build context: in production read feeds, on-chain data, github commits
        context = 'Project update: commits + testnet activity'
        tweet = self.llm.generate_tweet(context)
        self.poster.post(tweet, context=context)

    def mention_job(self):
        # Simple mentions poll: fetch mentions and reply when keywords match
        try:
            me = self.poster.client.get_me()
            uid = me.data.get('id')
            mentions = self.poster.client.get_users_mentions(id=uid, max_results=20)
            if not mentions or not mentions.data:
                return
            for mention in reversed(mentions.data):
                text = mention.text
                tid = mention.id
                if any(k.lower() in text.lower() for k in Config.PROJECT_KEYWORDS):
                    reply = self.llm.generate_reply(text)
                    # include screen name
                    # fetch user info
                    user = self.poster.client.get_user(id=mention.author_id)
                    username = getattr(user.data, 'username', '')
                    reply_text = f"@{username} {reply}"
                    self.poster.reply(reply_text, tid, context=f'mention_reply:{tid}')
        except Exception:
            logger.exception('Error in mention_job')

    def shutdown(self):
        self.scheduler.shutdown()
