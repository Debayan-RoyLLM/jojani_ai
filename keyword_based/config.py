"""Project configuration: loads .env and exposes LLM settings + paths."""

import os
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "output"
ENV_PATH = BASE_DIR / ".env"

INPUT_REVIEW_CSV = DATA_DIR / "Booking_reviews.csv"
PLACES_CSV = DATA_DIR / "places_data.csv"
REVIEWS_MD = OUTPUT_DIR / "reviews.md"
MATCHED_REVIEWS_MD = OUTPUT_DIR / "matched_reviews.md"
JUDGEMENTS_CSV = OUTPUT_DIR / "judgements.csv"
JUDGE_RESULTS_MD = OUTPUT_DIR / "judge_results.md"
PROGRESS_FILE = OUTPUT_DIR / "judgement_progress.json"


def _load_env(path: Path) -> None:
    """Populate os.environ from a key=value .env file (without overwriting existing vars)."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())


_load_env(ENV_PATH)

# LLM configuration (OpenAI-compatible endpoint)
LLM_URL = os.getenv("LLM_URL", "")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "")

# LLM call settings
BATCH_SIZE = 5
MAX_RETRIES = 3
LLM_TIMEOUT = 120
