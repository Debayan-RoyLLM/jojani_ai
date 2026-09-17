"""
Settings for embed.py — edit values here, then run:
    python embed.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import paths  # noqa: E402

# --- Input / output paths (centralized in paths.py) ---------------------------

INPUT_JSONL = paths.FLAT_NEG_CLAUSES
OUTPUT_JSONL = "negative_clauses_embedded.jsonl"
FAISS_INDEX  = "negative_clauses.faiss"

# --- Model (centralized in paths.py) ------------------------------------------
MODEL_DIR = str(paths.EMBED_MODEL_DIR)
FALLBACK_MODEL = paths.EMBED_MODEL_FALLBACK

# --- Inference tuning ---------------------------------------------------------

BATCH_SIZE = 64
