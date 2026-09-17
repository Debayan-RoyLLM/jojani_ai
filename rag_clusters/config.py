"""RAG cluster-based configuration."""

import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BASE_DIR))
import paths  # noqa: E402

OUTPUT_DIR = BASE_DIR / "output"
ENV_PATH = BASE_DIR / ".env"

# FAISS index over individual negative clause embeddings (384-dim, IndexFlatIP).
FAISS_INDEX = paths.FAISS_INDEX

# JSONL with clause metadata, aligned row-by-row with the FAISS index.
CLAUSE_META = paths.EMBEDDED_NEG

# Local MiniLM multilingual embedding model (384-dim), shared with the
# embedding pipeline. Falls back to the HF name if the local dir is absent.
DEFAULT_MODEL = paths.embedding_model()
MAX_REVIEWS = 15

# Canonical issue taxonomy (LLM classifies clauses into these)
TAXONOMY = [
    "venue_conditions_unpleasant",
    "poor_customer_service",
    "overpriced",
    "unsafe",
    "accessibility_issues",
    "poor_maintenance",
    "misleading_marketing",
    "language_barrier",
    "weather_related",
    "logistics_problems",
    "positive_highlight",
    "other",
]


def _load_env(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())


_load_env(ENV_PATH)

LLM_URL = os.getenv("LLM_URL", "")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "")

MAX_RETRIES = 3
LLM_TIMEOUT = 120
