# Future Plans

## 1. Add embeddings to RAG (cluster-first)

**Current state:** `RAG/` has no embedding layer. Retrieval is purely keyword-based (token overlap between query and cluster names, plus LLM taxonomy classification). There is no vector similarity, so the retriever can't match semantically equivalent but lexically different queries (e.g. "too spicy" vs "way too hot").

**Plan:**
1. **Cluster reviews before embedding** — group the ~1582 attraction reviews into clusters by:
   - **Sentiment** (positive / negative / mixed)
   - **Place** (the location-aware clusters already built in `RAG/retriever.py` from `data/places_data.csv`)
2. **Discard low-value reviews** at the cluster level — many reviews are boilerplate, too short, or uninformative. Dropping them before embedding cuts cost and improves retrieval precision (the vector DB holds only the reviews worth retrieving).
3. **Embed the surviving clusters**, not individual reviews — each cluster gets one representative vector (mean of its member embeddings, or an embedded cluster summary). Queries are matched against cluster vectors; the cluster then surfaces its member reviews.
   - Fewer vectors → faster ANN search, lower index size.
   - A cluster hit returns a coherent, thematically-grouped set of reviews instead of scattered top-k.

**Open questions:**
- Embedding model choice (local `sentence-transformers` vs hosted API).
- Whether to embed per-review and mean-pool into a cluster vector, or embed a generated cluster summary (LLM-written) — the latter is semantically tighter but costs one LLM call per cluster.
- Index backend: in-memory `faiss`/`numpy` for this data size, or `chroma`/`qdrant` if we want persistence.

## 2. Clause-level semantic sentiment classification (extend `split.py`)

**Current state:** `split.py` breaks each review/comment into individual clauses (regex-based split). Those clauses are then classified **keyword-only** by `src/classify_reviews.py` (does the clause mention a place from `places_data.csv?`). There is no semantic sentiment model — a clause that mentions a place is matched, but not scored for how strongly positive/negative it is.

**Plan:**
1. Feed each clause (already produced by `split.py`) into a **semantic sentiment model** (e.g. a fine-tuned classifier, or a hosted sentiment API) to label it **positive / negative / neutral** with a confidence score.
2. This replaces/augments the current keyword gate: a clause is flagged as actionable-negative only when (a) it mentions a tracked place **and** (b) the semantic model scores it as negative above a threshold.
3. Pipeline becomes:
   ```
   review → split.py (clause split)
          → semantic sentiment classifier (new)
          → keyword place-match (existing)
          → LLM judge (existing, src/llm_judge / src/web.app)
   ```

**Open questions:**
- Model: hosted (OpenAI-compatible endpoint already wired in `src/llm.py`) vs local (DeBERTa fine-tune, `transformers` pipeline).
- Threshold tuning — too low → noise, too high → miss soft negatives ("a bit cold", "service was okay-ish").
