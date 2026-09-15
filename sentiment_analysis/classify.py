#!/usr/bin/env python3
"""
classify.py — classify review clauses as negative / neutral / positive using a BERT
sentiment model, then write one JSONL file per sentiment.

Only the individual clause strings (the "text" field) are classified — the
review-level star rating is ignored.

Usage (from the project root):
    python sentiment_analysis/classify.py review_clauses.json
    python sentiment_analysis/classify.py review_clauses.json -o output/ --batch-size 32 --max-length 256
"""
import argparse
import os
import sys
from collections import Counter
from pathlib import Path

# Allow running this file directly (python sentiment_analysis/classify.py ...) by
# putting the project root on sys.path so the package's sibling modules import.
_PACKAGE_PARENT = str(Path(__file__).resolve().parent.parent)
if _PACKAGE_PARENT not in sys.path:
    sys.path.insert(0, _PACKAGE_PARENT)

import torch  # noqa: E402  (after sys.path tweak, so it stays consistent)

from sentiment_analysis import config, data, model  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description="Classify review clauses by sentiment.")
    parser.add_argument("input", help="path to review_clauses.json (JSONL from split.py)")
    parser.add_argument("-o", "--output-dir", default=str(config.PROJECT_ROOT / "output"),
                        help="directory for the three sentiment files (default: <project>/output)")
    parser.add_argument("--model", default=config.DEFAULT_MODEL,
                        help="local model dir or HF model id (default: %(default)s)")
    parser.add_argument("--batch-size", type=int, default=32, help="inference batch size (default 32)")
    parser.add_argument("--max-length", type=int, default=256,
                        help="max tokens per clause (default 256)")
    parser.add_argument("--threads", type=int, default=os.cpu_count() or 1,
                        help="torch intra-op threads (default: cpu count)")
    args = parser.parse_args()

    torch.set_num_threads(args.threads)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Loading clauses from {args.input} ...")
    unique = data.load_unique_clauses(args.input)
    texts = list(unique.keys())
    print(f"  unique clauses to classify: {len(texts)}")

    print(f"Loading model {args.model} ...")
    tokenizer, cls_model = model.load_model(args.model)

    results = model.predict_batched(cls_model, tokenizer, texts, args.batch_size, args.max_length)

    # Bucket each clause by sentiment.
    by_sentiment = {s: [] for s in config.SENTIMENT_FILES}
    counts = Counter()
    for (text, (review, clause)), (label, score) in zip(unique.items(), results):
        sentiment = config.LABEL_TO_SENTIMENT.get(label, "neutral")
        counts[sentiment] += 1
        by_sentiment[sentiment].append((review, clause, score))

    print("Sentiment distribution:", dict(counts))

    paths = data.write_sentiment_files(by_sentiment, config.SENTIMENT_FILES, output_dir)
    for sentiment in config.SENTIMENT_FILES:
        rows = by_sentiment[sentiment]
        print(f"  {sentiment:9s}: {len(rows):5d}  -> {paths[sentiment]}")

    total = sum(len(v) for v in by_sentiment.values())
    print(f"Done. {total} clauses written "
          f"(negative {len(by_sentiment['negative'])}, "
          f"neutral {len(by_sentiment['neutral'])}, "
          f"positive {len(by_sentiment['positive'])}).")


if __name__ == "__main__":
    main()
