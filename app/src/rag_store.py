"""Lightweight TF-IDF context store for retrieval-augmented prompts."""
from __future__ import annotations

import pickle
from pathlib import Path
from typing import List, Optional

from app.config import Config
from app.logger import logger


class RAGContextStore:
    """Loads a serialized TF-IDF index and returns top matching snippets."""

    def __init__(self, index_path: Path, top_k: int = 3):
        self.index_path = Path(index_path)
        self.top_k = top_k
        self._vectorizer = None
        self._matrix = None
        self._documents: List[str] = []
        self._metadata: List[dict] = []
        self._load_index()

    def _load_index(self):
        if not self.index_path.exists():
            logger.warning("RAG index not found at %s; continuing without retrieval", self.index_path)
            return
        with self.index_path.open("rb") as fh:
            payload = pickle.load(fh)
        self._vectorizer = payload.get("vectorizer")
        self._matrix = payload.get("matrix")
        self._documents = payload.get("documents", [])
        self._metadata = payload.get("metadata", [])
        logger.info("Loaded RAG index with %s chunks from %s", len(self._documents), self.index_path)

    @property
    def ready(self) -> bool:
        return self._vectorizer is not None and self._matrix is not None and bool(self._documents)

    def retrieve(self, query: str, top_k: Optional[int] = None) -> List[dict]:
        if not self.ready or not query.strip():
            return []
        k = top_k or self.top_k
        vector = self._vectorizer.transform([query])
        scores = (vector @ self._matrix.T).toarray()[0]
        ranked = scores.argsort()[::-1]
        results: List[dict] = []
        for idx in ranked[:k]:
            score = float(scores[idx])
            if score <= 0:
                break
            results.append(
                {
                    "text": self._documents[idx],
                    "score": score,
                    "meta": self._metadata[idx] if idx < len(self._metadata) else {},
                }
            )
        return results

    def build_context_block(self, query: str, top_k: Optional[int] = None) -> str:
        snippets = self.retrieve(query, top_k=top_k)
        if not snippets:
            return ""
        lines = [f"- {item['text']}" for item in snippets]
        return "Retrieved facts:\n" + "\n".join(lines)

    @classmethod
    def from_config(cls) -> Optional["RAGContextStore"]:
        if not Config.ENABLE_RAG:
            return None
        return cls(index_path=Path(Config.RAG_INDEX_PATH), top_k=Config.RAG_TOP_K)
