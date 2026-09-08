#!/usr/bin/env python3
"""Simple web app: click a button to run LLM judgement on matched reviews.

Stores results as (location_name, judgement, action) in output/judgements.csv.
"""

import csv
import json
import os
import time
from pathlib import Path

import requests
from flask import Flask, jsonify, render_template_string

BASE_DIR = Path(__file__).parent.parent
INPUT_PATH = BASE_DIR / "output" / "matched_reviews.md"
ENV_PATH = BASE_DIR / ".env"
OUTPUT_CSV = BASE_DIR / "output" / "judgements.csv"


def load_env(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())


load_env(ENV_PATH)

LLM_URL = os.getenv("LLM_URL", "")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "")
BATCH_SIZE = 5
MAX_RETRIES = 3

PROMPT = """You are a review analyst. For each review below, determine if it is NEGATIVE (complains about problems, poor service, hygiene issues, safety concerns, etc.).

- If NEGATIVE: list specific actionable improvements (what can be implemented/fixed).
- If POSITIVE or NEUTRAL: discard it (do not include in output).

Respond ONLY with a JSON array of the NEGATIVE reviews only. Each element:
{"index": <int>, "reason": "<one sentence explaining why it's negative>", "action_items": ["...", "..."]}

If NO reviews are negative, respond with an empty array: []

Reviews:
"""

app = Flask(__name__)


def parse_matched_reviews(path: Path) -> list[tuple[str, str]]:
    """Parse matched_reviews.md into (location_name, review_text) pairs."""
    text = path.read_text(encoding="utf-8")
    entries = []
    current_location = ""
    current_lines = []
    for line in text.splitlines():
        if line.startswith("## "):
            if current_location and current_lines:
                entries.append((current_location, "\n".join(current_lines).strip()))
            current_location = line[3:].strip()
            current_lines = []
        elif line.startswith("# "):
            continue
        else:
            current_lines.append(line)
    if current_location and current_lines:
        entries.append((current_location, "\n".join(current_lines).strip()))
    return [(loc, rev) for loc, rev in entries if rev]


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


def run_judgement() -> dict:
    """Run LLM judgement on all matched reviews, save to CSV."""
    entries = parse_matched_reviews(INPUT_PATH)
    if not entries:
        return {"status": "error", "message": "No reviews found in matched_reviews.md"}

    # Build batches
    reviews = [rev for _, rev in entries]
    locations = [loc for loc, _ in entries]

    all_results = []
    for start in range(0, len(reviews), BATCH_SIZE):
        batch = reviews[start : start + BATCH_SIZE]
        review_block = "\n\n".join(
            f"--- Review {start + i + 1} ---\n{r}" for i, r in enumerate(batch)
        )
        raw = call_llm(PROMPT + review_block)
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1]
            if raw.endswith("```"):
                raw = raw[: -3]
        batch_results = json.loads(raw)
        all_results.extend(batch_results)

    # Write to CSV: (location_name, judgement, action)
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["location_name", "judgement", "action"])
        for r in all_results:
            idx = r.get("index", 1) - 1
            loc = locations[idx] if 0 <= idx < len(locations) else f"Review {idx + 1}"
            judgement = r.get("reason", "")
            actions = r.get("action_items", [])
            action = "; ".join(actions) if actions else ""
            writer.writerow([loc, judgement, action])

    return {
        "status": "success",
        "total_reviews": len(entries),
        "negative_count": len(all_results),
        "output_file": str(OUTPUT_CSV),
    }


PAGE = """
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<title>Review Judgement</title>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body {
  font-family: 'Segoe UI', system-ui, sans-serif;
  background: #0f172a;
  color: #e2e8f0;
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
}
.card {
  background: #1e293b;
  border: 1px solid #334155;
  border-radius: 12px;
  padding: 2.5rem;
  text-align: center;
  max-width: 420px;
  width: 100%;
}
h1 { font-size: 1.3rem; margin-bottom: 0.5rem; }
p { color: #94a3b8; font-size: 0.9rem; margin-bottom: 1.5rem; }
button {
  background: #38bdf8;
  color: #0f172a;
  border: none;
  border-radius: 8px;
  padding: 0.75rem 2rem;
  font-size: 1rem;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.2s;
}
button:hover { background: #7dd3fc; }
button:disabled { background: #475569; cursor: not-allowed; }
#result {
  margin-top: 1.5rem;
  font-size: 0.85rem;
  text-align: left;
  white-space: pre-wrap;
}
#result.success { color: #34d399; }
#result.error { color: #f87171; }
</style>
</head>
<body>
<div class="card">
  <h1>Review Judgement</h1>
  <p>Run LLM analysis on matched reviews. Results saved to <code>output/judgements.csv</code></p>
  <button id="runBtn" onclick="runJudgement()">Run Judgement</button>
  <div id="result"></div>
</div>
<script>
async function runJudgement() {
  const btn = document.getElementById('runBtn');
  const result = document.getElementById('result');
  btn.disabled = true;
  btn.textContent = 'Running...';
  result.className = '';
  result.textContent = 'Sending reviews to LLM. This may take a while...';
  try {
    const resp = await fetch('/run', { method: 'POST' });
    const data = await resp.json();
    if (data.status === 'success') {
      result.className = 'success';
      result.textContent = `Done!\\nTotal reviews: ${data.total_reviews}\\nNegative found: ${data.negative_count}\\nSaved to: ${data.output_file}`;
    } else {
      result.className = 'error';
      result.textContent = data.message || 'Unknown error';
    }
  } catch (e) {
    result.className = 'error';
    result.textContent = 'Error: ' + e.message;
  }
  btn.disabled = false;
  btn.textContent = 'Run Judgement';
}
</script>
</body>
</html>
"""


@app.route("/")
def index():
    return render_template_string(PAGE)


@app.route("/run", methods=["POST"])
def run():
    result = run_judgement()
    return jsonify(result)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
