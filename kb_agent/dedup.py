"""Near-duplicate issue merging (deterministic, no LLM).

Two issues are considered repeats when their normalized token sets are highly
overlapping (Jaccard >= threshold). We keep the first/representative and drop the
duplicates, so the knowledge base never states the same issue twice.
"""
from __future__ import annotations

import re

# Words that carry no issue-specific meaning; dropping them keeps the similarity
# signal on the actual subject (food, staff, queue, price, ...).
STOPWORDS = {
    "a", "an", "the", "and", "or", "but", "is", "are", "was", "were", "be",
    "been", "being", "to", "of", "in", "on", "for", "with", "at", "by",
    "from", "as", "it", "its", "that", "this", "these", "those", "very",
    "too", "so", "just", "only", "also", "too", "not", "no", "can", "could",
    "will", "would", "should", "had", "have", "has", "there", "their", "them",
    "they", "you", "your", "we", "our", "my", "me", "i", "he", "she", "his",
    "her", "its", "about", "into", "over", "under", "again", "then", "than",
    "when", "while", "during", "before", "after", "up", "down", "out", "off",
}


def _tokens(text: str) -> set[str]:
    return {t for t in re.findall(r"[a-z']+", text.lower()) if t not in STOPWORDS}


def jaccard(a: str, b: str) -> float:
    sa, sb = _tokens(a), _tokens(b)
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def merge_near_duplicates(issues: list[str], threshold: float) -> list[str]:
    """Drop issues that are near-identical to an earlier one.

    Order-preserving: the first occurrence of an issue "family" is kept.
    """
    kept: list[str] = []
    for issue in issues:
        if any(jaccard(issue, k) >= threshold for k in kept):
            continue
        kept.append(issue)
    return kept
