#!/usr/bin/env python3
"""Step 2: Filter reviews.md by place-name keywords from places_data.csv."""

import csv

from src import config
from src.parse_reviews import parse_reviews_md


def load_keywords(path) -> list[str]:
    """Read place-name keywords from the first column of the CSV."""
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader, None)  # skip header if present
        return [row[0].strip() for row in reader if row and row[0].strip()]


def main() -> None:
    if not config.REVIEWS_MD.exists():
        raise SystemExit(
            f"{config.REVIEWS_MD.name} not found. Run step 1 first: python src/extract_reviews.py"
        )

    keywords = load_keywords(config.PLACES_CSV)
    reviews = parse_reviews_md(config.REVIEWS_MD)
    print(f"Loaded {len(keywords)} keywords, {len(reviews)} reviews")

    matched: list[tuple[str, str]] = []
    for review in reviews:
        lower = review.lower()
        for kw in keywords:
            if kw.lower() in lower:
                matched.append((kw, review))
                break  # one entry per review, first keyword wins

    lines = ["# Matched Reviews", ""]
    for kw, review in matched:
        lines += [f"## {kw}", "", review, ""]

    config.MATCHED_REVIEWS_MD.write_text("\n".join(lines), encoding="utf-8")
    print(f"Matched {len(matched)} reviews out of {len(reviews)}")
    print(f"Wrote to {config.MATCHED_REVIEWS_MD}")


if __name__ == "__main__":
    main()
