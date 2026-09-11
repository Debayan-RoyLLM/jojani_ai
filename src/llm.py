"""LLM API client — single implementation shared by CLI and web app."""

import json
import time

import requests

from src import config


def call_llm(prompt: str) -> str:
    """Send a prompt to the configured LLM and return the response text.

    Retries up to config.MAX_RETRIES times with linear backoff.
    Raises the last exception if all attempts fail.
    """
    payload = {
        "model": config.LLM_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.1,
    }
    headers = {
        "Authorization": f"Bearer {config.LLM_API_KEY}",
        "Content-Type": "application/json",
    }

    last_exc: Exception | None = None
    for attempt in range(1, config.MAX_RETRIES + 1):
        try:
            resp = requests.post(
                config.LLM_URL,
                json=payload,
                headers=headers,
                timeout=config.LLM_TIMEOUT,
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]
        except Exception as e:
            last_exc = e
            print(f"  Attempt {attempt}/{config.MAX_RETRIES} failed: {e}")
            if attempt < config.MAX_RETRIES:
                time.sleep(2 * attempt)
    raise last_exc  # type: ignore[misc]


def parse_llm_json(raw: str) -> list[dict]:
    """Strip markdown code fences and parse the result as a JSON list."""
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1]
        if raw.endswith("```"):
            raw = raw[:-3]
    return json.loads(raw.strip())
