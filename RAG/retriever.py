"""Keyword review retriever with optional location clustering.

The whole retrieval path lives in this one file so it can be read top to bottom:

  1. load reviews (JSON) + place names (CSV, optional)
  2. on each query: try to route it to a place, else fall back to global keyword search
  3. return top-K reviews (worst rating first, then most recent)

Pass ``_debug=True`` to Retriever to print the exact cluster it routed a query
to (or "no match"), which is handy when checking why a query returned what it did.
"""

import csv
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from . import config

# --- Text helpers ----------------------------------------------------------

# Words that carry no location meaning; dropped from ALL matching.
_STOP = {
    "the", "a", "an", "and", "or", "of", "in", "on", "at", "by",
    "beach", "island", "zanzibar", "tanzania", "nature", "reserve",
    "national", "park", "garden", "gardens", "museum", "house",
    "st", "street", "road", "old", "new", "private",
}

# So common they don't tell places apart: kept for review→place assignment,
# excluded from query→place routing (so a lone "farm" doesn't grab the first farm).
_GENERIC = {
    "spice", "farm", "farms", "tour", "tours", "adventure",
    "center", "centre", "aquarium", "lodge", "restaurant",
    "bar", "shop", "cave", "rock", "bay", "hill", "forest", "safari",
}


def _normalize(text: str) -> str:
    """Lowercase and keep only letters, digits, and spaces."""
    return re.sub(r"[^a-z0-9 ]+", " ", text.lower()).strip()


def _tokenize(text: str) -> set[str]:
    """Words longer than 2 chars, stopwords removed."""
    return {w for w in _normalize(text).split() if len(w) > 2 and w not in _STOP}


# --- Data models ------------------------------------------------------------

@dataclass
class Review:
    attraction_id: str
    date: str
    rating: float
    review_text: str
    locations: list[str] = field(default_factory=list)  # filled in during indexing


@dataclass
class PlaceCluster:
    name: str                       # display name
    tokens: frozenset               # all meaningful tokens → attach reviews
    route_tokens: frozenset         # distinguishing tokens → route queries
    review_indices: list[int] = field(default_factory=list)


# --- Loading & indexing -----------------------------------------------------

def _load_reviews(path: Path) -> list[Review]:
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


def _load_places(csv_path: Path) -> list[PlaceCluster]:
    """Load place names from CSV, deduplicated by normalized token set."""
    clusters: dict[frozenset, PlaceCluster] = {}
    with open(csv_path, encoding="utf-8") as f:
        for row in csv.reader(f):
            raw = row[0].strip() if row else ""
            if not raw:
                continue
            tokens = _tokenize(raw)
            if not tokens:
                continue
            key = frozenset(tokens)
            if key in clusters:
                continue
            clusters[key] = PlaceCluster(
                name=raw,
                tokens=key,
                route_tokens=frozenset(t for t in tokens if t not in _GENERIC),
            )
    return list(clusters.values())


def _index(reviews: list[Review], places: list[PlaceCluster]) -> None:
    """Attach each review to every place it mentions (mutates both)."""
    review_tokens = [_tokenize(r.review_text) for r in reviews]
    for cluster in places:
        for i, tokens in enumerate(review_tokens):
            if cluster.tokens & tokens:
                cluster.review_indices.append(i)
                if cluster.name not in reviews[i].locations:
                    reviews[i].locations.append(cluster.name)


# --- Retriever --------------------------------------------------------------

class Retriever:
    def __init__(self, kb_path: Path | None = None, places_path: Path | None = None, _debug: bool = False):
        self._debug = _debug
        self.reviews: list[Review] = _load_reviews(kb_path or config.KNOWLEDGE_BASE)
        self._tokens: list[set[str]] = [_tokenize(r.review_text) for r in self.reviews]

        # Place clustering is optional — skip cleanly if the CSV is missing.
        csv_path = places_path or config.PLACES_CSV
        self._places: list[PlaceCluster] = _load_places(csv_path) if csv_path.exists() else []
        if self._places:
            _index(self.reviews, self._places)

    def search(
        self, query: str, max_results: int | None = None
    ) -> tuple[list[Review], str | None]:
        """Return (reviews, matched_location_name).

        1. Route the query to a place cluster.
        2. If found, top-K reviews from that cluster (rating asc, date desc).
        3. Otherwise fall back to global keyword search.
        """
        k = max_results or config.MAX_REVIEWS
        cluster = self._route_query(query)
        if cluster and cluster.review_indices:
            if self._debug:
                print(f"  [retriever] routed to: {cluster.name} ({len(cluster.review_indices)} reviews)")
            return self._top_from_cluster(cluster, k), cluster.name
        if self._debug:
            print("  [retriever] no place match → global keyword search")
        return self._global_search(query, k), None

    # Route a query to the place whose distinguishing tokens best match it.
    def _route_query(self, query: str) -> PlaceCluster | None:
        q_tokens = _tokenize(query)
        if not q_tokens:
            return None
        best: tuple[int, float, float, PlaceCluster] | None = None
        for cluster in self._places:
            if not cluster.route_tokens:
                continue
            overlap = len(q_tokens & cluster.route_tokens)
            if overlap == 0:
                continue
            query_coverage = overlap / len(q_tokens)
            if query_coverage < 0.25:  # overlap must be a meaningful share of the query
                continue
            specificity = overlap / len(cluster.route_tokens)
            if best is None or (overlap, specificity, query_coverage) > (best[0], best[1], best[2]):
                best = (overlap, specificity, query_coverage, cluster)
        return best[3] if best else None

    # Worst rating first (more actionable), ties broken by most recent.
    def _top_from_cluster(self, cluster: PlaceCluster, k: int) -> list[Review]:
        def sort_key(i: int) -> tuple:
            r = self.reviews[i]
            return (r.rating if r.rating == r.rating else 3.0, r.date)
        idxs = sorted(cluster.review_indices, key=sort_key, reverse=True)
        return [self.reviews[i] for i in idxs[:k]]

    # Keyword search over the whole corpus, ranked by token overlap then rating.
    def _global_search(self, query: str, k: int) -> list[Review]:
        q_tokens = _tokenize(query)
        if not q_tokens:
            recent = sorted(self.reviews, key=lambda r: r.date, reverse=True)
            return recent[:k]
        scored: list[tuple[int, float, Review]] = []
        for i, rev in enumerate(self.reviews):
            overlap = len(q_tokens & self._tokens[i])
            if overlap > 0:
                rating = rev.rating if rev.rating == rev.rating else 3.0
                scored.append((overlap, rating, rev))
        scored.sort(key=lambda x: (-x[0], x[1]))
        return [rev for _, _, rev in scored[:k]]
