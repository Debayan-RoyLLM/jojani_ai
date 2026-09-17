"""
Settings for flatten.py — edit values here, then run:
    python flatten.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import paths  # noqa: E402

# --- Input / output paths (centralized in paths.py) ---------------------------

INPUT_JSONL = paths.NEG_CLAUSES
OUTPUT_JSONL = "negative_clauses_flat.jsonl"
