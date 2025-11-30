#!/usr/bin/env python3
"""Fetch engagement metrics for posted tweets and update bot_audit DB."""
from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path
from typing import List

from dotenv import load_dotenv
from tweepy import Client

load_dotenv(dotenv_path=Path(__file__).resolve().parents[1] / ".env")

from app.config import Config  # noqa: E402


def batched(iterable: List[str], size: int):
    for idx in range(0, len(iterable), size):
        yield iterable[idx : idx + size]


def fetch_metrics(ids: List[str]) -> dict:
    client = Client(bearer_token=Config.X_BEARER_TOKEN)
    resp = client.get_tweets(ids=ids, tweet_fields=["public_metrics"])
    metrics = {}
    if not resp or not getattr(resp, "data", None):
        return metrics
    for tweet in resp.data:
        pm = getattr(tweet, "public_metrics", {}) or {}
        metrics[str(tweet.id)] = {
            "likes": pm.get("like_count", 0),
            "retweets": pm.get("retweet_count", 0),
            "replies": pm.get("reply_count", 0),
            "quotes": pm.get("quote_count", 0),
        }
    return metrics


def main():
    parser = argparse.ArgumentParser(description="Update engagement metrics for posted tweets")
    parser.add_argument("--db", type=Path, default=Path("bot_audit.db"), help="Path to bot_audit.db")
    parser.add_argument("--limit", type=int, default=200, help="Maximum tweets to refresh per run")
    parser.add_argument(
        "--max-age-hours",
        type=int,
        default=6,
        help="Only refresh rows older than this many hours (0 = ignore age)",
    )
    args = parser.parse_args()

    if not Config.X_BEARER_TOKEN:
        raise SystemExit("X_BEARER_TOKEN missing; cannot fetch metrics")

    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    age_clause = ""
    params = []
    if args.max_age_hours > 0:
        age_clause = "AND (last_updated IS NULL OR last_updated < datetime('now', ?))"
        params.append(f"-{args.max_age_hours} hours")
    params.append(args.limit)
    cur.execute(
        f"""
        SELECT tweet_id
        FROM posts
        WHERE tweet_id IS NOT NULL
        {age_clause}
        ORDER BY posted_at DESC
        LIMIT ?
        """,
        params,
    )
    rows = cur.fetchall()
    tweet_ids = [row["tweet_id"] for row in rows if row["tweet_id"]]
    if not tweet_ids:
        print("No tweets eligible for refresh")
        conn.close()
        return

    updated = 0
    for batch in batched(tweet_ids, 100):
        metrics = fetch_metrics(batch)
        for tweet_id, data in metrics.items():
            cur.execute(
                """
                UPDATE posts
                SET likes_count = ?,
                    retweets_count = ?,
                    replies_count = ?,
                    last_updated = CURRENT_TIMESTAMP
                WHERE tweet_id = ?
                """,
                (data["likes"], data["retweets"], data["replies"], tweet_id),
            )
            updated += cur.rowcount
        conn.commit()
    conn.close()
    print(f"Updated metrics for {updated} tweets")


if __name__ == "__main__":
    main()
