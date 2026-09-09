"""Lightweight keyword-based review retriever."""

import json
import re
from dataclasses import dataclass
from pathlib import Path

from . import config


@dataclass
class Review:
    attraction_id: str
    date: str
    rating: float
    review_text: str


def _tokenize(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z']+", text.lower()) if len(w) > 2}


class Retriever:
    """Filter reviews by keyword overlap with the query, sorted by recency."""

    def __init__(self, kb_path: Path | None = None):
        path = kb_path or config.KNOWLEDGE_BASE
        with open(path, encoding="utf-8") as f:
            raw = json.load(f)
        self.reviews: list[Review] = [
            Review(
                attraction_id=r["attraction_id"],
                date=r["date"],
                rating=r["rating"],
                review_text=r["review_text"],
            )
            for r in raw
            if r.get("review_text", "").strip()
        ]
        self._tokens: list[set[str]] = [_tokenize(r.review_text) for r in self.reviews]

    def search(self, query: str, max_results: int | None = None) -> list[Review]:
        """Return reviews whose text shares keywords with the query, newest first."""
        k = max_results or config.MAX_REVIEWS
        query_tokens = _tokenize(query)
        if not query_tokens:
            # Fallback: return most recent reviews
            return sorted(self.reviews, key=lambda r: r.date, reverse=True)[:k]

        scored: list[tuple[int, float, Review]] = []
        for i, rev in enumerate(self.reviews):
            overlap = len(query_tokens & self._tokens[i])
            if overlap > 0:
                # Score: keyword overlap, tiebreak by rating (lower = more actionable)
                rating = rev.rating if rev.rating == rev.rating else 3.0  # NaN guard
                scored.append((overlap, -rating, rev))

        scored.sort(key=lambda x: (-x[0], x[1], x[2].date), reverse=False)
        # Primary sort: overlap desc, then rating asc, then date desc
        scored.sort(key=lambda x: (-x[0], x[1]))
        return [rev for _, _, rev in scored[:k]]
