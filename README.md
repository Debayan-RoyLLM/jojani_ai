# jojani_ai — Multilingual Review Analysis Pipeline

A 5-stage pipeline that ingests tourist-attraction reviews scraped from Google (via Apify), splits them into atomic clauses, classifies each clause by sentiment with a local BERT model, embeds the negative clauses with a multilingual MiniLM encoder, and answers natural-language questions about them using FAISS + LLM (RAG).

All models run locally (no cloud inference except the LLM for the final answer).

---

## Data Flow

```
data/
  apify_reviews.csv          ← raw reviews (one row per review, has translated_content)
  apify_places.csv           ← place metadata (place_name, coords, type, island)
       │
       ▼
join_csv/                    ① Inner-join reviews + places on google_place_id
       │
       ▼
output/apify_reviews_joined.csv
       │
       ▼
clause_split/                ② Split each review into atomic clauses (regex, multilingual)
       │
       ▼
clause_split/review_clauses.jsonl   one review per line, clauses nested
       │
       ▼
sentiment_analysis/          ③ BERT sentiment: split clauses → negative / positive
       │
       ├──► sentiment_analysis/negative_clauses.jsonl
       │         │
       │         ▼
       │    clause_flatten/        ④ Flatten negative clauses → one clause per line
       │         │
       │         ▼
       │    clause_flatten/negative_clauses_flat.jsonl
       │         │
       │         ▼
       │    embed/                 ⑤ MiniLM embed + FAISS index build
       │         │
       │         ▼
       │    embed/negative_clauses_embedded.jsonl  (clauses + 384-d vectors)
       │    embed/negative_clauses.faiss            (search index)
       │
       ▼
rag_clusters/                ⑥ RAG: query → FAISS retrieve top-K clauses → LLM summarize
                              Returns {summary, actions[], source_clauses[]}
```

---

## Setup

```bash
pip install -r requirements.txt
```

### Environment (LLM endpoint)

The RAG stage calls an LLM for the final answer. Configure in `.env` at the repo root:

```env
LLM_URL=https://your-endpoint/v1/chat/completions
LLM_API_KEY=sk-...
LLM_MODEL=qwen27b
```

### Models

Both models are downloaded from Hugging Face on first run and cached locally:

| Model | Used by | Purpose |
|---|---|---|
| `nlptown/bert-base-multilingual-uncased-sentiment` | sentiment_analysis | Clause sentiment (1–5 stars) |
| `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` | embed, rag_clusters | 384-d clause embeddings |

If you have a local copy of the MiniLM weights at `clustering/minilm-l12-v2/`, it will be used automatically (see `paths.py`).

---

## Running the Pipeline

### Run everything at once

```bash
# Full pipeline, all 6 stages
python run_all.py

# Skip the swap_translated step (if your reviews don't need translation)
python run_all.py --skip-swap

# Resume from a later stage (e.g. start at stage 3, skip join + swap)
python run_all.py --from 3
```

`run_all.py` runs stages in sequence and stops immediately if any stage fails, printing which one. After it completes, start querying:

```bash
python rag_clusters/cli.py --interactive
```

---

### Run individual stages

Each stage is a standalone script — edit its `config.py` / `*_config.py` to change paths, then run.

### ① Join reviews + places

```bash
python join_csv/join_csvs.py
```

Reads `data/apify_reviews.csv` and `data/apify_places.csv`, inner-joins on `google_place_id`, writes `output/apify_reviews_joined.csv`.

> **Tip:** If reviews have a `translated_content` column with machine-translated English text, run this afterwards to replace `content` with the translation (so downstream stages see English):
> ```bash
> python join_csv/swap_translated.py
> ```

### ② Split reviews into clauses

```bash
python clause_split/split.py
```

Reads `output/apify_reviews_joined.csv`, splits each review into atomic clauses using language-aware regex rules (handles English, French, German, Spanish, Italian, Portuguese, Dutch). Writes `clause_split/review_clauses.jsonl`.

Config: `clause_split/split_config.py` — set `COLUMNS` to map CSV headers to fields, and `MIN_WORDS` to control fragment merging.

### ③ Classify clause sentiment

```bash
python sentiment_analysis/classify.py
```

Loads the local BERT sentiment model, classifies every unique clause, writes:
- `sentiment_analysis/negative_clauses.jsonl` — reviews with only negative clauses
- `sentiment_analysis/positive_clauses.jsonl` — reviews with only positive clauses

Neutral clauses are discarded.

### ④ Flatten negative clauses

```bash
python clause_flatten/flatten.py
```

Converts the nested per-review format to one flat clause per line. Writes `clause_flatten/negative_clauses_flat.jsonl`.

### ⑤ Embed + build FAISS index

```bash
python embed/embed.py
```

Embeds all flat negative clauses with MiniLM (batch size 64), writes:
- `embed/negative_clauses_embedded.jsonl` — clauses with 384-d `embedding` field
- `embed/negative_clauses.faiss` — `IndexFlatIP` search index (cosine via inner product on normalized vectors)

### ⑥ Query with RAG

**CLI:**

```bash
# Single query
python rag_clusters/cli.py "What do people complain about at the beach?"

# Interactive REPL
python rag_clusters/cli.py --interactive

# Raw JSON output
python rag_clusters/cli.py "service issues" --json
```

**Web UI (Flask, port 5002):**

```bash
python rag_clusters/web/app.py
```

Open `http://localhost:5002` in a browser. The UI has a search box and renders the summary, action items, and source clauses for each query. The JSON API is also available directly at `GET /api/query?q=…`.

Each query returns:
```json
{
  "summary": "2-4 sentence summary of what reviewers say",
  "actions": ["Specific, actionable items for the business"],
  "source_clauses": [
    {"clause_text": "...", "score": 0.92, "place_name": "Bawe Beach"}
  ]
}
```

---

## Directory Structure

```
jojani_ai/
├── paths.py                 # Centralized path definitions (single source of truth)
├── requirements.txt
├── .env                     # LLM credentials (not in git)
│
├── data/
│   ├── apify_reviews.csv    # Raw reviews from Apify scraper
│   └── apify_places.csv     # Place metadata from Apify scraper
│
├── output/
│   └── apify_reviews_joined.csv   # After stage ①
│
├── join_csv/
│   ├── join_config.py
│   ├── join_csvs.py
│   └── swap_translated.py
│
├── clause_split/
│   ├── split_config.py
│   └── split.py
│
├── sentiment_analysis/
│   ├── config.py
│   ├── classify.py
│   ├── negative_clauses.jsonl     # After stage ③
│   └── positive_clauses.jsonl     # After stage ③
│
├── clause_flatten/
│   ├── config.py
│   ├── flatten.py
│   └── negative_clauses_flat.jsonl  # After stage ④
│
├── embed/
│   ├── config.py
│   ├── embed.py
│   ├── negative_clauses_embedded.jsonl  # After stage ⑤
│   └── negative_clauses.faiss           # After stage ⑤
│
├── rag_clusters/
│   ├── config.py            # Taxonomy, LLM settings, model path
│   ├── llm.py               # OpenAI-compatible LLM client
│   ├── retriever.py         # FAISS search over clause embeddings
│   ├── rag.py               # RAG engine: retrieve → LLM → structured dict
│   ├── cli.py               # CLI entry point
│   └── web/
│       ├── app.py           # Flask app (port 5002) + /api/query endpoint
│       └── templates/
│           └── index.html   # Single-page search UI
│
└── OLD/                     # Archived previous pipeline versions
    ├── keyword_based/       # Old keyword-based 3-step pipeline
    └── RAG/                 # Old RAG app (attraction_reviews.json KB)
```

---

## Key Design Decisions

**Clause-level analysis, not review-level.** A single review often mixes positive and negative statements. By splitting into clauses and classifying each independently, we can embed only the genuinely negative content and retrieve precisely relevant complaints.

**Multilingual regex clause splitter.** Reviews come in many languages. The splitter uses per-language connector rules (conjunctions, commas, semicolons) rather than a generic sentence tokenizer, giving more granular and accurate clause boundaries.

**FAISS over vector DB.** The clause index is small enough (~thousands of vectors) that a flat `IndexFlatIP` in-process index is faster to set up and query than a vector database. Swapping to a real DB is a drop-in change to `retriever.py` if the corpus grows.

**Centralized paths in `paths.py`.** All inter-stage file paths are defined in one file. Renaming a folder is a one-line change there instead of a hunt across per-stage config files.

---

## Issue Taxonomy

The LLM classifies retrieved clauses into these canonical labels (defined in `rag_clusters/config.py`):

| Label | Meaning |
|---|---|
| `venue_conditions_unpleasant` | Dirty, overcrowded, unpleasant physical environment |
| `poor_customer_service` | Rude, unhelpful, or absent staff |
| `overpriced` | Bad value for money |
| `unsafe` | Safety concerns |
| `accessibility_issues` | Difficulty accessing the venue |
| `poor_maintenance` | Broken or neglected facilities |
| `misleading_marketing` | Reality doesn't match what was advertised |
| `language_barrier` | Communication difficulties |
| `weather_related` | Weather negatively impacted the experience |
| `logistics_problems` | Transport, parking, timing issues |
| `positive_highlight` | Something worth noting positively |
| `other` | Doesn't fit above categories |
