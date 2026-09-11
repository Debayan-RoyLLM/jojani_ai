"""Text normalization, tokenization, and the stopword/generic-word sets.

These are the lowest-level helpers in the retrieval layer. They know nothing
about reviews or places — just how to turn raw text into comparable tokens.
"""

import re

# Words that appear in place names but carry no location meaning.
# Dropped from ALL token matching (place and review alike).
_STOP = {
    "the", "a", "an", "and", "or", "of", "in", "on", "at", "by",
    "beach", "island", "zanzibar", "tanzania", "nature", "reserve",
    "national", "park", "garden", "gardens", "museum", "house",
    "st", "street", "road", "old", "new", "private",
}

# Words that appear in so many place names they don't help tell places apart.
# Kept for *review → place* assignment (a review mentioning "farm" should still
# match a farm), but excluded from *query → place* routing so a lone "farm" in
# a query doesn't spuriously route to the first farm it finds.
_GENERIC = {
    "spice", "farm", "farms", "tour", "tours", "adventure",
    "center", "centre", "aquarium", "lodge", "restaurant",
    "bar", "shop", "cave", "rock", "bay", "hill", "forest", "safari",
}


def normalize(text: str) -> str:
    """Lowercase and strip everything except letters, digits, and spaces."""
    return re.sub(r"[^a-z0-9 ]+", " ", text.lower()).strip()


def tokenize(text: str) -> set[str]:
    """Tokenize for matching — keep words longer than 2 chars, drop stopwords."""
    return {w for w in normalize(text).split() if len(w) > 2 and w not in _STOP}
