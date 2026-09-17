"""Embedding-based retriever over negative clauses using FAISS.

Retrieval is embedding-only:
  1. Encode the query with the same MiniLM model that embedded the clauses.
  2. FAISS inner-product search over individual clause vectors.
  3. Return the top-K clauses (with metadata from the aligned JSONL).
"""

import json
from dataclasses import dataclass
from pathlib import Path

import faiss
import numpy as np
import sentence_transformers

from . import config


@dataclass
class Clause:
    clause_id: str
    review_id: str
    place_name: str
    clause_text: str
    sentence_no: int
    score: float


def _load_metadata(path: Path) -> list[dict]:
    """Load clause metadata from the JSONL file (row-aligned with FAISS index)."""
    records = []
    if not path.exists():
        print(f"  [retriever] WARNING: {path} not found")
        return records
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


class Retriever:
    def __init__(
        self,
        index_path: Path | None = None,
        meta_path: Path | None = None,
        model: str | None = None,
    ):
        index_path = index_path or config.FAISS_INDEX
        meta_path = meta_path or config.CLAUSE_META

        self._meta = _load_metadata(meta_path)

        model_dir = model or config.DEFAULT_MODEL
        print(f"  [retriever] loading embedding model: {model_dir}")
        self._model = sentence_transformers.SentenceTransformer(model_dir)

        if not index_path.exists():
            print(f"  [retriever] ERROR: FAISS index not found at {index_path}")
            self._index = None
        else:
            self._index = faiss.read_index(str(index_path))
            print(f"  [retriever] loaded FAISS index: {self._index.ntotal} clauses, dim={self._index.d}")

        if len(self._meta) != self._index.ntotal:
            print(f"  [retriever] WARNING: meta count ({len(self._meta)}) != index count ({self._index.ntotal})")

    def search(self, query: str, max_results: int | None = None) -> list[Clause]:
        """Return the top-K most similar negative clauses for the query."""
        k = max_results or config.MAX_REVIEWS

        if self._index is None or not self._meta:
            return []

        query_emb = self._model.encode(
            [query], convert_to_numpy=True, normalize_embeddings=True
        ).astype(np.float32)

        k_search = min(k, self._index.ntotal)
        sims, idxs = self._index.search(query_emb, k_search)

        results = []
        for sim, idx in zip(sims[0], idxs[0]):
            if idx == -1:
                continue
            r = self._meta[int(idx)]
            results.append(Clause(
                clause_id=r["clause_id"],
                review_id=r.get("review_id", ""),
                place_name=r.get("place_name", ""),
                clause_text=r["clause_text"],
                sentence_no=r.get("sentence_no", 0),
                score=r.get("score", 0.0),
            ))

        return results
