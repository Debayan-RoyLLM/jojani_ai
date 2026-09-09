#!/usr/bin/env python3
"""Flask web app: button-triggered LLM review judgement with progress tracking."""

import csv
import json
import threading
import time

from flask import Flask, jsonify, render_template, request

from src import config
from src.llm import call_llm
from src.parse_reviews import parse_matched_reviews
from src.prompts import build_judge_prompt

app = Flask(__name__)

# ---------------------------------------------------------------------------
# Job state (single background job at a time)
# ---------------------------------------------------------------------------
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
        config.PROGRESS_FILE.write_text(json.dumps(state, indent=2))
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Background work
# ---------------------------------------------------------------------------
def _run_judgement() -> None:
    """Judge all matched reviews and write results to judgements.csv."""
    _update_progress(
        running=True, total=0, done=0,
        total_batches=0, done_batches=0,
        start_time=time.time(), message="Starting...",
    )
    try:
        entries = parse_matched_reviews(config.MATCHED_REVIEWS_MD)
        if not entries:
            _update_progress(running=False, message="No reviews found in matched_reviews.md")
            return

        reviews = [rev for _, rev in entries]
        locations = [loc for loc, _ in entries]
        total = len(reviews)
        total_batches = (total + config.BATCH_SIZE - 1) // config.BATCH_SIZE
        _update_progress(total=total, total_batches=total_batches, message="Judging reviews...")

        all_results: list[dict] = []
        for start in range(0, total, config.BATCH_SIZE):
            batch = reviews[start : start + config.BATCH_SIZE]
            raw = call_llm(build_judge_prompt(batch, start)).strip()
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[1]
                if raw.endswith("```"):
                    raw = raw[: -3]
            all_results.extend(json.loads(raw))
            _update_progress(
                done=min(start + config.BATCH_SIZE, total),
                done_batches=(start + config.BATCH_SIZE) // config.BATCH_SIZE,
            )

        with open(config.JUDGEMENTS_CSV, "w", newline="", encoding="utf-8") as f:
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
            done=total, done_batches=total_batches, running=False,
            message=f"Done! {len(all_results)} negative out of {total} reviews.",
        )
    except Exception as e:
        _update_progress(running=False, message=f"Error: {e}")


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/run", methods=["POST"])
def run():
    with _job_lock:
        if _job["running"]:
            return jsonify({"status": "already_running"}), 409
    threading.Thread(target=_run_judgement, daemon=True).start()
    return jsonify({"status": "started"})


@app.route("/progress")
def progress():
    with _job_lock:
        state = dict(_job)
    return jsonify(state)


def _load_judgements() -> list[dict]:
    if not config.JUDGEMENTS_CSV.exists():
        return []
    with open(config.JUDGEMENTS_CSV, newline="", encoding="utf-8") as f:
        return [
            {
                "location_name": row.get("location_name", ""),
                "judgement": row.get("judgement", ""),
                "action": row.get("action", ""),
            }
            for row in csv.DictReader(f)
        ]


@app.route("/locations")
def locations():
    places = sorted({r["location_name"] for r in _load_judgements() if r["location_name"]})
    return jsonify({"locations": places})


@app.route("/judgements")
def get_judgements():
    location = request.args.get("location", "").strip()
    rows = _load_judgements()
    if location:
        rows = [r for r in rows if r["location_name"] == location]
    return jsonify({"judgements": rows, "count": len(rows)})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
