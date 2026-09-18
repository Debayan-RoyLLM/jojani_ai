"""Visualize the taxonomy grouping of negative-cluster blocks as interactive HTML.

Reads `output/taxonomy_grouping.jsonl` (one line per category:
{"category", "block_count", "blocks": [{"cluster_id", "block_name", "size"}]}),
prints a short summary, and writes a self-contained interactive HTML page
(inline SVG + vanilla JS, no CDN / no plotly — the only deps are stdlib + json).

The page shows every category as a horizontal bar (block count + clause total),
and clicking a category opens a drill-down panel listing its blocks with a
size bar per block.

Usage:
    python -m kb_agent.visualize_taxonomy
    python -m kb_agent.visualize_taxonomy --input path/to/taxonomy_grouping.jsonl
    python -m kb_agent.visualize_taxonomy --output path/to/taxonomy.html
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INPUT = ROOT / "output" / "taxonomy_grouping.jsonl"
OUTPUT_HTML = ROOT / "output" / "taxonomy_grouping.html"


def load_categories(path: Path) -> list[dict]:
    """Return a list of {"category", "block_count", "clause_total", "blocks"}
    ordered by clause_total desc (biggest issue first)."""
    cats: list[dict] = []
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            blocks = d.get("blocks", []) or []
            clause_total = sum(int(b.get("size", 0) or 0) for b in blocks)
            cats.append(
                {
                    "category": d.get("category", "other"),
                    "block_count": len(blocks),
                    "clause_total": clause_total,
                    "blocks": [
                        {
                            "cluster_id": int(b.get("cluster_id", 0) or 0),
                            "block_name": str(b.get("block_name", "")),
                            "size": int(b.get("size", 0) or 0),
                        }
                        for b in blocks
                    ],
                }
            )
    cats.sort(key=lambda c: (-c["clause_total"], -c["block_count"]))
    return cats


def print_summary(cats: list[dict]) -> None:
    total_blocks = sum(c["block_count"] for c in cats)
    total_clauses = sum(c["clause_total"] for c in cats)
    print(f"\n=== Taxonomy grouping ({len(cats)} categories) ===")
    print(f"Total: {total_blocks} blocks, {total_clauses} clauses\n")
    for c in cats:
        print(f"  {c['category']:<32} {c['block_count']:>4} blocks  {c['clause_total']:>5} clauses")


def render_html(cats: list[dict]) -> str:
    data = json.dumps(
        [
            {
                "category": c["category"],
                "block_count": c["block_count"],
                "clause_total": c["clause_total"],
                "blocks": c["blocks"],
            }
            for c in cats
        ],
        ensure_ascii=False,
    )
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Taxonomy grouping — negative-cluster blocks</title>
<style>
  :root {{ --bg:#0f1117; --panel:#171a23; --ink:#e7e9ef; --muted:#8a90a0;
           --line:#262b38; --accent:#5b8cff; }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; background:var(--bg); color:var(--ink);
          font:15px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif; }}
  header {{ padding:20px 24px 8px; }}
  h1 {{ font-size:20px; margin:0 0 4px; }}
  .sub {{ color:var(--muted); font-size:13px; }}
  .wrap {{ display:flex; gap:20px; padding:16px 24px 40px; align-items:flex-start; }}
  .panel {{ background:var(--panel); border:1px solid var(--line); border-radius:10px;
            padding:16px; }}
  #overview {{ flex:1 1 460px; min-width:320px; }}
  #detail {{ flex:1 1 460px; min-width:320px; }}
  .panel h2 {{ font-size:15px; margin:0 0 12px; color:var(--ink); }}
  .row {{ display:flex; align-items:center; gap:10px; padding:7px 8px; border-radius:7px;
          cursor:pointer; user-select:none; }}
  .row:hover {{ background:rgba(91,140,255,.08); }}
  .row.active {{ background:rgba(91,140,255,.16); outline:1px solid var(--accent); }}
  .row .name {{ flex:0 0 220px; font-size:13.5px; white-space:nowrap;
                overflow:hidden; text-overflow:ellipsis; }}
  .bar-track {{ flex:1 1 auto; height:14px; background:#0b0d13; border-radius:4px; overflow:hidden; }}
  .bar-fill {{ height:100%; background:var(--accent); border-radius:4px; }}
  .row .meta {{ flex:0 0 120px; text-align:right; color:var(--muted); font-size:12px; }}
  .blk {{ display:flex; align-items:center; gap:10px; padding:6px 8px; border-radius:6px; }}
  .blk:hover {{ background:rgba(255,255,255,.04); }}
  .blk .bid {{ flex:0 0 44px; color:var(--muted); font-size:12px; font-variant-numeric:tabular-nums; }}
  .blk .bname {{ flex:0 0 250px; font-size:13px; white-space:nowrap; overflow:hidden;
                 text-overflow:ellipsis; }}
  .blk .bar-track {{ height:12px; }}
  .blk .bsize {{ flex:0 0 52px; text-align:right; color:var(--muted); font-size:12px;
                 font-variant-numeric:tabular-nums; }}
  .empty {{ color:var(--muted); padding:24px; text-align:center; }}
  .tag {{ display:inline-block; background:rgba(91,140,255,.18); color:var(--accent);
          border-radius:6px; padding:2px 8px; font-size:12px; margin-bottom:10px; }}
</style>
</head>
<body>
<header>
  <h1>Taxonomy grouping — negative-cluster blocks</h1>
  <div class="sub">Click a category to inspect its blocks. Bars are scaled to the largest category / block shown.</div>
</header>
<div class="wrap">
  <div class="panel" id="overview">
    <h2>Categories (by clause volume)</h2>
    <div id="cat-list"></div>
  </div>
  <div class="panel" id="detail">
    <h2>Blocks</h2>
    <div id="blk-list"><div class="empty">Select a category on the left.</div></div>
  </div>
</div>
<script>
const DATA = {data};
const catList = document.getElementById("cat-list");
const blkList = document.getElementById("blk-list");
const maxClause = Math.max(1, ...DATA.map(c => c.clause_total));

DATA.forEach((c, i) => {{
  const row = document.createElement("div");
  row.className = "row";
  row.innerHTML =
    `<span class="name">${{c.category}}</span>` +
    `<span class="bar-track"><span class="bar-fill" style="width:${{c.clause_total / maxClause * 100}}%"></span></span>` +
    `<span class="meta">${{c.block_count}} blk · ${{c.clause_total}} cl</span>`;
  row.onclick = () => {{
    catList.querySelectorAll(".row").forEach(r => r.classList.remove("active"));
    row.classList.add("active");
    renderBlocks(c);
  }};
  catList.appendChild(row);
}});

function renderBlocks(c) {{
  const max = Math.max(1, ...c.blocks.map(b => b.size));
  const sorted = [...c.blocks].sort((a, b) => b.size - a.size);
  let html = `<span class="tag">${{c.category}} · ${{c.block_count}} blocks · ${{c.clause_total}} clauses</span>`;
  html += `<div>`;
  sorted.forEach(b => {{
    html += `<div class="blk">` +
      `<span class="bid">#${{b.cluster_id}}</span>` +
      `<span class="bname" title="${{b.block_name}}">${{b.block_name}}</span>` +
      `<span class="bar-track"><span class="bar-fill" style="width:${{b.size / max * 100}}%"></span></span>` +
      `<span class="bsize">${{b.size}}</span>` +
      `</div>`;
  }});
  html += `</div>`;
  blkList.innerHTML = html;
}}
</script>
</body>
</html>"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Visualize taxonomy grouping as interactive HTML")
    parser.add_argument("--input", default=str(INPUT))
    parser.add_argument("--output", default=str(OUTPUT_HTML))
    args = parser.parse_args()

    in_path = Path(args.input)
    if not in_path.exists():
        print(f"[error] input not found: {in_path}", file=sys.stderr)
        sys.exit(1)

    cats = load_categories(in_path)
    if not cats:
        print("[error] no categories loaded", file=sys.stderr)
        sys.exit(1)

    print_summary(cats)

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(render_html(cats), encoding="utf-8")
    print(f"\nWrote interactive page -> {out_path}")


if __name__ == "__main__":
    main()
