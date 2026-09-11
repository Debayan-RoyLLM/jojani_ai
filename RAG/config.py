"""RAG application configuration."""

import os
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
OUTPUT_DIR = BASE_DIR / "output"
ENV_PATH = BASE_DIR / ".env"

KNOWLEDGE_BASE = OUTPUT_DIR / "attraction_reviews.json"
PLACES_CSV = BASE_DIR / "data" / "places_data.csv"

# Canonical issue taxonomy (LLM classifies reviews into these)
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

# Retrieval: max reviews passed to LLM per query
MAX_REVIEWS = 15


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
