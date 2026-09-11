"""Parse markdown review files produced by the extract/classify steps."""

import csv
from pathlib import Path


def _parse_md_sections(path: Path, header_prefix: str) -> list[tuple[str, str]]:
    """Generic parser: split a markdown file into (header, body) pairs.

    Args:
        path: Path to the markdown file.
        header_prefix: Only lines starting with this string are treated as
            section boundaries. E.g. "## " or "## Review".
    """
    text = path.read_text(encoding="utf-8")
    sections: list[tuple[str, str]] = []
    current_header = ""
    current_lines: list[str] = []

    for line in text.splitlines():
        if line.startswith(header_prefix):
            if current_header and current_lines:
                sections.append((current_header, "\n".join(current_lines).strip()))
            current_header = line[len(header_prefix):].strip()
            current_lines = []
        elif line.startswith("# "):
            continue
        else:
            current_lines.append(line)

    if current_header and current_lines:
        sections.append((current_header, "\n".join(current_lines).strip()))

    return [(h, b) for h, b in sections if b]


def parse_matched_reviews(path: Path) -> list[tuple[str, str]]:
    """Parse matched_reviews.md into (location_name, review_text) pairs."""
    return _parse_md_sections(path, "## ")


def parse_reviews_md(path: Path) -> list[str]:
    """Parse a plain reviews.md (## Review N sections) into a list of review texts."""
    return [body for _, body in _parse_md_sections(path, "## Review")]


def load_keywords(path: Path) -> list[str]:
    """Read place-name keywords from the first column of a CSV."""
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader, None)  # skip header if present
        return [row[0].strip() for row in reader if row and row[0].strip()]
