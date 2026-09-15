"""Loading clause data from the split.py JSONL output."""
import json


def load_clauses(path):
    """Yield (review, clause) pairs from a JSONL file (one review per line)."""
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            review = json.loads(line)
            for clause in review.get("clauses", []):
                yield review, clause


def load_unique_clauses(path):
    """Return {clause_text: (review, clause)} keeping the first occurrence of each unique text.

    De-duping by text avoids re-classifying repeated clauses (a small but free speedup).
    """
    unique = {}
    for review, clause in load_clauses(path):
        text = clause.get("text", "").strip()
        if text and text not in unique:
            unique[text] = (review, clause)
    return unique


def write_sentiment_files(by_sentiment, sentiment_files, output_dir):
    """Write one JSONL file per sentiment; returns {sentiment: path}."""
    paths = {}
    for sentiment, fname in sentiment_files.items():
        out_path = output_dir / fname
        with open(out_path, "w", encoding="utf-8") as f:
            for review, clause, score in by_sentiment.get(sentiment, []):
                f.write(json.dumps({
                    "clause_id": clause["clause_id"],
                    "review_id": review["review_id"],
                    "attraction_id": review["attraction_id"],
                    "lang": review.get("lang"),
                    "date": review.get("date"),
                    "sentence_no": clause.get("sentence_no"),
                    "clause_text": clause["text"],
                    "sentiment": sentiment,
                    "score": round(score, 4),
                }, ensure_ascii=False) + "\n")
        paths[sentiment] = out_path
    return paths
