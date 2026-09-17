#!/usr/bin/env python3
"""CLI: judge matched reviews with the LLM, save results to judge_results.md."""

from keyword_based import config
from keyword_based.judge import judge_all_reviews
from keyword_based.parse_reviews import parse_matched_reviews


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

    results = judge_all_reviews(reviews)

    # Write markdown output (negative reviews only)
    lines = [
        "# LLM Judge — Negative Reviews",
        "",
        f"Total negative reviews: {len(results)}",
        "",
    ]
    for r in results:
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
    print(f"\nDone. Found {len(results)} negative reviews out of {len(reviews)} total")
    print(f"Results written to {config.JUDGE_RESULTS_MD}")


if __name__ == "__main__":
    main()
