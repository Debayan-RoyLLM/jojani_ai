# Future Plans

## 1. Sentiment-clustered embedding retrieval (FAISS)

**Current state:** `RAG/` has no embedding layer. Retrieval is purely keyword-based (token overlap between query and cluster names, plus LLM taxonomy classification). There is no vector similarity, so the retriever can't match semantically equivalent but lexically different queries (e.g. "too spicy" vs "way too hot").

**Design goal:** cluster reviews by **sentiment** (positive / negative) — neutral reviews are dropped, not clustered — then embed the surviving clusters and index them in **FAISS** for semantic retrieval. Sentiment is the first-class grouping axis (not an optional extra): the vector DB holds only opinionated, retrievable content, so a query like "anything bad about the tour?" lands in the negative cluster and "highlights?" in the positive one.

**Plan:**
1. **Break down reviews clause-wise** — reuse `split.py`'s clause splitter so each review becomes a list of clauses. Sentiment is scored at clause granularity, not on the whole review text (a single review often mixes positive and negative statements; whole-text scoring blurs them).
2. **Score each clause for sentiment** — classify every clause as **positive / negative / neutral** (semantic model or the existing LLM endpoint in `keyword_based/llm.py`).
3. **Discard neutral clauses** — only clauses with a clear positive or negative signal are kept. Neutral content ("the queue was long", "we visited in June") carries no opinion and would only add noise to the vectors.
4. **Group positive + negative clauses into clusters** — surviving clauses are grouped by (a) **sentiment polarity** (positive vs negative) and (b) **place** (the location clusters already built in `RAG/retriever.py`). Each cluster = one polarity × one place, holding the clauses that share both.
5. **Embed each cluster** — produce one representative vector per cluster (mean of its clause embeddings, or an embedded LLM-written cluster summary). Embed at the cluster level, not per clause: fewer vectors → faster ANN search, smaller index, and a cluster hit returns a coherent, thematically-grouped set instead of scattered clauses.
6. **Index in FAISS** — load the cluster vectors into a FAISS index (in-memory is fine at this data size) and retrieve by cosine similarity against the embedded query, filtered by the desired polarity.

**Pipeline:**
```
review → split.py (clause split)
       → per-clause sentiment classifier (positive / negative / neutral)
       → drop neutral
       → group by (polarity, place)
       → embed each cluster → FAISS index
       → query: embed → polarity-filtered ANN search → return cluster's clauses
```

**Open questions:**
- Embedding model: local `sentence-transformers` vs hosted API.
- Per-clause embed + mean-pool into a cluster vector, vs embed an LLM-written cluster summary (tighter semantics, one LLM call per cluster).
- Sentiment scorer: reuse the wired LLM endpoint vs a local DeBERTa-style classifier.

**Alternative — vector-less RAG (no embeddings, no FAISS):** a viable path that skips the embedding layer entirely. The current retrieval already works via keyword/token overlap plus LLM taxonomy classification; a vector-less design keeps and strengthens that route instead:
- **Lexical + BM25 ranking** over the clause/clusters already split and sentiment-grouped above (e.g. `rank_bm25`) — inverted-index search, no vectors, deterministic, and cheap to run locally.
- **LLM-assisted routing/reranking** — let the existing `keyword_based/llm.py` endpoint do relevance scoring and top-k reranking over the keyword-recall set, trading a little latency for semantic understanding without any embedding model.
- **Sparse/keyword vectors** — encode each cluster as a hashed or TF-IDF sparse vector (e.g. scikit-learn `TfidfVectorizer`) and do cosine similarity with plain numpy. Keeps the "vector" API without any embedding model; still misses true paraphrase but is stronger than raw token overlap.
- **Hybrid** — keep the keyword/BM25 recall as the base and add the FAISS index (above) only if semantic-miss cases prove it's needed; run both and compare hit rates before committing to embeddings.

This is useful if we want to stay dependency-light and avoid hosting/embedding-model cost; the trade-off is weaker semantic recall on paraphrased queries ("too spicy" vs "way too hot") that a vector index would catch.
