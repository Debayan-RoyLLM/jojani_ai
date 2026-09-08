# jojani_ai

Review analysis pipeline: extract → classify → LLM judge.

## Project Structure

```
jojani_ai/
├── data/
│   ├── Booking_reviews.csv          # Raw reviews (source)
│   ├── booking_attractions_reviews.csv
│   └── places_data.csv             # Place name keywords
├── src/
│   ├── extract_reviews.py          # Step 1: CSV → reviews.md
│   ├── classify_reviews.py         # Step 2: Filter by place keywords
│   ├── llm_judge.py               # Step 3: CLI LLM judgement
│   └── app.py                     # Step 3 (web): Button-triggered LLM judgement
├── output/                         # Generated files (gitignored)
│   ├── reviews.md
│   ├── matched_reviews.md
│   ├── judge_results.md
│   └── judgements.csv             # (location_name, judgement, action)
├── .env                            # LLM config (gitignored)
└── .gitignore
```

## Prerequisites

- Python 3.10+
- Dependencies: `pip install requests flask`

## Setup

Fill in your LLM credentials in `.env`:

```
LLM_URL=https://your-endpoint/v1/chat/completions
LLM_API_KEY=sk-your-key
LLM_MODEL=your-model-name
```

## How to Run

### Steps 1 & 2 (preprocessing)

```bash
# Step 1: Extract all reviews from CSV into output/reviews.md
python src/extract_reviews.py

# Step 2: Filter reviews containing place names into output/matched_reviews.md
python src/classify_reviews.py
```

### Step 3: LLM Judgement

**Option A — CLI:**

```bash
python src/llm_judge.py
```

**Option B — Web UI (click a button):**

```bash
python src/app.py
```

Then open http://localhost:5000 and click **"Run Judgement"**.

Results are saved to `output/judgements.csv` with columns:

| Column          | Description                          |
|-----------------|--------------------------------------|
| `location_name` | Place name from the review           |
| `judgement`     | One-sentence reason (why negative)   |
| `action`        | Semicolon-joined actionable fixes    |

## Configuration

| Var (in `.env`)  | Description                  |
|------------------|------------------------------|
| `LLM_URL`        | OpenAI-compatible endpoint   |
| `LLM_API_KEY`    | API key                      |
| `LLM_MODEL`      | Model identifier             |

Tweak `BATCH_SIZE` in `src/llm_judge.py` / `src/app.py` to control reviews per LLM call.
