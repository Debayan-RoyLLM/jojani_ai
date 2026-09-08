#!/usr/bin/env python3
"""LLM-as-judge: classify reviews in matched_reviews.md as positive/negative.

For negative reviews, the LLM states what can be implemented to improve.
Uses an OpenAI-compatible local LLM endpoint.
"""

import json
import os
import time
from pathlib import Path

import requests

BASE_DIR = Path(__file__).parent.parent
INPUT_PATH = BASE_DIR / "output" / "matched_reviews.md"
OUTPUT_PATH = BASE_DIR / "output" / "judge_results.md"
ENV_PATH = BASE_DIR / ".env"


def load_env(path: Path) -> None:
    """Load key=value pairs from .env file."""
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())


load_env(ENV_PATH)

# --- Config (from .env or system env vars) ---
LLM_URL = os.getenv("LLM_URL", "")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "")
BATCH_SIZE = 5  # reviews per LLM call
MAX_RETRIES = 3

PROMPT = """You are a review analyst. For each review below, determine if it is NEGATIVE (complains about problems, poor service, hygiene issues, safety concerns, etc.).

- If NEGATIVE: list specific actionable improvements (what can be implemented/fixed).
- If POSITIVE or NEUTRAL: discard it (do not include in output).

Respond ONLY with a JSON array of the NEGATIVE reviews only. Each element:
{"index": <int>, "reason": "<one sentence explaining why it's negative>", "action_items": ["...", "..."]}

If NO reviews are negative, respond with an empty array: []

Reviews:
"""


def parse_reviews(path: Path) -> list[str]:
    """Parse matched_reviews.md into review texts."""
    text = path.read_text(encoding="utf-8")
    reviews = []
    current = []
    for line in text.splitlines():
        if line.startswith("## "):
            if current:
                reviews.append("\n".join(current).strip())
            current = []
        elif line.startswith("# "):
            continue
        else:
            current.append(line)
    if current:
        reviews.append("\n".join(current).strip())
    return [r for r in reviews if r]


def call_llm(prompt: str) -> str:
    payload = {
        "model": LLM_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.1,
    }
    headers = {"Authorization": f"Bearer {LLM_API_KEY}", "Content-Type": "application/json"}

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.post(LLM_URL, json=payload, headers=headers, timeout=120)
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]
        except Exception as e:
            print(f"  Attempt {attempt}/{MAX_RETRIES} failed: {e}")
            if attempt == MAX_RETRIES:
                raise
            time.sleep(2 * attempt)


def judge_batch(reviews: list[str], offset: int) -> list[dict]:
    review_block = "\n\n".join(
        f"--- Review {offset + i + 1} ---\n{r}" for i, r in enumerate(reviews)
    )
    full_prompt = PROMPT + review_block
    print(f"  Calling LLM for reviews {offset + 1}–{offset + len(reviews)}...", end=" ", flush=True)
    raw = call_llm(full_prompt)
    # Strip markdown code fences if present
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1]
        if raw.endswith("```"):
            raw = raw[: -3]
    results = json.loads(raw)
    print(f"got {len(results)} results")
    return results


def main() -> None:
    reviews = parse_reviews(INPUT_PATH)
    print(f"Loaded {len(reviews)} reviews from {INPUT_PATH.name}")
    print(f"LLM: {LLM_URL} (model: {LLM_MODEL})")
    print(f"Batch size: {BATCH_SIZE}\n")

    all_results = []
    for start in range(0, len(reviews), BATCH_SIZE):
        batch = reviews[start : start + BATCH_SIZE]
        try:
            batch_results = judge_batch(batch, start)
            all_results.extend(batch_results)
        except Exception as e:
            print(f"  ERROR on batch starting at review {start + 1}: {e}")
            # Save what we have so far
            all_results.append({"index": start + 1, "sentiment": "error", "reason": str(e), "action_items": []})

    # Write output (only negatives)
    lines = ["# LLM Judge — Negative Reviews", "", f"Total negative reviews: {len(all_results)}", ""]

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

    OUTPUT_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nDone. Found {len(all_results)} negative reviews out of {len(reviews)} total")
    print(f"Results written to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
