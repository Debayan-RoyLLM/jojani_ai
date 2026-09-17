#!/usr/bin/env python3
"""Simple web app: click a button to run LLM judgement on matched reviews.

Stores results as (location_name, judgement, action) in output/judgements.csv.
"""

import csv
import json
import os
import threading
import time
from pathlib import Path

import requests
from flask import Flask, jsonify, render_template_string, request

BASE_DIR = Path(__file__).parent.parent
INPUT_PATH = BASE_DIR / "output" / "matched_reviews.md"
ENV_PATH = BASE_DIR / ".env"
OUTPUT_CSV = BASE_DIR / "output" / "judgements.csv"
PROGRESS_FILE = BASE_DIR / "output" / "judgement_progress.json"


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

# Module-level job state, protected by a lock.
_job_lock = threading.Lock()
_job = {
    "running": False,
    "total": 0,
    "done": 0,
    "total_batches": 0,
    "done_batches": 0,
    "start_time": None,
    "message": "",
}


def _update_progress(**kwargs) -> None:
    with _job_lock:
        _job.update(kwargs)
        state = dict(_job)
    try:
        PROGRESS_FILE.write_text(json.dumps(state, indent=2))
    except Exception:
        pass


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
    """Run LLM judgement on all matched reviews, save to CSV.

    Runs in a background thread so the HTTP request returns immediately.
    Progress is tracked via _update_progress() and persisted to PROGRESS_FILE.
    """
    def _work():
        _update_progress(
            running=True,
            total=0,
            done=0,
            total_batches=0,
            done_batches=0,
            start_time=time.time(),
            message="Starting...",
        )
        try:
            entries = parse_matched_reviews(INPUT_PATH)
            if not entries:
                _update_progress(
                    running=False,
                    message="No reviews found in matched_reviews.md",
                )
                return

            reviews = [rev for _, rev in entries]
            locations = [loc for loc, _ in entries]
            total = len(reviews)
            total_batches = (total + BATCH_SIZE - 1) // BATCH_SIZE
            _update_progress(
                total=total,
                total_batches=total_batches,
                message="Judging reviews...",
            )

            all_results = []
            for start in range(0, total, BATCH_SIZE):
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
                _update_progress(done=min(start + BATCH_SIZE, total), done_batches=(start + BATCH_SIZE) // BATCH_SIZE)

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

            _update_progress(
                done=total,
                done_batches=total_batches,
                running=False,
                message=f"Done! {len(all_results)} negative out of {total} reviews.",
            )
        except Exception as e:
            _update_progress(running=False, message=f"Error: {e}")

    threading.Thread(target=_work, daemon=True).start()
    return {"status": "started"}


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
#progressWrap {
  display: none;
  margin-top: 1.5rem;
  text-align: left;
}
#progressBarOuter {
  background: #334155;
  border-radius: 6px;
  height: 10px;
  overflow: hidden;
  margin-bottom: 0.5rem;
}
#progressBarInner {
  background: #38bdf8;
  height: 100%;
  width: 0%;
  transition: width 0.4s ease;
}
#progressLabel {
  font-size: 0.8rem;
  color: #94a3b8;
  display: flex;
  justify-content: space-between;
}
#eta {
  color: #38bdf8;
  font-weight: 600;
}
#result {
  margin-top: 1.5rem;
  font-size: 0.85rem;
  text-align: left;
  white-space: pre-wrap;
}
#result.success { color: #34d399; }
#result.error { color: #f87171; }
#placeWrap {
  margin-top: 1.5rem;
  text-align: left;
  display: none;
}
#placeWrap label {
  font-size: 0.8rem;
  color: #94a3b8;
  display: block;
  margin-bottom: 0.4rem;
}
#placeSelect {
  width: 100%;
  background: #0f172a;
  color: #e2e8f0;
  border: 1px solid #334155;
  border-radius: 8px;
  padding: 0.6rem 0.8rem;
  font-size: 0.9rem;
  cursor: pointer;
}
#placeSelect:focus { outline: 1px solid #38bdf8; }
#judgementsWrap {
  display: none;
  margin-top: 1.5rem;
  text-align: left;
}
#judgementsHeader {
  font-size: 0.85rem;
  color: #94a3b8;
  margin-bottom: 0.75rem;
  padding-bottom: 0.5rem;
  border-bottom: 1px solid #334155;
}
#judgementsHeader strong { color: #38bdf8; }
.judgement-card {
  background: #0f172a;
  border: 1px solid #334155;
  border-radius: 8px;
  padding: 0.9rem 1rem;
  margin-bottom: 0.75rem;
}
.judgement-card .j-text {
  font-size: 0.85rem;
  color: #e2e8f0;
  line-height: 1.45;
  margin-bottom: 0.5rem;
}
.judgement-card .a-label {
  font-size: 0.7rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: #64748b;
  margin-bottom: 0.3rem;
}
.judgement-card .a-text {
  font-size: 0.8rem;
  color: #94a3b8;
  line-height: 1.4;
  white-space: pre-wrap;
}
#noJudgements {
  font-size: 0.85rem;
  color: #64748b;
  text-align: center;
  padding: 1rem 0;
}
</style>
</head>
<body>
<div class="card">
  <h1>Review Judgement</h1>
  <p>Run LLM analysis on matched reviews. Results saved to <code>output/judgements.csv</code></p>
  <button id="runBtn" onclick="runJudgement()">Run Judgement</button>
  <div id="progressWrap">
    <div id="progressBarOuter"><div id="progressBarInner"></div></div>
    <div id="progressLabel">
      <span id="progressText">0%</span>
      <span id="eta">ETA: —</span>
    </div>
  </div>
  <div id="result"></div>
  <div id="placeWrap">
    <label for="placeSelect">View judgements for a place</label>
    <select id="placeSelect" onchange="onPlaceChange()">
      <option value="">— All places —</option>
    </select>
  </div>
  <div id="judgementsWrap">
    <div id="judgementsHeader"></div>
    <div id="judgementsList"></div>
  </div>
</div>
<script>
let pollTimer = null;
let pollStart = null;

function startPolling() {
  stopPolling();
  pollStart = Date.now();
  pollTimer = setInterval(pollProgress, 1000);
}

function stopPolling() {
  if (pollTimer) { clearInterval(pollTimer); pollTimer = null; }
}

function fmtDuration(sec) {
  if (sec < 60) return Math.round(sec) + 's';
  const m = Math.floor(sec / 60);
  const s = Math.round(sec % 60);
  return m + 'm ' + s + 's';
}

function pollProgress() {
  fetch('/progress').then(r => r.json()).then(d => {
    const wrap = document.getElementById('progressWrap');
    const bar = document.getElementById('progressBarInner');
    const text = document.getElementById('progressText');
    const eta = document.getElementById('eta');

    if (d.running && d.total > 0) {
      wrap.style.display = 'block';
      const pct = Math.min(100, Math.round((d.done / d.total) * 100));
      bar.style.width = pct + '%';
      text.textContent = pct + '% (' + d.done + '/' + d.total + ' reviews)';

      // ETA: elapsed so far / done * total - elapsed
      if (d.start_time) {
        const elapsed = (Date.now() - d.start_time * 1000) / 1000;
        if (elapsed > 2 && d.done > 0) {
          const remaining = (elapsed / d.done) * (d.total - d.done);
          eta.textContent = 'ETA: ' + fmtDuration(remaining);
        } else {
          eta.textContent = 'ETA: calculating...';
        }
      }
    } else if (!d.running && d.total > 0 && d.message) {
      // Job just finished — show final message once
      const result = document.getElementById('result');
      if (result.textContent === '') {
        wrap.style.display = 'block';
        bar.style.width = '100%';
        text.textContent = d.message.includes('Error') ? d.message : '100%';
        eta.textContent = 'Done';
        result.className = d.message.includes('Error') ? 'error' : 'success';
        result.textContent = d.message;
        const btn = document.getElementById('runBtn');
        btn.disabled = false;
        btn.textContent = 'Run Judgement';
      }
      stopPolling();
    }
  }).catch(() => {});
}

async function runJudgement() {
  const btn = document.getElementById('runBtn');
  const result = document.getElementById('result');
  const wrap = document.getElementById('progressWrap');
  btn.disabled = true;
  btn.textContent = 'Running...';
  result.className = '';
  result.textContent = '';
  wrap.style.display = 'none';
  document.getElementById('progressBarInner').style.width = '0%';
  document.getElementById('eta').textContent = 'ETA: calculating...';

  try {
    const resp = await fetch('/run', { method: 'POST' });
    if (resp.status === 409) {
      // Already running — just start polling
      startPolling();
      return;
    }
    startPolling();
  } catch (e) {
    result.className = 'error';
    result.textContent = 'Error: ' + e.message;
    btn.disabled = false;
    btn.textContent = 'Run Judgement';
  }
}

async function loadLocations() {
  try {
    const resp = await fetch('/locations');
    const data = await resp.json();
    const select = document.getElementById('placeSelect');
    select.innerHTML = '<option value="">— All places —</option>';
    data.locations.forEach(loc => {
      const opt = document.createElement('option');
      opt.value = loc;
      opt.textContent = loc;
      select.appendChild(opt);
    });
    if (data.locations.length > 0) {
      document.getElementById('placeWrap').style.display = 'block';
    }
  } catch (e) { /* file may not exist yet */ }
}

async function onPlaceChange() {
  const loc = document.getElementById('placeSelect').value;
  await fetchJudgements(loc);
}

async function fetchJudgements(location) {
  const wrap = document.getElementById('judgementsWrap');
  const header = document.getElementById('judgementsHeader');
  const list = document.getElementById('judgementsList');
  try {
    const url = location
      ? '/judgements?location=' + encodeURIComponent(location)
      : '/judgements';
    const resp = await fetch(url);
    const data = await resp.json();
    wrap.style.display = 'block';
    const label = location ? location : 'All places';
    header.innerHTML = '<strong>' + label + '</strong> — ' + data.count + ' judgement' + (data.count !== 1 ? 's' : '');
    if (data.count === 0) {
      list.innerHTML = '<div id="noJudgements">No judgements found.</div>';
      return;
    }
    let html = '';
    data.judgements.forEach(j => {
      const esc = s => String(s == null ? '' : s)
        .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
      let actionsHtml = '';
      if (j.action) {
        actionsHtml = '<div class="a-label">Action items</div><div class="a-text">' + esc(j.action) + '</div>';
      }
      html += '<div class="judgement-card">'
        + '<div class="j-text">' + esc(j.judgement) + '</div>'
        + actionsHtml
        + '</div>';
    });
    list.innerHTML = html;
  } catch (e) {
    list.innerHTML = '<div id="noJudgements">Failed to load judgements.</div>';
  }
}

// Load locations on page load (judgements.csv may already exist)
loadLocations();
// After a judgement run finishes, refresh the location list
const _origStopPolling = stopPolling;
stopPolling = function() {
  _origStopPolling();
  loadLocations();
};
</script>
</body>
</html>
"""


@app.route("/")
def index():
    return render_template_string(PAGE)


@app.route("/run", methods=["POST"])
def run():
    with _job_lock:
        if _job["running"]:
            return jsonify({"status": "already_running"}), 409
    result = run_judgement()
    return jsonify(result)


@app.route("/progress")
def progress():
    with _job_lock:
        state = dict(_job)
    return jsonify(state)


def load_judgements() -> list[dict]:
    """Read judgements.csv and return a list of dicts."""
    if not OUTPUT_CSV.exists():
        return []
    rows = []
    with open(OUTPUT_CSV, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append({
                "location_name": row.get("location_name", ""),
                "judgement": row.get("judgement", ""),
                "action": row.get("action", ""),
            })
    return rows


@app.route("/locations")
def locations():
    """Return a sorted, de-duplicated list of place names from judgements.csv."""
    rows = load_judgements()
    places = sorted({r["location_name"] for r in rows if r["location_name"]})
    return jsonify({"locations": places})


@app.route("/judgements")
def get_judgements():
    """Return judgements, optionally filtered by ?location=<name>."""
    location = request.args.get("location", "").strip()
    rows = load_judgements()
    if location:
        rows = [r for r in rows if r["location_name"] == location]
    return jsonify({"judgements": rows, "count": len(rows)})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
