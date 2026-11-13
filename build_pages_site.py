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
from datetime import UTC, datetime
import html
import json
from pathlib import Path
import re
import shutil
from typing import Any

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


def extract_item_summary(html_path: Path, item_id: int) -> dict[str, Any]:
    """Extract compact catalog metadata from a built zero-hash observatory HTML file."""
    raw = html_path.read_text(encoding="utf-8")
    m = OBS_JSON_RE.search(raw)
    if not m:
        return {
            "story_id": item_id,
            "story_title": f"HN Item {item_id}",
            "story_url": "",
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
    t2_utc = str(manifest.get("t2_ref_utc") or "")
    return {
        "story_id": item_id,
        "story_title": str(title),
        "story_url": story_url,
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
      margin: 0;
      background: rgb(247, 247, 245);
      color: rgb(13, 13, 13);
      font: 15px/1.5 "Helvetica Neue", Helvetica, Arial, sans-serif;
      -webkit-font-smoothing: antialiased;
    }}
    .shell {{
      max-width: 820px;
      margin: 56px auto;
      padding: 24px 28px 32px;
      border-top: 3px solid rgb(13, 13, 13);
      border-bottom: 1px solid rgb(13, 13, 13);
      background: rgb(255, 255, 253);
    }}
    .eyebrow {{
      font: 700 11px/1.3 ui-monospace, SFMono-Regular, Menlo, monospace;
      letter-spacing: 0.12em;
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


def render_index_html(
    items: list[dict[str, Any]],
    *,
    repo: str,
    server_url: str,
    workflow_file: str,
) -> str:
    """Build zero-hash landing directory listing all published `/item?id=<id>` observatories."""
    actions_url = (
        f"{server_url.rstrip('/')}/{repo.strip('/')}/actions/workflows/{workflow_file}"
        if repo
        else ""
    )
    rows_html: list[str] = []
    for it in items:
        sid = int(it["story_id"])
        title = _safe_no_hash(it["story_title"])
        total = int(it["total_comments"])
        gold = int(it["epistemic_gold"])
        grounded = int(it["grounded_analysis"])
        useful = gold + grounded
        useful_pct = 100.0 * useful / max(1, total) if total else 0.0
        rows_html.append(
            f"""<tr>
              <td><a class="uri-link" href="./item?id={sid}">/item?id={sid}</a></td>
              <td style="text-align:left"><strong><a class="title-link" href="./item?id={sid}">{title}</a></strong></td>
              <td>{total:,}</td>
              <td>{gold} Gold / {grounded} Grounded ({useful_pct:.1f}%)</td>
              <td><a class="hn-orig" href="https://news.ycombinator.com/item?id={sid}" target="_blank" rel="noopener">news.ycombinator.com/item?id={sid}</a></td>
            </tr>"""
        )

    table_body = "\n".join(rows_html) if rows_html else '<tr><td colspan="5">No items published yet.</td></tr>'
    actions_btn = (
        f'<a class="btn alt" href="{_safe_no_hash(actions_url)}" target="_blank" rel="noopener">Trigger Workflow on GitHub</a>'
        if actions_url
        else ""
    )

    doc = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>HN Epistemic Observatory // Published Mirror Index</title>
  <style>
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: rgb(247, 247, 245);
      color: rgb(13, 13, 13);
      font: 15px/1.5 "Helvetica Neue", Helvetica, Arial, sans-serif;
      -webkit-font-smoothing: antialiased;
    }}
    .wrap {{
      max-width: 1240px;
      margin: 0 auto;
      padding: 28px 28px 64px;
    }}
    header {{
      border-top: 3px solid rgb(13, 13, 13);
      border-bottom: 1px solid rgb(13, 13, 13);
      padding: 16px 0 24px;
      margin-bottom: 24px;
    }}
    .eyebrow {{
      font: 700 11px/1.4 ui-monospace, SFMono-Regular, Menlo, monospace;
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
      font-size: clamp(32px, 4.5vw, 58px);
      line-height: 0.98;
      letter-spacing: -0.04em;
      margin: 14px 0 12px;
      font-weight: 800;
    }}
    h1 .accent {{ color: rgb(255, 51, 0); }}
    .launcher {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      padding: 16px;
      background: rgb(239, 239, 234);
      border: 1px solid rgb(13, 13, 13);
      margin-bottom: 24px;
      align-items: center;
    }}
    .launcher input {{
      flex: 1;
      min-width: 260px;
      padding: 9px 12px;
      border: 1px solid rgb(13, 13, 13);
      background: rgb(255, 255, 253);
      font: 13px/1.3 ui-monospace, SFMono-Regular, Menlo, monospace;
    }}
    button.btn, a.btn {{
      appearance: none;
      padding: 9px 14px;
      border: 1px solid rgb(13, 13, 13);
      background: rgb(13, 13, 13);
      color: rgb(247, 247, 245);
      font: 600 12px/1.2 ui-monospace, SFMono-Regular, Menlo, monospace;
      text-decoration: none;
      cursor: pointer;
    }}
    a.btn.alt {{
      background: rgb(255, 255, 253);
      color: rgb(13, 13, 13);
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      background: rgb(255, 255, 253);
      border: 1px solid rgb(13, 13, 13);
      font-size: 13.5px;
    }}
    th, td {{
      padding: 10px 12px;
      border-bottom: 1px solid rgb(214, 214, 208);
      text-align: right;
      font-variant-numeric: tabular-nums;
    }}
    th:first-child, td:first-child {{
      text-align: left;
      font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    }}
    th:nth-child(2) {{ text-align: left; }}
    th {{
      background: rgb(236, 236, 231);
      font: 700 10px/1.3 ui-monospace, SFMono-Regular, Menlo, monospace;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      color: rgb(60, 60, 58);
    }}
    a.uri-link {{
      color: rgb(255, 51, 0);
      font-weight: 700;
      text-decoration: none;
    }}
    a.title-link {{
      color: rgb(13, 13, 13);
      text-decoration: underline;
      text-underline-offset: 3px;
    }}
    a.hn-orig {{
      color: rgb(90, 90, 88);
      font: 12px/1.3 ui-monospace, SFMono-Regular, Menlo, monospace;
    }}
  </style>
</head>
<body>
<div class="wrap">
  <header>
    <div class="eyebrow">
      <span>NYX EPISTEMIC OBSERVATORY // GITHUB PAGES MIRROR</span>
      <span><strong>{len(items)} PUBLISHED THREADS</strong> // URI PARITY: <code>/item?id=&lt;HN_ID&gt;</code></span>
    </div>
    <h1>Same <code>/item?id=</code> URI. <span class="accent">Zero Bullshit.</span></h1>
    <p style="max-width:860px;color:rgb(52,52,50);margin:0">
      Swap <code>https://news.ycombinator.com</code> with this GitHub Pages base URL:
      every built story resolves at its exact Hacker News relative URI <code>/item?id=&lt;id&gt;</code>.
    </p>
  </header>

  <form class="launcher" id="jumpForm">
    <input type="text" id="hnInput" placeholder="Paste https://news.ycombinator.com/item?id=50472038 or item ID..." required>
    <button type="submit" class="btn">Open /item?id=...</button>
    {actions_btn}
  </form>

  <div style="overflow-x:auto">
    <table>
      <thead>
        <tr>
          <th>Pages Mirror URI</th>
          <th>Story Title</th>
          <th>Comments</th>
          <th>Epistemic Signal</th>
          <th>Original Hacker News</th>
        </tr>
      </thead>
      <tbody>
        {table_body}
      </tbody>
    </table>
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
) -> dict[str, Any]:
    """Build or incrementally update a GitHub Pages directory with `/item?id=<id>` routing."""
    site_dir = Path(site_dir)
    items_dir = site_dir / "items"
    items_dir.mkdir(parents=True, exist_ok=True)

    # Copy all `show-me-hn-<id>.html` observatories from source_dir into `site_dir/items/<id>.html`
    copied_ids: list[int] = []
    for src_html in sorted(Path(source_dir).glob("show-me-hn-*.html")):
        m = ITEM_FILE_RE.match(src_html.name)
        if not m:
            continue
        item_id = int(m.group(1))
        raw_html = src_html.read_text(encoding="utf-8")
        assert "#" not in raw_html, f"Zero-hash mandate violated in {src_html}"
        dst = items_dir / f"{item_id}.html"
        if src_html.resolve() != dst.resolve():
            shutil.copyfile(src_html, dst)
        copied_ids.append(item_id)

    # Scan all published `items/<id>.html` (including stories built in prior workflow runs!)
    summaries: list[dict[str, Any]] = []
    for pub_html in sorted(items_dir.glob("*.html")):
        pm = PUBLISHED_ITEM_RE.match(pub_html.name)
        if not pm:
            continue
        sid = int(pm.group(1))
        summaries.append(extract_item_summary(pub_html, sid))

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
    )
    (site_dir / "index.html").write_text(index_html, encoding="utf-8")

    catalog = {
        "updated_utc": datetime.now(tz=UTC).isoformat(),
        "total_published": len(summaries),
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
        "published_ids": [int(x["story_id"]) for x in summaries],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site-dir", type=Path, required=True, help="Output GitHub Pages directory")
    parser.add_argument(
        "--source-dir",
        type=Path,
        default=HERE,
        help="Directory containing show-me-hn-<id>.html files",
    )
    parser.add_argument("--repo", default="", help="owner/repo slug for workflow links")
    parser.add_argument("--server-url", default="https://github.com", help="GitHub server base URL")
    parser.add_argument("--workflow-file", default="hn-observatory-pages.yml", help="Workflow filename")
    args = parser.parse_args()

    res = build_pages_site(
        site_dir=args.site_dir,
        source_dir=args.source_dir,
        repo=args.repo,
        server_url=args.server_url,
        workflow_file=args.workflow_file,
    )
    print(json.dumps(res, indent=2))


if __name__ == "__main__":
    main()
