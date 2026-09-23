"""RAG engine: embed-query → retrieve clusters → LLM classify/summarize → structured response."""

import json
import re

from . import config
from .llm import call_llm
from .retriever import Retriever

_SYSTEM_PROMPT = """\
You are a multilingual review analyst. You receive a set of tourist-attraction review clauses \
and a user query. Classify and summarize them.

Canonical taxonomy (use these exact labels for issue_type):
{taxonomy}

Rules:
- Clauses may be in any language (German, French, Spanish, etc.). Classify into the English taxonomy regardless.
- "summary" must be a concise 2-4 sentence summary of what reviewers say about the queried topic.
- "actions" must be specific, actionable items the business can take (derived from negative/constructive feedback).
- "source_clauses" must list the raw clauses you used as evidence (keep original language).
- If the clauses are mostly positive, say so in the summary and keep actions minimal.
- Respond ONLY with valid JSON, no markdown fences, no extra text.
"""

# Reverse lookup: human-readable label -> snake_case key. Lets the parser
# accept either form the LLM may echo back for issue_type.
_LABEL_TO_KEY = {v.lower().replace("–", "-"): k for k, v in config.TAXONOMY_DISPLAY.items()}


def _build_prompt(query: str, clauses: list[dict]) -> str:
    # Present the human-readable labels to the LLM (more natural than raw keys).
    taxonomy_str = "\n".join(f"- {config.display_title(t)}" for t in config.TAXONOMY)
    system = _SYSTEM_PROMPT.format(taxonomy=taxonomy_str)

    clauses_str = "\n\n".join(
        f"[{i+1}] place: {c['place_name']} | score: {c['score']:.2f}\n"
        f"\"{c['clause_text'][:400]}\""
        for i, c in enumerate(clauses)
    )

    return (
        f"{system}\n\n"
        f"Review clauses:\n{clauses_str}\n\n"
        f"User query: \"{query}\"\n\n"
        f"Respond in JSON:\n"
        f'{{"summary": "...", "actions": ["..."], "source_clauses": '
        f'[{{"clause_text": "...", "score": 0, "date": "..."}}]}}'
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
    return {"summary": text, "actions": [], "source_clauses": []}


class RAGEngine:
    """Top-level RAG: query → embed → retrieve clusters → LLM → structured dict."""

    def __init__(self):
        self.retriever = Retriever()

    def ask(self, query: str, max_clauses: int | None = None) -> dict:
        k = max_clauses or config.MAX_REVIEWS
        clauses = self.retriever.search(query, k)

        if not clauses:
            return {
                "summary": "No relevant review clauses found for this query.",
                "actions": [],
                "source_clauses": [],
            }

        clauses_list = [
            {
                "clause_text": c.clause_text,
                "score": c.score,
                "place_name": c.place_name,
            }
            for c in clauses
        ]

        prompt = _build_prompt(query, clauses_list)
        raw = call_llm(prompt)
        result = _parse_response(raw)

        result.setdefault("summary", "")
        result.setdefault("actions", [])
        result["source_clauses"] = clauses_list
        return result
