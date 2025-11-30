#!/usr/bin/env python3
"""Kick off an OpenAI-style fine-tune job using prepared JSONL datasets."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from openai import OpenAI
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).resolve().parents[1] / ".env")

from app.config import Config  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description="Launch OpenAI fine-tune job")
    parser.add_argument("train_file", type=Path, help="Path to train JSONL")
    parser.add_argument("val_file", type=Path, help="Path to validation JSONL")
    parser.add_argument("--model", default="gpt-3.5-turbo", help="Base model to fine-tune")
    parser.add_argument("--suffix", default="campaign-tweets", help="Suffix for the fine-tune job")
    args = parser.parse_args()

    client = OpenAI(api_key=Config.OPENAI_API_KEY)

    def _upload(path: Path):
        with path.open("rb") as fh:
            resp = client.files.create(file=fh, purpose="fine-tune")
            return resp.id

    train_id = _upload(args.train_file)
    val_id = _upload(args.val_file)

    job = client.fine_tuning.jobs.create(
        model=args.model,
        training_file=train_id,
        validation_file=val_id,
        suffix=args.suffix,
        hyperparameters={
            "n_epochs": 3,
            "batch_size": 16,
            "learning_rate_multiplier": 0.5,
        },
    )

    print("Submitted fine-tune job:")
    print(json.dumps(job, indent=2))
    print("Track status with: openai fine_tuning.jobs.retrieve", job.id)


if __name__ == "__main__":
    main()
