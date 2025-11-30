"""Simple TF-IDF based retriever for local RAG prompts."""

import os
from functools import lru_cache
from pathlib import Path
from typing import List, Dict, Optional

import joblib
import numpy as np
from scipy import sparse

INDEX_PATH = Path(os.getenv("TFIDF_INDEX_PATH", "data/tfidf_index.joblib"))


def _load_index():
    if not INDEX_PATH.exists():
        raise FileNotFoundError(f"TF-IDF index not found at {INDEX_PATH}. Run tools/build_tfidf_index.py first.")
    bundle = joblib.load(INDEX_PATH)
    matrix = bundle["matrix"]
    if not sparse.isspmatrix_csr(matrix):
        matrix = sparse.csr_matrix(matrix)
    return {
        "matrix": matrix,
        "vectorizer": bundle["vectorizer"],
        "documents": bundle["documents"],
    }


@lru_cache(maxsize=1)
def _cached_index():
    return _load_index()


def retrieve(query: str, top_k: int = 5, k: Optional[int] = None) -> List[Dict[str, float]]:
    if not query:
        return []
    if k is not None:
        top_k = k
    store = _cached_index()
    vector = store["vectorizer"].transform([query])
    scores = store["matrix"].dot(vector.T).toarray().ravel()
    if scores.size == 0:
        return []
    ranked = np.argsort(scores)[::-1][:top_k]
    return [
        {
            "text": store["documents"][idx],
            "score": float(scores[idx])
        }
        for idx in ranked
        if scores[idx] > 0
    ]


def build_context_block(query: str, top_k: int = 5) -> str:
    facts = retrieve(query, top_k=top_k)
    if not facts:
        return ""
    lines = ["Relevant facts:"]
    for fact in facts:
        lines.append(f"- {fact['text']}")
    return "\n".join(lines)
