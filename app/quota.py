"""Quota management for posts and replies to keep the bot under platform limits."""
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from threading import RLock
from typing import Deque, Dict, Optional, Tuple

from .config import Config
from .logger import logger

QuotaStatus = Tuple[bool, str]


class QuotaManager:
    """Tracks post/reply budgets with sliding windows."""

    DAY_SECONDS = 24 * 60 * 60

    def __init__(self):
        self._lock = RLock()
        self._post_events: Deque[datetime] = deque()
        self._reply_daily_events: Deque[datetime] = deque()
        self._reply_hour_events: Deque[datetime] = deque()
        self._reply_user_hour_events: Dict[str, Deque[datetime]] = defaultdict(deque)
        self._monthly_events: Deque[datetime] = deque()
        self._month_window = int(Config.MONTHLY_WRITE_LIMIT_DAYS) * self.DAY_SECONDS

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    def _prune(self, events: Deque[datetime], window_seconds: int):
        cutoff = self._now() - timedelta(seconds=window_seconds)
        while events and events[0] < cutoff:
            events.popleft()

    def _check_monthly_budget(self) -> QuotaStatus:
        if Config.MONTHLY_WRITE_LIMIT <= 0:
            return True, ""
        self._prune(self._monthly_events, self._month_window)
        if len(self._monthly_events) >= Config.MONTHLY_WRITE_LIMIT:
            return False, "monthly_write_limit_reached"
        return True, ""

    def can_post(self) -> QuotaStatus:
        with self._lock:
            monthly_ok, reason = self._check_monthly_budget()
            if not monthly_ok:
                return False, reason

            post_cap = max(Config.POSTS_PER_DAY, 1)
            self._prune(self._post_events, self.DAY_SECONDS)
            if len(self._post_events) >= post_cap:
                return False, "post_daily_quota_reached"
            return True, ""

    def record_post(self):
        with self._lock:
            ts = self._now()
            self._post_events.append(ts)
            self._monthly_events.append(ts)
            logger.debug("Recorded post event for quota tracking")

    def can_reply(self, author_id: Optional[str]) -> QuotaStatus:
        with self._lock:
            monthly_ok, reason = self._check_monthly_budget()
            if not monthly_ok:
                return False, reason

            daily_cap = max(Config.REPLIES_PER_DAY, 1)
            hourly_cap = max(Config.GLOBAL_REPLIES_PER_HOUR, 1)
            per_user_cap = max(Config.REPLIES_PER_USER_PER_HOUR, 1)

            self._prune(self._reply_daily_events, self.DAY_SECONDS)
            if len(self._reply_daily_events) >= daily_cap:
                return False, "reply_daily_quota_reached"

            self._prune(self._reply_hour_events, 3600)
            if len(self._reply_hour_events) >= hourly_cap:
                return False, "reply_global_hourly_quota_reached"

            if author_id:
                key = str(author_id)
            else:
                key = "unknown"
            user_events = self._reply_user_hour_events[key]
            self._prune(user_events, 3600)
            if len(user_events) >= per_user_cap:
                return False, "reply_user_hourly_quota_reached"

            return True, ""

    def record_reply(self, author_id: Optional[str]):
        with self._lock:
            ts = self._now()
            self._reply_daily_events.append(ts)
            self._reply_hour_events.append(ts)
            key = str(author_id) if author_id else "unknown"
            self._reply_user_hour_events[key].append(ts)
            self._monthly_events.append(ts)
            logger.debug("Recorded reply event for quota tracking (user=%s)", key)


_quota_manager: Optional[QuotaManager] = None


def get_quota_manager() -> QuotaManager:
    global _quota_manager
    if _quota_manager is None:
        _quota_manager = QuotaManager()
    return _quota_manager
