"""Prompt templates for LLM review analysis."""

REVIEW_JUDGE_PROMPT = """You are a review analyst. For each review below, determine if it is NEGATIVE (complains about problems, poor service, hygiene issues, safety concerns, etc.).

- If NEGATIVE: list specific actionable improvements (what can be implemented/fixed).
- If POSITIVE or NEUTRAL: discard it (do not include in output).

Respond ONLY with a JSON array of the NEGATIVE reviews only. Each element:
{"index": <int>, "reason": "<one sentence explaining why it's negative>", "action_items": ["...", "..."]}

If NO reviews are negative, respond with an empty array: []

Reviews:
"""


def build_judge_prompt(reviews: list[str], offset: int = 0) -> str:
    """Build the full LLM prompt for a batch of reviews.

    Args:
        reviews: List of review texts to judge.
        offset: 0-based index of the first review in the batch (used for numbering).
    """
    review_block = "\n\n".join(
        f"--- Review {offset + i + 1} ---\n{r}" for i, r in enumerate(reviews)
    )
    return REVIEW_JUDGE_PROMPT + review_block
