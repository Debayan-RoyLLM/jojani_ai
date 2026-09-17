#!/usr/bin/env python3
"""Step 1: Extract the 'Reviews' column from Booking_reviews.csv into output/reviews.md."""

import csv

from keyword_based import config


def main() -> None:
    if not config.INPUT_REVIEW_CSV.exists():
        raise SystemExit(f"Input CSV not found: {config.INPUT_REVIEW_CSV}")

    with open(config.INPUT_REVIEW_CSV, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader)
        reviews_idx = header.index("Reviews")

        count = 0
        lines = ["# Reviews", ""]
        for row in reader:
            if reviews_idx >= len(row):
                continue
            review = row[reviews_idx].strip()
            if not review:
                continue
            count += 1
            lines += [f"## Review {count}", "", review, ""]

    config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    config.REVIEWS_MD.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {count} reviews to {config.REVIEWS_MD}")


if __name__ == "__main__":
    main()
