"""Minimal OpenAI-compatible LLM client (mirrors rag_clusters/llm.py, KISS)."""
from __future__ import annotations

import json
import time

import requests

from . import config

SYSTEM_PROMPT = (
    "You are a quality-assurance analyst. You are given a block of short "
    "complaint clauses gathered from tourist reviews of a place. Your job is to "
    "distill the DISTINCT issues raised. Rules:\n"
    "1. Merge clauses that say the same thing into ONE canonical issue "
    "statement. Do NOT repeat an issue in different wording.\n"
    "2. Each issue must be a single, concise, factual sentence (no fluff, no "
    "reviewer quotes, no 'reviewers say').\n"
    "3. Assign each issue an importance score from 0 to 10 (integer). Score "
    "reflects how serious and how frequently the issue appears in this block: "
    "safety hazards or issues raised by almost every clause -> 8-10; minor or "
    "one-off annoyances -> 1-4.\n"
    "4. Ignore anything that is not a genuine problem.\n"
    "Respond with ONLY a JSON object, no prose, in this exact shape:\n"
    '{"issues": [{"issue": "<one-sentence issue>", "importance": <0-10>}]}'
)


def _call(messages: list[dict]) -> str:
    payload = {
        "model": config.LLM_MODEL,
        "messages": messages,
        "temperature": 0.0,
    }
    headers = {
        "Authorization": f"Bearer {config.LLM_API_KEY}",
        "Content-Type": "application/json",
    }
    last_exc: Exception | None = None
    for attempt in range(1, config.MAX_RETRIES + 1):
        try:
            resp = requests.post(
                config.LLM_URL, json=payload, headers=headers, timeout=config.LLM_TIMEOUT
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]
        except Exception as e:  # noqa: BLE001
            last_exc = e
            print(f"  LLM attempt {attempt}/{config.MAX_RETRIES} failed: {e}")
            if attempt < config.MAX_RETRIES:
                time.sleep(2 * attempt)
    raise last_exc  # type: ignore[misc]


def _extract_json(text: str) -> dict:
    """Parse the JSON object out of the LLM reply (tolerate stray prose/fences)."""
    text = text.strip()
    if "```" in text:
        text = text.split("```")[1]
        if text.lower().startswith("json"):
            text = text[4:]
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ValueError(f"No JSON object in LLM reply: {text[:200]!r}")
    return json.loads(text[start : end + 1])


def _normalize_issue(obj: dict) -> tuple[str, int]:
    issue = str(obj.get("issue", "")).strip()
    try:
        importance = int(round(float(obj.get("importance", 0))))
    except (TypeError, ValueError):
        importance = 0
    return issue, max(0, min(10, importance))


def summarize_clauses(clauses: list[str]) -> list[dict]:
    """Return distinct issues for one block of clauses: [{issue, importance}]."""
    if not clauses:
        return []
    body = "\n".join(f"- {c[: config.CLAUSE_CHAR_LIMIT]}" for c in clauses)
    user = f"Complaint clauses from this block:\n{body}"
    raw = _call(
        [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user},
        ]
    )
    data = _extract_json(raw)
    issues = [_normalize_issue(o) for o in data.get("issues", []) if isinstance(o, dict)]
    return [{"issue": i, "importance": s} for i, s in issues if i]


CONSOLIDATE_SYSTEM_PROMPT = (
    "You are given a list of issue statements distilled from a block of "
    "complaints. Some describe the SAME underlying problem in different words. "
    "Your job: merge any issues that are really the same root problem into ONE "
    "statement, and keep issues that are genuinely distinct separate. Keep one "
    "concise factual sentence per issue. Respond with ONLY a JSON object, no "
    "prose:\n"
    '{"issues": [{"issue": "<merged or kept issue>", "importance": <0-10>}]} '
    "Preserve the highest importance score when you merge two issues."
)


def consolidate(issues: list[dict]) -> list[dict]:
    """Second pass: re-merge issues the first pass left as near-duplicate
    paraphrases. Returns the same [{issue, importance}] shape."""
    if len(issues) <= 1:
        return issues
    body = "\n".join(f"- {i['issue']} (importance {i['importance']})" for i in issues)
    user = f"Issues to consolidate:\n{body}"
    raw = _call(
        [
            {"role": "system", "content": CONSOLIDATE_SYSTEM_PROMPT},
            {"role": "user", "content": user},
        ]
    )
    data = _extract_json(raw)
    out = [_normalize_issue(o) for o in data.get("issues", []) if isinstance(o, dict)]
    return [{"issue": i, "importance": s} for i, s in out if i] or issues
