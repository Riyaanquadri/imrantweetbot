#!/usr/bin/env python3
"""Build a lightweight TF-IDF index for local RAG retrieval."""

import argparse
import json
from pathlib import Path
from typing import List

import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import normalize


def _load_file(file_path: Path) -> List[str]:
    records: List[str] = []
    with file_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                text = obj.get("text") or obj.get("content") or ""
                if text:
                    records.append(text)
                    continue
            except json.JSONDecodeError:
                pass
            records.append(line)
    return records


def load_corpus(path: Path) -> List[str]:
    """Load documents from a JSONL/plain text file or walk all files under a directory."""
    if path.is_dir():
        docs: List[str] = []
        for file in sorted(path.rglob("*")):
            if file.is_file() and not file.name.startswith("."):
                try:
                    docs.extend(_load_file(file))
                except UnicodeDecodeError:
                    continue
        return docs
    return _load_file(path)


def build_index(documents: List[str], max_features: int, ngram_high: int):
    vectorizer = TfidfVectorizer(
        max_features=max_features,
        ngram_range=(1, ngram_high),
        stop_words="english",
        strip_accents="ascii"
    )
    matrix = vectorizer.fit_transform(documents)
    matrix = normalize(matrix, norm="l2", copy=False)
    return {
        "matrix": matrix,
        "vectorizer": vectorizer,
        "documents": documents,
    }


def main():
    parser = argparse.ArgumentParser(description="Build TF-IDF index for quick RAG-style lookups.")
    parser.add_argument("--docs", default="data/facts.jsonl", help="Corpus file or directory of docs")
    parser.add_argument("--out", default="data/tfidf_index.joblib", help="Where to store the index bundle")
    parser.add_argument("--max-features", type=int, default=20000, help="Vocabulary size cap")
    parser.add_argument("--ngram-high", type=int, default=2, help="Highest ngram size")
    args = parser.parse_args()

    src = Path(args.docs)
    if not src.exists():
        raise FileNotFoundError(f"Input corpus not found: {src}")

    docs = load_corpus(src)
    if not docs:
        raise RuntimeError("No documents loaded; provide a non-empty corpus")

    bundle = build_index(docs, max_features=args.max_features, ngram_high=args.ngram_high)
    out_path = Path(args.out)
    if out_path.is_dir() or out_path.suffix == "":
        out_path = out_path.with_suffix(".joblib")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(bundle, out_path)
    print(f"Saved TF-IDF index with {len(docs)} docs to {out_path}")


if __name__ == "__main__":
    main()
