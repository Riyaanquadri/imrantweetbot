from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timezone
from typing import Dict, Optional

from .logger import logger
from .llm_provider import LLMProvider
from .poster_safe import SafePoster
from .config import Config
from .quota import get_quota_manager

class BotScheduler:
    def __init__(self):
        self.llm = LLMProvider()
        self.poster = SafePoster()
        self.scheduler = BackgroundScheduler()
        self.quota = get_quota_manager()

    def start(self):
        # Post job
        self.scheduler.add_job(
            self.post_job,
            'interval',
            hours=Config.POST_INTERVAL_HOURS,
            id='post_job',
            jitter=max(Config.POST_JITTER_SECONDS, 0)
        )
        # Mention poll job
        self.scheduler.add_job(
            self.mention_job,
            'interval',
            minutes=Config.MENTION_POLL_MINUTES,
            id='mention_job',
            jitter=max(Config.MENTION_JITTER_SECONDS, 0)
        )
        self.scheduler.start()
        logger.info('Scheduler started')

    def post_job(self):
        # Build context: in production read feeds, on-chain data, github commits
        can_post, reason = self.quota.can_post()
        if not can_post:
            logger.info('Skipping post job: %s', reason)
            return
        context = 'Project update: commits + testnet activity'
        tweet = self.llm.generate_tweet(context)
        self.poster.post(tweet, context=context, force_review=Config.REQUIRE_POST_APPROVAL)

    def mention_job(self):
        # Simple mentions poll: fetch mentions and reply when keywords match
        try:
            me = self.poster.client.get_me()
            uid = me.data.get('id')
            mentions = self.poster.client.get_users_mentions(
                id=uid,
                max_results=Config.MENTION_MAX_RESULTS,
                expansions=['author_id'],
                tweet_fields=['created_at','author_id'],
                user_fields=['username','public_metrics']
            )
            if not mentions or not mentions.data:
                return
            user_map: Dict[str, object] = {}
            includes = getattr(mentions, 'includes', None)
            if includes:
                users = getattr(includes, 'users', None)
                if users:
                    for usr in users:
                        user_map[str(getattr(usr, 'id', ''))] = usr

            def _extract_user(author_id: Optional[str]):
                if not author_id:
                    return None
                if author_id in user_map:
                    return user_map[author_id]
                try:
                    resp = self.poster.client.get_user(id=author_id, user_fields=['username','public_metrics'])
                    return getattr(resp, 'data', None)
                except Exception:
                    logger.exception('Failed to fetch user %s metadata', author_id)
                    return None

            mention_entries = []
            for mention in mentions.data:
                text = mention.text
                if not text or not any(k.lower() in text.lower() for k in Config.PROJECT_KEYWORDS):
                    continue
                author_id = getattr(mention, 'author_id', None)
                user = _extract_user(str(author_id) if author_id else None)
                username = getattr(user, 'username', '') if user else ''
                metrics = getattr(user, 'public_metrics', {}) if user else {}
                followers = 0
                if isinstance(metrics, dict):
                    followers = metrics.get('followers_count', 0)
                else:
                    followers = getattr(metrics, 'followers_count', 0)
                is_big = followers >= Config.BIG_ACCOUNT_FOLLOWERS
                mention_entries.append({
                    'mention': mention,
                    'text': text,
                    'username': username,
                    'author_id': str(author_id) if author_id else None,
                    'followers': followers,
                    'is_big': is_big,
                    'created_at': getattr(mention, 'created_at', None)
                })

            if not mention_entries:
                return

            def _sort_key(entry):
                created = entry['created_at']
                if isinstance(created, datetime):
                    created_at = created
                else:
                    created_at = datetime.now(timezone.utc)
                return (
                    0 if entry['is_big'] else 1,
                    created_at,
                    -entry['followers']
                )

            for entry in sorted(mention_entries, key=_sort_key):
                author_id = entry['author_id']
                can_reply, reason = self.quota.can_reply(author_id)
                if not can_reply:
                    logger.info('Skipping reply to mention %s: %s', entry['mention'].id, reason)
                    continue
                reply = self.llm.generate_reply(entry['text'])
                username = entry['username'] or 'friend'
                reply_text = f"@{username} {reply}".strip()
                self.poster.reply(
                    reply_text,
                    entry['mention'].id,
                    context=f"mention_reply:{entry['mention'].id}",
                    author_id=author_id,
                    priority='high' if entry['is_big'] else 'normal'
                )
        except Exception:
            logger.exception('Error in mention_job')

    def shutdown(self):
        self.scheduler.shutdown()
