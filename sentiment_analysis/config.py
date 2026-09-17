"""
Settings for classify.py — edit values here, then run:
    python classify.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import paths  # noqa: E402

# --- Input / output paths (centralized in paths.py) ---------------------------

INPUT_JSONL = paths.REVIEW_CLAUSES
OUTPUT_NEGATIVE = "negative_clauses.jsonl"
OUTPUT_POSITIVE = "positive_clauses.jsonl"

# --- Model (centralized in paths.py) ------------------------------------------
MODEL = paths.SENTIMENT_MODEL

# --- Inference tuning ---------------------------------------------------------

BATCH_SIZE  = 32
MAX_LENGTH  = 256
