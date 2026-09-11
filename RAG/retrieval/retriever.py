"""Location-aware review retriever.

Clusters reviews by the place names they mention. On search(), the query is
first routed to the best-matching place cluster; if one is found, top-K reviews
from that cluster are returned (low rating first — more actionable — then
recency). If no place matches, we fall back to global keyword search.

The CSV of place names is optional: without it, the retriever still works as a
plain keyword search over the whole corpus.
"""

from pathlib import Path

from .. import config
from .corpus import index, load_places, load_reviews
from .models import PlaceCluster, Review
from .text import tokenize


class Retriever:
    def __init__(self, kb_path: Path | None = None, places_path: Path | None = None):
        self.reviews: list[Review] = load_reviews(kb_path or config.KNOWLEDGE_BASE)
        self._tokens: list[set[str]] = [tokenize(r.review_text) for r in self.reviews]

        # Place clustering is optional — skip it cleanly if the CSV is missing.
        csv_path = places_path or config.PLACES_CSV
        self._places: list[PlaceCluster] = (
            load_places(csv_path) if csv_path.exists() else []
        )
        if self._places:
            index(self.reviews, self._places)

    # ------------------------------------------------------------------
    # Routing: find the best-matching place cluster for a query
    # ------------------------------------------------------------------
    def _route_query(self, query: str) -> PlaceCluster | None:
        """Return the place cluster whose distinguishing tokens best match the query.

        Requires at least one route-token overlap AND that the overlap is a
        significant fraction of the query's own tokens (avoids spurious matches
        on single common words).
        """
        q_tokens = tokenize(query)
        if not q_tokens:
            return None

        best: tuple[int, float, float, PlaceCluster] | None = None
        for cluster in self._places:
            if not cluster.route_tokens:
                continue
            overlap = len(q_tokens & cluster.route_tokens)
            if overlap == 0:
                continue
            # Overlap must be a meaningful fraction of the query tokens
            query_coverage = overlap / len(q_tokens)
            if query_coverage < 0.25:
                continue
            specificity = overlap / len(cluster.route_tokens)
            if best is None or (overlap, specificity, query_coverage) > (best[0], best[1], best[2]):
                best = (overlap, specificity, query_coverage, cluster)

        return best[3] if best else None

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------
    def search(
        self, query: str, max_results: int | None = None
    ) -> tuple[list[Review], str | None]:
        """
        Return (reviews, matched_location_name).

        1. Route query to a location cluster.
        2. If found, return top-K reviews from that cluster (rating asc, date desc).
        3. If no location match, fall back to global keyword search.
        """
        k = max_results or config.MAX_REVIEWS

        cluster = self._route_query(query)
        if cluster and cluster.review_indices:
            # Stable two-pass sort: date desc, then rating asc.
            idxs = sorted(cluster.review_indices, key=lambda i: self.reviews[i].date, reverse=True)
            idxs = sorted(
                idxs,
                key=lambda i: self.reviews[i].rating
                if self.reviews[i].rating == self.reviews[i].rating
                else 3.0,
            )
            return [self.reviews[i] for i in idxs[:k]], cluster.name

        # Fallback: global keyword search.
        q_tokens = tokenize(query)
        if not q_tokens:
            recent = sorted(self.reviews, key=lambda r: r.date, reverse=True)
            return recent[:k], None

        scored: list[tuple[int, float, Review]] = []
        for i, rev in enumerate(self.reviews):
            overlap = len(q_tokens & self._tokens[i])
            if overlap > 0:
                rating = rev.rating if rev.rating == rev.rating else 3.0
                scored.append((overlap, rating, rev))

        scored.sort(key=lambda x: (-x[0], x[1]))
        return [rev for _, _, rev in scored[:k]], None
