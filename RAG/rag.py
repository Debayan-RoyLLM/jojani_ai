"""RAG engine: retrieve reviews → LLM classify/summarize → structured response."""

import json
import re

from . import config
from .llm import call_llm
from .retrieval import Retriever

_SYSTEM_PROMPT = """\
You are a multilingual review analyst. You receive a set of tourist-attraction reviews \
and a user query. Classify and summarize them.

Canonical taxonomy (use these exact labels for issue_type):
{taxonomy}

Rules:
- Reviews may be in any language (German, French, Spanish, etc.). Classify into the English taxonomy regardless of the review language.
- "summary" must be a concise 2-4 sentence summary of what reviewers say about the queried topic.
- "actions" must be specific, actionable items the business can take (derived from negative/constructive feedback).
- "source_reviews" must list the raw reviews you used as evidence (keep original language).
- If the reviews are mostly positive, say so in the summary and keep actions minimal.
- Respond ONLY with valid JSON, no markdown fences, no extra text.
"""


def _build_prompt(query: str, reviews: list[dict], location: str | None) -> str:
    taxonomy_str = "\n".join(f"- {t}" for t in config.TAXONOMY)
    system = _SYSTEM_PROMPT.format(taxonomy=taxonomy_str)

    reviews_str = "\n\n".join(
        f"[{i+1}] attraction_id: {r['attraction_id']} | date: {r['date']} | rating: {r['rating']}\n"
        f"\"{r['review_text'][:800]}\""
        for i, r in enumerate(reviews)
    )

    location_str = f"\nMatched location: {location}" if location else ""
    return (
        f"{system}\n\n"
        f"Reviews:\n{reviews_str}\n\n"
        f"User query: \"{query}\"{location_str}\n\n"
        f"Respond in JSON:\n"
        f'{{"summary": "...", "actions": ["..."], "source_reviews": [{{"attraction_id": "...", '
        f'"date": "...", "rating": 0, "review_text": "..."}}]}}'
    )


def _parse_response(text: str) -> dict:
    """Extract JSON from LLM response (handles accidental markdown fences)."""
    text = text.strip()
    m = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.DOTALL)
    if m:
        text = m.group(1)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            pass
    return {"summary": text, "actions": [], "source_reviews": []}


class RAGEngine:
    """Top-level RAG: query → retrieve → LLM → structured dict."""

    def __init__(self):
        self.retriever = Retriever()

    def ask(self, query: str, max_reviews: int | None = None) -> dict:
        k = max_reviews or config.MAX_REVIEWS
        reviews, location = self.retriever.search(query, k)

        if not reviews:
            return {
                "location": location,
                "summary": "No relevant reviews found for this query.",
                "actions": [],
                "source_reviews": [],
            }

        reviews_list = [
            {
                "attraction_id": r.attraction_id,
                "date": r.date,
                "rating": r.rating,
                "review_text": r.review_text,
            }
            for r in reviews
        ]

        prompt = _build_prompt(query, reviews_list, location)
        raw = call_llm(prompt)
        result = _parse_response(raw)

        result.setdefault("summary", "")
        result.setdefault("actions", [])
        result.setdefault("source_reviews", reviews_list)
        result["location"] = location
        return result
