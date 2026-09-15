"""sentiment_analysis — classify review clauses into negative / neutral / positive.

Pipeline: split.py -> review_clauses.json -> sentiment_analysis/classify.py
          -> <project>/output/{negative,neutral,positive}_clauses.jsonl

Run:
    python sentiment_analysis/classify.py review_clauses.json -o output
"""
from . import config, data, model  # noqa: F401
