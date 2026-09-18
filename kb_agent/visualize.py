"""Validate the negative-clustering and visualize it as an interactive HTML scatter.

Loads the embedded clauses, runs the same clustering as `kb_agent.cluster`,
prints a validation report (block count, size distribution, near-duplicate
centroids, cohesion vs separation), then projects the 384-d embeddings to 2D
with UMAP and writes a self-contained HTML scatter (inline SVG + vanilla JS,
no plotly/CDN — the only extra dep is umap-learn).

Usage:
    python -m kb_agent.visualize                 # report + output/negative_clusters.html
    python -m kb_agent.visualize --report-only   # skip the UMAP projection + HTML
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np

from .cluster import DISTANCE_THRESHOLD, ROOT, _load, build_clusters

OUTPUT_HTML = ROOT / "output" / "negative_clusters.html"


def validate(texts, places, vecs, clusters) -> None:
    print(f"\n=== Cluster validation (threshold={DISTANCE_THRESHOLD}) ===")

    # 1. Block count + size distribution.
    sizes = sorted((len(c) for c in clusters), reverse=True)
    by_size = Counter(sizes)
    print(f"1) {len(clusters)} blocks, {sum(sizes)} clauses kept "
          f"({sum(sizes)}/{len(texts)} = {sum(sizes) / len(texts):.0%})")
    print("   size histogram:", {k: by_size[k] for k in sorted(by_size)})
    print(f"   top-5 sizes: {sizes[:5]}")

    # 2. Near-duplicate centroids: two clusters whose centroids are very close
    #    suggest the threshold split one topic (or two topics overlap heavily).
    centroids = np.stack([vecs[ids].mean(axis=0) for ids in clusters])
    centroids = centroids / np.linalg.norm(centroids, axis=1, keepdims=True)
    sim = centroids @ centroids.T
    np.fill_diagonal(sim, 0)
    near = np.argwhere(sim > 0.90)
    pairs = sorted({(min(i, j), max(i, j)) for i, j in near})
    print(f"2) centroid near-duplicates (cos sim > 0.90): {len(pairs)} pairs")
    for i, j in pairs[:10]:
        print(f"   block {i + 1} (n={len(clusters[i])}) ~ block {j + 1} (n={len(clusters[j])}) "
              f"sim={sim[i, j]:.3f}")

    # 3. Cohesion (mean intra-cluster sim) vs separation (mean nearest-other-centroid sim).
    intra = []
    for ids in clusters:
        m = vecs[ids] @ vecs[ids].T
        intra.append(m[~np.eye(len(ids), dtype=bool)].mean())
    intra = np.array(intra)
    # separation: for each centroid, sim to the nearest *other* centroid
    sep = np.array([sim[i].max() for i in range(len(clusters))])
    print(f"3) mean intra-cluster sim: {intra.mean():.3f}  (min {intra.min():.3f}, max {intra.max():.3f})")
    print(f"   mean nearest-centroid sim (separation): {sep.mean():.3f}  (higher = less separated)")
    print(f"   gap (intra - nearest-centroid): {intra.mean() - sep.mean():+.3f}")

    # 4. Outlier drop rate.
    kept = sum(sizes)
    print(f"4) dropped as singletons/small: {len(texts) - kept} clauses ({(len(texts) - kept) / len(texts):.0%})")


def project_and_render(texts, places, vecs, clusters, out_path: Path) -> None:
    from umap import UMAP  # heavy import, only needed here

    print(f"\nUMAP-projecting {len(texts)} x {vecs.shape[1]} embeddings -> 2D ...")
    reducer = UMAP(n_components=2, metric="cosine", random_state=42)
    coords = reducer.fit_transform(vecs)

    # Color by cluster; unassigned clauses get their own neutral color.
    label_of = np.full(len(texts), 0, dtype=int)
    for cid, ids in enumerate(clusters, 1):
        label_of[ids] = cid
    n_clusters = int(label_of.max())
    labels = label_of  # 0 = "unassigned"

    html = _render_svg(coords, labels, texts, places, n_clusters)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    print(f"Wrote interactive scatter -> {out_path}")


def _color_for(cid: int) -> str:
    import hashlib
    if cid == 0:
        return "#888"
    hue = int(hashlib.md5(str(cid).encode()).hexdigest()[:6], 16) % 360
    return f"hsl({hue},70%,55%)"


def _render_svg(coords, labels, texts, places, n_clusters) -> str:
    """Self-contained HTML: inline SVG scatter + vanilla-JS hover tooltip. No CDN, no pip deps."""
    W, H, PAD = 1200, 800, 40
    x0, x1 = coords[:, 0].min(), coords[:, 0].max()
    y0, y1 = coords[:, 1].min(), coords[:, 1].max()
    sx = lambda v: PAD + (v - x0) / (x1 - x0) * (W - 2 * PAD)
    sy = lambda v: H - PAD - (v - y0) / (y1 - y0) * (H - 2 * PAD)

    # Cap huge blocks so the SVG stays a reasonable size; keep unassigned visible.
    dots = []
    for cid in range(0, n_clusters + 1):
        idxs = np.where(labels == cid)[0]
        if len(idxs) > 300:  # subsample the big ones
            idxs = idxs[np.linspace(0, len(idxs) - 1, 300).astype(int)]
        color = _color_for(cid)
        for i in idxs:
            dots.append((sx(coords[i, 0]), sy(coords[i, 1]), color, cid, i))

    pts_svg = "\n".join(
        f'<circle cx="{x:.1f}" cy="{y:.1f}" r="2.2" fill="{c}" opacity="0.75" '
        f'data-cid="{cid}" data-i="{i}"/>'
        for x, y, c, cid, i in dots
    )

    # Tooltip payload as a JS map (index -> "place || text").
    tip_entries = ",".join(
        f'{i}:{json.dumps(places[i] + " || " + texts[i][:200], ensure_ascii=False)}'
        for _, _, _, _, i in dots
    )
    legend = "".join(
        f'<span style="margin-right:10px"><i style="display:inline-block;width:10px;height:10px;'
        f'background:{_color_for(c)};border-radius:2px"></i> block {c} (n={int((labels == c).sum())})</span>'
        for c in sorted(set(labels[labels > 0]))
    )

    return f"""<!doctype html>
<html><head><meta charset="utf-8">
<title>Negative-clause clusters (UMAP)</title>
<style>
  body{{font-family:system-ui,sans-serif;margin:16px;background:#fafafa}}
  #tip{{position:absolute;pointer-events:none;background:#222;color:#fff;padding:6px 8px;
       border-radius:4px;font-size:12px;max-width:340px;display:none;z-index:10;white-space:pre-wrap}}
  i{{border-radius:2px}}
  h2{{font-size:16px}} .legend{{font-size:12px;color:#444;margin:8px 0}}
</style></head>
<body>
<h2>Negative-clause clusters — UMAP (cosine), {n_clusters} blocks, {int((labels > 0).sum())} kept clauses</h2>
<div class="legend"><span style="margin-right:10px"><i style="background:#888"></i> unassigned ({int((labels == 0).sum())})</span>{legend}</div>
<div style="position:relative">
<svg width="{W}" height="{H}" style="background:#fff;border:1px solid #ddd">
<g>{pts_svg}</g>
</svg>
<div id="tip"></div>
</div>
<script>
const TIPS = {{ {tip_entries} }};
const tip = document.getElementById('tip');
document.querySelectorAll('circle').forEach(el => {{
  el.addEventListener('mousemove', e => {{
    const t = TIPS[el.dataset.i]; if (!t) return;
    tip.textContent = t; tip.style.display = 'block';
    tip.style.left = (e.pageX + 12) + 'px'; tip.style.top = (e.pageY + 12) + 'px';
  }});
  el.addEventListener('mouseleave', () => tip.style.display = 'none');
}});
</script>
</body></html>"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate + visualize negative-clause clustering")
    parser.add_argument("--input", default=str(ROOT / "embed" / "negative_clusters.jsonl"))
    parser.add_argument("--output", default=str(OUTPUT_HTML))
    parser.add_argument("--report-only", action="store_true", help="Skip UMAP projection + HTML")
    args = parser.parse_args()

    in_path = Path(args.input)
    if not in_path.exists():
        print(f"[error] input not found: {in_path}", file=sys.stderr)
        sys.exit(1)

    texts, places, vecs = _load(in_path)
    print(f"Loaded {len(texts)} clauses from {in_path.name}")
    clusters = build_clusters(texts, places, vecs)
    print(f"Formed {len(clusters)} blocks")

    validate(texts, places, vecs, clusters)
    if not args.report_only:
        project_and_render(texts, places, vecs, clusters, Path(args.output))


if __name__ == "__main__":
    main()
