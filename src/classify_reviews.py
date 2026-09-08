#!/usr/bin/env python3
"""Classify reviews from reviews.md by matching place names from places_data.csv.

Any review containing a place name keyword is saved to matched_reviews.md.
"""

import csv
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
REVIEWS_PATH = BASE_DIR / "output" / "reviews.md"
PLACES_PATH = BASE_DIR / "data" / "places_data.csv"
OUTPUT_PATH = BASE_DIR / "output" / "matched_reviews.md"


def load_keywords(path: Path) -> list[str]:
    keywords = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader, None)  # skip header if present
        for row in reader:
            if row and row[0].strip():
                keywords.append(row[0].strip())
    return keywords


def load_reviews(path: Path) -> list[str]:
    """Parse reviews.md into a list of review texts."""
    text = path.read_text(encoding="utf-8")
    reviews = []
    current = []
    for line in text.splitlines():
        if line.startswith("## Review"):
            if current:
                reviews.append("\n".join(current).strip())
            current = []
        elif line.startswith("# "):
            continue
        elif current is not None:
            current.append(line)
    if current:
        reviews.append("\n".join(current).strip())
    return [r for r in reviews if r]


def main() -> None:
    keywords = load_keywords(PLACES_PATH)
    reviews = load_reviews(REVIEWS_PATH)
    print(f"Loaded {len(keywords)} keywords, {len(reviews)} reviews")

    matched = []
    for i, review in enumerate(reviews, start=1):
        lower_review = review.lower()
        for kw in keywords:
            if kw.lower() in lower_review:
                matched.append((kw, review))
                break  # one entry per review, first keyword matched

    lines = ["# Matched Reviews", ""]
    for i, (kw, review) in enumerate(matched, start=1):
        lines.append(f"## {kw}")
        lines.append("")
        lines.append(review)
        lines.append("")

    OUTPUT_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"Matched {len(matched)} reviews out of {len(reviews)}")
    print(f"Wrote to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
