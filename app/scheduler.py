import os
import random
from datetime import datetime, timezone
from typing import Dict, Optional

from apscheduler.schedulers.background import BackgroundScheduler

from .config import Config
from .llm_provider import LLMProvider
from .logger import logger
from .poster_safe import SafePoster
from .quota import get_quota_manager


def choose_ab_variant() -> str:
    """Pick a variant from AB_VARIANTS env list; fallback to default."""
    raw = os.getenv("AB_VARIANTS", "control").split(",")
    variants = [variant.strip() for variant in raw if variant.strip()]
    if not variants:
        return os.getenv("AB_DEFAULT_VARIANT", "control")
    return random.choice(variants)

class BotScheduler:
    def __init__(self, twitter_client=None, quota_manager=None):
        self.llm = LLMProvider()
        self.poster = SafePoster(twitter_client=twitter_client)
        self.scheduler = BackgroundScheduler()
        self.quota = quota_manager or get_quota_manager()
        self.ab_variant_tones = Config.AB_VARIANT_TONES

    def start(self):
        # Post job - use POST_INTERVAL_MINUTES if available, else POST_INTERVAL_HOURS
        post_interval = {}
        if hasattr(Config, 'POST_INTERVAL_MINUTES') and Config.POST_INTERVAL_MINUTES:
            post_interval['minutes'] = Config.POST_INTERVAL_MINUTES
        else:
            post_interval['hours'] = Config.POST_INTERVAL_HOURS
        
        self.scheduler.add_job(
            self.post_job,
            'interval',
            **post_interval,
            id='post_job',
            jitter=max(Config.POST_JITTER_SECONDS, 0),
            max_instances=1,
            coalesce=True,
            misfire_grace_time=300
        )
        # Mention poll job
        self.scheduler.add_job(
            self.mention_job,
            'interval',
            minutes=Config.MENTION_POLL_MINUTES,
            id='mention_job',
            jitter=max(Config.MENTION_JITTER_SECONDS, 0),
            max_instances=1,
            coalesce=True,
            misfire_grace_time=300
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
        variant = choose_ab_variant() if Config.AB_TEST_ENABLED else os.getenv('AB_DEFAULT_VARIANT', 'control')
        tone = self.ab_variant_tones.get(variant, 'concise') if variant else 'concise'
        if variant:
            logger.info('Selected A/B variant %s (tone=%s)', variant, tone)
        tweet = self.llm.generate_tweet(context, tone=tone)
        self.poster.post(
            tweet,
            context=context,
            force_review=Config.REQUIRE_POST_APPROVAL,
            ab_variant=variant
        )

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
                    priority='high' if entry['is_big'] else 'normal',
                    ab_variant=None
                )
        except Exception:
            logger.exception('Error in mention_job')

    def shutdown(self):
        self.scheduler.shutdown()
