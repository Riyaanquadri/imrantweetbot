# test_runner.py
"""Local dry-run harness for the safety/audit/posting pipeline."""
import time

from app.src.db import init_db, get_conn
from app.src.posting import post_safe
from app.src.safety import passes_safety


class MockTwitterClient:
    """Tiny stand-in for Tweepy.Client used by post_safe."""

    class Resp:
        def __init__(self, tid):
            self.data = {"id": tid}

    def __init__(self):
        self.counter = 1_000

    def create_tweet(self, text):
        self.counter += 1
        print("[MockTwitterClient] create_tweet ->", text[:80])
        return MockTwitterClient.Resp(self.counter)


def run_tests():
    print("Initializing DB...")
    init_db()
    client = MockTwitterClient()

    samples = [
        ("Short update: testnet txs + new commit. Not financial advice.", "weekly summary"),
        ("Buy now! guaranteed returns!", "spammy sample"),
        ("This contains shit which is profanity", "profanity sample"),
        ("A long informative tweet " + "x" * 200, "too long sample"),
    ]

    for text, ctx in samples:
        ok, reason = passes_safety(text)
        print(f"\nContext: {ctx}\nPreview: {text[:120]!r}\npasses_safety -> {ok} ({reason})")
        tid = post_safe(text, context=ctx, twitter_client=client)
        print("post_safe returned:", tid)
        time.sleep(0.3)

    print("\nDB preview (latest rows):")
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, status, substr(text,1,60) as preview, safety_flags, posted_tweet_id "
        "FROM drafts ORDER BY id DESC LIMIT 10"
    )
    for row in cur.fetchall():
        print(row)
    conn.close()


if __name__ == "__main__":
    run_tests()
