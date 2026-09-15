# jojani_ai

A suite of tools for analyzing Booking.com-style reviews. Independent, self-contained components share the same data and LLM configuration but are otherwise decoupled:

| Component | Location | Entry point (CLI) | Entry point (Web) | What it does |
|-----------|----------|-------------------|-------------------|--------------|
| Clause Splitting | `split.py` | `python split.py <csv> -o out.jsonl` | — | Splits raw reviews into language-aware clauses (JSONL). Stdlib only. |
| Sentiment Classification | `sentiment_analysis/` | `python sentiment_analysis/classify.py <jsonl>` | — | Classifies each clause as negative/neutral/positive via local BERT. |
| Review Analysis Pipeline | `keyword_based/` | `python -m keyword_based.llm_judge` | `python -m keyword_based.web.app` (:5000) | 3-step pipeline: extract → classify → LLM judge. Flags negative reviews for specific places and produces actionable fixes. |
| RAG Review Analyst | `RAG/` | `python RAG/cli.py "query"` | `python RAG/web/app.py` (:5001) | Keyword-based retrieval + LLM classification/summary for ad-hoc review queries. No embeddings. |

Both components use an OpenAI-compatible LLM endpoint configured via `.env` (`LLM_URL`, `LLM_API_KEY`, `LLM_MODEL`).

## Data

| File | Used by | Notes |
|------|---------|-------|
| `data/Booking_reviews.csv` | `keyword_based/` pipeline (step 1) | Raw guest reviews; column `Reviews`. |
| `data/places_data.csv` | `keyword_based/` pipeline (step 2) + `RAG/` | Place names for keyword filtering / place clustering. Single-column list, has duplicates/aliases/noise. |
| `output/attraction_reviews.json` | `RAG/` | Knowledge base: ~1582 reviews, ~265 attractions. Fields: `attraction_id`, `date`, `rating`, `review_text`. No location field — only opaque `attraction_id`s. |

## Output folder

`output/` holds the generated artifacts of the pipeline and RAG components.

| File | Written by | Description |
|------|-----------|-------------|
| `reviews.md` | `keyword_based/` step 1 | All reviews extracted from `Booking_reviews.csv`, one `## Review N` section per row. |
| `matched_reviews.md` | `keyword_based/` step 2 | Subset of `reviews.md` mentioning a place from `places_data.csv`; one `## <Place Name>` section per place. |
| `judge_results.md` | `keyword_based/` step 3 (CLI) | LLM judgement of matched reviews: negative reviews flagged with specific, actionable fixes. |
| `judgements.csv` | `keyword_based/` step 3 (Web) | LLM judgement as a CSV; columns `location_name`, `judgement`, `action`. |
| `judgement_progress.json` | `keyword_based/` step 3 (Web) | Live progress tracker for a running web judgement: `running`, `total`, `done`, `start_time`, `message`. |
| `attraction_reviews.json` | (input to `RAG/`) | RAG knowledge base — see Data table above. |

---

# Clause Splitting + Sentiment Classification

A two-stage pre-processing pipeline that breaks raw reviews into clauses and classifies each clause's sentiment using a local BERT model.

## Pipeline Flow

```mermaid
flowchart LR
    CSV[/"data/booking_attractions_reviews.csv"/] --> SPLIT["split.py"]
    SPLIT -->|writes| JSONL[("review_clauses.jsonl")]
    JSONL --> CLASSIFY["sentiment_analysis/classify.py"]
    BERT{{"BERT multilingual-sentiment"}}
    CLASSIFY -->|reads| BERT
    CLASSIFY --> NEG[("output/negative_clauses.jsonl")]
    CLASSIFY --> NEU[("output/neutral_clauses.jsonl")]
    CLASSIFY --> POS[("output/positive_clauses.jsonl")]
```

## Stage 1 — split.py

Splits each review into sentences and clauses using language-aware regex. Handles broken CSV quoting, abbreviation protection, and merges fragments shorter than `--min-words` (default 3).

```bash
python split.py data/booking_attractions_reviews.csv -o review_clauses.jsonl
# optional: also write a flat one-row-per-clause CSV
python split.py data/booking_attractions_reviews.csv -o review_clauses.jsonl --flat-csv review_clauses.csv
```

| Option | Default | Description |
|--------|---------|-------------|
| `input_csv` | *(required)* | Path to the raw Booking.com reviews CSV |
| `-o / --output` | `review_clauses.jsonl` | Output JSONL (one review per line, with `clauses` array) |
| `--flat-csv` | *(none)* | Also write one row per clause to this CSV |
| `--min-words` | `3` | Fragments shorter than this are merged into a neighbour |

## Stage 2 — sentiment_analysis/classify.py

Classifies every unique clause as **negative** / **neutral** / **positive** using a local BERT model (`bert-multilingual-sentiment/`), then writes one JSONL file per sentiment bucket.

```bash
# from the project root
python sentiment_analysis/classify.py review_clauses.jsonl
python sentiment_analysis/classify.py review_clauses.jsonl -o output/ --batch-size 32 --max-length 256
```

| Option | Default | Description |
|--------|---------|-------------|
| `input` | *(required)* | Path to the JSONL produced by `split.py` |
| `-o / --output-dir` | `<project>/output` | Directory for the three sentiment JSONL files |
| `--model` | `bert-multilingual-sentiment/` (local) or `nlptown/bert-base-multilingual-uncased-sentiment` (HF) | Model dir or HF model id |
| `--batch-size` | `32` | Inference batch size |
| `--max-length` | `256` | Max tokens per clause |
| `--threads` | CPU count | torch intra-op threads |

## Dependencies

`split.py` uses only the standard library. `sentiment_analysis/` additionally requires:

```
torch
transformers
```

## Output files

| File | Contents |
|------|----------|
| `review_clauses.jsonl` | One review per line: `review_id`, `attraction_id`, `rating`, `lang`, `date`, `source_review`, `clauses[{clause_id, sentence_no, text}]` |
| `output/negative_clauses.jsonl` | One clause per line: `clause_id`, `review_id`, `attraction_id`, `lang`, `date`, `sentence_no`, `clause_text`, `sentiment`, `score` |
| `output/neutral_clauses.jsonl` | Same schema |
| `output/positive_clauses.jsonl` | Same schema |

---

# keyword_based/ — Review Analysis Pipeline

3-step pipeline: extract → classify → LLM judge.

## Pipeline Flow

```mermaid
flowchart LR
    CSV[/"data/Booking_reviews.csv"/] --> S1["extract_reviews.py"]
    S1 -->|writes| MD1[("output/reviews.md")]
    CSV2[/"data/places_data.csv"/] --> S2["classify_reviews.py"]
    MD1 -->|reads| S2
    S2 -->|writes| MD2[("output/matched_reviews.md")]
    MD2 --> JUDGE["judge.py"]
    LLM{{"LLM endpoint"}}
    JUDGE -.->|batch| LLM
    JUDGE --> R1[("output/judge_results.md")]
    JUDGE --> R2[("output/judgements.csv")]
```

## Steps

| Step | Command | Reads | Writes |
|------|---------|-------|--------|
| 1 | `python -m keyword_based.extract_reviews` | `Booking_reviews.csv` | `output/reviews.md` |
| 2 | `python -m keyword_based.classify_reviews` | `reviews.md` + `places_data.csv` | `output/matched_reviews.md` |
| 3 (CLI) | `python -m keyword_based.llm_judge` | `matched_reviews.md` | `output/judge_results.md` |
| 3 (Web) | `python -m keyword_based.web.app` → http://localhost:5000 | `matched_reviews.md` | `output/judgements.csv` |

## Module Map

| File | Role |
|------|------|
| `config.py` | Paths, LLM env vars, batch/retry constants |
| `llm.py` | `call_llm()` — single LLM client with retry; `parse_llm_json()` — strips code fences |
| `prompts.py` | `REVIEW_JUDGE_PROMPT` template + `build_judge_prompt()` |
| `parse_reviews.py` | Markdown section parser (shared), `load_keywords()` |
| `extract_reviews.py` | Step 1: CSV → markdown |
| `classify_reviews.py` | Step 2: keyword filter |
| `judge.py` | Step 3 core: batch-judge loop (shared by CLI + web) |
| `llm_judge.py` | Step 3 CLI entry point |
| `web/app.py` | Step 3 Flask entry point |

## Markdown File Format

All intermediate files use the same structure — `## ` sections with a title line and body:

```markdown
# Title

## Section Name
body text...

## Next Section
body text...
```

`parse_reviews._parse_md_sections(path, prefix)` splits on any `## ` header; the public wrappers pick the right prefix per file type.

---

# RAG/ — RAG Review Analyst

Retrieves the reviews most relevant to a query, then asks an LLM to classify and summarize them. Keyword-based retrieval — no embeddings.

## Files

| File             | Responsibility                                            |
|------------------|-----------------------------------------------------------|
| `config.py`      | Paths, LLM settings, taxonomy, review-count limit.        |
| `retriever.py`   | All retrieval: tokenization, place clustering, search.    |
| `rag.py`         | `RAGEngine.ask()` — the glue: retrieve → prompt → LLM.    |
| `llm.py`         | `call_llm()` — one POST to an OpenAI-compatible endpoint. |
| `cli.py`         | Command-line entry point.                                 |
| `web/app.py`     | Flask entry point (port 5001) + `templates/index.html`.   |

## Pipeline Flow

```mermaid
flowchart LR
    Q[/"user query"/] --> SEARCH["Retriever.search()"]
    JSON[/"output/attraction_reviews.json"/] --> SEARCH
    PLACES[/"data/places_data.csv"/] --> SEARCH
    SEARCH --> ROUTE{"_route_query()"}
    ROUTE -->|hit ≥25% route_tokens| CLUSTER["_top_from_cluster()"]
    ROUTE -->|miss| GLOBAL["_global_search()"]
    CLUSTER --> TOPK[("top-K reviews")]
    GLOBAL --> TOPK
    TOPK --> ASK["RAGEngine.ask()"]
    ASK --> LLM{{"LLM endpoint"}}
    LLM --> RESULT[("JSON: summary, actions, source_reviews, location")]
```

## The flow (one query)

```
query
  └─ Retriever.search()                 retriever.py
       ├─ _route_query()                try to match a place cluster
       │     └─ hit  → _top_from_cluster()  worst rating first, then recent
       │     └─ miss → _global_search()        keyword overlap across all reviews
       └─ → (top-K reviews, location_or_None)
  └─ RAGEngine.ask()                    rag.py
       ├─ build prompt from reviews
       ├─ call_llm()                    llm.py
       └─ parse JSON → {summary, actions, source_reviews, location}
```

## How retrieval picks reviews

1. **Tokenize** — lowercase, drop punctuation, drop words ≤2 chars and stopwords
   (`_STOP`).
2. **Route to a place** — a place "matches" only if it shares ≥25% of the query's
   tokens with the place's *distinguishing* tokens (`route_tokens`), which exclude
   generic words like "farm" (`_GENERIC`). No match → global keyword search.
3. **Rank** — cluster path sorts by rating ascending (most actionable) then date
   descending; global path ranks by token-overlap count, then rating.

## Worked example: "what are the issues in jozani forest"

A concrete trace of one query through the steps above.

**1. Tokenize** (`_tokenize`)

```
"what are the issues in jozani forest"
→ drop stopwords (are, the, in)  →  {what, issues, jozani, forest}
```

Note `forest` is **not** a stopword, so it stays. The word `issues` carries no
retrieval weight — it is only present in the query, never matched against data.

**2. Route to a place** (`_route_query`). The places CSV contains several
distinct Jozani spellings, each its own cluster after dedup:

| Place name (from `places_data.csv`) | route_tokens (non-generic) |
|--------------------------------------|----------------------------|
| `Jozani`                             | {jozani}                   |
| `Jozani Forest`                      | {jozani, forest}           |
| `Jozani Forest National Park Mangrove Walk` | {jozani, forest, mangrove, walk} |
| `Jozani Chwaka Bay National Park`    | {jozani, chwaka, bay}      |
| `Jozani Sea Turtle Sanctuary`        | {jozani, sea, turtle, sanctuary} |

Each is scored as `(overlap, specificity, query_coverage)` with a ≥25%
coverage floor:

| Cluster | overlap | query_coverage | specificity | score |
|---------|---------|----------------|-------------|-------|
| `Jozani Forest` | 2 | 2/4 = 0.50 | 2/2 = 1.0 | **(2, 1.0, 0.50)** ✓ best |
| `Jozani Forest … Mangrove Walk` | 2 | 0.50 | 2/4 = 0.5 | (2, 0.5, 0.50) |
| `Jozani` | 1 | 1/4 = 0.25 | 1/1 = 1.0 | (1, 1.0, 0.25) |
| `Jozani Chwaka Bay …` | 1 | 0.25 | 1/3 ≈ 0.33 | (1, 0.33, 0.25) |
| `Jozani Sea Turtle Sanctuary` | 1 | 0.25 | 1/5 = 0.2 | (1, 0.2, 0.25) |

Max tuple wins → **routes to the `Jozani Forest` cluster.**

**3. Recall is place-based, not query-based** (`_index`). At startup every
review that *mentions* a Jozani-Forest token is attached to the cluster —
including 5★ "the monkeys were adorable" reviews. The query word `issues`
plays **no role** in which reviews are recalled.

**4. Top-K** (`_top_from_cluster`, `MAX_REVIEWS = 15`). The cluster's reviews
are sorted **rating ascending, then date descending** (worst, most recent
first) and the first 15 are kept. Low-rated reviews surface first *because of
their rating*, not because the system matched the word "issues."

**5. LLM** (`RAGEngine.ask`). The 15 reviews are sent to the LLM (each
truncated to 800 chars). It classifies each into the taxonomy, writes a
2–4-sentence `summary`, and derives `actions`. The UI receives the **full,
untruncated** reviews (`result["source_reviews"] = reviews_list` in
`rag.py`), not the LLM's echoed copies.

**Limitations this example exposes**

- **No semantic handling of "issues".** If every Jozani review were 5★, the
  system would still return the 15 most recent 5★ reviews; the LLM would simply
  report "mostly positive." It cannot dig past what the rating sort yields.
- **Alias fragmentation.** `Jozani`, `Jozani Forest`, and
  `Jozani Forest National Park Mangrove Walk` are separate clusters (different
  token sets), so reviews mentioning bare "Jozani" are **not** pulled in when
  the query routes to `Jozani Forest`.
- **Typos silently degrade.** "jojhani forest" tokenizes to `jojhani`, matches
  no route_token → `_route_query` returns `None` → global keyword search,
  which also won't match "jozani," yielding a near-empty or off-topic result.

## Run it

```bash
python RAG/cli.py "your query"            # one query
python RAG/cli.py --interactive           # REPL
python RAG/cli.py "your query" --json     # raw JSON
python RAG/web/app.py                     # web UI on :5001
```

Set `LLM_URL`, `LLM_API_KEY`, `LLM_MODEL` in `.env` (or environment).

## Debugging

- To see exactly which place a query routed to (or that it fell back to global
  search), instantiate with the debug flag:
  `Retriever(_debug=True)` — it prints one line per `search()` call.
- The knowledge base is `output/attraction_reviews.json`; place names come from
  `data/places_data.csv` (optional — without it, retrieval is plain keyword search).
