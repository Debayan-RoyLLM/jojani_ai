"""Classify each negative-cluster block into ONE canonical taxonomy category.

Reads `negative_clusters.jsonl` (944 blocks), asks the LLM to assign each block
the single best category from the canonical taxonomy (reused from
rag_clusters.config) plus a short 3-6 word block name, and writes a grouped
report: each category lists its blocks (name + id) and the block count.

Output: `output/taxonomy_grouping.jsonl` — one line per category:
    {"category": "...", "block_count": N,
     "blocks": [{"cluster_id": 1, "block_name": "...", "size": 117}, ...]}

KISS + resumable: per-block results are checkpointed to
`output/.taxonomy_cache.json` as we go, so an interrupted run can be resumed
without re-calling the LLM for blocks already classified.

Usage:
    python -m kb_agent.classify_taxonomy              # full run (resumable)
    python -m kb_agent.classify_taxonomy --limit 20   # only first 20 blocks (test)
    python -m kb_agent.classify_taxonomy --report-only # just re-emit the report
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import OrderedDict
from pathlib import Path

from . import config, llm

ROOT = Path(__file__).resolve().parent.parent
INPUT = ROOT / "negative_clusters.jsonl"
OUTPUT = ROOT / "output" / "taxonomy_grouping.jsonl"
CACHE = ROOT / "output" / ".taxonomy_cache.json"

# Canonical taxonomy reused from the RAG config (single source of truth).
sys_path_hack = None
try:
    from rag_clusters import config as rag_config
    TAXONOMY = list(rag_config.TAXONOMY)
except Exception:  # pragma: no cover - rag_clusters import edge case
    import rag_clusters.config as rag_config  # type: ignore
    TAXONOMY = list(rag_config.TAXONOMY)

# Number of representative clauses sampled per block for the LLM prompt.
SAMPLE_CLAUSES = 12
# Truncate each sampled clause to this many chars (mirrors kb_agent style).
CLAUSE_CHAR_LIMIT = 200

SYSTEM_PROMPT = (
    "You are a review analyst. You are given a block of complaint clauses "
    "gathered from tourist reviews. Decide the SINGLE best category that best "
    "describes this block's dominant issue, and a short label for the block.\n"
    "Categories (choose exactly one, use the exact label):\n"
    "{taxonomy}\n"
    "Rules:\n"
    "- Pick ONE category only — the one that captures the block's main theme.\n"
    "- If the block's clauses are mostly positive, use 'positive_highlight'.\n"
    "- If nothing fits, use 'other'.\n"
    "- 'block_name' must be a short 3-6 word English label naming the block's "
    "core issue (no reviewer quotes, no fluff).\n"
    "Respond with ONLY a JSON object, no prose, in this exact shape:\n"
    '{{"category": "<one of the labels above>", "block_name": "<3-6 word label>"}}'
)


def _block_label(block: dict) -> tuple[int, int, list[str]]:
    """Return (cluster_id, size, clauses) from a block line, tolerating shape."""
    cid = block.get("cluster_id", 0)
    try:
        cid = int(cid)
    except (TypeError, ValueError):
        cid = 0
    clauses = block.get("clauses", []) or []
    texts = []
    for c in clauses:
        if isinstance(c, str) and c.strip():
            texts.append(c)
        elif isinstance(c, dict):
            t = c.get("clause_text") or c.get("text") or ""
            if isinstance(t, str) and t.strip():
                texts.append(t)
    size = block.get("size", len(texts))
    return cid, size, texts


def classify_block(texts: list[str]) -> tuple[str, str]:
    """Ask the LLM for (category, block_name) for one block. Falls back to
    ('other', '') on parse errors so a single bad block never kills the run."""
    sample = texts[:SAMPLE_CLAUSES]
    body = "\n".join(f"- {t[:CLAUSE_CHAR_LIMIT]}" for t in sample)
    user = f"Complaint clauses from this block:\n{body}"
    raw = llm._call(
        [
            {"role": "system", "content": SYSTEM_PROMPT.format(taxonomy="\n".join(f"- {t}" for t in TAXONOMY))},
            {"role": "user", "content": user},
        ]
    )
    try:
        data = llm._extract_json(raw)
        cat = str(data.get("category", "")).strip().lower()
        name = str(data.get("block_name", "")).strip()
    except Exception:  # noqa: BLE001
        cat, name = "", ""
    # Sanitize: must be one of the canonical labels, else 'other'.
    if cat not in TAXONOMY:
        cat = "other"
    return cat, name


def _load_cache() -> dict:
    if CACHE.exists():
        try:
            return json.loads(CACHE.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            return {}
    return {}


def _save_cache(cache: dict) -> None:
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=0), encoding="utf-8")


def build_report(cache: dict) -> dict:
    """Group classified blocks by category -> {cat: [block dicts]}, ordered by
    taxonomy order (with 'other' last)."""
    groups: "OrderedDict[str, list[dict]]" = OrderedDict((c, []) for c in TAXONOMY)
    # Any category outside the taxonomy (shouldn't happen) still gets a slot.
    for cid, entry in cache.items():
        cat = entry.get("category", "other")
        groups.setdefault(cat, []).append(
            {
                "cluster_id": int(cid),
                "block_name": entry.get("block_name", ""),
                "size": entry.get("size", 0),
            }
        )
    # Sort blocks within each category by id for stable output.
    for cat in groups:
        groups[cat].sort(key=lambda b: b["cluster_id"])
    # Drop empty categories so the report only shows what's present.
    return OrderedDict((cat, blocks) for cat, blocks in groups.items() if blocks)


def main() -> None:
    parser = argparse.ArgumentParser(description="Group negative-cluster blocks by taxonomy")
    parser.add_argument("--input", default=str(INPUT))
    parser.add_argument("--output", default=str(OUTPUT))
    parser.add_argument("--limit", type=int, default=0, help="Only process the first N blocks")
    parser.add_argument("--report-only", action="store_true", help="Just re-emit the report from the cache")
    args = parser.parse_args()

    in_path = Path(args.input)
    if not in_path.exists():
        print(f"[error] input not found: {in_path}", file=sys.stderr)
        sys.exit(1)

    blocks = []
    with in_path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                blocks.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    if args.limit > 0:
        blocks = blocks[: args.limit]

    cache = _load_cache()
    todo = [b for b in blocks if str(b.get("cluster_id", 0)) not in cache]
    print(f"Loaded {len(blocks)} blocks; {len(todo)} to classify "
          f"({len(blocks) - len(todo)} already cached)")

    for i, block in enumerate(todo, 1):
        cid, size, texts = _block_label(block)
        if not texts:
            cat, name = "other", ""
        else:
            try:
                cat, name = classify_block(texts)
            except Exception as e:  # noqa: BLE001
                print(f"  [block {cid}] FAILED: {e} — skipping", file=sys.stderr)
                continue
        cache[str(cid)] = {"category": cat, "block_name": name, "size": size}
        if i % 10 == 0 or i == len(todo):
            print(f"  [{i}/{len(todo)}] classified -> {cat} | {name}")
            _save_cache(cache)  # checkpoint every 10 so a crash loses <=10 blocks

    _save_cache(cache)
    report = build_report(cache)

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as fh:
        for cat, blks in report.items():
            fh.write(json.dumps(
                {"category": cat, "block_count": len(blks), "blocks": blks},
                ensure_ascii=False,
            ) + "\n")

    print(f"\nWrote {out_path}")
    print(f"\n=== Grouping summary ({len(report)} categories) ===")
    for cat, blks in sorted(report.items(), key=lambda kv: -len(kv[1])):
        print(f"  {cat:<28} {len(blks):>4} blocks")


if __name__ == "__main__":
    main()
