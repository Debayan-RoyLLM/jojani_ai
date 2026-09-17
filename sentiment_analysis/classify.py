#!/usr/bin/env python3
"""
classify.py — split review clauses into negative / positive buckets using a
local BERT sentiment model. No CLI args; edit config.py to change paths.

Pipeline:
    INPUT_JSONL  (one review per line, each with a "clauses" list)
        -> load unique clause texts, classify each
        -> write OUTPUT_NEGATIVE and OUTPUT_POSITIVE (one review per line,
           with only that sentiment's clauses kept)

Usage:
    python classify.py
"""
import json
import time
from collections import Counter
from pathlib import Path

import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer

import config

_HERE = Path(__file__).resolve().parent


def resolve_path(p):
    path = Path(p)
    return path if path.is_absolute() else _HERE / path


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_unique_clauses(path):
    """
    Read the input JSONL and return an ordered dict:
        clause_text  ->  (review_dict, clause_dict)
    keeping the first occurrence of each unique clause text.
    """
    unique = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            review = json.loads(line)
            for clause in review.get("clauses", []):
                text = clause.get("text", "").strip()
                if text and text not in unique:
                    unique[text] = (review, clause)
    return unique


# ---------------------------------------------------------------------------
# Model
# ---------------------------------------------------------------------------

def load_model(model_name):
    offline = "/" in model_name or "\\" in model_name or model_name.startswith((".", "/"))
    kwargs = {"local_files_only": True} if offline else {}
    tokenizer = AutoTokenizer.from_pretrained(model_name, fix_mistral_regex=True, **kwargs)
    model = AutoModelForSequenceClassification.from_pretrained(model_name, **kwargs)
    model.eval()
    return tokenizer, model


def _fmt_eta(seconds):
    seconds = int(round(seconds))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}h {m:02d}m {s:02d}s"
    if m:
        return f"{m}m {s:02d}s"
    return f"{s}s"


def predict_batched(model, tokenizer, texts, batch_size, max_length):
    """Return a list of (label, score) aligned to `texts`."""
    results = []
    total = len(texts)
    t0 = time.time()
    with torch.no_grad():
        for i in range(0, total, batch_size):
            batch = texts[i:i + batch_size]
            enc = tokenizer(batch, return_tensors="pt", padding=True,
                            truncation=True, max_length=max_length)
            out = model(**enc).logits
            probs = out.softmax(dim=-1)
            for prob, logit in zip(probs, out):
                idx = int(logit.argmax())
                results.append((model.config.id2label[idx], float(prob[idx])))
            done = i + len(batch)
            elapsed = time.time() - t0
            rate = done / max(elapsed, 1e-6)
            eta = (total - done) / max(rate, 1e-6)
            print(f"\r  {done}/{total} ({100 * done / total:.1f}%)  "
                  f"ETA {_fmt_eta(eta)}", end="", flush=True)
    print()
    return results


# ---------------------------------------------------------------------------
# Output writing
# ---------------------------------------------------------------------------

# BERT model labels -> sentiment bucket
LABEL_TO_SENTIMENT = {
    "1 star": "negative",
    "2 stars": "negative",
    "3 stars": "neutral",
    "4 stars": "positive",
    "5 stars": "positive",
}


def build_clause_record(clause, score):
    """Format one clause for the output JSONL."""
    return {
        "clause_id":   clause.get("clause_id"),
        "clause_text": clause.get("text"),
        "sentence_no": clause.get("sentence_no"),
        "score":       round(score, 4),
    }


def write_sentiment_file(path, by_review):
    """
    `by_review` maps review_id -> (review_dict, [clause_records]).
    Writes one JSON line per review with only that sentiment's clauses.
    """
    with open(path, "w", encoding="utf-8") as f:
        for _, (review, clauses) in by_review.items():
            record = {
                "review_id":   review.get("review_id"),
                "place_name":  review.get("place_name"),
                "content":     review.get("content"),
                "clauses":     clauses,
            }
            f.write(json.dumps(record, ensure_ascii=False) + "\n")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    input_path  = resolve_path(config.INPUT_JSONL)
    out_neg     = resolve_path(config.OUTPUT_NEGATIVE)
    out_pos     = resolve_path(config.OUTPUT_POSITIVE)

    # Load
    print(f"Loading clauses from {input_path} ...")
    unique = load_unique_clauses(input_path)
    texts  = list(unique.keys())
    print(f"  unique clauses to classify: {len(texts)}")

    # Model
    print(f"Loading model from {config.MODEL} ...")
    tokenizer, cls_model = load_model(config.MODEL)

    # Classify
    results = predict_batched(cls_model, tokenizer, texts,
                              config.BATCH_SIZE, config.MAX_LENGTH)

    # Bucket: review_id -> (review, [clause_records])
    by_neg = {}
    by_pos = {}
    counts = Counter()

    for (text, (review, clause)), (label, score) in zip(unique.items(), results):
        sentiment = LABEL_TO_SENTIMENT.get(label, "neutral")
        counts[sentiment] += 1
        if sentiment == "negative":
            rid = review.get("review_id") or ""
            by_neg.setdefault(rid, (review, []))
            by_neg[rid][1].append(build_clause_record(clause, score))
        elif sentiment == "positive":
            rid = review.get("review_id") or ""
            by_pos.setdefault(rid, (review, []))
            by_pos[rid][1].append(build_clause_record(clause, score))

    print("Sentiment distribution:", dict(counts))

    # Write
    for path, by_review, name in [
        (out_neg, by_neg, "negative"),
        (out_pos, by_pos, "positive"),
    ]:
        path.parent.mkdir(parents=True, exist_ok=True)
        write_sentiment_file(path, by_review)
        n_clauses = sum(len(v[1]) for v in by_review.values())
        print(f"  {name:9s}: {len(by_review)} reviews, {n_clauses} clauses  -> {path}")

    print("Done.")


if __name__ == "__main__":
    main()
