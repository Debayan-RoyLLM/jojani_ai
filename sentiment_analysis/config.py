"""Configuration for the sentiment-analysis pipeline."""
from pathlib import Path

# Project root (two levels up from this file: sentiment-analysis/ -> repo root)
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Default BERT model. A local download of it lives in PROJECT_ROOT/bert-multilingual-sentiment
# (loaded offline); the HF id is the fallback.
MODEL_DIR = PROJECT_ROOT / "bert-multilingual-sentiment"
DEFAULT_MODEL = str(MODEL_DIR) if MODEL_DIR.is_dir() else "nlptown/bert-base-multilingual-uncased-sentiment"

# The model is a sentiment classifier whose internal labels are named "1 star".."5 stars";
# map them to the 3-way semantic buckets: 1-2 -> negative, 3 -> neutral, 4-5 -> positive.
LABEL_TO_SENTIMENT = {
    "1 star": "negative",
    "2 stars": "negative",
    "3 stars": "neutral",
    "4 stars": "positive",
    "5 stars": "positive",
}

# Output file per sentiment, in stable order.
SENTIMENT_FILES = {
    "negative": "negative_clauses.jsonl",
    "neutral": "neutral_clauses.jsonl",
    "positive": "positive_clauses.jsonl",
}
