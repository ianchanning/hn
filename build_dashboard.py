"""Compile zero-hash Nyx swiss-grid / cyber-industrial HTML Observatory for any HN post."""

from collections import Counter
import copy
import html
import json
import math
from pathlib import Path
import subprocess
import sys
from typing import Any
from urllib.parse import urlparse

HERE = Path(__file__).resolve().parent
JUDGE_SCRIPT = HERE / "judge" / "judge_v1_1.py"
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import corpus_science
from ingest import parse_hn_item_id
import ranker

LEGACY_FACET_LABELS: dict[str, str] = {
    "governance_fiduciary": "Governance & Fiduciary",
    "intelligence_megaspeed": "Intelligence & Megaspeed",
    "export_controls_supply": "Export Controls & Supply",
    "technical_moat": "CUDA & Technical Moat",
    "market_financials": "Market & Financials",
    "general_commentary": "General Commentary",
}


def _safe_html_no_hash(text: str) -> str:
    """Escape HTML special characters and guarantee zero literal `#` characters."""
    return html.escape(str(text), quote=True).replace("#", "No. ")


def _safe_url_no_hash(url: str) -> str:
    """Strip `#fragment` from a static HTML href attribute and escape safely."""
    clean = str(url or "").split("#", 1)[0].strip()
    return html.escape(clean, quote=True)


def _compute_top20_diversity(top20: list[dict[str, Any]]) -> float:
    """Compute unsupervised submodular Top-20 portfolio diversity in [0, 1]."""
    if not top20:
        return 0.0
    facet_counts = Counter(c.get("facet", "general_commentary") for c in top20)
    n = float(len(top20))
    entropy = -sum((cnt / n) * math.log2(cnt / n) for cnt in facet_counts.values())
    norm_entropy = min(1.0, entropy / math.log2(5.0))

    vecs = [{str(k): float(v) for k, v in (c.get("tfidf_top") or [])} for c in top20]
    sim_sum = 0.0
    pairs = 0
    for i in range(len(vecs)):
        for j in range(i + 1, len(vecs)):
            sim = sum(w * vecs[j].get(t, 0.0) for t, w in vecs[i].items())
            sim_sum += min(1.0, sim)
            pairs += 1
    mean_sim = (sim_sum / pairs) if pairs > 0 else 0.0
    unique_roots = len({c.get("root_id") or c["id"] for c in top20}) / n
    return round(
        0.45 * norm_entropy
        + 0.35 * (1.0 - mean_sim)
        + 0.20 * min(1.0, unique_roots / 0.75),
        4,
    )


def _compute_largest_root(comments: list[dict[str, Any]]) -> dict[str, Any]:
    """Identify the single root subtree occupying the largest share of Live HN DOM slots."""
    live = [c for c in comments if c.get("live_dom_rank") is not None]
    if not live:
        return {
            "root_id": 0,
            "author": "none",
            "slots": 0,
            "start_dom": 1,
            "end_dom": 1,
            "share_pct": 0.0,
            "top_dom1_age": 0.0,
            "top_dom1_author": "none",
        }
    by_id = {c["id"]: c for c in comments}
    by_root: dict[int, list[int]] = {}
    for c in live:
        rid = int(c.get("root_id") or c["id"])
        by_root.setdefault(rid, []).append(int(c["live_dom_rank"]))

    best_rid, doms = max(by_root.items(), key=lambda kv: (len(kv[1]), -min(kv[1])))
    root_row = by_id.get(best_rid, {})
    dom1 = min(live, key=lambda c: int(c["live_dom_rank"]))
    return {
        "root_id": best_rid,
        "author": str(root_row.get("author") or "root"),
        "slots": len(doms),
        "start_dom": min(doms),
        "end_dom": max(doms),
        "share_pct": round(100.0 * len(doms) / max(1, len(live)), 1),
        "top_dom1_age": round(float(dom1.get("age_hours") or 1.0), 1),
        "top_dom1_author": str(dom1.get("author") or "top"),
    }


def build_html(
    target: str | int = 50467087,
    *,
    corpus: list[dict[str, Any]] | None = None,
    manifest: dict[str, Any] | None = None,
    ranked_comments: list[dict[str, Any]] | None = None,
    out_path: Path | None = None,
    data_dir: Path | None = None,
    offline: bool = False,
) -> Path:
    """Generate `show-me-hn-<story_id>.html` and assert strict zero-hash compliance."""
    story_id = parse_hn_item_id(target)
    resolved_data_dir = Path(data_dir) if data_dir is not None else (HERE / "data")

    use_frozen_50467087 = (
        story_id == 50467087
        and corpus is None
        and manifest is None
        and (resolved_data_dir / "corpus_v2.json").is_file()
        and (resolved_data_dir / "manifest_v2.json").is_file()
        and JUDGE_SCRIPT.is_file()
        and (HERE / "ablation.py").is_file()
    )

    judge_res: dict[str, Any] | None = None
    ablations: list[dict[str, Any]] = []
    tourney_history: list[dict[str, Any]] = []

    if use_frozen_50467087:
        import ablation

        corpus = json.loads(
            (resolved_data_dir / "corpus_v2.json").read_text(encoding="utf-8")
        )
        manifest = json.loads(
            (resolved_data_dir / "manifest_v2.json").read_text(encoding="utf-8")
        )
        ablations = ablation.run_ablations()
        judge_proc = subprocess.run(
            [sys.executable, str(JUDGE_SCRIPT), str(HERE)],
            capture_output=True,
            text=True,
            check=True,
        )
        judge_res = json.loads(judge_proc.stdout)
        tourney_path = resolved_data_dir / "tournament_history.json"
        if tourney_path.is_file():
            tourney_history = json.loads(tourney_path.read_text(encoding="utf-8"))
    elif corpus is None or manifest is None:
        item_corpus_path = resolved_data_dir / "items" / str(story_id) / "corpus.json"
        item_manifest_path = (
            resolved_data_dir / "items" / str(story_id) / "manifest.json"
        )
        if item_corpus_path.is_file() and item_manifest_path.is_file():
            corpus = json.loads(item_corpus_path.read_text(encoding="utf-8"))
            manifest = json.loads(item_manifest_path.read_text(encoding="utf-8"))
        else:
            corpus, manifest = corpus_science.build_story_corpus(
                story_id,
                data_dir=resolved_data_dir,
                offline=offline,
                write_output=True,
            )

    assert corpus is not None and manifest is not None
    ranked = (
        ranked_comments
        if ranked_comments is not None
        else ranker.rank_comments(copy.deepcopy(corpus))
    )

    story_title = str(
        manifest.get("story_title")
        or ("Jensen Huang resigns" if story_id == 50467087 else f"HN Item {story_id}")
    )
    story_url = str(manifest.get("story_url") or "")
    story_host = (
        urlparse(story_url).netloc.lower().removeprefix("www.")
        if story_url
        else "news.ycombinator.com"
    )
    counts = manifest.get("counts") or {}
    authors_profiled = int(counts.get("unique_authors_profiled") or 0)
    pages_fetched = int(counts.get("pages_fetched") or 1)
    delta_min = float(manifest.get("delta_minutes") or 0.0)

    tiers = Counter(c["tier"] for c in ranked)
    facets = Counter(c["facet"] for c in ranked)
    raw_facet_labels = dict(LEGACY_FACET_LABELS)
    raw_facet_labels.update(manifest.get("facet_labels") or {})

    # Build ordered facet dropdown metadata
    facet_options: list[dict[str, Any]] = []
    non_general_facets = [
        (slug, cnt)
        for slug, cnt in facets.most_common()
        if slug != "general_commentary" and cnt > 0
    ]
    for slug, cnt in non_general_facets:
        label = raw_facet_labels.get(slug) or slug.replace("_", " ").title()
        facet_options.append({"slug": slug, "label": label, "count": cnt})
    if facets.get("general_commentary", 0) > 0 or not facet_options:
        facet_options.append(
            {
                "slug": "general_commentary",
                "label": raw_facet_labels.get(
                    "general_commentary", "General Commentary"
                ),
                "count": facets.get("general_commentary", 0),
            }
        )

    total_cnt = len(ranked)
    live_cnt = sum(1 for c in ranked if c.get("live_dom_rank") is not None) or max(
        1, total_cnt
    )
    buried_cutoff = (
        min(500, max(25, int(round(0.30 * live_cnt)))) if live_cnt < 1600 else 500
    )
    rescue_top_k = (
        min(80, max(20, int(round(0.20 * live_cnt)))) if live_cnt < 1600 else 80
    )

    largest_root = _compute_largest_root(ranked)
    top20_div = _compute_top20_diversity(ranked[:20])
    primary_sourced_cnt = sum(1 for c in ranked if int(c.get("url_tier", 0)) >= 2)
    top30_slice = ranked[: min(30, max(1, total_cnt))]
    top30_sourced_pct = (
        100.0
        * sum(1 for c in top30slice if int(c.get("url_tier", 0)) >= 2)
        / max(1, len(top30_slice))
        if (top30slice := top30_slice)
        else 0.0
    )

    # Source registry breakdown for live diagnostics drawer
    cat_counts: Counter[str] = Counter()
    for c in ranked:
        for cat in c.get("url_categories") or []:
            cat_counts[str(cat)] += 1
    if not cat_counts:
        for c in ranked:
            ut = int(c.get("url_tier", 0))
            if ut >= 3:
                cat_counts["tier3_primary"] += 1
            elif ut == 2:
                cat_counts["tier2_investigative"] += 1
            elif ut == -1:
                cat_counts["low_cred_or_joke"] += 1
            elif ut == 1:
                cat_counts["general_web"] += 1

    facet_diagnostics: list[dict[str, Any]] = []
    cluster_terms_map = {
        str(cl.get("slug")): list(cl.get("top_terms") or [])
        for cl in (manifest.get("facet_clusters") or [])
    }
    for opt in facet_options:
        f_slug = opt["slug"]
        f_rows = [c for c in ranked if c.get("facet") == f_slug]
        f_useful = sum(
            1 for c in f_rows if c["tier"] in ("epistemic_gold", "grounded_analysis")
        )
        top_t = cluster_terms_map.get(f_slug) or f_slug.split("_")
        facet_diagnostics.append(
            {
                "slug": f_slug,
                "label": opt["label"],
                "count": len(f_rows),
                "useful": f_useful,
                "useful_pct": round(100.0 * f_useful / max(1, len(f_rows)), 1),
                "terms": ", ".join(top_t[:4]),
            }
        )

    anchors = list(manifest.get("story_anchors") or [])
    hint_terms = anchors[:5] if anchors else ["evidence", "benchmark", "source"]
    search_placeholder = f"Search text, @author, {', '.join(hint_terms)}..."

    compact_comments: list[dict[str, Any]] = []
    w = ranker.DEFAULT_WEIGHTS
    for c in ranked:
        comp = c["components"]
        compact_comments.append(
            {
                "id": c["id"],
                "au": c["author"],
                "dom": c["live_dom_rank"] or max(1, total_cnt),
                "sr": c["signal_rank"],
                "sc": round(c["signal_score"], 2),
                "ep": round(c["epistemic_score"], 2),
                "bs": round(c["bullshit_score"], 2),
                "d": c["depth"],
                "age": round(c["age_hours"], 2),
                "grav": round(c["gravity_denom"], 1),
                "surf": round(c["surf_mirage_index"], 1),
                "fade": c["fade_class"],
                "dt": c["downvote_tier"],
                "ut": c["url_tier"],
                "lu": c["low_cred_url_count"],
                "w": c["own_word_count"],
                "qw": c["quoted_word_count"],
                "k": c["author_karma"],
                "kpp": round(c["author_kpp"], 1),
                "td": round(c["temporal_pct_delta"], 3),
                "mod": 1 if c["is_mod_rebuked"] else 0,
                "pp": c["ping_pong_depth"],
                "meme": c["meme_hits"],
                "tier": c["tier"],
                "facet": c["facet"],
                "flbl": raw_facet_labels.get(c["facet"])
                or c["facet"].replace("_", " "),
                "urls": [u for u in c["urls"] if not u.startswith("item?id=")][:3],
                "ig": round(comp["info_gain"] / max(0.01, w["info_gain"]), 3),
                "fa": round(comp["falsifiability"] / max(0.01, w["falsifiability"]), 3),
                "gp": round(
                    comp["gravity_progeny"] / max(0.01, w["gravity_progeny"]), 3
                ),
                "bl": round(
                    -comp["bullshit_load"] / max(0.01, w["bullshit_penalty"]), 3
                ),
                "ds": round(
                    -comp["downvote_sink"] / max(0.01, w["downvote_penalty"]), 3
                ),
                "txt": c["text"][:1400],
            }
        )

    payload = {
        "story_id": story_id,
        "story_title": story_title,
        "story_url": story_url,
        "is_benchmark": bool(judge_res is not None),
        "manifest": manifest,
        "judge": judge_res,
        "weights": ranker.DEFAULT_WEIGHTS,
        "tiers": dict(tiers),
        "facets": dict(facets),
        "facet_options": facet_options,
        "facet_diagnostics": facet_diagnostics,
        "source_categories": [
            {"category": k, "count": v} for k, v in cat_counts.most_common()
        ],
        "story_anchors": anchors[:18],
        "largest_root": largest_root,
        "buried_cutoff": buried_cutoff,
        "rescue_top_k": rescue_top_k,
        "ablations": ablations,
        "tournament": tourney_history,
        "comments": compact_comments,
    }

    json_blob = (
        json.dumps(payload, ensure_ascii=False)
        .replace("</", "<\\/")
        .replace("#", "\\u0023")
    )

    useful_cnt = tiers.get("epistemic_gold", 0) + tiers.get("grounded_analysis", 0)
    useful_pct = 100.0 * useful_cnt / max(1, total_cnt)
    gold_pct = 100.0 * tiers.get("epistemic_gold", 0) / max(1, total_cnt)
    noise_pct = 100.0 - useful_pct

    safe_title = _safe_html_no_hash(story_title)
    safe_host = _safe_html_no_hash(story_host)
    safe_placeholder = _safe_html_no_hash(search_placeholder)
    hn_item_href = f"https://news.ycombinator.com/item?id={story_id}"
    story_link_html = (
        f'<a class="ext-link" href="{_safe_url_no_hash(story_url)}" target="_blank" rel="noopener">{safe_title} ({safe_host})</a>'
        if story_url
        else f'<a class="ext-link" href="{hn_item_href}" target="_blank" rel="noopener">{safe_title}</a>'
    )

    if judge_res is not None:
        eyebrow_right = (
            f"<span><strong>JUDGE v{_safe_html_no_hash(judge_res['judge_version'])}: "
            f"{judge_res['score']:.2f} / 100</strong> "
            f"(LIVE HN: {judge_res['hn_live_baseline_score']:.2f})</span>"
        )
        snap_sub = (
            f"t1 + t2 (+{delta_min}m) &bull; {authors_profiled:,} authors"
            if delta_min > 0
            else f"{pages_fetched} page(s) &bull; {authors_profiled:,} authors"
        )
        kpi_4_5_html = f"""
      <div class="kpi-cell">
        <div class="kpi-label">External Judge Score</div>
        <div class="kpi-val ok">{judge_res["score"]:.2f}</div>
        <div class="kpi-sub">vs Live HN {judge_res["hn_live_baseline_score"]:.2f} (+{judge_res["delta_vs_hn"]:.2f} pts)</div>
      </div>
      <div class="kpi-cell">
        <div class="kpi-label">Holdout Generalization</div>
        <div class="kpi-val">{judge_res["holdout_score"]:.2f}</div>
        <div class="kpi-sub">Dev {judge_res["dev_score"]:.2f} &bull; Adv Traps {100 * judge_res["full_metrics"]["adversarial_acc"]:.1f}%</div>
      </div>"""
        drawer_html = f"""
  <details class="proof-drawer" id="proofDrawer">
    <summary>
      <span>01 // SCIENTIFIC JUSTIFICATION: 01A ABLATION MATRIX &amp; 01B FORGET-TEAM TOURNAMENT LEDGER (CHAMPION {judge_res["score"]:.2f} VS LIVE HN {judge_res["hn_live_baseline_score"]:.2f} &bull; HOLDOUT {judge_res["holdout_score"]:.2f})</span>
      <span class="toggle-pill" data-show="[+] SHOW" data-hide="[-] HIDE"></span>
    </summary>
    <div class="proof-body grid-12">
      <div class="col-7">
        <div class="sec-tag">01A / CONTROLLED ABLATION MATRIX</div>
        <h2>Marginal Gain of Each Epistemic Pillar</h2>
        <div style="overflow-x:auto">
          <table class="ablation" id="ablationTable">
            <thead>
              <tr>
                <th>Model / Controlled Ablation Stage</th>
                <th>Score</th>
                <th>NDCG@20</th>
                <th>Concord</th>
                <th>Adv Traps</th>
                <th>Rescue</th>
                <th>Sink</th>
                <th>Div</th>
              </tr>
            </thead>
            <tbody id="ablationBody"></tbody>
          </table>
        </div>
      </div>
      <div class="col-5">
        <div class="sec-tag">01B / FORGET-TEAM 4-AGENT HERDR TOURNAMENT</div>
        <h2>Amnesia Reset &amp; Holdout Generalization</h2>
        <div style="overflow-x:auto; max-height: 365px; overflow-y: auto;">
          <table class="ablation" id="tourneyTable">
            <thead>
              <tr>
                <th>Stage / Worker</th>
                <th>SHA</th>
                <th>Full</th>
                <th>Dev</th>
                <th>Holdout</th>
              </tr>
            </thead>
            <tbody id="tourneyBody"></tbody>
          </table>
        </div>
      </div>
    </div>
  </details>"""
    else:
        eyebrow_right = (
            f"<span><strong>TOP-20 DIVERSITY: {top20_div:.3f}</strong> "
            f"&bull; {primary_sourced_cnt} PRIMARY-SOURCED COMMENTS</span>"
        )
        snap_sub = f"{pages_fetched} HTML page(s) &bull; {authors_profiled:,} cached/live authors"
        kpi_4_5_html = f"""
      <div class="kpi-cell">
        <div class="kpi-label">Primary Citations</div>
        <div class="kpi-val ok">{primary_sourced_cnt}</div>
        <div class="kpi-sub">{top30_sourced_pct:.0f}% of Epistemic Top 30 cite Tier 2/3</div>
      </div>
      <div class="kpi-cell">
        <div class="kpi-label">Portfolio Diversity</div>
        <div class="kpi-val">{top20_div:.3f}</div>
        <div class="kpi-sub">{len(non_general_facets)} auto-discovered TF-IDF facets</div>
      </div>"""
        drawer_html = f"""
  <details class="proof-drawer" id="proofDrawer">
    <summary>
      <span>01 // UNSUPERVISED CORPUS TELEMETRY: 01A AUTO-LABELED TOPIC CLUSTERS &amp; 01B CROSS-DOMAIN SOURCE REGISTRY (DIVERSITY {top20_div:.3f} &bull; {len(anchors)} ANCHORS)</span>
      <span class="toggle-pill" data-show="[+] SHOW" data-hide="[-] HIDE"></span>
    </summary>
    <div class="proof-body grid-12">
      <div class="col-7">
        <div class="sec-tag">01A / UNSUPERVISED 5-CLUSTER FACETS (SPHERICAL K-MEANS++)</div>
        <h2>Auto-Discovered Sub-Themes &amp; Signal Yield</h2>
        <div style="overflow-x:auto">
          <table class="ablation" id="facetDiagTable">
            <thead>
              <tr>
                <th>Discovered Facet Cluster</th>
                <th>Comments</th>
                <th>Useful Signal</th>
                <th>Signal %</th>
                <th>Centroid Salient Terms</th>
              </tr>
            </thead>
            <tbody id="facetDiagBody"></tbody>
          </table>
        </div>
      </div>
      <div class="col-5">
        <div class="sec-tag">01B / SOURCE REGISTRY &amp; STORY ANCHORS</div>
        <h2>Cross-Domain Citations &amp; TF-IDF Anchors</h2>
        <div style="overflow-x:auto; max-height: 365px; overflow-y: auto;">
          <table class="ablation" id="sourceCatTable">
            <thead>
              <tr>
                <th>Source Registry Category</th>
                <th>Cited Comments</th>
              </tr>
            </thead>
            <tbody id="sourceCatBody"></tbody>
          </table>
          <div id="anchorListBox" style="margin-top:10px;font:600 11px/1.5 ui-monospace,Menlo,monospace;color:rgb(70,70,68)"></div>
        </div>
      </div>
    </div>
  </details>"""

    facet_select_html = "\n          ".join(
        [f'<option value="all">All Facets ({total_cnt:,})</option>']
        + [
            f'<option value="{_safe_html_no_hash(opt["slug"])}">'
            f"{_safe_html_no_hash(opt['label'])} ({opt['count']})</option>"
            for opt in facet_options
        ]
    )

    html_doc = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>HN {story_id} // {safe_title} — Epistemic Observatory</title>
  <style>
    * {{ box-sizing: border-box; }}
    html {{
      scrollbar-gutter: stable;
      overflow-anchor: none;
    }}
    @supports (interpolate-size: allow-keywords) {{
      :root {{ interpolate-size: allow-keywords; }}
    }}
    body {{
      margin: 0;
      background: rgb(247, 247, 245);
      color: rgb(13, 13, 13);
      font: 15px/1.5 "Helvetica Neue", Helvetica, Arial, sans-serif;
      -webkit-font-smoothing: antialiased;
    }}
    .wrap {{
      max-width: 1420px;
      margin: 0 auto;
      padding: 28px 28px 64px;
    }}
    .sheet-top {{
      border-top: 3px solid rgb(13, 13, 13);
      border-bottom: 1px solid rgb(13, 13, 13);
      padding: 16px 0 26px;
    }}
    .eyebrow {{
      font: 600 11px/1.4 ui-monospace, SFMono-Regular, Menlo, monospace;
      letter-spacing: 0.14em;
      text-transform: uppercase;
      color: rgb(90, 90, 88);
      display: flex;
      justify-content: space-between;
      flex-wrap: wrap;
      gap: 8px;
    }}
    .eyebrow strong {{ color: rgb(255, 51, 0); }}
    h1 {{
      font-size: clamp(36px, 5.2vw, 72px);
      line-height: 0.96;
      letter-spacing: -0.045em;
      margin: 18px 0 14px;
      font-weight: 800;
    }}
    h1 .accent {{ color: rgb(255, 51, 0); }}
    .sublead {{
      max-width: 920px;
      font-size: 16px;
      color: rgb(52, 52, 50);
      margin: 0;
    }}
    .grid-12 {{
      display: grid;
      grid-template-columns: repeat(12, minmax(0, 1fr));
      gap: 18px;
    }}
    .col-1 {{ grid-column: span 1; min-width: 0; }}
    .col-2 {{ grid-column: span 2; min-width: 0; }}
    .col-3 {{ grid-column: span 3; min-width: 0; }}
    .col-4 {{ grid-column: span 4; min-width: 0; }}
    .col-5 {{ grid-column: span 5; min-width: 0; }}
    .col-6 {{ grid-column: span 6; min-width: 0; }}
    .col-7 {{ grid-column: span 7; min-width: 0; }}
    .col-8 {{ grid-column: span 8; min-width: 0; }}
    .col-9 {{ grid-column: span 9; min-width: 0; }}
    .col-10 {{ grid-column: span 10; min-width: 0; }}
    .col-11 {{ grid-column: span 11; min-width: 0; }}
    .col-12 {{ grid-column: span 12; min-width: 0; }}

    .band {{
      border-bottom: 1px solid rgb(195, 195, 190);
      padding: 24px 0;
    }}
    .sec-tag {{
      font: 700 11px/1.2 ui-monospace, SFMono-Regular, Menlo, monospace;
      letter-spacing: 0.12em;
      text-transform: uppercase;
      color: rgb(255, 51, 0);
      margin-bottom: 6px;
    }}
    h2 {{
      font-size: 24px;
      letter-spacing: -0.03em;
      line-height: 1.12;
      margin: 0 0 10px;
    }}
    .kpi-strip {{
      display: grid;
      grid-template-columns: repeat(6, minmax(0, 1fr));
      border: 1px solid rgb(13, 13, 13);
      background: rgb(255, 255, 253);
    }}
    .kpi-cell {{
      padding: 16px 16px 14px;
      border-right: 1px solid rgb(205, 205, 200);
    }}
    .kpi-cell:last-child {{ border-right: 0; }}
    .kpi-label {{
      font: 600 10px/1.3 ui-monospace, SFMono-Regular, Menlo, monospace;
      letter-spacing: 0.1em;
      text-transform: uppercase;
      color: rgb(90, 90, 88);
    }}
    .kpi-val {{
      font-size: 34px;
      font-weight: 800;
      letter-spacing: -0.04em;
      line-height: 1.05;
      margin: 8px 0 4px;
    }}
    .kpi-val.hi {{ color: rgb(255, 51, 0); }}
    .kpi-val.ok {{ color: rgb(0, 138, 75); }}
    .kpi-sub {{
      font-size: 12px;
      color: rgb(90, 90, 88);
    }}

    /* Cyber-Industrial Recessed OLED Bays (Locked Equal-Height & Zero-Jitter) */
    .oled-bay {{
      background: rgb(13, 15, 17);
      color: rgb(228, 232, 236);
      border: 2px solid rgb(35, 38, 42);
      padding: 16px;
      position: relative;
      border-radius: 6px;
      corner-shape: bevel;
      display: flex;
      flex-direction: column;
      flex: 1;
      min-width: 0;
      overflow: hidden;
    }}
    .oled-head {{
      display: flex;
      justify-content: space-between;
      align-items: baseline;
      gap: 10px;
      height: 16px;
      min-width: 0;
      overflow: hidden;
      white-space: nowrap;
      margin-bottom: 10px;
      font: 600 11px/16px ui-monospace, SFMono-Regular, Menlo, monospace;
      color: rgb(156, 166, 176);
      text-transform: uppercase;
      letter-spacing: 0.08em;
    }}
    .oled-head > span:first-child {{
      min-width: 0;
      overflow: hidden;
      text-overflow: ellipsis;
    }}
    .oled-head span.sig {{ color: rgb(0, 230, 118); flex-shrink: 0; }}
    canvas.plot {{
      width: 100%;
      max-width: 100%;
      min-width: 0;
      height: 300px;
      display: block;
      background: rgb(9, 11, 13);
      border: 1px solid rgb(42, 47, 54);
      cursor: crosshair;
      flex-shrink: 0;
    }}
    .legend-row {{
      display: flex;
      flex-wrap: wrap;
      align-content: flex-start;
      gap: 4px 12px;
      height: 34px;
      overflow: hidden;
      margin-top: 10px;
      font: 500 11px/15px ui-monospace, SFMono-Regular, Menlo, monospace;
      color: rgb(180, 188, 196);
    }}
    .dot {{
      display: inline-block;
      width: 9px;
      height: 9px;
      border-radius: 50%;
      margin-right: 5px;
      vertical-align: -1px;
    }}
    .probe-box {{
      margin-top: 10px;
      padding: 10px 12px;
      height: 58px;
      background: rgb(20, 24, 28);
      border-left: 3px solid rgb(0, 230, 118);
      font: 12px/19px ui-monospace, SFMono-Regular, Menlo, monospace;
      color: rgb(220, 226, 232);
      overflow: hidden;
    }}
    .probe-clamp {{
      display: -webkit-box;
      -webkit-line-clamp: 2;
      -webkit-box-orient: vertical;
      overflow: hidden;
      max-height: 38px;
    }}

    /* Collapsible 03A / 03B Justification Drawer */
    details.proof-drawer {{
      border-bottom: 1px solid rgb(195, 195, 190);
      padding: 12px 0;
    }}
    details.proof-drawer > summary {{
      list-style: none;
      cursor: pointer;
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 12px;
      padding: 10px 14px;
      background: rgb(239, 239, 234);
      border: 1px solid rgb(13, 13, 13);
      font: 700 11px/1.3 ui-monospace, SFMono-Regular, Menlo, monospace;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      user-select: none;
    }}
    details.proof-drawer > summary::-webkit-details-marker {{ display: none; }}
    details.proof-drawer > summary:hover {{ border-color: rgb(255, 51, 0); }}
    details.proof-drawer > summary .toggle-pill {{
      flex-shrink: 0;
      padding: 3px 8px;
      background: rgb(13, 13, 13);
      color: rgb(247, 247, 245);
      font-size: 10px;
    }}
    details.proof-drawer[open] > summary .toggle-pill::before {{ content: attr(data-hide); }}
    details.proof-drawer:not([open]) > summary .toggle-pill::before {{ content: attr(data-show); }}
    .proof-body {{
      padding-top: 16px;
    }}

    /* Scientific Ablation Table */
    table.ablation {{
      width: 100%;
      border-collapse: collapse;
      font-size: 13px;
      background: rgb(255, 255, 253);
      border: 1px solid rgb(13, 13, 13);
    }}
    table.ablation th, table.ablation td {{
      padding: 9px 11px;
      border-bottom: 1px solid rgb(214, 214, 208);
      text-align: right;
      font-variant-numeric: tabular-nums;
    }}
    table.ablation th:first-child, table.ablation td:first-child {{
      text-align: left;
      font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
      font-size: 12px;
    }}
    table.ablation th {{
      background: rgb(236, 236, 231);
      font: 700 10px/1.3 ui-monospace, SFMono-Regular, Menlo, monospace;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      color: rgb(60, 60, 58);
    }}
    table.ablation tr.winner {{
      background: rgba(0, 230, 118, 0.11);
      font-weight: 700;
    }}
    table.ablation tr.hn-row {{
      background: rgba(255, 51, 0, 0.08);
    }}

    /* Controls & Explorer */
    .control-panel {{
      background: rgb(239, 239, 234);
      border: 1px solid rgb(13, 13, 13);
      padding: 16px;
    }}
    .slider-row {{
      margin-bottom: 11px;
    }}
    .slider-lbl {{
      display: flex;
      justify-content: space-between;
      font: 600 11px/1.3 ui-monospace, SFMono-Regular, Menlo, monospace;
      margin-bottom: 3px;
    }}
    input[type="range"] {{
      width: 100%;
      accent-color: rgb(255, 51, 0);
    }}
    .btn-bar {{
      display: flex;
      flex-wrap: wrap;
      gap: 7px;
      margin-bottom: 12px;
    }}
    button.tab-btn {{
      appearance: none;
      border: 1px solid rgb(13, 13, 13);
      background: rgb(255, 255, 253);
      color: rgb(13, 13, 13);
      padding: 7px 11px;
      font: 600 11px/1.2 ui-monospace, SFMono-Regular, Menlo, monospace;
      cursor: pointer;
      box-shadow: 0 2px 0 rgb(13, 13, 13);
    }}
    button.tab-btn.active {{
      background: rgb(13, 13, 13);
      color: rgb(247, 247, 245);
    }}
    button.tab-btn:hover {{
      border-color: rgb(255, 51, 0);
    }}
    .filter-bar {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin-bottom: 12px;
      align-items: center;
    }}
    input.search-in, select.sel-in {{
      padding: 8px 11px;
      border: 1px solid rgb(13, 13, 13);
      background: rgb(255, 255, 253);
      font: 600 12.5px/1.3 ui-monospace, SFMono-Regular, Menlo, monospace;
      color: rgb(13, 13, 13);
      min-width: 0;
    }}
    input.search-in {{ flex: 1; min-width: 220px; font-weight: 400; }}
    .probe-inline-btn {{
      appearance: none;
      border: 1px solid rgb(0, 230, 118);
      background: rgba(0, 230, 118, 0.14);
      color: rgb(0, 230, 118);
      padding: 1px 7px;
      margin-left: 6px;
      font: 700 10.5px/1.3 ui-monospace, SFMono-Regular, Menlo, monospace;
      cursor: pointer;
    }}

    /* Comment Cards — Authentic Hacker News Surface & Typography */
    .card-list {{
      display: flex;
      flex-direction: column;
      gap: 10px;
      min-height: 100vh;
      overflow-anchor: none;
    }}
    article.c-card {{
      background: rgb(246, 246, 239);
      border: 1px solid rgb(216, 216, 206);
      border-left: 4px solid rgb(255, 102, 0);
      padding: 11px 15px 10px;
    }}
    article.c-card.tier-epistemic_gold {{ border-left-color: rgb(0, 158, 96); }}
    article.c-card.tier-grounded_analysis {{ border-left-color: rgb(16, 98, 188); }}
    article.c-card.tier-meme_or_snark {{ border-left-color: rgb(230, 145, 0); }}
    article.c-card.tier-bullshit_or_flamewar {{ border-left-color: rgb(255, 51, 0); }}
    article.c-card.tier-downvoted_sink {{ border-left-color: rgb(156, 156, 156); }}

    .hn-comhead {{
      font: 8pt/1.35 Verdana, Geneva, sans-serif;
      color: rgb(130, 130, 130);
      margin-bottom: 5px;
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
      align-items: center;
    }}
    .hn-comhead a {{
      color: rgb(130, 130, 130);
      text-decoration: none;
    }}
    .hn-comhead a:hover {{ text-decoration: underline; }}
    .hn-votearrow {{
      color: rgb(150, 150, 150);
      font-size: 9px;
      margin-right: 1px;
    }}
    .c-meta {{
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
      align-items: center;
      font: 600 10px/1.25 ui-monospace, SFMono-Regular, Menlo, monospace;
      color: rgb(90, 90, 86);
      margin-bottom: 6px;
    }}
    .badge {{
      padding: 2px 6px;
      background: rgb(236, 236, 228);
      border: 1px solid rgb(204, 204, 194);
      color: rgb(35, 35, 35);
    }}
    .badge.rank-sig {{ background: rgb(13, 13, 13); color: rgb(247, 247, 245); border-color: rgb(13, 13, 13); }}
    .badge.rescue {{ background: rgba(0, 180, 100, 0.15); border-color: rgb(0, 140, 80); color: rgb(0, 105, 58); }}
    .badge.drop {{ background: rgba(255, 51, 0, 0.12); border-color: rgb(220, 45, 0); color: rgb(175, 30, 0); }}
    .badge.c5a {{ background: rgba(255, 179, 0, 0.20); border-color: rgb(195, 130, 0); color: rgb(120, 75, 0); }}

    /* Exact news.css Verdana comment font & downvote fade color ramp */
    .c-body {{
      white-space: pre-wrap;
      font: 9.5pt/1.44 Verdana, Geneva, sans-serif;
      color: rgb(0, 0, 0);
      margin: 6px 0 9px;
      max-width: 96ch;
      overflow-wrap: anywhere;
    }}
    .c-body.comm-c00 {{ color: rgb(0, 0, 0); }}
    .c-body.comm-c5a {{ color: rgb(90, 90, 90); }}
    .c-body.comm-c73 {{ color: rgb(115, 115, 115); }}
    .c-body.comm-c88 {{ color: rgb(136, 136, 136); }}
    .c-body.comm-c9c {{ color: rgb(156, 156, 156); }}
    .c-body.comm-cae {{ color: rgb(174, 174, 174); }}
    .c-body.comm-cbe {{ color: rgb(190, 190, 190); }}
    .c-body.comm-cce {{ color: rgb(206, 206, 206); }}
    .c-body.comm-cdd {{ color: rgb(221, 221, 221); }}
    .c-body .hn-quote {{
      color: rgb(85, 85, 85);
      font-style: italic;
    }}
    .vec-bars {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      font: 600 10px/1.2 ui-monospace, SFMono-Regular, Menlo, monospace;
      color: rgb(88, 88, 84);
      padding-top: 8px;
      border-top: 1px dashed rgb(218, 218, 212);
    }}
    .ext-link {{
      color: rgb(16, 78, 158);
      text-decoration: underline;
      text-underline-offset: 3px;
    }}
    footer.sheet-foot {{
      border-top: 3px solid rgb(13, 13, 13);
      padding-top: 14px;
      margin-top: 36px;
      font: 12px/1.5 ui-monospace, SFMono-Regular, Menlo, monospace;
      color: rgb(90, 90, 88);
      display: flex;
      justify-content: space-between;
      flex-wrap: wrap;
      gap: 10px;
    }}

    .dual-oled {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 16px;
      min-width: 0;
    }}
    details.graph-drawer {{
      display: flex;
      flex-direction: column;
      min-width: 0;
    }}
    details.graph-drawer:not([open]) > .oled-bay,
    details.graph-drawer:not([open]) > .control-panel {{
      display: none;
    }}
    summary.graph-summary {{
      list-style: none;
      pointer-events: none;
      cursor: default;
      min-width: 0;
    }}
    summary.graph-summary::-webkit-details-marker {{ display: none; }}
    .graph-title-group {{ min-width: 0; }}
    .mob-graph-pill {{ display: none; }}
    .dual-oled h2 {{
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }}

    @media (max-width: 960px) {{
      .wrap {{ padding: 18px 14px 48px; }}
      .col-1, .col-2, .col-3, .col-4, .col-5, .col-6,
      .col-7, .col-8, .col-9, .col-10, .col-11 {{ grid-column: span 12; }}
      .dual-oled {{ grid-template-columns: 1fr; gap: 10px; }}
      details.graph-drawer {{ display: block; }}
      summary.graph-summary {{
        pointer-events: auto;
        cursor: pointer;
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: 12px;
        padding: 10px 12px;
        background: rgb(239, 239, 234);
        border: 1px solid rgb(13, 13, 13);
        user-select: none;
      }}
      summary.graph-summary h2 {{
        font-size: 17px;
        margin: 0;
        white-space: normal;
      }}
      details.graph-drawer[open] > .oled-bay,
      details.graph-drawer[open] > .control-panel {{
        margin-top: 8px;
      }}
      .mob-graph-pill {{
        display: inline-block;
        flex-shrink: 0;
        padding: 4px 8px;
        background: rgb(13, 13, 13);
        color: rgb(247, 247, 245);
        font: 700 10px/1.2 ui-monospace, SFMono-Regular, Menlo, monospace;
        letter-spacing: 0.06em;
      }}
      details.graph-drawer[open] > summary .mob-graph-pill::before {{ content: "[-] HIDE"; }}
      details.graph-drawer:not([open]) > summary .mob-graph-pill::before {{ content: "[+] SHOW"; }}
      .kpi-strip {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
      .kpi-cell {{ border-bottom: 1px solid rgb(205, 205, 200); }}
      .filter-bar {{
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 8px;
      }}
      .filter-bar select.sel-in {{
        width: 100%;
        font-size: 16px;
        padding: 8px 9px;
      }}
      .filter-bar input.search-in {{
        grid-column: span 2;
        width: 100%;
        min-width: 0;
        font-size: 16px;
      }}
    }}
  </style>
</head>
<body>
<div class="wrap">
  <header class="sheet-top">
    <div class="eyebrow">
      <span>NYX OBSERVATORY // <a class="ext-link" href="{hn_item_href}" target="_blank" rel="noopener">HN ITEM {story_id}</a> // {safe_host.upper()}</span>
      {eyebrow_right}
    </div>
    <h1>Bullshit vs. <span class="accent">Epistemic.</span></h1>
    <p class="sublead">
      Empirical autopsy of all <strong>{total_cnt:,}</strong> Hacker News comments on {story_link_html}.
      Replacing surface crowd prediction and <code>(T + 2)^1.8</code> recency decay with Shannon/IDF surprisal, Popperian falsifiability,
      Frankfurtian bullshit suppression, inverse <code>news.arc</code> physics, and submodular portfolio selection.
    </p>
  </header>

  <details class="proof-drawer" id="kpiDrawer">
    <summary>
      <span>00 // CORPUS SUMMARY ({total_cnt:,} COMMENTS &bull; {useful_pct:.1f}% USEFUL SIGNAL &bull; {tiers.get("epistemic_gold", 0)} GOLD &bull; MAX SUBTREE {largest_root["slots"]} SLOTS)</span>
      <span class="toggle-pill" data-show="[+] SHOW" data-hide="[-] HIDE"></span>
    </summary>
    <div class="proof-body">
      <div class="kpi-strip">
        <div class="kpi-cell">
          <div class="kpi-label">Corpus Audited</div>
          <div class="kpi-val">{total_cnt:,}</div>
          <div class="kpi-sub">{snap_sub}</div>
        </div>
        <div class="kpi-cell">
          <div class="kpi-label">Actual Useful Signal</div>
          <div class="kpi-val ok">{useful_pct:.1f}%</div>
          <div class="kpi-sub">{useful_cnt} comments ({tiers.get("epistemic_gold", 0)} Gold / {gold_pct:.1f}%)</div>
        </div>
        <div class="kpi-cell">
          <div class="kpi-label">Chatter &amp; Bullshit</div>
          <div class="kpi-val hi">{noise_pct:.1f}%</div>
          <div class="kpi-sub">{tiers.get("crowd_chatter", 0)} chatter &bull; {tiers.get("bullshit_or_flamewar", 0)} BS &bull; {tiers.get("downvoted_sink", 0)} faded</div>
        </div>{kpi_4_5_html}
        <div class="kpi-cell">
          <div class="kpi-label">Largest Root Monopoly</div>
          <div class="kpi-val hi">{largest_root["slots"]}</div>
          <div class="kpi-sub">HN POS {largest_root["start_dom"]}..{largest_root["end_dom"]} ({largest_root["share_pct"]:.1f}% of thread)</div>
        </div>
      </div>
    </div>
  </details>
{drawer_html}

  <details class="proof-drawer" id="labDrawer">
    <summary>
      <span>02 // EPISTEMIC PHASE PLANE, NEWS.ARC GRAVITY &amp; LIVE WEIGHT TUNER (TAP TO INSPECT N = {total_cnt:,})</span>
      <span class="toggle-pill" data-show="[+] SHOW" data-hide="[-] HIDE"></span>
    </summary>
    <div class="proof-body grid-12">
      <div class="col-3">
        <details class="graph-drawer" id="tunerDrawer">
          <summary class="graph-summary">
            <div class="graph-title-group">
              <div class="sec-tag">02A / INTERACTIVE EQUATION</div>
              <h2>Live Epistemic Tuner</h2>
            </div>
            <span class="mob-graph-pill"></span>
          </summary>
          <div class="control-panel">
            <div class="slider-row">
              <div class="slider-lbl"><span>1. Info Gain (IDF)</span><span id="val_ig"></span></div>
              <input type="range" id="sl_ig" min="0" max="5" step="0.05">
            </div>
            <div class="slider-row">
              <div class="slider-lbl"><span>2. Falsifiability</span><span id="val_fa"></span></div>
              <input type="range" id="sl_fa" min="0" max="5" step="0.05">
            </div>
            <div class="slider-row">
              <div class="slider-lbl"><span>3. Gravity &amp; Precision</span><span id="val_gp"></span></div>
              <input type="range" id="sl_gp" min="0" max="4" step="0.05">
            </div>
            <div class="slider-row">
              <div class="slider-lbl"><span>4. Bullshit Penalty</span><span id="val_bp"></span></div>
              <input type="range" id="sl_bp" min="0" max="5" step="0.05">
            </div>
            <div class="slider-row">
              <div class="slider-lbl"><span>5. Downvote Sink</span><span id="val_dp"></span></div>
              <input type="range" id="sl_dp" min="0" max="5" step="0.05">
            </div>
            <button class="tab-btn" id="resetWeightsBtn" style="width:100%;margin-top:6px">Reset Calibrated Weights</button>
            <p style="font-size:11.5px;line-height:1.42;color:rgb(85,85,82);margin:12px 0 0">
              <strong>Live Feedback Loop:</strong><br>
              Drag any weight to watch the {total_cnt:,}-point phase plane and comment ranking re-solve instantaneously.<br>
              &bull; <strong>c5A Rescue:</strong> Sourced <code>c5A</code> rebuttals survive partisan downvotes.<br>
              &bull; <strong>Context Gate:</strong> Meme links &amp; bare drops get zero citation boost.
            </p>
          </div>
        </details>
      </div>

      <div class="col-9">
        <div class="dual-oled">
          <details class="graph-drawer" id="phaseDrawer" open>
            <summary class="graph-summary">
              <div class="graph-title-group">
                <div class="sec-tag">03 / EPISTEMIC PHASE PLANE</div>
                <h2>Crowd Chatter vs. Grounded Signal</h2>
              </div>
              <span class="mob-graph-pill"></span>
            </summary>
            <div class="oled-bay">
              <div class="oled-head">
                <span>X: Epistemic Potential // Y: Bullshit &amp; Sink</span>
                <span class="sig">TAP POINT (N = {total_cnt:,})</span>
              </div>
              <canvas id="phaseCanvas" class="plot" width="540" height="300"></canvas>
              <div class="legend-row">
                <span><i class="dot" style="background:rgb(0,230,118)"></i>Gold ({tiers.get("epistemic_gold", 0)})</span>
                <span><i class="dot" style="background:rgb(56,189,248)"></i>Grounded ({tiers.get("grounded_analysis", 0)})</span>
                <span><i class="dot" style="background:rgb(148,163,184)"></i>Chatter ({tiers.get("crowd_chatter", 0)})</span>
                <span><i class="dot" style="background:rgb(255,179,0)"></i>Meme ({tiers.get("meme_or_snark", 0)})</span>
                <span><i class="dot" style="background:rgb(255,68,0)"></i>BS ({tiers.get("bullshit_or_flamewar", 0)})</span>
              </div>
              <div class="probe-box"><div id="phaseProbe" class="probe-clamp">Tap or hover any point to inspect its coordinates and filter the comment below.</div></div>
            </div>
          </details>

          <details class="graph-drawer" id="gravityDrawer">
            <summary class="graph-summary">
              <div class="graph-title-group">
                <div class="sec-tag">04 / NEWS.ARC GRAVITY &amp; TREE-LOCK</div>
                <h2>Why Live HN Buried Primary Evidence</h2>
              </div>
              <span class="mob-graph-pill"></span>
            </summary>
            <div class="oled-bay">
              <div class="oled-head">
                <span>X: Age (Hours) // Y: Live HN POS (1..{live_cnt:,})</span>
                <span class="sig">(T + 2)^1.8</span>
              </div>
              <canvas id="gravityCanvas" class="plot" width="540" height="300"></canvas>
              <div class="legend-row">
                <span><i class="dot" style="background:rgb(0,230,118)"></i>Buried Gold (HN POS &gt; {buried_cutoff})</span>
                <span><i class="dot" style="background:rgb(255,179,0)"></i>Surf Mirage (&lt;3.2h)</span>
                <span><i class="dot" style="background:rgb(255,68,0)"></i>Downvoted / Mod-Rebuked</span>
              </div>
              <div class="probe-box"><div id="gravProbe" class="probe-clamp">Top slot (@{_safe_html_no_hash(largest_root["top_dom1_author"])}, {largest_root["top_dom1_age"]}h); largest subtree (@{_safe_html_no_hash(largest_root["author"])}) occupies {largest_root["slots"]} slots (HN POS {largest_root["start_dom"]}..{largest_root["end_dom"]}).</div></div>
            </div>
          </details>
        </div>
      </div>
    </div>
  </details>

  <section class="band grid-12" id="explorerSection" style="padding-top:16px">
    <div class="col-12">
      <div class="sec-tag">05 / CORPUS EXPLORER ({total_cnt:,} COMMENTS)</div>
      <h2>Signal Rank vs. Live Hacker News</h2>
      <div class="filter-bar">
        <select id="modeSelect" class="sel-in" aria-label="Ranking view">
          <option value="top_signal">View: Epistemic Top 50</option>
          <option value="buried_gems">View: Buried Gems (HN POS &gt; {buried_cutoff})</option>
          <option value="hn_top40">View: Live HN Top 40 Autopsy</option>
          <option value="c5a_rescues">View: c5A Heterodox Rescues</option>
          <option value="bullshit_traps">View: High-Karma / URL Traps Caught</option>
          <option value="mod_morgue">View: Mod Rebukes &amp; Downvoted Morgue</option>
        </select>
        <select id="facetSelect" class="sel-in" aria-label="Topic facet">
          {facet_select_html}
        </select>
        <input type="search" id="searchInput" class="search-in" placeholder="{safe_placeholder}">
      </div>
      <div id="resultMeta" style="font:600 11px/1.4 ui-monospace,Menlo,monospace;color:rgb(90,90,88);margin-bottom:10px"></div>
      <div id="cardContainer" class="card-list"></div>
    </div>
  </section>

  <footer class="sheet-foot">
    <span>SILICON PIRATE &times; CARBON PIRATE // ZERO-HASH DEFENSIVE ARTIFACT (RGB ONLY)</span>
    <span>SOURCE: HN {story_id} + {safe_host.upper()} + ALGOLIA + AUTHOR CACHE</span>
  </footer>
</div>

<script id="observatoryData" type="application/json">{json_blob}</script>
<script>
(() => {{
  const DATA = JSON.parse(document.getElementById("observatoryData").textContent);
  const DEFAULT_W = DATA.weights;
  const TOTAL_N = Math.max(1, DATA.comments.length);
  const BURIED_CUTOFF = DATA.buried_cutoff || 500;
  const RESCUE_TOP_K = DATA.rescue_top_k || 80;
  let curW = {{
    ig: DEFAULT_W.info_gain,
    fa: DEFAULT_W.falsifiability,
    gp: DEFAULT_W.gravity_progeny,
    bp: DEFAULT_W.bullshit_penalty,
    dp: DEFAULT_W.downvote_penalty
  }};
  let activeMode = "top_signal";
  let selectedId = null;

  function escHtml(s) {{
    return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }}

  // Render 01A / 01B tables (benchmark ablation OR live unsupervised diagnostics)
  const abBody = document.getElementById("ablationBody");
  if (abBody && DATA.ablations && DATA.ablations.length > 0) {{
    const maxAbScore = Math.max(...DATA.ablations.map(r => r.score));
    DATA.ablations.forEach((r, idx) => {{
      const tr = document.createElement("tr");
      if (idx === 0) tr.className = "hn-row";
      else if (Math.abs(r.score - maxAbScore) < 0.02) tr.className = "winner";
      tr.innerHTML = [
        `<td>${{escHtml(r.name)}}</td>`,
        `<td><strong>${{r.score.toFixed(2)}}</strong></td>`,
        `<td>${{r.ndcg20.toFixed(3)}}</td>`,
        `<td>${{r.pairwise_concordance.toFixed(3)}}</td>`,
        `<td>${{(100 * r.adversarial_acc).toFixed(1)}}%</td>`,
        `<td>${{(100 * r.buried_gold_recall_top45).toFixed(1)}}%</td>`,
        `<td>${{(100 * r.bullshit_sink_percentile).toFixed(1)}}%</td>`,
        `<td>${{r.top20_diversity.toFixed(3)}}</td>`
      ].join("");
      abBody.appendChild(tr);
    }});
  }}

  const tBody = document.getElementById("tourneyBody");
  if (tBody && DATA.tournament && DATA.tournament.length > 0) {{
    DATA.tournament.forEach((t, idx) => {{
      const tr = document.createElement("tr");
      if (idx === 0) tr.className = "hn-row";
      else if (t.disposition === "promoted_champion" || t.disposition === "promoted_best") tr.className = "winner";
      tr.innerHTML = [
        `<td>${{escHtml(t.stage)}}${{t.disposition === "promoted_champion" ? " ★" : ""}}</td>`,
        `<td>${{escHtml(t.sha)}}</td>`,
        `<td><strong>${{t.score.toFixed(2)}}</strong></td>`,
        `<td>${{t.dev_score.toFixed(2)}}</td>`,
        `<td>${{t.holdout_score.toFixed(2)}}</td>`
      ].join("");
      tBody.appendChild(tr);
    }});
  }}

  const fdBody = document.getElementById("facetDiagBody");
  if (fdBody && DATA.facet_diagnostics) {{
    DATA.facet_diagnostics.forEach((f, idx) => {{
      const tr = document.createElement("tr");
      if (idx === 0) tr.className = "winner";
      tr.innerHTML = [
        `<td>${{escHtml(f.label)}}</td>`,
        `<td>${{f.count}}</td>`,
        `<td><strong>${{f.useful}}</strong></td>`,
        `<td>${{f.useful_pct.toFixed(1)}}%</td>`,
        `<td style="text-align:left">${{escHtml(f.terms)}}</td>`
      ].join("");
      fdBody.appendChild(tr);
    }});
  }}

  const scBody = document.getElementById("sourceCatBody");
  if (scBody && DATA.source_categories) {{
    if (DATA.source_categories.length === 0) {{
      const tr = document.createElement("tr");
      tr.innerHTML = `<td>No external links</td><td>0</td>`;
      scBody.appendChild(tr);
    }} else {{
      DATA.source_categories.forEach(sc => {{
        const tr = document.createElement("tr");
        tr.innerHTML = `<td>${{escHtml(sc.category)}}</td><td><strong>${{sc.count}}</strong></td>`;
        scBody.appendChild(tr);
      }});
    }}
  }}
  const ancBox = document.getElementById("anchorListBox");
  if (ancBox && DATA.story_anchors && DATA.story_anchors.length > 0) {{
    ancBox.textContent = "UNSUPERVISED STORY ANCHORS: " + DATA.story_anchors.join(", ");
  }}

  // Bind Sliders
  const sliderMap = [
    ["ig", "sl_ig", "val_ig"],
    ["fa", "sl_fa", "val_fa"],
    ["gp", "sl_gp", "val_gp"],
    ["bp", "sl_bp", "val_bp"],
    ["dp", "sl_dp", "val_dp"]
  ];
  function syncSliders() {{
    sliderMap.forEach(([k, sid, vid]) => {{
      const el = document.getElementById(sid);
      el.value = curW[k];
      document.getElementById(vid).textContent = curW[k].toFixed(2);
    }});
  }}
  sliderMap.forEach(([k, sid, vid]) => {{
    document.getElementById(sid).addEventListener("input", (e) => {{
      curW[k] = parseFloat(e.target.value);
      document.getElementById(vid).textContent = curW[k].toFixed(2);
      recomputeAndRender();
    }});
  }});
  document.getElementById("resetWeightsBtn").addEventListener("click", () => {{
    curW = {{
      ig: DEFAULT_W.info_gain,
      fa: DEFAULT_W.falsifiability,
      gp: DEFAULT_W.gravity_progeny,
      bp: DEFAULT_W.bullshit_penalty,
      dp: DEFAULT_W.downvote_penalty
    }};
    syncSliders();
    recomputeAndRender();
  }});

  function isDefaultWeights() {{
    return Math.abs(curW.ig - DEFAULT_W.info_gain) < 1e-4 &&
           Math.abs(curW.fa - DEFAULT_W.falsifiability) < 1e-4 &&
           Math.abs(curW.gp - DEFAULT_W.gravity_progeny) < 1e-4 &&
           Math.abs(curW.bp - DEFAULT_W.bullshit_penalty) < 1e-4 &&
           Math.abs(curW.dp - DEFAULT_W.downvote_penalty) < 1e-4;
  }}

  const agesSorted = DATA.comments.map(c => c.age).sort((a, b) => a - b);
  const p98Age = agesSorted.length ? agesSorted[Math.floor(0.98 * (agesSorted.length - 1))] : 12.0;
  const MAX_AGE_PLOT = Math.max(4.0, Math.ceil(p98Age));

  let liveList = [];
  function recomputeAndRender() {{
    const useCanonical = isDefaultWeights();
    liveList = DATA.comments.map(c => {{
      const pos = curW.ig * c.ig + curW.fa * c.fa + curW.gp * c.gp;
      const neg = curW.bp * c.bl + curW.dp * c.ds;
      const dynScore = useCanonical ? c.sc : (pos - neg);
      return Object.assign({{}}, c, {{
        liveScore: dynScore,
        liveEp: Math.max(0, pos),
        liveBs: Math.max(0, neg)
      }});
    }});
    if (useCanonical) {{
      liveList.sort((a, b) => a.sr - b.sr);
    }} else {{
      liveList.sort((a, b) => (b.liveScore - a.liveScore) || (a.dom - b.dom));
    }}
    liveList.forEach((c, i) => {{ c.liveRank = i + 1; }});
    drawPhaseCanvas();
    drawGravityCanvas();
    renderCards();
  }}

  const TIER_COLORS = {{
    epistemic_gold: "rgb(0, 230, 118)",
    grounded_analysis: "rgb(56, 189, 248)",
    crowd_chatter: "rgba(148, 163, 184, 0.45)",
    meme_or_snark: "rgb(255, 179, 0)",
    bullshit_or_flamewar: "rgba(255, 68, 0, 0.72)",
    downvoted_sink: "rgba(110, 118, 128, 0.45)"
  }};

  // Plot 1: 2D Epistemic Phase Plane
  const pCanvas = document.getElementById("phaseCanvas");
  const pCtx = pCanvas.getContext("2d");
  let phasePts = [];
  function drawPhaseCanvas() {{
    const W = pCanvas.width, H = pCanvas.height;
    pCtx.clearRect(0, 0, W, H);
    pCtx.strokeStyle = "rgb(30, 36, 44)";
    pCtx.lineWidth = 1;
    for (let i = 1; i < 6; i++) {{
      pCtx.beginPath(); pCtx.moveTo((W * i) / 6, 0); pCtx.lineTo((W * i) / 6, H); pCtx.stroke();
      pCtx.beginPath(); pCtx.moveTo(0, (H * i) / 6); pCtx.lineTo(W, (H * i) / 6); pCtx.stroke();
    }}
    pCtx.strokeStyle = "rgba(0, 230, 118, 0.32)";
    pCtx.setLineDash([4, 4]);
    pCtx.beginPath(); pCtx.moveTo(30, H - 24); pCtx.lineTo(W - 20, 20); pCtx.stroke();
    pCtx.setLineDash([]);

    const maxX = 16.5, maxY = 16.5;
    phasePts = [];
    const drawOrder = [...liveList].reverse();
    drawOrder.forEach(c => {{
      const x = 32 + Math.min(1, c.liveEp / maxX) * (W - 52);
      const y = (H - 26) - Math.min(1, c.liveBs / maxY) * (H - 46);
      const r = c.tier === "epistemic_gold" ? 4.2 : (c.tier === "grounded_analysis" ? 2.8 : 2.0);
      pCtx.fillStyle = TIER_COLORS[c.tier] || "rgb(148,163,184)";
      pCtx.beginPath();
      pCtx.arc(x, y, r, 0, Math.PI * 2);
      pCtx.fill();
      if (selectedId === c.id) {{
        pCtx.strokeStyle = "rgb(255, 255, 255)";
        pCtx.lineWidth = 2;
        pCtx.beginPath();
        pCtx.arc(x, y, r + 4, 0, Math.PI * 2);
        pCtx.stroke();
      }}
      phasePts.push({{ x, y, c }});
    }});
    pCtx.fillStyle = "rgb(140, 150, 162)";
    pCtx.font = "10px ui-monospace, Menlo, monospace";
    pCtx.fillText("EPISTEMIC POTENTIAL (INFO + FALSIFIABILITY) ->", W - 295, H - 7);
    pCtx.fillText("BULLSHIT / SINK LOAD ^", 8, 14);
  }}

  // Plot 2: news.arc Age vs HN DOM Rank
  const gCanvas = document.getElementById("gravityCanvas");
  const gCtx = gCanvas.getContext("2d");
  let gravPts = [];
  function drawGravityCanvas() {{
    const W = gCanvas.width, H = gCanvas.height;
    gCtx.clearRect(0, 0, W, H);
    const lr = DATA.largest_root || {{ slots: 0, start_dom: 1, end_dom: 1, author: "root" }};
    if (lr.slots > 1) {{
      const yStart = 20 + (lr.start_dom / TOTAL_N) * (H - 44);
      const yEnd = 20 + (lr.end_dom / TOTAL_N) * (H - 44);
      gCtx.fillStyle = "rgba(255, 68, 0, 0.09)";
      gCtx.fillRect(32, yStart, W - 48, Math.max(4, yEnd - yStart));
      gCtx.fillStyle = "rgba(255, 110, 64, 0.75)";
      gCtx.font = "10px ui-monospace, Menlo, monospace";
      gCtx.fillText(
        `LARGEST SUBTREE (@${{lr.author}}: ${{lr.slots}} SLOTS, HN POS ${{lr.start_dom}}..${{lr.end_dom}})`,
        40,
        Math.min(H - 22, yStart + 13)
      );
    }}

    gravPts = [];
    liveList.forEach(c => {{
      const x = 32 + Math.min(1, c.age / MAX_AGE_PLOT) * (W - 52);
      const y = 20 + Math.min(1, c.dom / TOTAL_N) * (H - 44);
      let col = "rgba(148, 163, 184, 0.30)";
      let rad = 2.0;
      if (c.tier === "epistemic_gold") {{ col = "rgb(0, 230, 118)"; rad = 4.2; }}
      else if (c.surf >= 4.0) {{ col = "rgb(255, 179, 0)"; rad = 3.2; }}
      else if (c.dt >= 2 || c.mod) {{ col = "rgba(255, 68, 0, 0.7)"; rad = 2.4; }}
      gCtx.fillStyle = col;
      gCtx.beginPath();
      gCtx.arc(x, y, rad, 0, Math.PI * 2);
      gCtx.fill();
      if (selectedId === c.id) {{
        gCtx.strokeStyle = "rgb(255, 255, 255)";
        gCtx.lineWidth = 2;
        gCtx.beginPath();
        gCtx.arc(x, y, rad + 4, 0, Math.PI * 2);
        gCtx.stroke();
      }}
      gravPts.push({{ x, y, c }});
    }});
    gCtx.fillStyle = "rgb(140, 150, 162)";
    gCtx.fillText(`COMMENT AGE IN HOURS (0h -> ${{MAX_AGE_PLOT}}h) ->`, W - 245, H - 7);
    gCtx.fillText("HN POS 1 (TOP)", 8, 14);
    gCtx.fillText(`HN POS ${{TOTAL_N.toLocaleString()}}`, 8, H - 8);
  }}

  function clearSelectedPoint() {{
    selectedId = null;
    document.getElementById("searchInput").value = "";
    drawPhaseCanvas();
    drawGravityCanvas();
    renderCards();
  }}

  function attachCanvasProbe(canvas, getPts, probeElId) {{
    const probeEl = document.getElementById(probeElId);
    function findNearest(ev, maxDistSq) {{
      const rect = canvas.getBoundingClientRect();
      if (!rect.width || !rect.height) return null;
      const sx = (ev.clientX - rect.left) * (canvas.width / rect.width);
      const sy = (ev.clientY - rect.top) * (canvas.height / rect.height);
      let best = null, bestD = maxDistSq;
      for (const p of getPts()) {{
        const d = (p.x - sx) * (p.x - sx) + (p.y - sy) * (p.y - sy);
        if (d < bestD) {{ bestD = d; best = p.c; }}
      }}
      return best;
    }}
    function showProbeSummary(hit, isPinned) {{
      const delta = hit.dom - hit.liveRank;
      const dStr = delta >= 0 ? `+${{delta}}` : `${{delta}}`;
      const snippet = escHtml(hit.txt.slice(0, 88).replace(/\\s+/g, " "));
      const jumpBtns = isPinned
        ? `<button type="button" class="probe-inline-btn" data-probe-jump="1">Comment &darr;</button>` +
          `<button type="button" class="probe-inline-btn" data-probe-clear="1">Clear &times;</button>`
        : "";
      probeEl.innerHTML =
        `<strong>@${{escHtml(hit.au)}}</strong> | Signal ${{hit.liveRank}} vs HN ${{hit.dom}} (${{dStr}})` +
        jumpBtns +
        `<br>"${{snippet}}..."`;
      const jBtn = probeEl.querySelector("[data-probe-jump]");
      if (jBtn) {{
        jBtn.addEventListener("click", () => {{
          document.getElementById("explorerSection").scrollIntoView({{ behavior: "smooth", block: "start" }});
        }});
      }}
      const cBtn = probeEl.querySelector("[data-probe-clear]");
      if (cBtn) {{
        cBtn.addEventListener("click", clearSelectedPoint);
      }}
    }}
    canvas.addEventListener("mousemove", (ev) => {{
      if (selectedId !== null) return;
      const hit = findNearest(ev, 169);
      if (hit) showProbeSummary(hit, false);
    }});
    canvas.addEventListener("click", (ev) => {{
      const hit = findNearest(ev, 576);
      if (!hit) return;
      selectedId = hit.id;
      document.getElementById("searchInput").value = String(hit.id);
      showProbeSummary(hit, true);
      drawPhaseCanvas();
      drawGravityCanvas();
      renderCards();
    }});
  }}
  attachCanvasProbe(pCanvas, () => phasePts, "phaseProbe");
  attachCanvasProbe(gCanvas, () => gravPts, "gravProbe");

  function formatHnBody(raw) {{
    return raw.split("\\n").map(line => {{
      const safe = escHtml(line);
      return line.trimStart().startsWith(">")
        ? `<span class="hn-quote">${{safe}}</span>`
        : safe;
    }}).join("\\n");
  }}

  function renderCards() {{
    const q = document.getElementById("searchInput").value.trim().toLowerCase();
    const facet = document.getElementById("facetSelect").value;
    let pool = liveList;

    if (q) {{
      pool = pool.filter(c =>
        String(c.id) === q ||
        c.au.toLowerCase().includes(q.replace(/^@/, "")) ||
        c.txt.toLowerCase().includes(q)
      );
    }} else {{
      if (activeMode === "top_signal") {{
        pool = pool.slice(0, 60);
      }} else if (activeMode === "buried_gems") {{
        pool = pool.filter(c => c.dom > BURIED_CUTOFF && c.liveRank <= RESCUE_TOP_K);
      }} else if (activeMode === "hn_top40") {{
        pool = [...liveList].sort((a, b) => a.dom - b.dom).slice(0, 45);
      }} else if (activeMode === "c5a_rescues") {{
        pool = pool.filter(c => c.dt === 1 && c.ut >= 2);
      }} else if (activeMode === "bullshit_traps") {{
        const demoteFloor = Math.max(40, Math.round(TOTAL_N * 0.40));
        const topCeil = Math.max(20, Math.round(TOTAL_N * 0.15));
        pool = pool.filter(c =>
          (c.meme > 0 && (c.k >= 5000 || c.urls.length > 0)) ||
          (c.lu > 0 && c.urls.length > 0) ||
          (c.dom <= topCeil && c.liveRank > demoteFloor)
        ).slice(0, 50);
      }} else if (activeMode === "mod_morgue") {{
        pool = [...liveList].filter(c => c.mod === 1 || c.dt >= 2 || c.pp >= 4).slice(0, 50);
      }}
    }}

    if (facet !== "all") {{
      pool = pool.filter(c => c.facet === facet);
    }}

    const prevScrollY = window.scrollY;
    const shown = pool.slice(0, 50);
    const metaEl = document.getElementById("resultMeta");
    metaEl.innerHTML =
      `Showing ${{shown.length}} of ${{pool.length}} matching comments (mode: ${{activeMode}})` +
      (q ? ` &nbsp;<button type="button" id="clearFilterBtn" class="tab-btn" style="padding:2px 8px;box-shadow:none">Clear selection</button>` : "");
    const clrBtn = document.getElementById("clearFilterBtn");
    if (clrBtn) {{
      clrBtn.addEventListener("click", clearSelectedPoint);
    }}

    const rescueJump = Math.max(25, Math.min(150, Math.round(TOTAL_N * 0.15)));
    const demoteDrop = -Math.max(40, Math.min(300, Math.round(TOTAL_N * 0.25)));
    const box = document.getElementById("cardContainer");
    box.innerHTML = shown.map(c => {{
      const delta = c.dom - c.liveRank;
      const deltaBadge = delta >= rescueJump
        ? `<span class="badge rescue">RESCUED +${{delta}} SPOTS</span>`
        : (delta <= demoteDrop ? `<span class="badge drop">DEMOTED ${{delta}} SPOTS</span>` : "");
      const fadeBadge = c.dt === 1
        ? `<span class="badge c5a">HN FADE: ${{escHtml(c.fade)}} (RESCUED)</span>`
        : (c.dt >= 2 ? `<span class="badge drop">HN FADE: ${{escHtml(c.fade)}} (TIER ${{c.dt}})</span>` : "");
      const modBadge = c.mod ? `<span class="badge drop">MOD REBUKED (dang/tomhow)</span>` : "";
      const surfBadge = c.surf >= 4.0 ? `<span class="badge c5a">SURF MIRAGE ${{c.surf}}x</span>` : "";
      const urlLinks = c.urls.map(u => {{
        let host = "source";
        try {{ host = new URL(u).hostname.replace(/^www\\./, ""); }} catch (_e) {{}}
        return `<a class="ext-link" href="${{escHtml(u)}}" target="_blank" rel="noopener">[${{escHtml(host)}}]</a>`;
      }}).join(" ");

      const commClass = "comm-" + String(c.fade || "c00").toLowerCase();
      return `<article class="c-card tier-${{c.tier}}">
        <div class="hn-comhead">
          <span class="hn-votearrow">▲</span>
          <a href="https://news.ycombinator.com/user?id=${{encodeURIComponent(c.au)}}" target="_blank" rel="noopener">${{escHtml(c.au)}}</a>
          <span>${{c.age}} hours ago</span>
          <span>|</span>
          <span>depth ${{c.d}}</span>
          <span>|</span>
          <span>karma ${{c.k.toLocaleString()}} (${{c.kpp}}/post)</span>
          <span>|</span>
          <a href="https://news.ycombinator.com/item?id=${{c.id}}" target="_blank" rel="noopener">link</a>
        </div>
        <div class="c-meta">
          <span class="badge rank-sig">SIGNAL ${{c.liveRank}}</span>
          <span class="badge">HN POS ${{c.dom}}</span>
          ${{deltaBadge}} ${{fadeBadge}} ${{modBadge}} ${{surfBadge}}
          <span class="badge">${{escHtml(c.flbl || c.facet.replace(/_/g, " "))}}</span>
        </div>
        <div class="c-body ${{commClass}}">${{formatHnBody(c.txt)}}</div>
        <div class="vec-bars">
          <span>SCORE: <strong>${{c.liveScore.toFixed(2)}}</strong></span>
          <span>INFO: +${{(curW.ig * c.ig).toFixed(2)}}</span>
          <span>FALSIFIABILITY: +${{(curW.fa * c.fa).toFixed(2)}}</span>
          <span>GRAVITY/PRECISION: +${{(curW.gp * c.gp).toFixed(2)}}</span>
          <span>BULLSHIT LOAD: -${{(curW.bp * c.bl).toFixed(2)}}</span>
          <span>DOWNVOTE SINK: -${{(curW.dp * c.ds).toFixed(2)}}</span>
          ${{urlLinks ? `<span>LINKS: ${{urlLinks}}</span>` : ""}}
        </div>
      </article>`;
    }}).join("");
    if (window.scrollY !== prevScrollY) {{
      window.scrollTo(0, prevScrollY);
    }}
  }}

  const modeSelect = document.getElementById("modeSelect");
  modeSelect.addEventListener("change", () => {{
    activeMode = modeSelect.value;
    selectedId = null;
    document.getElementById("searchInput").value = "";
    drawPhaseCanvas();
    drawGravityCanvas();
    renderCards();
  }});
  document.getElementById("searchInput").addEventListener("input", renderCards);
  document.getElementById("facetSelect").addEventListener("change", renderCards);

  const labDrawer = document.getElementById("labDrawer");
  const tunerDrawer = document.getElementById("tunerDrawer");
  const phaseDrawer = document.getElementById("phaseDrawer");
  const gravityDrawer = document.getElementById("gravityDrawer");
  const graphDrawers = [tunerDrawer, phaseDrawer, gravityDrawer];

  [labDrawer, phaseDrawer, gravityDrawer].forEach(d => {{
    d.addEventListener("toggle", () => {{
      if (d.open) {{
        drawPhaseCanvas();
        drawGravityCanvas();
      }}
    }});
  }});

  const mobMq = window.matchMedia("(max-width: 960px)");
  function syncViewportDrawers(isMobile) {{
    if (!isMobile) {{
      // Desktop: Tuner & both graphs stay open side-by-side inside the lab drawer (mobile-only inner collapse)
      graphDrawers.forEach(d => {{ d.open = true; }});
    }} else {{
      // Mobile: keep Tuner & second graph collapsed initially so Phase Plane + Comments stay tight
      tunerDrawer.open = false;
    }}
    drawPhaseCanvas();
    drawGravityCanvas();
  }}
  syncViewportDrawers(mobMq.matches);
  mobMq.addEventListener("change", (e) => syncViewportDrawers(e.matches));

  syncSliders();
  recomputeAndRender();
}})();
</script>
</body>
</html>
"""
    assert "#" not in html_doc, (
        f"Zero-hash mandate violated at index {html_doc.find('#')}!"
    )
    resolved_out = out_path or (HERE / f"show-me-hn-{story_id}.html")
    resolved_out.write_text(html_doc, encoding="utf-8")
    return resolved_out


if __name__ == "__main__":
    arg_target: str | int = sys.argv[1] if len(sys.argv) > 1 else 50467087
    out = build_html(arg_target)
    print(f"Built zero-hash observatory: {out} ({out.stat().st_size / 1024:.1f} KB)")
