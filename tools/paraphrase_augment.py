from dotenv import load_dotenv
load_dotenv(".env")

import os
import json
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.src.llm_provider import LLMProvider


def load_input(path):
    with open(path, "r", encoding="utf-8") as handle:
        lines = [json.loads(line) for line in handle if line.strip()]
    return lines


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="JSONL file with gold tweets, each line: {\"text\":\"...\"}")
    parser.add_argument("--out", default="data/paraphrases.jsonl", help="Output JSONL path")
    parser.add_argument("--copies", type=int, default=3, help="Number of paraphrases per input tweet")
    args = parser.parse_args()

    out_dir = os.path.dirname(args.out) or "."
    os.makedirs(out_dir, exist_ok=True)

    provider = LLMProvider()
    items = load_input(args.input)

    with open(args.out, "w", encoding="utf-8") as out_handle:
        for item in items:
            text = item.get("text") or item.get("tweet") or ""
            if not text:
                continue
            out_handle.write(json.dumps({"text": text, "source": "orig"}) + "\n")
            for _ in range(args.copies):
                paraphrase = provider.generate_paraphrase(text)
                out_handle.write(json.dumps({
                    "text": paraphrase,
                    "source": "paraphrase",
                    "orig": text
                }) + "\n")

    print("Wrote paraphrases to", args.out)


if __name__ == "__main__":
    main()
