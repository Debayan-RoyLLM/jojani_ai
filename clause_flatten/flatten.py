#!/usr/bin/env python3
"""
flatten.py — flatten review-level clause JSONL to one clause per line,
ready for embedding.

Input  (one review per line, nested clauses):
    {"review_id": "...", "place_name": "...", "content": "...",
     "clauses": [{"clause_id": "...", "clause_text": "...", "sentence_no": 1, "score": 0.9}]}

Output (one clause per line, flat):
    {"clause_id": "...", "clause_text": "...", "place_name": "...",
     "review_id": "...", "sentence_no": 1, "score": 0.9}

Usage:
    python flatten.py
"""
import json
from pathlib import Path

import config

_HERE = Path(__file__).resolve().parent


def resolve_path(p):
    path = Path(p)
    return path if path.is_absolute() else _HERE / path


def main():
    input_path  = resolve_path(config.INPUT_JSONL)
    output_path = resolve_path(config.OUTPUT_JSONL)

    n_reviews = 0
    n_clauses = 0

    with open(input_path, encoding="utf-8") as fin, \
         open(output_path, "w", encoding="utf-8") as fout:
        for line in fin:
            line = line.strip()
            if not line:
                continue
            review = json.loads(line)
            n_reviews += 1
            for clause in review.get("clauses", []):
                flat = {
                    "clause_id":   clause.get("clause_id"),
                    "clause_text": clause.get("clause_text"),
                    "place_name":  review.get("place_name"),
                    "review_id":   review.get("review_id"),
                    "sentence_no": clause.get("sentence_no"),
                    "score":       clause.get("score"),
                }
                fout.write(json.dumps(flat, ensure_ascii=False) + "\n")
                n_clauses += 1

    print(f"Flattened {n_reviews} reviews -> {n_clauses} clauses")
    print(f"Wrote {output_path}")


if __name__ == "__main__":
    main()
