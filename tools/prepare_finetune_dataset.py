#!/usr/bin/env python3
"""Prepare prompt/completion JSONL for supervised fine-tuning from exported dataset."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable, Tuple

from sklearn.model_selection import train_test_split

TEMPLATE = (
    "TYPE: {type}\n"
    "TONE: {tone}\n"
    "TAGS: {tags}\n"
    "ENGAGEMENT: {engagement}\n"
    "INSTRUCTIONS: Craft <=220 char tweet with one metric + CTA, factual, no financial advice.\n"
    "CONTEXT: {context}\n"
)


def load_records(path: Path) -> Iterable[dict]:
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            yield json.loads(line)


def to_prompt_completion(record: dict) -> Tuple[str, str]:
    prompt = TEMPLATE.format(
        type=record.get("type", "general"),
        tone=record.get("tone", "concise"),
        tags=",".join(record.get("tags", [])),
        engagement=record.get("engagement", 0),
        context=record.get("context") or record.get("text", "").strip(),
    )
    completion = record.get("text", "").strip()
    if not completion.endswith("\n"):
        completion += "\n"
    return prompt, completion


def write_jsonl(records: Iterable[Tuple[str, str]], path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for prompt, completion in records:
            fh.write(json.dumps({"prompt": prompt, "completion": completion}, ensure_ascii=False) + "\n")


def main():
    parser = argparse.ArgumentParser(description="Split dataset and emit prompt/completion JSONL files")
    parser.add_argument("input", type=Path, help="Input JSONL produced by export_tweets_to_jsonl.py")
    parser.add_argument("--output-dir", type=Path, default=Path("data/finetune"), help="Where to write train/val JSONL")
    parser.add_argument("--val-ratio", type=float, default=0.1, help="Validation split ratio")
    args = parser.parse_args()

    records = list(load_records(args.input))
    prompts = [to_prompt_completion(r) for r in records]
    train, val = train_test_split(prompts, test_size=args.val_ratio, random_state=42)

    write_jsonl(train, args.output_dir / "train.jsonl")
    write_jsonl(val, args.output_dir / "val.jsonl")
    print(f"Wrote {len(train)} train and {len(val)} validation samples to {args.output_dir}")


if __name__ == "__main__":
    main()
