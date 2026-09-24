"""Visualize the FINE taxonomy grouping of negative-cluster blocks as interactive HTML.

Fine-grained counterpart of `visualize_taxonomy.py`. Instead of the 20-category
canonical list, this uses the 20-group / 90-subcategory taxonomy (kb_agent/taxonomy.py).
Reads `output/fine_taxonomy_grouping.jsonl` (one line PER GROUP:
    {"group_id", "group_label", "block_count", "blocks": [{"cluster_id",
     "subcategory_key", "subcategory_label", "block_name", "size"}]}),
prints a short summary, and writes a self-contained interactive HTML page
(inline CSS + vanilla JS, no CDN — the only deps are stdlib + json).

Three-level drill-down:
    Groups (by clause volume) -> Subcategories within a group -> Blocks in a subcategory.
Click a group on the left to see its subcategories (middle); click a subcategory
to see its blocks with a size bar each (right). Bars scale to the largest value
in the currently shown level.

Usage:
    python -m kb_agent.visualize_fine_taxonomy
    python -m kb_agent.visualize_fine_taxonomy --input path/to/fine_taxonomy_grouping.jsonl
    python -m kb_agent.visualize_fine_taxonomy --output path/to/fine_taxonomy.html
"""
from __future__ import annotations

import argparse
import html
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INPUT = ROOT / "output" / "fine_taxonomy_grouping.jsonl"
OUTPUT_HTML = ROOT / "output" / "fine_taxonomy_grouping.html"


def load_groups(path: Path) -> list[dict]:
    """Return a list of group dicts ordered by clause_total desc (biggest issue
    first), each with its blocks nested under a "subcategories" map.

    Each output group:
        {"group_id", "group_label", "block_count", "clause_total",
         "subcategories": [{ "key", "label", "block_count", "clause_total",
                             "blocks": [{cluster_id, block_name, size}] }]}
    Subcategories within a group are sorted by clause_total desc, then label."""
    groups: list[dict] = []
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            raw_blocks = d.get("blocks", []) or []
            # Bucket blocks by their subcategory_key, preserving order.
            subs: "dict[str, dict]" = {}
            for b in raw_blocks:
                key = str(b.get("subcategory_key", "other") or "other")
                s = subs.get(key)
                if s is None:
                    s = subs[key] = {
                        "key": key,
                        "label": html.escape(str(b.get("subcategory_label", key) or key)),
                        "block_count": 0,
                        "clause_total": 0,
                        "blocks": [],
                    }
                size = int(b.get("size", 0) or 0)
                s["block_count"] += 1
                s["clause_total"] += size
                s["blocks"].append(
                    {
                        "cluster_id": int(b.get("cluster_id", 0) or 0),
                        "block_name": html.escape(str(b.get("block_name", ""))),
                        "size": size,
                    }
                )
            # Sort blocks within each subcategory by size desc, then cluster_id.
            for s in subs.values():
                s["blocks"].sort(key=lambda b: (-b["size"], b["cluster_id"]))
            sub_list = sorted(
                subs.values(), key=lambda s: (-s["clause_total"], s["label"])
            )
            clause_total = sum(s["clause_total"] for s in sub_list)
            groups.append(
                {
                    "group_id": str(d.get("group_id", "other") or "other"),
                    "group_label": html.escape(str(d.get("group_label", d.get("group_id", "")) or d.get("group_id", ""))),
                    "block_count": sum(s["block_count"] for s in sub_list),
                    "clause_total": clause_total,
                    "subcategories": sub_list,
                }
            )
    groups.sort(key=lambda g: (-g["clause_total"], -g["block_count"]))
    return groups


def print_summary(groups: list[dict]) -> None:
    total_blocks = sum(g["block_count"] for g in groups)
    total_clauses = sum(g["clause_total"] for g in groups)
    total_subs = sum(len(g["subcategories"]) for g in groups)
    print(f"\n=== Fine taxonomy grouping ({len(groups)} groups) ===")
    print(f"Total: {total_subs} subcategories, {total_blocks} blocks, {total_clauses} clauses\n")
    for g in groups:
        label = html.unescape(g["group_label"])
        print(f"  {label:<24} {g['block_count']:>4} blocks  {g['clause_total']:>5} clauses  ({len(g['subcategories'])} subcats)")


# --- HTML template pieces ------------------------------------------------------
# Kept as plain strings (NOT f-strings) so the CSS/JS braces need no escaping.
# PAGE.format() substitutes only {css}, {js}, {sub_text}; the JS is built by a
# single .replace() of the __DATA__ placeholder (no .format over the JS itself).

CSS = """
  :root { --bg:#0f1117; --panel:#171a23; --ink:#e7e9ef; --muted:#8a90a0;
          --line:#262b38; --accent:#5b8cff; --track:#0b0d13; color-scheme:dark;
          box-sizing:border-box; padding-top:env(safe-area-inset-top,0px); padding-bottom:env(safe-area-inset-bottom,0px); }
  :root[data-theme="light"] { --bg:#f4f6fa; --panel:#ffffff; --ink:#1a1f2b; --muted:#5f6778;
          --line:#dde2ec; --accent:#2f66e0; --track:#e8ecf4; color-scheme:light; }
  html { scroll-padding-top:env(safe-area-inset-top,0px); }
  *,*::before,*::after { box-sizing:inherit; }
  body { margin:0; background:var(--bg); color:var(--ink);
         font:15px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif; }
  header { padding:20px 24px 8px; display:flex; justify-content:space-between; gap:16px;
           align-items:flex-start; }
  h1 { font-size:20px; margin:0 0 4px; }
  .sub { color:var(--muted); font-size:13px; }
  .themebtn { background:var(--panel); color:var(--muted); border:1px solid var(--line); border-radius:7px;
              padding:5px 10px; font:inherit; font-size:12px; cursor:pointer; }
  .wrap { display:flex; flex-wrap:wrap; gap:20px; padding:16px 24px 40px; align-items:flex-start; }
  .panel { background:var(--panel); border:1px solid var(--line); border-radius:10px; padding:16px; min-width:0; }
  #groups { flex:1 1 360px; min-width:300px; }
  #subs { flex:1 1 360px; min-width:300px; }
  #blocks { flex:1 1 420px; min-width:320px; }
  .panel h2 { font-size:15px; margin:0 0 12px; color:var(--ink); }
  .row { display:flex; align-items:center; gap:10px; padding:7px 8px; border-radius:7px;
         cursor:pointer; user-select:none; width:100%; background:none; border:0; color:inherit;
         font:inherit; text-align:left; }
  .row:hover { background:rgba(91,140,255,.08); }
  .row.active { background:rgba(91,140,255,.16); outline:1px solid var(--accent); }
  .row .name { flex:0 0 200px; font-size:13.5px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
  #subs .row .name { flex:0 0 220px; }
  .bar-track { flex:1 1 auto; height:14px; background:var(--track); border-radius:4px; overflow:hidden; min-width:40px; }
  .bar-fill { display:block; height:100%; background:var(--accent); border-radius:4px; }
  .row .meta { flex:0 0 110px; text-align:right; color:var(--muted); font-size:12px; font-variant-numeric:tabular-nums; }
  .blk { display:flex; align-items:center; gap:10px; padding:6px 8px; border-radius:6px; }
  .blk:hover { background:rgba(255,255,255,.04); }
  .blk .bid { flex:0 0 44px; color:var(--muted); font-size:12px; font-variant-numeric:tabular-nums; }
  .blk .bname { flex:1 1 auto; font-size:13px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
  .blk .bar-track { height:12px; }
  .blk .bsize { flex:0 0 48px; text-align:right; color:var(--muted); font-size:12px; font-variant-numeric:tabular-nums; }
  .empty { color:var(--muted); padding:24px; text-align:center; }
  .tag { display:inline-block; background:rgba(91,140,255,.18); color:var(--accent);
         border-radius:6px; padding:2px 8px; font-size:12px; margin-bottom:10px; }
"""

# NOTE: this JS uses only single-quoted strings (so .format() is safe) and no
# literal `{...}` except the intended placeholders. It runs in the browser over
# the inlined DATA array (group -> subcategories -> blocks).
JS = """
const DATA = __DATA__;
const groupList = document.getElementById('group-list');
const subList = document.getElementById('sub-list');
const blkList = document.getElementById('block-list');
const maxClause = Math.max(1, ...DATA.map(g => g.clause_total));

// --- Level 1: groups ---------------------------------------------------------
DATA.forEach((g, i) => {
  const row = document.createElement('div');
  row.className = 'row';
  row.innerHTML =
    '<span class="name">' + g.group_label + '</span>' +
    '<span class="bar-track"><span class="bar-fill" style="width:' + (g.clause_total / maxClause * 100) + '%"></span></span>' +
    '<span class="meta">' + g.block_count + ' blk · ' + g.clause_total.toLocaleString() + ' cl</span>';
  row.onclick = () => {
    groupList.querySelectorAll('.row').forEach(r => r.classList.remove('active'));
    row.classList.add('active');
    renderSubs(g);
    renderBlocks(null);
  };
  groupList.appendChild(row);
});

// --- Level 2: subcategories within a group -----------------------------------
function renderSubs(g) {
  const max = Math.max(1, ...g.subcategories.map(s => s.clause_total));
  subList.innerHTML = '';
  const tag = document.createElement('div');
  tag.className = 'tag';
  tag.textContent = g.group_label + ' · ' + g.block_count + ' blocks · ' + g.clause_total.toLocaleString() + ' clauses';
  subList.appendChild(tag);
  g.subcategories.forEach(s => {
    const row = document.createElement('div');
    row.className = 'row';
    row.innerHTML =
      '<span class="name" title="' + s.label + '">' + s.label + '</span>' +
      '<span class="bar-track"><span class="bar-fill" style="width:' + (s.clause_total / max * 100) + '%"></span></span>' +
      '<span class="meta">' + s.block_count + ' blk · ' + s.clause_total.toLocaleString() + ' cl</span>';
    row.onclick = () => {
      subList.querySelectorAll('.row').forEach(r => r.classList.remove('active'));
      row.classList.add('active');
      renderBlocks(s);
    };
    subList.appendChild(row);
  });
}

// --- Level 3: blocks within a subcategory ------------------------------------
function renderBlocks(s) {
  if (!s) {
    blkList.innerHTML = '<div class="empty">Select a subcategory to inspect its blocks.</div>';
    return;
  }
  const max = Math.max(1, ...s.blocks.map(b => b.size));
  let html = '<span class="tag">' + s.label + ' · ' + s.block_count + ' blocks · ' + s.clause_total.toLocaleString() + ' clauses</span><div>';
  s.blocks.forEach(b => {
    html += '<div class="blk">' +
      '<span class="bid">#' + b.cluster_id + '</span>' +
      '<span class="bname" title="' + b.block_name + '">' + b.block_name + '</span>' +
      '<span class="bar-track"><span class="bar-fill" style="width:' + (b.size / max * 100) + '%"></span></span>' +
      '<span class="bsize">' + b.size.toLocaleString() + '</span>' +
      '</div>';
  });
  html += '</div>';
  blkList.innerHTML = html;
}

// --- Theme toggle -------------------------------------------------------------
const themeBtn = document.getElementById('themeBtn');
function applyTheme(t) {
  if (t === 'light') document.documentElement.dataset.theme = 'light';
  else delete document.documentElement.dataset.theme;
  themeBtn.textContent = t === 'light' ? 'Dark theme' : 'Light theme';
}
let theme = 'dark';
try { theme = localStorage.getItem('theme') || 'dark'; } catch (e) {}
applyTheme(theme);
themeBtn.onclick = () => { theme = theme === 'light' ? 'dark' : 'light'; applyTheme(theme);
                           try { localStorage.setItem('theme', theme); } catch (e) {} };
"""

# The page shell. Only {css}, {js}, {sub_text} are substituted via .format();
# every other brace is inside {css}/{js} which arrive already-formed.
PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Fine taxonomy grouping — negative-cluster blocks</title>
<style>{css}</style>
</head>
<body>
<header>
  <div>
    <h1>Fine taxonomy grouping — negative-cluster blocks</h1>
    <div class="sub">{sub_text}. Drill down group → subcategory → block. Bars scale to the largest value in the shown level.</div>
  </div>
  <button class="themebtn" id="themeBtn" type="button">Light theme</button>
</header>
<div class="wrap">
  <div class="panel" id="groups">
    <h2>Groups (by clause volume)</h2>
    <div id="group-list"></div>
  </div>
  <div class="panel" id="subs">
    <h2>Subcategories</h2>
    <div id="sub-list"><div class="empty">Select a group on the left.</div></div>
  </div>
  <div class="panel" id="blocks">
    <h2>Blocks</h2>
    <div id="block-list"><div class="empty">Select a subcategory to inspect its blocks.</div></div>
  </div>
</div>
<script>
{js}
</script>
</body>
</html>"""


def render_html(groups: list[dict]) -> str:
    """Build the self-contained interactive HTML page (no CDN, stdlib only).

    The three panels are always present; the subcategory and block panels show
    a placeholder until the user clicks through group -> subcategory -> block.
    Labels are HTML-escaped in load_groups() so they are safe to inject.
    """
    total_blocks = sum(g["block_count"] for g in groups)
    total_clauses = sum(g["clause_total"] for g in groups)
    total_subs = sum(len(g["subcategories"]) for g in groups)
    data = json.dumps(groups, ensure_ascii=False)
    js = JS.replace("__DATA__", data)
    sub_text = f"{len(groups)} groups · {total_subs} subcategories · {total_blocks:,} blocks · {total_clauses:,} clauses"
    return PAGE.format(css=CSS, js=js, sub_text=sub_text)


def main() -> None:
    parser = argparse.ArgumentParser(description="Visualize fine taxonomy grouping as interactive HTML")
    parser.add_argument("--input", default=str(INPUT))
    parser.add_argument("--output", default=str(OUTPUT_HTML))
    args = parser.parse_args()

    in_path = Path(args.input)
    if not in_path.exists():
        print(f"[error] input not found: {in_path}", file=sys.stderr)
        sys.exit(1)

    groups = load_groups(in_path)
    if not groups:
        print("[error] no groups loaded", file=sys.stderr)
        sys.exit(1)

    print_summary(groups)

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(render_html(groups), encoding="utf-8")
    print(f"\nWrote interactive page -> {out_path}")


if __name__ == "__main__":
    main()
