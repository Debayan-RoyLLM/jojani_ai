"""Parse markdown review files produced by the extract/classify steps."""

from pathlib import Path


def parse_matched_reviews(path: Path) -> list[tuple[str, str]]:
    """Parse matched_reviews.md into (location_name, review_text) pairs.

    The file format is:
        # Matched Reviews
        ## <location_name>
        <review text lines...>
        ## <next location>
        ...
    """
    text = path.read_text(encoding="utf-8")
    entries: list[tuple[str, str]] = []
    current_location = ""
    current_lines: list[str] = []

    for line in text.splitlines():
        if line.startswith("## "):
            if current_location and current_lines:
                entries.append((current_location, "\n".join(current_lines).strip()))
            current_location = line[3:].strip()
            current_lines = []
        elif line.startswith("# "):
            continue
        else:
            current_lines.append(line)

    if current_location and current_lines:
        entries.append((current_location, "\n".join(current_lines).strip()))

    return [(loc, rev) for loc, rev in entries if rev]


def parse_reviews_md(path: Path) -> list[str]:
    """Parse a plain reviews.md (## Review N sections) into a list of review texts."""
    text = path.read_text(encoding="utf-8")
    reviews: list[str] = []
    current: list[str] = []

    for line in text.splitlines():
        if line.startswith("## Review"):
            if current:
                reviews.append("\n".join(current).strip())
            current = []
        elif line.startswith("# "):
            continue
        else:
            current.append(line)

    if current:
        reviews.append("\n".join(current).strip())

    return [r for r in reviews if r]
