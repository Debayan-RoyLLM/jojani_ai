"""LLM client for the RAG app (OpenAI-compatible endpoint)."""

import time

import requests

from . import config


def call_llm(prompt: str) -> str:
    """Send prompt to LLM, return response text. Retries with backoff."""
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
            print(f"  LLM attempt {attempt}/{config.MAX_RETRIES} failed: {e}")
            if attempt < config.MAX_RETRIES:
                time.sleep(2 * attempt)
    raise last_exc  # type: ignore[misc]
