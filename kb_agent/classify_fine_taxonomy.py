"""Classify each negative-cluster block into ONE fine-grained subcategory.

Fine-grained counterpart of `classify_taxonomy.py`. Instead of the 20-category
canonical list (rag_clusters.config), this uses the 20-group / 90-subcategory
taxonomy defined in `kb_agent/taxonomy.py`. Each block is assigned the SINGLE
best subcategory key (snake_case, e.g. "high_entry_fee") plus a 3-6 word block
name. A block that fits nothing gets the residual key "other".

Reads `negative_clusters.jsonl` (one block per line). Output
`output/fine_taxonomy_grouping.jsonl` is one line PER GROUP:
    {"group_id": "pricing", "group_label": "Pricing", "block_count": N,
     "blocks": [{"cluster_id": 1, "subcategory_key": "high_entry_fee",
                 "subcategory_label": "High entry / admission fee",
                 "block_name": "...", "size": 117}, ...]}
Blocks are nested under their group; a group is omitted if it has no blocks.

KISS + resumable: per-block results are checkpointed to
`output/.fine_taxonomy_cache.json` as we go, so an interrupted run resumes
without re-calling the LLM for already-classified blocks.

Usage:
    python -m kb_agent.classify_fine_taxonomy              # full run (resumable)
    python -m kb_agent.classify_fine_taxonomy --limit 20   # only first 20 blocks
    python -m kb_agent.classify_fine_taxonomy --report-only
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import OrderedDict
from pathlib import Path

from . import llm, taxonomy

ROOT = Path(__file__).resolve().parent.parent
INPUT = ROOT / "negative_clusters.jsonl"
OUTPUT = ROOT / "output" / "fine_taxonomy_grouping.jsonl"
CACHE = ROOT / "output" / ".fine_taxonomy_cache.json"

# Number of representative clauses sampled per block for the LLM prompt.
SAMPLE_CLAUSES = 12
# Truncate each sampled clause to this many chars (mirrors classify_taxonomy.py).
CLAUSE_CHAR_LIMIT = 200

# Valid subcategory keys the LLM may echo (all 90 + the residual "other").
_VALID_KEYS = taxonomy.all_subcategory_keys()
RESIDUAL_KEY = "other"

SYSTEM_PROMPT = (
    "You are a review analyst. You are given a block of complaint clauses "
    "gathered from tourist reviews. Decide the SINGLE best subcategory that "
    "best describes this block's dominant issue, and a short label for the block.\n"
    "Subcategories (choose exactly one, use the exact key in [brackets]):\n"
    "{taxonomy}\n"
    "Rules:\n"
    "- Pick ONE subcategory only — the one that captures the block's main theme.\n"
    "- 'subcategory_key' must be the exact snake_case key shown in [brackets].\n"
    "- If nothing fits any subcategory, use the residual key 'other'.\n"
    "- 'block_name' must be a short 3-6 word English label naming the block's "
    "core issue (no reviewer quotes, no fluff).\n"
    "Respond with ONLY a JSON object, no prose, in this exact shape:\n"
    '{{"subcategory_key": "<snake_case_key>", "block_name": "<3-6 word label>"}}'
)


def _taxonomy_listing() -> str:
    """Render all groups + subcategories as `[key] label`, grouped, for the prompt."""
    lines: list[str] = []
    for g in taxonomy.all_groups():
        lines.append(f"## {g['group_id']} — {g['label']}")
        for key, label in g["subcategories"]:
            lines.append(f"[{key}] {label}")
    return "\n".join(lines)


def _block_label(block: dict) -> tuple[int, int, list[str]]:
    """Return (cluster_id, size, clauses) from a block line, tolerating shape."""
    cid = block.get("cluster_id", 0)
    try:
        cid = int(cid)
    except (TypeError, ValueError):
        cid = 0
    clauses = block.get("clauses", []) or []
    texts: list[str] = []
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
    """Ask the LLM for (subcategory_key, block_name) for one block. Falls back to
    ("other", '') on parse errors so a single bad block never kills the run."""
    sample = texts[:SAMPLE_CLAUSES]
    body = "\n".join(f"- {t[:CLAUSE_CHAR_LIMIT]}" for t in sample)
    user = f"Complaint clauses from this block:\n{body}"
    raw = llm._call(
        [
            {"role": "system", "content": SYSTEM_PROMPT.format(taxonomy=_taxonomy_listing())},
            {"role": "user", "content": user},
        ]
    )
    try:
        data = llm._extract_json(raw)
        key = str(data.get("subcategory_key", "")).strip().lower()
        name = str(data.get("block_name", "")).strip()
    except Exception:  # noqa: BLE001
        key, name = "", ""
    # A key outside the valid set (incl. a mis-parsed group id) -> residual.
    if key not in _VALID_KEYS:
        key = RESIDUAL_KEY
    return key, name


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
    """Group classified blocks by their subcategory's group ->
    {group_id: [block dicts]}, ordered by taxonomy display order.

    Each block dict also carries its subcategory_key/label. Groups with no
    blocks are dropped."""
    # Map each subcategory key to its group so we can bucket blocks by group.
    # (Copy so we don't mutate the module-level dict.)
    key_to_group = dict(taxonomy.KEY_TO_GROUP)
    # The residual key lives in RESIDUALS, not FINE_TAXONOMY.
    key_to_group["other"] = "residual"
    order = [g["group_id"] for g in taxonomy.all_groups()]

    groups: "OrderedDict[str, list[dict]]" = OrderedDict((gid, []) for gid in order)
    for cid, entry in cache.items():
        key = str(entry.get("subcategory_key", "other")).strip()
        if key not in key_to_group:
            key = "other"
        gid = key_to_group[key]
        groups.setdefault(gid, []).append(
            {
                "cluster_id": int(cid),
                "subcategory_key": key,
                "subcategory_label": taxonomy.subcategory_label(key),
                "block_name": entry.get("block_name", ""),
                "size": entry.get("size", 0),
            }
        )
    for gid in groups:
        groups[gid].sort(key=lambda b: b["cluster_id"])
    return OrderedDict((gid, blks) for gid, blks in groups.items() if blks)


def main() -> None:
    parser = argparse.ArgumentParser(description="Group negative-cluster blocks by fine-grained taxonomy")
    parser.add_argument("--input", default=str(INPUT))
    parser.add_argument("--output", default=str(OUTPUT))
    parser.add_argument("--limit", type=int, default=0, help="Only process the first N blocks")
    parser.add_argument("--report-only", action="store_true", help="Just re-emit the report from the cache")
    parser.add_argument("--no-cache", action="store_true",
                        help="Ignore any existing cache and re-call the LLM for every block "
                             "(use after the taxonomy has changed, so old keys don't fall to 'other')")
    args = parser.parse_args()

    in_path = Path(args.input)
    if not in_path.exists():
        print(f"[error] input not found: {in_path}", file=sys.stderr)
        sys.exit(1)

    blocks: list[dict] = []
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

    cache = {} if args.no_cache else _load_cache()
    todo = [b for b in blocks if str(b.get("cluster_id", 0)) not in cache]
    print(f"Loaded {len(blocks)} blocks; {len(todo)} to classify "
          f"({len(blocks) - len(todo)} already cached)")

    if not args.report_only:
        for i, block in enumerate(todo, 1):
            cid, size, texts = _block_label(block)
            if not texts:
                key, name = RESIDUAL_KEY, ""
            else:
                try:
                    key, name = classify_block(texts)
                except Exception as e:  # noqa: BLE001
                    print(f"  [block {cid}] FAILED: {e} — skipping", file=sys.stderr)
                    continue
            cache[str(cid)] = {"subcategory_key": key, "block_name": name, "size": size}
            if i % 10 == 0 or i == len(todo):
                print(f"  [{i}/{len(todo)}] classified -> {key} | {name}")
                _save_cache(cache)  # checkpoint every 10 so a crash loses <=10 blocks
        _save_cache(cache)

    report = build_report(cache)

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as fh:
        for gid, blks in report.items():
            fh.write(json.dumps(
                {"group_id": gid, "group_label": taxonomy.group_label(gid),
                 "block_count": len(blks), "blocks": blks},
                ensure_ascii=False,
            ) + "\n")

    print(f"\nWrote {out_path}")
    print(f"\n=== Grouping summary ({len(report)} groups) ===")
    for gid, blks in sorted(report.items(), key=lambda kv: -len(kv[1])):
        print(f"  {taxonomy.group_label(gid):<35} {len(blks):>4} blocks")


if __name__ == "__main__":
    main()
