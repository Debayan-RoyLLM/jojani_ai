"""kb_agent runner.

Reads negative_clusters.jsonl (one cluster block per line), and for each block
produces one knowledge-base entry: the distinct issues raised, each with an
importance score out of 10. No issue is repeated.

Usage:
    python -m kb_agent.run                  # full run -> output/knowledge_base.jsonl
    python -m kb_agent.run --limit 5        # only the first 5 blocks (for testing)
    python -m kb_agent.run --input PATH     # override the input file

The input file format is flexible; each JSON line may be:
    * a list of clause strings            ["staff was rude", "food was cold", ...]
    * {"clauses": [...]}                  clauses nested under a key
    * {"clauses": [{"clause_text": ...}]} clauses as objects
    * a single object with a "text"/"clause_text"/"clause" string field
Anything else is ignored (see _extract_clauses).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import config, llm
from .dedup import merge_near_duplicates


def _extract_clauses(obj) -> list[str]:
    """Pull a list of clause strings out of one JSON line, whatever its shape."""
    if isinstance(obj, str):
        return [obj] if obj.strip() else []

    if isinstance(obj, list):
        clauses: list[str] = []
        for item in obj:
            if isinstance(item, str):
                if item.strip():
                    clauses.append(item)
            elif isinstance(item, dict):
                text = item.get("clause_text") or item.get("clause") or item.get("text")
                if isinstance(text, str) and text.strip():
                    clauses.append(text)
        return clauses

    if isinstance(obj, dict):
        # Nested clause list under a common key.
        for key in ("clauses", "items", "members", "samples", "text", "issue", "issues"):
            if key in obj:
                nested = _extract_clauses(obj[key])
                if nested:
                    return nested
        # Otherwise treat this single object as one clause.
        text = obj.get("clause_text") or obj.get("clause") or obj.get("text")
        if isinstance(text, str) and text.strip():
            return [text]

    return []


def _load_blocks(path: Path) -> list[list[str]]:
    blocks: list[list[str]] = []
    with path.open(encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, 1):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError as e:
                print(f"  [warn] line {lineno}: unparseable JSON, skipped ({e})")
                continue
            clauses = _extract_clauses(obj)
            if clauses:
                blocks.append(clauses)
    return blocks


def _chunk(seq: list[str], size: int) -> list[list[str]]:
    return [seq[i : i + size] for i in range(0, len(seq), size)]


def build_entry(clauses: list[str]) -> dict:
    """Summarize one block into distinct, scored issues (no repeats)."""
    # Pre-merge near-identical clauses so the LLM sees a tighter input.
    clauses = merge_near_duplicates(clauses, config.DEDUP_THRESHOLD)

    issues: list[dict] = []
    for chunk in _chunk(clauses, config.MAX_CHUNK_CLAUSES):
        issues.extend(llm.summarize_clauses(chunk))

    # Canonical issue text + re-merge any duplicates across chunks.
    text_issues = merge_near_duplicates(
        [i["issue"] for i in issues], config.DEDUP_THRESHOLD
    )

    # When the same issue text recurs across chunks, average its importance.
    importance: dict[str, list[int]] = {}
    for i in issues:
        importance.setdefault(i["issue"], []).append(i["importance"])

    result = []
    for issue in text_issues:
        scores = importance.get(issue) or [0]
        result.append({"issue": issue, "importance": round(sum(scores) / len(scores))})

    # Most important first.
    result.sort(key=lambda x: x["importance"], reverse=True)
    return {"issues": result, "clause_count": len(clauses)}


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a knowledge base from negative-cluster blocks")
    parser.add_argument("--input", default=str(config.INPUT_JSONL))
    parser.add_argument("--output", default=str(config.OUTPUT_JSONL))
    parser.add_argument("--limit", type=int, default=0, help="Only process the first N blocks")
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"[error] input not found: {input_path}", file=sys.stderr)
        print("        Place your negative_clusters.jsonl there (or pass --input PATH).", file=sys.stderr)
        sys.exit(1)

    blocks = _load_blocks(input_path)
    if args.limit > 0:
        blocks = blocks[: args.limit]
    if not blocks:
        print("[warn] no cluster blocks found in input.", file=sys.stderr)
        return

    print(f"Loaded {len(blocks)} cluster block(s) from {input_path.name}")
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    written = 0
    with out_path.open("w", encoding="utf-8") as fh:
        for idx, clauses in enumerate(blocks, 1):
            try:
                entry = build_entry(clauses)
            except Exception as e:  # noqa: BLE001
                print(f"  [block {idx}] FAILED: {e} — skipped")
                continue
            entry = {"cluster_id": idx, **entry}
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
            written += 1
            top = entry["issues"][0]["issue"] if entry["issues"] else "(no issues)"
            n = len(entry["issues"])
            print(f"  [block {idx}] {n} distinct issue(s) | top: {top}")

    print(f"\nWrote {written} knowledge-base entries -> {out_path}")


if __name__ == "__main__":
    main()
