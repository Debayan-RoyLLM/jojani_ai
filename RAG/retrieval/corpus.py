"""Corpus loading and indexing.

Reads the review knowledge base (JSON) and the place-name list (CSV) and wires
them together: every review is tokenized, and every review is attached to each
place it mentions. This is all the one-time setup work, kept out of the
Retriever so Retriever.search() can stay focused on the query path.
"""

import csv
import json
from pathlib import Path

from .models import PlaceCluster, Review
from .text import _GENERIC, tokenize


def load_reviews(path: Path) -> list[Review]:
    """Load review records, skipping any with empty text."""
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)
    return [
        Review(
            attraction_id=r["attraction_id"],
            date=r["date"],
            rating=r["rating"],
            review_text=r["review_text"],
        )
        for r in raw
        if r.get("review_text", "").strip()
    ]


def load_places(csv_path: Path) -> list[PlaceCluster]:
    """Load place names from CSV, deduplicating by normalized token set."""
    clusters: dict[frozenset, PlaceCluster] = {}
    order: list[frozenset] = []

    with open(csv_path, encoding="utf-8") as f:
        for row in csv.reader(f):
            raw = row[0].strip() if row else ""
            if not raw:
                continue
            tokens = tokenize(raw)
            if not tokens:
                continue
            key = frozenset(tokens)
            if key in clusters:
                continue
            route_tokens = frozenset(t for t in tokens if t not in _GENERIC)
            clusters[key] = PlaceCluster(
                name=raw,
                tokens=key,
                route_tokens=route_tokens,
            )
            order.append(key)

    return [clusters[k] for k in order]


def index(reviews: list[Review], places: list[PlaceCluster]) -> None:
    """Attach each review to every place it mentions (mutates both in place)."""
    review_tokens = [tokenize(r.review_text) for r in reviews]

    for cluster in places:
        for i, tokens in enumerate(review_tokens):
            if cluster.tokens & tokens:
                cluster.review_indices.append(i)
                if cluster.name not in reviews[i].locations:
                    reviews[i].locations.append(cluster.name)
