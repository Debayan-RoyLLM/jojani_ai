"""Single source of truth for the pipeline layout.

Every stage resolves its input/output paths and the embedding model through
this module, so a folder rename is a one-line change here instead of a hunt
across per-stage config.py files.
"""
from pathlib import Path

# Repo root = this file's directory.
ROOT = Path(__file__).resolve().parent

# --- Stage folders (edit a name HERE if you rename a folder) ----------------
CLAUSE_SPLIT_DIR     = ROOT / "clause_split"
SENTIMENT_DIR        = ROOT / "sentiment_analysis"
CLAUSE_FLATTEN_DIR   = ROOT / "clause_flatten"
EMBED_DIR            = ROOT / "embed"
RAG_DIR              = ROOT / "rag_clusters"
OUTPUT_DIR           = ROOT / "output"

# --- Data / intermediate artifacts (what each stage consumes/produces) -------
JOINED_REVIEW_CSV = OUTPUT_DIR / "apify_reviews_joined.csv"   # join_csv -> clause_split
REVIEW_CLAUSES   = CLAUSE_SPLIT_DIR / "review_clauses.jsonl"   # clause_split -> sentiment_analysis
NEG_CLAUSES      = SENTIMENT_DIR / "negative_clauses.jsonl"    # sentiment_analysis -> clause_flatten
POS_CLAUSES      = SENTIMENT_DIR / "positive_clauses.jsonl"
FLAT_NEG_CLAUSES = CLAUSE_FLATTEN_DIR / "negative_clauses_flat.jsonl"  # clause_flatten -> embed
EMBEDDED_NEG     = EMBED_DIR / "negative_clauses_embedded.jsonl"       # embed -> rag_clusters
FAISS_INDEX      = EMBED_DIR / "negative_clauses.faiss"                # embed -> rag_clusters

# --- Embedding model ---------------------------------------------------------
# The local `clustering/minilm-l12-v2` dir is no longer in the tree; the model
# lives in the HuggingFace cache, so the HF id is the working default. Point
# this at a local dir if you ever vendor the weights back into the repo.
EMBED_MODEL_DIR = ROOT / "clustering" / "minilm-l12-v2"
EMBED_MODEL_FALLBACK = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

# --- BERT sentiment model ----------------------------------------------------
# HF id (cached locally after first download).
SENTIMENT_MODEL = "nlptown/bert-base-multilingual-uncased-sentiment"


def embedding_model() -> str:
    """Local MiniLM dir if present, else the HF id (pulled from cache)."""
    return str(EMBED_MODEL_DIR) if EMBED_MODEL_DIR.is_dir() else EMBED_MODEL_FALLBACK
