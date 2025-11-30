#!/usr/bin/env python3
"""Generate engagement and duplicate reports from bot_audit.db."""
from __future__ import annotations

import argparse
import csv
import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).resolve().parents[1] / ".env")


def _connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def _cutoff(days: int) -> str:
    if days <= 0:
        return '1970-01-01T00:00:00'
    target = datetime.utcnow() - timedelta(days=days)
    return target.strftime('%Y-%m-%dT%H:%M:%S')


def fetch_variant_stats(conn: sqlite3.Connection, cutoff: str):
    cur = conn.cursor()
    cur.execute(
        """
        SELECT d.ab_variant,
               COUNT(*) AS total_posts,
               AVG(COALESCE(p.likes_count,0) + COALESCE(p.retweets_count,0) + COALESCE(p.replies_count,0)) AS avg_engagement,
               AVG(COALESCE(p.likes_count,0)) AS avg_likes,
               AVG(COALESCE(p.retweets_count,0)) AS avg_retweets,
               AVG(COALESCE(p.replies_count,0)) AS avg_replies
        FROM drafts d
        JOIN posts p ON p.draft_id = d.id
        WHERE p.posted_at >= ?
        GROUP BY d.ab_variant
        ORDER BY total_posts DESC
        """,
        (cutoff,),
    )
    rows = [dict(row) for row in cur.fetchall()]
    for row in rows:
        if row.get('avg_engagement') is None:
            row['avg_engagement'] = 0.0
    return rows


def fetch_duplicate_counts(conn: sqlite3.Connection, cutoff: str):
    cur = conn.cursor()
    cur.execute(
        """
        SELECT COUNT(*)
        FROM review_queue
        WHERE reason = 'duplicate_recent' AND created_at >= ?
        """,
        (cutoff,),
    )
    duplicates = cur.fetchone()[0]
    cur.execute(
        """
        SELECT COUNT(*)
        FROM drafts
        WHERE generated_at >= ?
        """,
        (cutoff,),
    )
    total = cur.fetchone()[0]
    return duplicates, total


def fetch_overall(conn: sqlite3.Connection, cutoff: str):
    cur = conn.cursor()
    cur.execute(
        """
        SELECT COUNT(*)
        FROM drafts d
        JOIN posts p ON p.draft_id = d.id
        WHERE p.posted_at >= ?
        """,
        (cutoff,),
    )
    posted = cur.fetchone()[0]
    return {
        "total_posted": posted,
    }


def main():
    parser = argparse.ArgumentParser(description="Report engagement metrics per variant")
    parser.add_argument("--db", type=Path, default=Path("bot_audit.db"), help="Path to bot_audit.db")
    parser.add_argument("--since-days", type=int, default=7, help="Only include tweets posted in the last N days")
    parser.add_argument("--json", action="store_true", help="Output JSON instead of human-readable text")
    parser.add_argument("--csv", type=Path, help="Optional path to write per-variant metrics as CSV")
    args = parser.parse_args()

    cutoff = _cutoff(args.since_days)
    conn = _connect(args.db)
    variant_stats = fetch_variant_stats(conn, cutoff)
    duplicates, total = fetch_duplicate_counts(conn, cutoff)
    overall = fetch_overall(conn, cutoff)
    conn.close()

    report = {
        "since": cutoff,
        "overall": overall,
        "variants": variant_stats,
        "duplicate_recent": {
            "count": duplicates,
            "total_generated": total,
            "rate": (duplicates / total) if total else 0.0,
        },
    }

    if args.csv and variant_stats:
        fieldnames = list(variant_stats[0].keys())
        with args.csv.open('w', newline='', encoding='utf-8') as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(variant_stats)
        print(f"Variant metrics written to {args.csv}")

    if args.json:
        print(json.dumps(report, indent=2))
        return

    print(f"Engagement report since {cutoff}")
    print(f"Total posted: {overall['total_posted']}")
    print("Duplicate skips: {count} / {total} ({rate:.2%})".format(
        count=report["duplicate_recent"]["count"],
        total=report["duplicate_recent"]["total_generated"],
        rate=report["duplicate_recent"]["rate"]
    ))
    if not variant_stats:
        print("No posts found in the given window")
        return

    for stat in variant_stats:
        label = stat.get('ab_variant') or 'default'
        print(
            f"Variant {label}: posts={stat['total_posts']} avg_eng={stat['avg_engagement'] or 0:.2f} "
            f"(likes {stat['avg_likes'] or 0:.2f}, retweets {stat['avg_retweets'] or 0:.2f}, replies {stat['avg_replies'] or 0:.2f})"
        )


if __name__ == "__main__":
    main()
