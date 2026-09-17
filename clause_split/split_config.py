"""
Settings for split.py.

Edit the values below, then run:  python split.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import paths  # noqa: E402

# --- Paths (centralized in paths.py) ----------------------------------------

INPUT_CSV = paths.JOINED_REVIEW_CSV
OUTPUT_JSONL = "review_clauses.jsonl"

# --- Which CSV column holds each field ---------------------------------------
#
# The keys below are fixed field names used by split.py.
# The values are the matching CSV header names, or None to leave a field out.
#
#   text       -> the review text. This one is required.
#   lang       -> leave as None and the language is guessed from the text.
#   (anything) -> leave as None if your CSV does not have that column; the
#                 field is simply omitted from the output.
COLUMNS = {
    "text": "content",
    #"review_id": None,
    "review_id": "review_id",
    "place_name": "place_name",
    #"rating": None,
    #"date": None,
    #"lang": None,
}

# --- Splitting ---------------------------------------------------------------

# A clause with fewer than this many words is glued onto a neighbouring clause,
# so the output does not end up full of tiny fragments.
MIN_WORDS = 3
