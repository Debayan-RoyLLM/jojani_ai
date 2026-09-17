#!/usr/bin/env python3
"""
embed.py — embed each clause in a flat clause JSONL and write one line per
clause with the embedding vector attached.

Input  (one clause per line):
    {"clause_id": "...", "clause_text": "...", "place_name": "...",
     "review_id": "...", "sentence_no": 1, "score": 0.9}

Output (one clause per line, with "embedding" field added):
    {"clause_id": "...", "clause_text": "...", "place_name": "...",
     "review_id": "...", "sentence_no": 1, "score": 0.9,
     "embedding": [0.012, -0.034, ...]}   # 384 floats

Usage:
    python embed.py
"""
import json
import sys
import time
from pathlib import Path

import faiss
import numpy as np
import sentence_transformers

import config

_HERE = Path(__file__).resolve().parent


def resolve_path(p):
    path = Path(p)
    return path if path.is_absolute() else _HERE / path


def load_clauses(path):
    """Load flat clause records — one dict per line."""
    records = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def embed(records, model, batch_size):
    """Return a (N, dim) float32 array of normalized embeddings."""
    texts = [r["clause_text"] for r in records]
    n = len(texts)
    parts = []
    for start in range(0, n, batch_size):
        batch = texts[start:start + batch_size]
        emb = model.encode(batch, convert_to_numpy=True,
                           normalize_embeddings=True, show_progress_bar=False)
        parts.append(emb)
        pct = (start + len(batch)) / n * 100
        sys.stderr.write(f"\r  {pct:.0f}% ({start + len(batch)}/{n})")
        sys.stderr.flush()
    sys.stderr.write("\n")
    return np.vstack(parts).astype(np.float32)


def main():
    input_path  = resolve_path(config.INPUT_JSONL)
    output_path = resolve_path(config.OUTPUT_JSONL)
    faiss_path  = resolve_path(config.FAISS_INDEX)

    print(f"Loading clauses from {input_path} ...")
    records = load_clauses(input_path)
    print(f"  {len(records)} clauses loaded")

    model_name = config.MODEL_DIR if Path(config.MODEL_DIR).is_dir() else config.FALLBACK_MODEL
    print(f"Loading model from {model_name} ...")
    model = sentence_transformers.SentenceTransformer(model_name)

    print("Embedding ...")
    t0 = time.time()
    embeddings = embed(records, model, config.BATCH_SIZE)
    t1 = time.time()
    print(f"  Done in {t1 - t0:.1f}s, shape={embeddings.shape}")

    # Write JSONL with embeddings
    with open(output_path, "w", encoding="utf-8") as f:
        for record, vec in zip(records, embeddings):
            record["embedding"] = vec.tolist()
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    print(f"Wrote {output_path}")

    # Build and save FAISS index (inner product on normalized vectors = cosine)
    dim = embeddings.shape[1]
    index = faiss.IndexFlatIP(dim)
    index.add(embeddings)
    faiss.write_index(index, str(faiss_path))
    print(f"Wrote FAISS index ({index.ntotal} vectors, dim={dim}) -> {faiss_path}")


if __name__ == "__main__":
    main()
