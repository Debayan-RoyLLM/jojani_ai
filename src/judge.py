"""Shared batch-judging logic used by both the CLI and the web app."""

from src import config
from src.llm import call_llm, parse_llm_json
from src.prompts import build_judge_prompt


def judge_all_reviews(reviews: list[str], on_batch_done=None) -> list[dict]:
    """Judge all reviews in batches and return the combined results.

    Args:
        reviews: List of review texts.
        on_batch_done: Optional callback called with (done_count, total)
            after each batch completes. Used for progress reporting.
    """
    results: list[dict] = []
    for start in range(0, len(reviews), config.BATCH_SIZE):
        batch = reviews[start : start + config.BATCH_SIZE]
        prompt = build_judge_prompt(batch, start)
        print(f"  Calling LLM for reviews {start + 1}–{start + len(batch)}...", end=" ", flush=True)
        raw = call_llm(prompt)
        batch_results = parse_llm_json(raw)
        results.extend(batch_results)
        print(f"got {len(batch_results)} results")
        if on_batch_done:
            on_batch_done(min(start + config.BATCH_SIZE, len(reviews)), len(reviews))
    return results
