#!/usr/bin/env python3
"""Flask web app for the RAG review analyst. Run: python RAG/web/app.py"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from flask import Flask, jsonify, render_template, request  # noqa: E402

from RAG.rag import RAGEngine  # noqa: E402

app = Flask(__name__)
engine = RAGEngine()


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/query")
def api_query():
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify({"error": "Missing 'q' parameter"}), 400
    try:
        result = engine.ask(q)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=False)
