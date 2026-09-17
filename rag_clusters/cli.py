#!/usr/bin/env python3
"""CLI for the cluster-based RAG review analyst.

Usage:
    python rag_clusters/cli.py "your query"
    python rag_clusters/cli.py --interactive
    python rag_clusters/cli.py "your query" --json
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from rag_clusters.rag import RAGEngine  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description="Cluster RAG review analyst")
    parser.add_argument("query", nargs="?", help="Search query")
    parser.add_argument("--interactive", "-i", action="store_true", help="Interactive mode")
    parser.add_argument("--json", action="store_true", help="Output raw JSON")
    parser.add_argument("--max-clauses", type=int, default=None, help="Max clauses to retrieve")
    args = parser.parse_args()

    if not args.query and not args.interactive:
        parser.print_help()
        sys.exit(1)

    engine = RAGEngine()

    if args.interactive:
        print("Cluster RAG Review Analyst (type 'quit' to exit)")
        while True:
            try:
                q = input("\n> ").strip()
            except (EOFError, KeyboardInterrupt):
                break
            if q.lower() in ("quit", "exit", "q"):
                break
            if not q:
                continue
            _run_query(engine, q, args)
        return

    _run_query(engine, args.query, args)


def _run_query(engine: RAGEngine, query: str, args) -> None:
    result = engine.ask(query, max_clauses=args.max_clauses)

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return

    print(f"\n{'='*60}")
    print(f"Query: {query}")
    print(f"{'='*60}")
    print(f"\nSummary:\n{result.get('summary', 'N/A')}")

    actions = result.get("actions", [])
    if actions:
        print(f"\nActions:")
        for a in actions:
            print(f"  • {a}")

    sources = result.get("source_clauses", [])
    if sources:
        print(f"\nSource clauses ({len(sources)}):")
        for i, c in enumerate(sources, 1):
            text = c.get("clause_text", "")[:200]
            print(f"  [{i}] ({c.get('place_name', '?')}, score {c.get('score', 0):.2f}) {text}")
    print()


if __name__ == "__main__":
    main()
