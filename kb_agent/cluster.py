"""Cluster flat negative clauses into semantic blocks (one block per JSONL line).

Reads the embedded clauses (each has a 384-d `embedding` + `clause_text` +
`place_name`), groups them by cosine similarity with agglomerative clustering,
and writes `negative_clusters.jsonl` — one block per line, shaped for kb_agent.

KISS: no separate config; tweak the three constants below.

Usage:
    python -m kb_agent.cluster            # write negative_clusters.jsonl
    python -m kb_agent.cluster --dry      # just report how many blocks, no write
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from sklearn.cluster import AgglomerativeClustering
from sklearn.metrics.pairwise import cosine_similarity

ROOT = Path(__file__).resolve().parent.parent
INPUT = ROOT / "embed" / "negative_clauses_embedded.jsonl"
OUTPUT = ROOT / "negative_clusters.jsonl"

# Clustering knobs. distance_threshold is a cosine *distance* (1 - similarity):
# 0.45 means clauses more than ~45% apart (cosine sim < 0.55) form separate
# blocks. Lower = finer-grained, more blocks.
DISTANCE_THRESHOLD = 0.45
# Clauses that land in a block smaller than this are dropped (noise / outliers)
# so the knowledge base stays signal, not singletons.
MIN_CLUSTER_SIZE = 3


def _load(path: Path) -> tuple[list[str], list[str], np.ndarray]:
    texts: list[str] = []
    places: list[str] = []
    vecs: list[list[float]] = []
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            o = json.loads(line)
            text = o.get("clause_text")
            emb = o.get("embedding")
            if not text or not emb:
                continue
            texts.append(text)
            places.append(o.get("place_name", ""))
            vecs.append(emb)
    return texts, places, np.asarray(vecs, dtype="float32")


def build_clusters(texts: list[str], places: list[str], vecs: np.ndarray) -> list[list[int]]:
    """Return lists of clause indices, one per cluster (size-filtered)."""
    sim = cosine_similarity(vecs)  # embeddings are unit-normalized already
    model = AgglomerativeClustering(
        n_clusters=None,
        distance_threshold=DISTANCE_THRESHOLD,
        metric="precomputed",
        linkage="average",
    )
    labels = model.fit_predict(1.0 - sim)  # sklearn wants a distance matrix

    by_label: dict[int, list[int]] = {}
    for idx, lab in enumerate(labels):
        by_label.setdefault(int(lab), []).append(idx)

    clusters = [ids for ids in by_label.values() if len(ids) >= MIN_CLUSTER_SIZE]
    clusters.sort(key=len, reverse=True)  # biggest blocks first
    return clusters


def main() -> None:
    parser = argparse.ArgumentParser(description="Cluster embedded negative clauses into blocks")
    parser.add_argument("--input", default=str(INPUT))
    parser.add_argument("--output", default=str(OUTPUT))
    parser.add_argument("--dry", action="store_true", help="Report block count only, no write")
    args = parser.parse_args()

    in_path = Path(args.input)
    if not in_path.exists():
        print(f"[error] input not found: {in_path}", file=sys.stderr)
        sys.exit(1)

    texts, places, vecs = _load(in_path)
    print(f"Loaded {len(texts)} clauses from {in_path.name}")

    clusters = build_clusters(texts, places, vecs)
    print(f"Formed {len(clusters)} blocks "
          f"(threshold={DISTANCE_THRESHOLD}, min_size={MIN_CLUSTER_SIZE})")
    if args.dry:
        sizes = [len(c) for c in clusters[:10]]
        print(f"Top block sizes: {sizes}")
        return

    out_path = Path(args.output)
    with out_path.open("w", encoding="utf-8") as fh:
        for cid, ids in enumerate(clusters, 1):
            block = {
                "cluster_id": cid,
                "clauses": [texts[i] for i in ids],
                "place_names": sorted({places[i] for i in ids}),
                "size": len(ids),
            }
            fh.write(json.dumps(block, ensure_ascii=False) + "\n")

    total = sum(len(c) for c in clusters)
    print(f"Wrote {len(clusters)} blocks ({total} clauses) -> {out_path}")
    print("Now build the knowledge base:")
    print(f"  python -m kb_agent.run --input {out_path}")


if __name__ == "__main__":
    main()
