"""kb_agent configuration — all paths and settings in one place.

The agent reads a JSONL of negative-cluster blocks, and for each block it
produces one knowledge-base entry: the distinct issues raised (no repeats),
each with an importance score out of 10.
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parent
ENV_PATH = ROOT_DIR / ".env"

# --- I/O ---------------------------------------------------------------------
# Input is the clustered blocks written by `python -m kb_agent.cluster` (one
# block per line, shaped {"cluster_id", "clauses": [...], "place_names": [...]}).
# Each line = one cluster block (a list of clause strings). See _load_blocks /
# _extract_clauses in run.py for the tolerated shapes.
INPUT_JSONL = ROOT_DIR / "negative_clusters.jsonl"
OUTPUT_JSONL = ROOT_DIR / "output" / "knowledge_base.jsonl"

# --- LLM endpoint (OpenAI-compatible, same as the rest of the pipeline) -------
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

# --- Agent behaviour ----------------------------------------------------------
MAX_RETRIES = 3
LLM_TIMEOUT = 120

# Near-duplicate merge threshold (Jaccard on normalized token sets). This is a
# SAFETY NET for exact/lexical repeats the LLM still emits; it is NOT the main
# dedup — the LLM merges semantic paraphrases. 0.45 catches close paraphrases
# ("turtles kept in captivity in a small pool" vs "…in a small enclosure")
# without collapsing genuinely distinct issues.
DEDUP_THRESHOLD = 0.45

# A block with this many or fewer clauses is passed to the LLM in one call.
# Larger blocks are split into chunks of CHUNK_SIZE clauses each (each summarized,
# then the per-chunk issues are merged in a final dedup pass).
MAX_CHUNK_CLAUSES = 60

# Truncate each clause to this many characters before sending to the LLM to
# keep prompts bounded (complaints are usually short).
CLAUSE_CHAR_LIMIT = 400
