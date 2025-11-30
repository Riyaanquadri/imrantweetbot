#!/usr/bin/env python3
"""Evaluate model generations against a holdout set using similarity heuristics."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable, List, Tuple

import numpy as np
from rapidfuzz.distance import Levenshtein

try:
    from sentence_transformers import SentenceTransformer
except ImportError:  # pragma: no cover - optional dependency
    SentenceTransformer = None


def load_generations(path: Path) -> List[dict]:
    with path.open("r", encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def pairwise_similarity(model_outputs: Iterable[str], references: Iterable[str]) -> Tuple[float, float]:
    outputs = list(model_outputs)
    refs = list(references)
    if not outputs or not refs:
        return 0.0, 0.0
    lev_scores = []
    ratio_scores = []
    for out, ref in zip(outputs, refs):
        lev = 1 - Levenshtein.normalized_distance(out, ref)
        lev_scores.append(lev)
        ratio_scores.append(lev)
    return float(np.mean(lev_scores)), float(np.std(lev_scores))


def semantic_similarity(model_outputs: List[str], references: List[str]) -> float:
    if SentenceTransformer is None:
        return -1.0
    model = SentenceTransformer("all-MiniLM-L6-v2")
    emb_out = model.encode(model_outputs, convert_to_tensor=True)
    emb_ref = model.encode(references, convert_to_tensor=True)
    sim = np.sum(emb_out * emb_ref, axis=1) / (
        np.linalg.norm(emb_out, axis=1) * np.linalg.norm(emb_ref, axis=1)
    )
    return float(np.mean(sim))


def main():
    parser = argparse.ArgumentParser(description="Evaluate tweet generations")
    parser.add_argument("predictions", type=Path, help="JSONL file with model outputs")
    parser.add_argument("references", type=Path, help="JSONL reference dataset")
    parser.add_argument("--key", default="text", help="JSON key for the tweet text in both files")
    args = parser.parse_args()

    preds = load_generations(args.predictions)
    refs = load_generations(args.references)
    model_texts = [p.get(args.key, "") for p in preds]
    ref_texts = [r.get(args.key, "") for r in refs[: len(model_texts)]]

    lev_mean, lev_std = pairwise_similarity(model_texts, ref_texts)
    semantic = semantic_similarity(model_texts, ref_texts)
    print(f"Levenshtein similarity mean={lev_mean:.3f} std={lev_std:.3f}")
    if semantic >= 0:
        print(f"Semantic similarity mean={semantic:.3f}")
    else:
        print("sentence-transformers not installed; skipping semantic similarity")


if __name__ == "__main__":
    main()
