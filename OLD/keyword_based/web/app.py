#!/usr/bin/env python3
"""Flask web app: button-triggered LLM review judgement with progress tracking."""

import csv
import json
import threading
import time

from flask import Flask, jsonify, render_template, request

from keyword_based import config
from keyword_based.judge import judge_all_reviews
from keyword_based.parse_reviews import load_keywords, parse_matched_reviews

app = Flask(__name__)

# ---------------------------------------------------------------------------
# Job state (single background job at a time)
# ---------------------------------------------------------------------------
_job_lock = threading.Lock()
_job: dict = {
    "running": False,
    "total": 0,
    "done": 0,
    "start_time": None,
    "message": "",
}


def _set_job(**kwargs) -> None:
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
    _set_job(running=True, total=0, done=0, start_time=time.time(), message="Starting...")
    try:
        entries = parse_matched_reviews(config.MATCHED_REVIEWS_MD)
        if not entries:
            _set_job(running=False, message="No reviews found in matched_reviews.md")
            return

        reviews = [rev for _, rev in entries]
        locations = [loc for loc, _ in entries]
        total = len(reviews)
        _set_job(total=total, message="Judging reviews...")

        results = judge_all_reviews(reviews, on_batch_done=lambda done, _: _set_job(done=done))

        with open(config.JUDGEMENTS_CSV, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["location_name", "judgement", "action"])
            for r in results:
                idx = r.get("index", 1) - 1
                loc = locations[idx] if 0 <= idx < len(locations) else f"Review {idx + 1}"
                writer.writerow([loc, r.get("reason", ""), "; ".join(r.get("action_items", []))])

        _set_job(done=total, running=False, message=f"Done! {len(results)} negative out of {total}.")
    except Exception as e:
        _set_job(running=False, message=f"Error: {e}")


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
    places = sorted(set(load_keywords(config.PLACES_CSV)))
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
