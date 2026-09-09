#!/usr/bin/env python3
"""CLI: judge matched reviews with the LLM, save results to judge_results.md."""

import json

from src import config
from src.llm import call_llm
from src.parse_reviews import parse_matched_reviews
from src.prompts import build_judge_prompt


def judge_batch(reviews: list[str], offset: int) -> list[dict]:
    """Send one batch of reviews to the LLM and return the parsed JSON results."""
    prompt = build_judge_prompt(reviews, offset)
    print(f"  Calling LLM for reviews {offset + 1}–{offset + len(reviews)}...", end=" ", flush=True)
    raw = call_llm(prompt).strip()
    # Strip markdown code fences if the model wrapped the response
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1]
        if raw.endswith("```"):
            raw = raw[: -3]
    results = json.loads(raw)
    print(f"got {len(results)} results")
    return results


def main() -> None:
    if not config.MATCHED_REVIEWS_MD.exists():
        raise SystemExit(
            f"Input file not found: {config.MATCHED_REVIEWS_MD}\n"
            "Run steps 1 and 2 first (see README)."
        )

    entries = parse_matched_reviews(config.MATCHED_REVIEWS_MD)
    reviews = [rev for _, rev in entries]
    print(f"Loaded {len(reviews)} reviews from {config.MATCHED_REVIEWS_MD.name}")
    print(f"LLM: {config.LLM_URL} (model: {config.LLM_MODEL})")
    print(f"Batch size: {config.BATCH_SIZE}\n")

    all_results: list[dict] = []
    for start in range(0, len(reviews), config.BATCH_SIZE):
        batch = reviews[start : start + config.BATCH_SIZE]
        try:
            all_results.extend(judge_batch(batch, start))
        except Exception as e:
            print(f"  ERROR on batch starting at review {start + 1}: {e}")
            all_results.append({
                "index": start + 1,
                "sentiment": "error",
                "reason": str(e),
                "action_items": [],
            })

    # Write markdown output (negative reviews only)
    lines = [
        "# LLM Judge — Negative Reviews",
        "",
        f"Total negative reviews: {len(all_results)}",
        "",
    ]
    for r in all_results:
        idx = r.get("index", "?")
        lines.append(f"## Review {idx}")
        lines.append("")
        lines.append(f"**Reason:** {r.get('reason', 'N/A')}")
        if r.get("action_items"):
            lines.append("")
            lines.append("**Action items:**")
            for item in r["action_items"]:
                lines.append(f"- {item}")
        lines.append("")

    config.JUDGE_RESULTS_MD.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nDone. Found {len(all_results)} negative reviews out of {len(reviews)} total")
    print(f"Results written to {config.JUDGE_RESULTS_MD}")


if __name__ == "__main__":
    main()
