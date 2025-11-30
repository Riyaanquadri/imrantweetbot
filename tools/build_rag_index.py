#!/usr/bin/env python3
"""Build a lightweight TF-IDF context index for retrieval-augmented prompts."""
from __future__ import annotations

import argparse
import pickle
import re
from pathlib import Path
from typing import Iterable, List

from dotenv import load_dotenv
from sklearn.feature_extraction.text import TfidfVectorizer

load_dotenv(dotenv_path=Path(__file__).resolve().parents[1] / ".env")

DEFAULT_EXTENSIONS = {".md", ".txt", ".rst"}


def _read_file(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="latin-1", errors="ignore")


def _chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> List[str]:
    clean = re.sub(r"\s+", " ", text).strip()
    if not clean:
        return []
    chunks = []
    start = 0
    text_len = len(clean)
    while start < text_len:
        end = min(text_len, start + chunk_size)
        chunks.append(clean[start:end].strip())
        if end >= text_len:
            break
        start = max(0, end - overlap)
    return [c for c in chunks if c]


def _gather_documents(
    sources: Iterable[Path],
    extensions: set[str],
    chunk_size: int,
    overlap: int,
) -> List[tuple[str, dict]]:
    docs: List[tuple[str, dict]] = []
    for src in sources:
        if src.is_file() and src.suffix.lower() in extensions:
            chunks = _chunk_text(_read_file(src), chunk_size=chunk_size, overlap=overlap)
            docs.extend((chunk, {"source": str(src), "chunk_id": idx}) for idx, chunk in enumerate(chunks))
        elif src.is_dir():
            for path in src.rglob("*"):
                if path.is_file() and path.suffix.lower() in extensions:
                    chunks = _chunk_text(_read_file(path), chunk_size=chunk_size, overlap=overlap)
                    docs.extend((chunk, {"source": str(path), "chunk_id": idx}) for idx, chunk in enumerate(chunks))
    return docs


def build_index(sources: List[Path], output: Path, chunk_size: int, overlap: int):
    docs_with_meta = _gather_documents(sources, DEFAULT_EXTENSIONS, chunk_size=chunk_size, overlap=overlap)
    if not docs_with_meta:
        raise SystemExit("No documents found for indexing")
    texts = [text for text, _ in docs_with_meta]
    metadata = [meta for _, meta in docs_with_meta]
    vectorizer = TfidfVectorizer(ngram_range=(1, 2), stop_words="english")
    matrix = vectorizer.fit_transform(texts)
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "vectorizer": vectorizer,
        "matrix": matrix,
        "documents": texts,
        "metadata": metadata,
        "chunk_size": chunk_size,
        "overlap": overlap,
        "sources": [str(p) for p in sources],
    }
    with output.open("wb") as fh:
        pickle.dump(payload, fh)
    print(f"Indexed {len(texts)} chunks from {len(sources)} source paths -> {output}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build TF-IDF index for RAG prompts")
    parser.add_argument("sources", nargs="+", type=Path, help="Files or directories with project docs")
    parser.add_argument("--output", type=Path, default=Path("data/rag_index.pkl"), help="Index output path")
    parser.add_argument("--chunk-size", type=int, default=500, help="Characters per chunk before vectorizing")
    parser.add_argument("--overlap", type=int, default=60, help="Character overlap between chunks")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    build_index(args.sources, args.output, chunk_size=args.chunk_size, overlap=args.overlap)
