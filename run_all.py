#!/usr/bin/env python3
"""
run_all.py — run the full pipeline in order:

    ① join_csv/join_csvs.py          join reviews + places
    ② join_csv/swap_translated.py   replace content with translated_content (optional)
    ③ clause_split/split.py          split reviews into clauses
    ④ sentiment_analysis/classify.py BERT sentiment classification
    ⑤ clause_flatten/flatten.py      flatten negative clauses
    ⑥ embed/embed.py                 MiniLM embed + FAISS index

Usage:
    python run_all.py             # run all stages
    python run_all.py --skip-swap # skip the swap_translated step
    python run_all.py --from 3    # start from stage 3 (split)
"""
import argparse
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent

STAGES = [
    ("① Join reviews + places",     "join_csv/join_csvs.py"),
    ("② Swap translated content",   "join_csv/swap_translated.py"),
    ("③ Split reviews into clauses","clause_split/split.py"),
    ("④ BERT sentiment classify",   "sentiment_analysis/classify.py"),
    ("⑤ Flatten negative clauses",  "clause_flatten/flatten.py"),
    ("⑥ Embed + build FAISS index", "embed/embed.py"),
]


def run(label, script):
    print(f"\n{'='*60}")
    print(f"  {label}")
    print(f"  python {script}")
    print(f"{'='*60}")
    t0 = time.time()
    result = subprocess.run([sys.executable, str(ROOT / script)], cwd=ROOT)
    elapsed = time.time() - t0
    if result.returncode != 0:
        print(f"\n  [FAILED] {script} exited with code {result.returncode}", file=sys.stderr)
        sys.exit(result.returncode)
    print(f"\n  [OK] {label}  ({elapsed:.1f}s)")


def main():
    parser = argparse.ArgumentParser(description="Run the full jojani_ai pipeline")
    parser.add_argument("--skip-swap", action="store_true",
                        help="Skip the swap_translated step (stage 2)")
    parser.add_argument("--from", dest="start", type=int, default=1,
                        metavar="N", help="Start from stage N (1-6)")
    args = parser.parse_args()

    stages = list(enumerate(STAGES, 1))
    if args.skip_swap:
        stages = [(i, (l, s)) for i, (l, s) in stages if "swap" not in s]

    started = False
    for idx, (label, script) in stages:
        if not started:
            if idx < args.start:
                print(f"[skip] stage {idx}: {label}")
                continue
            started = True
        run(label, script)

    print(f"\n{'='*60}")
    print("  All stages complete.")
    print(f"  Query the RAG engine:")
    print(f"    python rag_clusters/cli.py --interactive")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
