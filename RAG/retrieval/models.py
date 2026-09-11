"""Data models for the retrieval layer.

- Review: one loaded review record.
- PlaceCluster: one canonical place, with the token sets used to match it.
"""

from dataclasses import dataclass, field


@dataclass
class Review:
    """A single review record loaded from the knowledge base."""
    attraction_id: str
    date: str
    rating: float
    review_text: str
    # Place names this review mentions (filled in during indexing).
    locations: list[str] = field(default_factory=list)


@dataclass
class PlaceCluster:
    """A canonical place, deduplicated by its token set.

    Two token sets are kept on purpose:
      - tokens:       every meaningful (non-stopword) token → used to attach
                      reviews to a place.
      - route_tokens: only the *distinguishing* (non-generic) tokens → used to
                      route a query to a place. A query matching only generic
                      words like "farm" won't route here.
    """
    name: str                    # canonical display name
    tokens: frozenset            # all meaningful tokens
    route_tokens: frozenset      # distinguishing tokens (non-generic)
    review_indices: list[int] = field(default_factory=list)  # filled in during indexing
