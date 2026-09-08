#!/usr/bin/env python3
"""Extract all values from the 'Reviews' column of Booking_reviews.csv into a .md file."""

import csv
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
CSV_PATH = BASE_DIR / "data" / "Booking_reviews.csv"
OUTPUT_PATH = BASE_DIR / "output" / "reviews.md"


def main() -> None:
    with open(CSV_PATH, newline="", encoding="utf-8") as f:
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
            lines.append(f"## Review {count}")
            lines.append("")
            lines.append(review)
            lines.append("")

    OUTPUT_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {count} reviews to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
