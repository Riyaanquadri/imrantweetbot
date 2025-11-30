#!/usr/bin/env python3
"""Export curated tweets/drafts from bot_audit.db into JSONL for training."""
from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path
from typing import Iterable, List, Sequence

from dotenv import load_dotenv

# Ensure .env is loaded so Config has access to keywords if present
load_dotenv(dotenv_path=Path(__file__).resolve().parents[1] / ".env")

from app.config import Config  # noqa: E402


def _infer_type(text: str, context: str | None) -> str:
    ctx = (context or "").lower()
    if ctx.startswith("reply_to:"):
        return "reply"
    lower = (text or "").lower()
    if any(term in lower for term in ("upgrade", "release", "launch")):
        return "announcement"
    if any(term in lower for term in ("how", "guide", "step")):
        return "howto"
    return "general"


def _infer_tone(text: str) -> str:
    lower = (text or "").lower()
    if any(word in lower for word in ("faster", "secure", "throughput")):
        return "authoritative"
    if any(word in lower for word in ("excited", "stoked", "thrilled")):
        return "evangelical"
    if len(text.split()) <= 18:
        return "concise"
    return "neutral"


def _infer_tags(text: str, keywords: Sequence[str]) -> List[str]:
    lower = (text or "").lower()
    tags = [kw for kw in keywords if kw.lower() in lower]
    return tags


def _load_rows(conn: sqlite3.Connection, statuses: Sequence[str], limit: int | None) -> Iterable[sqlite3.Row]:
    if not statuses:
        raise ValueError("At least one status must be provided")
    placeholders = ",".join("?" * len(statuses))
    query = f"""
        SELECT d.id, d.text, d.context, d.status, d.safety_flags, d.generated_at,
               d.posted_tweet_id, d.posted_at,
               COALESCE(p.likes_count, 0) AS likes,
               COALESCE(p.retweets_count, 0) AS retweets,
               COALESCE(p.replies_count, 0) AS replies
        FROM drafts d
        LEFT JOIN posts p ON p.draft_id = d.id
        WHERE d.status IN ({placeholders})
        ORDER BY COALESCE(d.posted_at, d.generated_at) DESC
    """
    params: List[object] = list(statuses)
    if limit is not None:
        query += " LIMIT ?"
        params.append(limit)
    cur = conn.cursor()
    cur.execute(query, params)
    for row in cur.fetchall():
        yield row


def export_dataset(
    db_path: Path,
    output_path: Path,
    statuses: Sequence[str],
    min_chars: int,
    keywords: Sequence[str],
    limit: int | None = None,
):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    exported = 0
    with output_path.open("w", encoding="utf-8") as fh:
        for row in _load_rows(conn, statuses, limit):
            text = row["text"] or ""
            if len(text.strip()) < min_chars:
                continue
            safety_raw = row["safety_flags"] or "[]"
            try:
                safety_flags = json.loads(safety_raw)
            except json.JSONDecodeError:
                safety_flags = []
            record = {
                "draft_id": row["id"],
                "text": text.strip(),
                "type": _infer_type(text, row["context"]),
                "tone": _infer_tone(text),
                "status": row["status"],
                "context": row["context"],
                "tags": _infer_tags(text, keywords),
                "engagement": int(row["likes"] or 0) + int(row["retweets"] or 0) + int(row["replies"] or 0),
                "likes": row["likes"],
                "retweets": row["retweets"],
                "replies": row["replies"],
                "posted_tweet_id": row["posted_tweet_id"],
                "generated_at": row["generated_at"],
                "posted_at": row["posted_at"],
                "safety_flags": safety_flags,
            }
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
            exported += 1
    conn.close()
    print(f"Exported {exported} rows to {output_path}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export tweets/drafts into JSONL")
    parser.add_argument("--db", type=Path, default=Path("bot_audit.db"), help="Path to bot_audit.db")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/dataset.jsonl"),
        help="Destination JSONL file",
    )
    parser.add_argument(
        "--status",
        dest="statuses",
        action="append",
        default=["posted", "queued", "approved"],
        help="Draft statuses to include (can specify multiple times)",
    )
    parser.add_argument("--min-chars", type=int, default=40, help="Minimum tweet length to export")
    parser.add_argument("--limit", type=int, help="Optional limit on number of rows")
    parser.add_argument(
        "--keywords",
        type=str,
        default=",".join(Config.PROJECT_KEYWORDS) if Config.PROJECT_KEYWORDS else "",
        help="Comma-separated keywords/tags to detect in tweets",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    keyword_list = [kw.strip() for kw in args.keywords.split(",") if kw.strip()]
    export_dataset(
        db_path=args.db,
        output_path=args.output,
        statuses=args.statuses,
        min_chars=args.min_chars,
        keywords=keyword_list,
        limit=args.limit,
    )
