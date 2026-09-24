# KPIs Extractable from the Negative-Review Clusters

Companion doc for the `kb_agent` pipeline. It maps each Key Performance Indicator
to the **exact fields** the pipeline already produces, so every metric below can
be computed without new infrastructure.

## Pipeline inputs

| File | Producer | Shape (one line) |
|---|---|---|
| `negative_clusters.jsonl` | `kb_agent/cluster.py` | `{"cluster_id", "clauses[]", "place_names[]", "size"}` |
| `kb_agent/output/knowledge_base.jsonl` | `kb_agent/run.py` | `{"cluster_id", "clause_count", "issues[{issue, importance}]}` |
| `kb_agent/output/fine_taxonomy_grouping.jsonl` | `kb_agent/classify_fine_taxonomy.py` | per group: `{"group_id", "group_label", "block_count", "blocks[{cluster_id, subcategory_key, subcategory_label, block_name, size}]}` |

Note: only `negative_clusters.jsonl` is present by default. `knowledge_base.jsonl`
and `fine_taxonomy_grouping.jsonl` are generated on demand:

```bash
python -m kb_agent.run                    # -> knowledge_base.jsonl
python -m kb_agent.classify_fine_taxonomy # -> fine_taxonomy_grouping.jsonl
```

---

## Tier 1 — From the raw clustering (no LLM needed)

Source: `negative_clusters.jsonl`. Runs immediately.

| KPI | Formula / source | What it tells you |
|---|---|---|
| Total negative clauses | `sum(size)` across blocks | Volume of the problem |
| Block / complaint-topic count | number of JSONL lines | Number of distinct issue themes |
| Block size distribution | min / max / mean / median of `size`; Gini or top-10% share | Are complaints concentrated in a few hot themes or spread thin? |
| Complaint density per place | clauses grouped by `place_names` | Which locations generate the most negativity (negative-review hotspot ranking) |
| Places per block | avg `len(place_names)` per cluster | Cross-venue themes (e.g. "tourist trap" across many sites) — systemic vs. local signal |
| Cluster purity / tightness | intra-block mean cosine similarity | Whether a block is a coherent single theme or a grab-bag — a data-quality KPI for tuning `DISTANCE_THRESHOLD` |
| Drop rate | `(total input clauses − clauses kept) / total` | How much signal `MIN_CLUSTER_SIZE=3` discards |

## Tier 2 — From the knowledge-base importance scores (needs LLM output)

Source: `kb_agent/output/knowledge_base.jsonl`. Requires `kb_agent.run` first.

| KPI | Formula | What it tells you |
|---|---|---|
| Average severity per block | mean of `importance` in a block | How severe the dominant issues are, 0–10 |
| Severity-weighted volume | `sum(importance)` per block (or per place) | "Pain point" ranking — the highest *impact* issues, not just the most frequent |
| Distinct-issue diversity | count of `issues` per block | How many separate problems one location/cluster raises |
| Top-N most-urgent issues | rank issues by `importance`, aggregate across blocks | A priority list for management |
| Severity × frequency | count of blocks containing an issue × its avg `importance` | A single "impact score" combining how often and how badly an issue appears |

## Tier 3 — From the fine-taxonomy classification (needs LLM output)

Source: `kb_agent/output/fine_taxonomy_grouping.jsonl`. Requires
`kb_agent.classify_fine_taxonomy` first.

| KPI | Formula | What it tells you |
|---|---|---|
| Issue-mix share | `block_count` per group / total | The complaint "portfolio" — e.g. 30% animal welfare, 15% pricing |
| Top problem group / subcategory | argmax `block_count` (group or subcategory level) | The single biggest complaint driver |
| Residual ("other") rate | blocks in `residual` / total | How well the taxonomy covers reality — high = taxonomy is missing categories |
| Concentration index | HHI over group shares (Σ share²) | Is negativity dominated by one area or balanced? |
| Subcategory spread within group | distribution of `size` across a group's subcategories | Within "Pricing", is it mostly entry-fee or value? |

## Tier 4 — Cross-dataset (needs the positive side too)

The `sentiment_analysis` classifier writes both polarities out of
`clause_split` output (see `sentiment_analysis/config.py` → `OUTPUT_POSITIVE`,
default `positive_clauses.jsonl`). To get a *clustered* positive side comparable
to the negative blocks above, run the same agglomerative cosine clustering
(`kb_agent/cluster.py` logic) over the positive clauses and their MiniLM
embeddings, then join on place:

- **Negative:positive clause ratio per place** — a "satisfaction index" per location.
- **Sentiment mix by place** — negative share, positive share, and their ratio over time (if review dates are available).
- **Place-level net score** — e.g. `(positive_clauses − negative_clauses) / total`.

---

## Recommended headline KPIs

The few that matter most for a tourism / destination audience:

1. **Complaint density per place** (Tier 1) — which venues are worst.
2. **Severity-weighted top issues** (Tier 2) — the most *urgent* pain points.
3. **Issue-mix share + residual rate** (Tier 3) — what kinds of problems dominate, and whether the taxonomy covers them.
4. **Negative:positive ratio per place** (Tier 4) — the overall sentiment balance.
