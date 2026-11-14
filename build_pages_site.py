#!/usr/bin/env python3
"""Assemble a static GitHub Pages site mirroring Hacker News `/item?id=<id>` URIs.

Builds an incremental static tree (compatible with both GitHub.com Pages and
GitHub Enterprise Server `gh-pages` branches) where any published observatory
is served at the exact HN-equivalent URI:

    Original HN:   https://news.ycombinator.com/item?id=50472038
    GitHub Pages:  <pages-base-url>/item?id=50472038

Layout emitted into `--site-dir`:
- `.nojekyll`         — disables Jekyll processing so raw files serve as-is
- `items/<id>.html`   — self-contained zero-hash observatories (preserved across runs)
- `item.html`         — `/item?id=<id>` in-place URI router (keeps `/item?id=<id>` in URL bar)
- `404.html`          — identical `/item?id=<id>` fallback for servers without `.html` auto-lookup
- `catalog.json`      — machine-readable manifest of all published HN items
- `index.html`        — zero-hash directory & instant HN-URL-to-Pages launcher
"""

import argparse
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
import html
import json
from pathlib import Path
import re
import shutil
from typing import Any
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent
ITEM_FILE_RE = re.compile(r"^show-me-hn-(\d+)\.html$")
PUBLISHED_ITEM_RE = re.compile(r"^(\d+)\.html$")
OBS_JSON_RE = re.compile(
    r'<script\s+id=["\']observatoryData["\']\s+type=["\']application/json["\']>(.*?)</script>',
    flags=re.S,
)


def _safe_no_hash(text: str) -> str:
    """Escape HTML entities and ensure zero literal `#` characters."""
    return html.escape(str(text), quote=True).replace("#", "No. ")


def _safe_url_no_hash(url: str) -> str:
    """Sanitize an external http(s) URL and strip `#fragment` for zero-hash HTML."""
    raw = str(url or "").split("#", 1)[0].strip()
    if not raw:
        return ""
    parsed = urlparse(raw)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return ""
    return html.escape(raw, quote=True).replace("#", "")


def _format_hn_sitebit(url: str) -> str:
    """Format an HN-style `(domain)` comhead label, or empty string for internal/empty URLs."""
    raw = str(url or "").split("#", 1)[0].strip()
    if not raw:
        return ""
    parsed = urlparse(raw)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        return ""
    host = parsed.hostname.lower().removeprefix("www.")
    if host == "news.ycombinator.com":
        return ""
    if host in ("github.com", "gitlab.com"):
        parts = [seg for seg in parsed.path.split("/") if seg]
        if parts:
            return _safe_no_hash(f"{host}/{parts[0].lower()}")
    return _safe_no_hash(host)


def evaluate_schedule_window(
    cron_expr: str = "",
    *,
    now_utc: datetime | None = None,
) -> dict[str, Any]:
    """Determine whether a UTC schedule trigger corresponds to 08:00 London or 08:00 San Francisco.

    GitHub Actions cron runs strictly in UTC without DST awareness and can experience queue delays.
    By scheduling `0 7,8,15,16 * * *` and anchoring to `cron_expr`'s scheduled UTC hour on today's
    date, this guard fires twice daily year-round at exact 08:00 `Europe/London` (GMT/BST) and
    08:00 `America/Los_Angeles` (PST/PDT), even if Actions starts the job 60+ minutes late.
    """
    ref_utc = (now_utc or datetime.now(tz=UTC)).astimezone(UTC)
    parts = cron_expr.strip().split()
    sched_hour: int | None = None
    if len(parts) >= 2 and parts[1].isdigit():
        h_val = int(parts[1])
        if 0 <= h_val <= 23:
            sched_hour = h_val

    slot_targets: list[tuple[str, str, datetime]] = []
    if sched_hour in (7, 8):
        anchor = ref_utc.replace(hour=sched_hour, minute=0, second=0, microsecond=0)
        slot_targets.append(("london_0800", "Europe/London", anchor))
    elif sched_hour in (15, 16):
        anchor = ref_utc.replace(hour=sched_hour, minute=0, second=0, microsecond=0)
        slot_targets.append(("sf_0800", "America/Los_Angeles", anchor))
    else:
        slot_targets.extend(
            [
                ("london_0800", "Europe/London", ref_utc),
                ("sf_0800", "America/Los_Angeles", ref_utc),
            ]
        )

    checks: list[dict[str, Any]] = []
    for slot_name, tz_name, anchor_dt in slot_targets:
        local_dt = anchor_dt.astimezone(ZoneInfo(tz_name))
        checks.append(
            {
                "slot": slot_name,
                "timezone": tz_name,
                "local_iso": local_dt.isoformat(),
                "local_hour": local_dt.hour,
                "matched": local_dt.hour == 8,
            }
        )
        if local_dt.hour == 8:
            return {
                "should_run": True,
                "matched_slot": slot_name,
                "timezone": tz_name,
                "local_iso": local_dt.isoformat(),
                "cron_expr": cron_expr,
                "checks": checks,
            }

    return {
        "should_run": False,
        "matched_slot": "",
        "timezone": "",
        "local_iso": ref_utc.isoformat(),
        "cron_expr": cron_expr,
        "checks": checks,
    }


def _parse_item_timestamp(summary: dict[str, Any], html_path: Path) -> datetime:
    """Resolve an item's UTC timestamp from `t2_ref_utc` metadata or file modification time."""
    raw_ts = str(summary.get("t2_ref_utc") or "").strip()
    if raw_ts:
        try:
            dt = datetime.fromisoformat(raw_ts.replace("Z", "+00:00"))
            return dt.astimezone(UTC) if dt.tzinfo else dt.replace(tzinfo=UTC)
        except ValueError:
            pass
    return datetime.fromtimestamp(html_path.stat().st_mtime, tz=UTC)


def extract_item_summary(html_path: Path, item_id: int) -> dict[str, Any]:
    """Extract compact catalog metadata from a built zero-hash observatory HTML file."""
    raw = html_path.read_text(encoding="utf-8")
    m = OBS_JSON_RE.search(raw)
    if not m:
        return {
            "story_id": item_id,
            "story_title": f"HN Item {item_id}",
            "story_url": "",
            "points": 0,
            "story_author": "",
            "total_comments": 0,
            "epistemic_gold": 0,
            "grounded_analysis": 0,
            "size_kb": round(html_path.stat().st_size / 1024.0, 1),
        }

    data = json.loads(m.group(1))
    manifest = data.get("manifest") or {}
    tiers = data.get("tiers") or {}
    comments = data.get("comments") or []
    title = (
        data.get("story_title")
        or manifest.get("story_title")
        or ("Jensen Huang resigns" if item_id == 50467087 else f"HN Item {item_id}")
    )
    story_url = str(data.get("story_url") or manifest.get("story_url") or "")
    points = int(manifest.get("points") or data.get("points") or 0)
    story_author = str(manifest.get("story_author") or data.get("story_author") or "")
    t2_utc = str(manifest.get("t2_ref_utc") or "")
    return {
        "story_id": item_id,
        "story_title": str(title),
        "story_url": story_url,
        "points": points,
        "story_author": story_author,
        "total_comments": int(len(comments)),
        "epistemic_gold": int(tiers.get("epistemic_gold") or 0),
        "grounded_analysis": int(tiers.get("grounded_analysis") or 0),
        "t2_ref_utc": t2_utc,
        "size_kb": round(html_path.stat().st_size / 1024.0, 1),
    }


def render_item_router_html(*, repo: str, server_url: str, workflow_file: str) -> str:
    """Build zero-hash `item.html` / `404.html` router preserving `/item?id=<id>` in the URL bar."""
    actions_url = (
        f"{server_url.rstrip('/')}/{repo.strip('/')}/actions/workflows/{workflow_file}"
        if repo
        else ""
    )
    cfg_json = (
        json.dumps(
            {
                "repo": repo,
                "actions_url": actions_url,
                "workflow_file": workflow_file,
            },
            ensure_ascii=False,
        )
        .replace("</", "<\\/")
        .replace("#", "\\u0023")
    )

    doc = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>HN Epistemic Observatory // Item Router</title>
  <style>
    * {{ box-sizing: border-box; }}
    body {{
      margin: 8px;
      background: rgb(247, 247, 245);
      color: rgb(13, 13, 13);
      font: 15px/1.5 "Helvetica Neue", Helvetica, Arial, sans-serif;
      -webkit-font-smoothing: antialiased;
    }}
    .shell {{
      max-width: 1240px;
      margin: 0 auto;
      width: 85%;
      padding: 16px 0 26px;
      border-top: 3px solid rgb(13, 13, 13);
      border-bottom: 1px solid rgb(13, 13, 13);
    }}
    .eyebrow {{
      font: 600 11px/1.4 ui-monospace, SFMono-Regular, Menlo, monospace;
      letter-spacing: 0.14em;
      text-transform: uppercase;
      color: rgb(255, 51, 0);
      margin-bottom: 10px;
    }}
    h1 {{
      margin: 0 0 10px;
      font-size: 32px;
      letter-spacing: -0.035em;
      line-height: 1.05;
    }}
    p {{ color: rgb(55, 55, 52); margin: 8px 0 16px; }}
    code, pre {{
      font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
      font-size: 12.5px;
    }}
    pre {{
      background: rgb(13, 15, 17);
      color: rgb(228, 232, 236);
      padding: 12px 14px;
      overflow-x: auto;
      border: 1px solid rgb(35, 38, 42);
    }}
    .actions {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin-top: 16px;
    }}
    a.btn {{
      display: inline-block;
      padding: 8px 14px;
      border: 1px solid rgb(13, 13, 13);
      background: rgb(13, 13, 13);
      color: rgb(247, 247, 245);
      text-decoration: none;
      font: 600 12px/1.2 ui-monospace, SFMono-Regular, Menlo, monospace;
    }}
    a.btn.alt {{
      background: rgb(255, 255, 253);
      color: rgb(13, 13, 13);
    }}
  </style>
</head>
<body>
<div class="shell" id="routerStatus">
  <div class="eyebrow">NYX OBSERVATORY // HN URI MIRROR</div>
  <h1 id="statusTitle">Loading Hacker News Observatory...</h1>
  <p id="statusBody">Resolving <code>/item?id=...</code> from static observatory archive.</p>
</div>
<script id="routerConfig" type="application/json">{cfg_json}</script>
<script>
(async () => {{
  const CFG = JSON.parse(document.getElementById("routerConfig").textContent);
  const params = new URLSearchParams(window.location.search);
  let rawId = (params.get("id") || "").trim();

  // Also accept full HN URL passed in ?id= or path /item/<id>
  if (rawId && !/^\\d+$/.test(rawId)) {{
    const m = rawId.match(/[?&]id=(\\d+)/) || rawId.match(/(\\d+)/);
    rawId = m ? m[1] : "";
  }}
  if (!rawId) {{
    const pm = window.location.pathname.match(/\\/item(?:s)?\\/(\\d+)(?:\\.html|\\/)?$/);
    if (pm) rawId = pm[1];
  }}

  const siteBase = window.location.pathname
    .replace(/\\/item(?:\\.html|\\/)?$/, "")
    .replace(/\\/items\\/\\d+(?:\\.html|\\/)?$/, "")
    .replace(/\\/404\\.html$/, "")
    .replace(/\\/$/, "");
  const indexHref = (siteBase || ".") + "/";

  const titleEl = document.getElementById("statusTitle");
  const bodyEl = document.getElementById("statusBody");
  const shellEl = document.getElementById("routerStatus");

  if (!rawId || !/^\\d+$/.test(rawId)) {{
    titleEl.textContent = "Missing or Invalid Hacker News Item ID";
    bodyEl.innerHTML =
      "Append <code>?id=50472038</code> just like Hacker News (<code>/item?id=50472038</code>), or browse the published index.";
    const bar = document.createElement("div");
    bar.className = "actions";
    bar.innerHTML = `<a class="btn" href="${{indexHref}}">Open Published Index</a>`;
    shellEl.appendChild(bar);
    return;
  }}

  const artifactUrl = `${{siteBase}}/items/${{encodeURIComponent(rawId)}}.html`;
  try {{
    const resp = await fetch(artifactUrl, {{ cache: "no-cache" }});
    if (resp.ok) {{
      const htmlText = await resp.text();
      document.open();
      document.write(htmlText);
      document.close();
      return;
    }}
  }} catch (_err) {{
    // Fall through to helpful not-yet-built view
  }}

  const hnUrl = `https://news.ycombinator.com/item?id=${{encodeURIComponent(rawId)}}`;
  titleEl.textContent = `HN Item ${{rawId}} Not Yet Built`;
  bodyEl.innerHTML =
    `No pre-built observatory was found at <code>/items/${{rawId}}.html</code>. ` +
    `Trigger the GitHub Actions workflow with item ID <code>${{rawId}}</code> to publish <code>/item?id=${{rawId}}</code>:`;

  const pre = document.createElement("pre");
  pre.textContent =
    `gh workflow run ${{CFG.workflow_file}} -f target=${{rawId}}\\n` +
    `uv run --no-project python hn-comments/cli.py ${{rawId}} --open`;
  shellEl.appendChild(pre);

  const bar = document.createElement("div");
  bar.className = "actions";
  const btns = [];
  if (CFG.actions_url) {{
    btns.push(`<a class="btn" href="${{CFG.actions_url}}" target="_blank" rel="noopener">Run GitHub Workflow</a>`);
  }}
  btns.push(`<a class="btn alt" href="${{hnUrl}}" target="_blank" rel="noopener">View Original HN Thread</a>`);
  btns.push(`<a class="btn alt" href="${{indexHref}}">Published Index</a>`);
  bar.innerHTML = btns.join("");
  shellEl.appendChild(bar);
}})();
</script>
</body>
</html>
"""
    assert "#" not in doc, f"Zero-hash violated in router HTML at {doc.find('#')}"
    return doc


def _render_item_row_html(it: dict[str, Any], *, rank: int) -> str:
    """Render a classic Hacker News 3-row item block (`athing`, `subtext`, `spacer`) with zero `#`."""
    sid = int(it["story_id"])
    title = _safe_no_hash(it["story_title"])
    raw_url = str(it.get("story_url") or "")
    sitebit = _format_hn_sitebit(raw_url)
    ext_href = _safe_url_no_hash(raw_url) if sitebit else ""
    item_href = f"./item?id={sid}"

    if ext_href:
        title_link = (
            f'<a class="storylink" href="{ext_href}" rel="noopener">{title}</a>'
        )
        sitebit_html = f' <span class="sitebit comhead">(<a href="{ext_href}" rel="noopener">{sitebit}</a>)</span>'
    else:
        title_link = f'<a class="storylink" href="{item_href}">{title}</a>'
        sitebit_html = ""

    points = int(it.get("points") or 0)
    author = _safe_no_hash(it["story_author"]) if it.get("story_author") else ""
    total = int(it.get("total_comments") or 0)
    gold = int(it.get("epistemic_gold") or 0)
    grounded = int(it.get("grounded_analysis") or 0)
    useful = gold + grounded
    bs_pct = max(0.0, 100.0 - (100.0 * useful / max(1, total))) if total else 0.0

    meta_bits: list[str] = []
    if points > 0 and author:
        pt_word = "point" if points == 1 else "points"
        meta_bits.append(f"{points} {pt_word} by {author}")
    elif points > 0:
        pt_word = "point" if points == 1 else "points"
        meta_bits.append(f"{points} {pt_word}")
    elif author:
        meta_bits.append(f"by {author}")

    if total > 0:
        c_word = "comment" if total == 1 else "comments"
        meta_bits.append(f'<a href="{item_href}">{total:,} {c_word}</a>')
        meta_bits.append(
            f'<a href="{item_href}">{gold} gold &middot; {bs_pct:.0f}% bullshit</a>'
        )
    else:
        meta_bits.append(f'<a href="{item_href}">discuss</a>')

    meta_bits.append(
        f'<a href="https://news.ycombinator.com/item?id={sid}" target="_blank" rel="noopener">hn</a>'
    )
    subtext_html = " | ".join(meta_bits)

    return f"""<tr class="athing">
            <td class="title rank">{rank}.</td>
            <td class="title"><span class="titleline">{title_link}{sitebit_html}</span></td>
          </tr>
          <tr>
            <td></td>
            <td class="subtext">{subtext_html}</td>
          </tr>
          <tr class="spacer"><td colspan="2"></td></tr>"""


def render_index_html(
    items: list[dict[str, Any]],
    *,
    repo: str,
    server_url: str,
    workflow_file: str,
    frontpage_ids: Sequence[int] = (),
    frontpage_synced_utc: str = "",
) -> str:
    """Build zero-hash Hacker News style front-page index (`news.ycombinator.com` layout)."""
    actions_url = (
        f"{server_url.rstrip('/')}/{repo.strip('/')}/actions/workflows/{workflow_file}"
        if repo
        else ""
    )
    by_id = {int(it["story_id"]): it for it in items}
    fp_ordered = [by_id[int(sid)] for sid in frontpage_ids if int(sid) in by_id]
    fp_id_set = {int(it["story_id"]) for it in fp_ordered}

    main_items = fp_ordered if fp_ordered else list(items)
    past_items = (
        [it for it in items if int(it["story_id"]) not in fp_id_set]
        if fp_ordered
        else []
    )

    if main_items:
        main_rows_html = "\n          ".join(
            _render_item_row_html(it, rank=idx)
            for idx, it in enumerate(main_items, start=1)
        )
    else:
        main_rows_html = (
            '<tr><td colspan="3" class="empty-msg">No stories built yet. '
            "Run the GitHub Actions frontpage workflow or paste an item ID below.</td></tr>"
        )

    sync_label = (
        f"Synced {_safe_no_hash(frontpage_synced_utc[:16].replace('T', ' '))} UTC"
        if frontpage_synced_utc
        else "08:00 London &amp; 08:00 SF"
    )

    footer_bits = [sync_label, f"{len(items)} published"]
    if actions_url:
        footer_bits.append(
            f'<a href="{_safe_no_hash(actions_url)}" target="_blank" rel="noopener">run workflow</a>'
        )
    footer_bits.append(
        '<a href="https://news.ycombinator.com/" target="_blank" rel="noopener">news.ycombinator.com</a>'
    )
    footer_links_html = " | ".join(footer_bits)

    doc = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Hacker News // Bullshit vs. Epistemic.</title>
  <style>
    * {{ box-sizing: border-box; }}
    body {{
      margin: 8px;
      padding: 0;
      background: rgb(255, 255, 255);
      color: rgb(0, 0, 0);
      font: 10pt/1.35 Verdana, Geneva, sans-serif;
    }}
    .hnmain {{
      width: 85%;
      max-width: 1240px;
      margin: 0 auto;
      background: rgb(246, 246, 239);
    }}
    .topbar {{
      background: rgb(255, 102, 0);
      padding: 2px 4px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 8px;
      min-height: 24px;
    }}
    .topbar-left {{
      display: flex;
      align-items: center;
      flex-wrap: wrap;
      gap: 5px;
      font-size: 10pt;
      line-height: 12pt;
      color: rgb(0, 0, 0);
    }}
    .hn-logo {{
      display: inline-block;
      width: 18px;
      height: 18px;
      line-height: 16px;
      text-align: center;
      border: 1px solid rgb(255, 255, 255);
      color: rgb(255, 255, 255);
      font-weight: 700;
      font-size: 13px;
      text-decoration: none;
      flex-shrink: 0;
    }}
    a.hnname {{
      color: rgb(0, 0, 0);
      font-weight: 700;
      text-decoration: none;
      margin-right: 4px;
    }}
    .pagetop, .pagetop a, .topbar-right, .topbar-right a {{
      color: rgb(0, 0, 0);
      font-size: 10pt;
      text-decoration: none;
    }}
    .topbar-right {{
      padding-right: 4px;
      white-space: nowrap;
      font-size: 9pt;
    }}
    button.nav-btn {{
      appearance: none;
      border: 0;
      background: transparent;
      padding: 0;
      margin: 0;
      font: inherit;
      color: rgb(0, 0, 0);
      cursor: pointer;
    }}
    button.nav-btn:hover, .pagetop a:hover, .topbar-right a:hover {{
      text-decoration: underline;
    }}
    .list-pad {{
      padding: 10px 8px 4px 4px;
    }}
    table.itemlist {{
      border-collapse: collapse;
      border: 0;
      width: 100%;
    }}
    td.title {{
      font-size: 10pt;
      line-height: 14pt;
      vertical-align: top;
    }}
    td.rank {{
      color: rgb(130, 130, 130);
      text-align: right;
      padding-right: 4px;
      white-space: nowrap;
      width: 1%;
      font-variant-numeric: tabular-nums;
    }}
    td.votelinks {{
      vertical-align: top;
      text-align: center;
      width: 14px;
      padding: 0 3px 0 1px;
    }}
    a.votearrow {{
      color: rgb(153, 153, 153);
      font-size: 9pt;
      line-height: 14pt;
      text-decoration: none;
      display: inline-block;
    }}
    a.storylink {{
      color: rgb(0, 0, 0);
      text-decoration: none;
    }}
    a.storylink:visited {{
      color: rgb(130, 130, 130);
    }}
    .comhead, .comhead a {{
      font-size: 8pt;
      color: rgb(130, 130, 130);
      text-decoration: none;
    }}
    .comhead a:hover, td.subtext a:hover {{
      text-decoration: underline;
    }}
    td.subtext {{
      font-size: 7.5pt;
      line-height: 11pt;
      color: rgb(130, 130, 130);
      padding-bottom: 1px;
    }}
    td.subtext a {{
      color: rgb(130, 130, 130);
      text-decoration: none;
    }}
    tr.spacer td {{
      height: 5px;
    }}
    td.empty-msg {{
      padding: 16px 12px;
      color: rgb(130, 130, 130);
      font-size: 9.5pt;
    }}
    details.past-drawer {{
      margin: 6px 0 2px;
    }}
    summary.morelink {{
      list-style: none;
      cursor: pointer;
      padding: 4px 0 6px 32px;
      font-size: 10pt;
      color: rgb(0, 0, 0);
      user-select: none;
    }}
    summary.morelink::-webkit-details-marker {{ display: none; }}
    summary.morelink:hover {{ text-decoration: underline; }}
    table.pastlist {{
      margin-top: 4px;
      padding-top: 6px;
      border-top: 1px solid rgb(226, 226, 218);
    }}
    .hn-footer {{
      margin-top: 12px;
      border-top: 2px solid rgb(255, 102, 0);
      padding: 12px 10px 18px;
      text-align: center;
      font-size: 8pt;
      color: rgb(130, 130, 130);
    }}
    .yclinks a {{
      color: rgb(130, 130, 130);
      text-decoration: none;
    }}
    .yclinks a:hover {{
      text-decoration: underline;
    }}
    form.hn-search {{
      margin-top: 10px;
      color: rgb(130, 130, 130);
      font-size: 8.5pt;
    }}
    form.hn-search input {{
      font: 9pt/1.2 Verdana, Geneva, sans-serif;
      padding: 2px 5px;
      border: 1px solid rgb(130, 130, 130);
      background: rgb(255, 255, 255);
      color: rgb(0, 0, 0);
      max-width: 86vw;
    }}
    @media (max-width: 750px) {{
      body {{ margin: 0; }}
      .hnmain {{ width: 100%; }}
      .topbar {{ padding: 4px 6px; }}
      td.title {{ font-size: 11pt; line-height: 15pt; }}
      td.subtext {{ font-size: 8.5pt; line-height: 13pt; }}
      tr.spacer td {{ height: 7px; }}
    }}
  </style>
</head>
<body>
<div class="hnmain">
  <div class="topbar">
    <div class="topbar-left">
      <a class="hn-logo" href="./">E</a>
      <a class="hnname" href="./">Epistemic News</a>
      <span class="pagetop"><a href="https://news.ycombinator.com/" target="_blank" rel="noopener">hn</a></span>
    </div>
  </div>

  <div class="list-pad">
    <table class="itemlist" id="frontpageList">
      <tbody>
        {main_rows_html}
      </tbody>
    </table>
  </div>

  <div class="hn-footer">
    <div class="yclinks">{footer_links_html}</div>
    <form class="hn-search" id="jumpForm">
      <label for="hnInput">Open item:</label>
      <input type="text" id="hnInput" size="28" placeholder="ID or news.ycombinator.com/item?id=..." required>
    </form>
  </div>
</div>
<script>
document.getElementById("jumpForm").addEventListener("submit", (ev) => {{
  ev.preventDefault();
  const raw = document.getElementById("hnInput").value.trim();
  const m = raw.match(/[?&]id=(\\d+)/) || raw.match(/^(\\d+)$/) || raw.match(/(\\d{{5,}})/);
  if (m) {{
    window.location.href = `./item?id=${{encodeURIComponent(m[1])}}`;
  }}
}});
const pastBtn = document.getElementById("openPastBtn");
const pastDrawer = document.getElementById("pastDrawer");
if (pastBtn && pastDrawer) {{
  pastBtn.addEventListener("click", () => {{
    pastDrawer.open = true;
    pastDrawer.scrollIntoView({{ behavior: "smooth", block: "start" }});
  }});
}}
</script>
</body>
</html>
"""
    assert "#" not in doc, f"Zero-hash violated in index HTML at {doc.find('#')}"
    return doc


def build_pages_site(
    *,
    site_dir: Path,
    source_dir: Path = HERE,
    repo: str = "",
    server_url: str = "https://github.com",
    workflow_file: str = "hn-observatory-pages.yml",
    force_ids: set[int] | None = None,
    frontpage_ids: Sequence[int] | None = None,
    frontpage_synced_utc: str = "",
    prune_older_than_days: int = 90,
    prune_trigger_mb: float = 500.0,
    max_site_mb: float = 750.0,
    now_utc: datetime | None = None,
) -> dict[str, Any]:
    """Build or incrementally update a GitHub Pages directory with `/item?id=<id>` routing.

    Explicitly refreshed `force_ids` always overwrite `items/<id>.html`. Other baseline
    `show-me-hn-<id>.html` files in `source_dir` never overwrite a newer/larger version
    already published on `gh-pages`. Keeps all items until total `items/` size reaches
    `prune_trigger_mb`, then prunes unpinned items older than `prune_older_than_days`
    (and oldest unpinned items if exceeding `max_site_mb`) to stay safely under GitHub
    Pages' 1 GB limit.
    """
    ref_now = (now_utc or datetime.now(tz=UTC)).astimezone(UTC)
    site_dir = Path(site_dir)
    items_dir = site_dir / "items"
    items_dir.mkdir(parents=True, exist_ok=True)
    forced = set(force_ids or set())

    # Copy `show-me-hn-<id>.html` observatories without regressing fresher gh-pages builds
    copied_ids: list[int] = []
    skipped_fresher_ids: list[int] = []
    source_repo_ids: set[int] = set()
    for src_html in sorted(Path(source_dir).glob("show-me-hn-*.html")):
        m = ITEM_FILE_RE.match(src_html.name)
        if not m:
            continue
        item_id = int(m.group(1))
        source_repo_ids.add(item_id)
        raw_html = src_html.read_text(encoding="utf-8")
        assert "#" not in raw_html, f"Zero-hash mandate violated in {src_html}"
        dst = items_dir / f"{item_id}.html"
        if (
            dst.is_file()
            and item_id not in forced
            and src_html.resolve() != dst.resolve()
        ):
            src_meta = extract_item_summary(src_html, item_id)
            dst_meta = extract_item_summary(dst, item_id)
            src_key = (
                str(src_meta.get("t2_ref_utc") or ""),
                int(src_meta.get("total_comments") or 0),
            )
            dst_key = (
                str(dst_meta.get("t2_ref_utc") or ""),
                int(dst_meta.get("total_comments") or 0),
            )
            if dst_key > src_key:
                skipped_fresher_ids.append(item_id)
                continue
        if src_html.resolve() != dst.resolve():
            shutil.copyfile(src_html, dst)
        copied_ids.append(item_id)

    # Persist or restore Live HN Front Page ordering (`frontpage.json`) across single-item builds
    fp_json_path = site_dir / "frontpage.json"
    resolved_fp_ids: list[int] = []
    resolved_fp_utc = frontpage_synced_utc
    if frontpage_ids is not None:
        resolved_fp_ids = [int(x) for x in frontpage_ids if int(x) > 0]
        if not resolved_fp_utc:
            resolved_fp_utc = ref_now.isoformat()
        fp_json_path.write_text(
            json.dumps(
                {"synced_utc": resolved_fp_utc, "frontpage_ids": resolved_fp_ids},
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
    elif fp_json_path.is_file():
        try:
            fp_saved = json.loads(fp_json_path.read_text(encoding="utf-8"))
            resolved_fp_ids = [
                int(x) for x in (fp_saved.get("frontpage_ids") or []) if int(x) > 0
            ]
            resolved_fp_utc = str(fp_saved.get("synced_utc") or "")
        except Exception:
            resolved_fp_ids = []

    # Scan all published `items/<id>.html` and enforce safe-under-1GB archive retention
    pinned_ids = {50467087} | forced | source_repo_ids | set(resolved_fp_ids)
    raw_entries: list[tuple[int, Path, dict[str, Any], int, datetime]] = []
    total_bytes = 0
    for pub_html in sorted(items_dir.glob("*.html")):
        pm = PUBLISHED_ITEM_RE.match(pub_html.name)
        if not pm:
            continue
        sid = int(pm.group(1))
        meta = extract_item_summary(pub_html, sid)
        fsize = pub_html.stat().st_size
        total_bytes += fsize
        raw_entries.append(
            (sid, pub_html, meta, fsize, _parse_item_timestamp(meta, pub_html))
        )

    pruned_ids: list[int] = []
    trigger_bytes = int(prune_trigger_mb * 1024 * 1024)
    cap_bytes = int(max_site_mb * 1024 * 1024)
    cutoff_dt = ref_now - timedelta(days=max(1, int(prune_older_than_days)))

    if total_bytes > trigger_bytes:
        kept_after_age: list[tuple[int, Path, dict[str, Any], int, datetime]] = []
        for entry in raw_entries:
            sid, pub_html, _meta, fsize, item_dt = entry
            if sid not in pinned_ids and item_dt < cutoff_dt:
                pub_html.unlink(missing_ok=True)
                total_bytes -= fsize
                pruned_ids.append(sid)
            else:
                kept_after_age.append(entry)
        raw_entries = kept_after_age

    if total_bytes > cap_bytes:
        # Evict oldest unpinned items first until safely under `max_site_mb`
        evictable = sorted(
            [e for e in raw_entries if e[0] not in pinned_ids],
            key=lambda e: (e[4], e[0]),
        )
        evicted_set: set[int] = set()
        for sid, pub_html, _meta, fsize, _dt in evictable:
            if total_bytes <= cap_bytes:
                break
            pub_html.unlink(missing_ok=True)
            total_bytes -= fsize
            pruned_ids.append(sid)
            evicted_set.add(sid)
        raw_entries = [e for e in raw_entries if e[0] not in evicted_set]

    summaries: list[dict[str, Any]] = [e[2] for e in raw_entries]
    summaries.sort(key=lambda x: int(x["story_id"]), reverse=True)

    (site_dir / ".nojekyll").write_text("", encoding="utf-8")

    router_html = render_item_router_html(
        repo=repo,
        server_url=server_url,
        workflow_file=workflow_file,
    )
    (site_dir / "item.html").write_text(router_html, encoding="utf-8")
    (site_dir / "404.html").write_text(router_html, encoding="utf-8")

    index_html = render_index_html(
        summaries,
        repo=repo,
        server_url=server_url,
        workflow_file=workflow_file,
        frontpage_ids=resolved_fp_ids,
        frontpage_synced_utc=resolved_fp_utc,
    )
    (site_dir / "index.html").write_text(index_html, encoding="utf-8")

    catalog = {
        "updated_utc": ref_now.isoformat(),
        "total_published": len(summaries),
        "total_size_mb": round(total_bytes / (1024.0 * 1024.0), 2),
        "frontpage_synced_utc": resolved_fp_utc,
        "frontpage_ids": [
            sid
            for sid in resolved_fp_ids
            if any(int(s["story_id"]) == sid for s in summaries)
        ],
        "uri_template": "/item?id={story_id}",
        "items": summaries,
    }
    (site_dir / "catalog.json").write_text(
        json.dumps(catalog, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return {
        "site_dir": str(site_dir),
        "copied_ids": copied_ids,
        "skipped_fresher_ids": skipped_fresher_ids,
        "pruned_ids": pruned_ids,
        "frontpage_ids": catalog["frontpage_ids"],
        "published_ids": [int(x["story_id"]) for x in summaries],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--site-dir", type=Path, default=None, help="Output GitHub Pages directory"
    )
    parser.add_argument(
        "--source-dir",
        type=Path,
        default=HERE,
        help="Directory containing show-me-hn-<id>.html files",
    )
    parser.add_argument("--repo", default="", help="owner/repo slug for workflow links")
    parser.add_argument(
        "--server-url", default="https://github.com", help="GitHub server base URL"
    )
    parser.add_argument(
        "--workflow-file", default="hn-observatory-pages.yml", help="Workflow filename"
    )
    parser.add_argument(
        "--force-id",
        type=int,
        action="append",
        default=[],
        help="Story ID explicitly refreshed in this run (always overwrites gh-pages copy)",
    )
    parser.add_argument(
        "--frontpage-manifest",
        type=Path,
        default=None,
        help="Path to frontpage sync manifest JSON emitted by `cli.py frontpage`",
    )
    parser.add_argument(
        "--prune-older-than-days",
        type=int,
        default=90,
        help="Age threshold in days for pruning unpinned items when site grows large (default: 90)",
    )
    parser.add_argument(
        "--prune-trigger-mb",
        type=float,
        default=500.0,
        help="Total items/ size in MB above which >90d unpinned items are pruned (default: 500)",
    )
    parser.add_argument(
        "--max-site-mb",
        type=float,
        default=750.0,
        help="Hard ceiling in MB for items/ directory before oldest unpinned eviction (default: 750)",
    )
    parser.add_argument(
        "--check-schedule",
        action="store_true",
        help="Evaluate whether --cron-expr matches 08:00 Europe/London or 08:00 America/Los_Angeles and exit",
    )
    parser.add_argument(
        "--cron-expr", default="", help="UTC cron string from github.event.schedule"
    )
    parser.add_argument(
        "--now-utc",
        default="",
        help="Optional ISO-8601 UTC override for schedule evaluation",
    )
    args = parser.parse_args()

    if args.check_schedule:
        override_dt = (
            datetime.fromisoformat(args.now_utc.replace("Z", "+00:00")).astimezone(UTC)
            if args.now_utc
            else None
        )
        sched_res = evaluate_schedule_window(args.cron_expr, now_utc=override_dt)
        print(json.dumps(sched_res, indent=2))
        return

    if args.site_dir is None:
        parser.error("--site-dir is required unless --check-schedule is set")

    fp_ids: list[int] | None = None
    fp_utc = ""
    forced_set = set(args.force_id)
    if args.frontpage_manifest is not None and args.frontpage_manifest.is_file():
        fp_doc = json.loads(args.frontpage_manifest.read_text(encoding="utf-8"))
        fp_ids = [int(x) for x in (fp_doc.get("frontpage_ids") or []) if int(x) > 0]
        fp_utc = str(fp_doc.get("synced_utc") or "")
        forced_set.update(
            int(x) for x in (fp_doc.get("built_ids") or fp_ids) if int(x) > 0
        )

    res = build_pages_site(
        site_dir=args.site_dir,
        source_dir=args.source_dir,
        repo=args.repo,
        server_url=args.server_url,
        workflow_file=args.workflow_file,
        force_ids=forced_set,
        frontpage_ids=fp_ids,
        frontpage_synced_utc=fp_utc,
        prune_older_than_days=args.prune_older_than_days,
        prune_trigger_mb=args.prune_trigger_mb,
        max_site_mb=args.max_site_mb,
    )
    print(json.dumps(res, indent=2))


if __name__ == "__main__":
    main()
