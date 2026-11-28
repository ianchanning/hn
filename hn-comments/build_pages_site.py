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
import json
from pathlib import Path
import re
import shutil
import subprocess
from typing import Any
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE if (HERE / "elm").is_dir() else HERE.parent
ELM_DIR = REPO_ROOT / "elm"
ELM_DIST_DIR = ELM_DIR / "dist"
ELM_OBSERVATORY_JS = ELM_DIST_DIR / "observatory.js"
ELM_STATIC_DIR = ELM_DIR / "static"
ELM_STYLE_CSS = ELM_STATIC_DIR / "style.css"


def _get_observatory_js() -> str:
    """Read compiled Elm bundle, building it if missing."""
    if not ELM_OBSERVATORY_JS.is_file():
        subprocess.run(["npm", "run", "build"], cwd=ELM_DIR, check=True)
    return ELM_OBSERVATORY_JS.read_text(encoding="utf-8")



def _get_style_css() -> str:
    """Read consolidated Elm styles, guaranteeing zero `#` characters."""
    if ELM_STYLE_CSS.is_file():
        css = ELM_STYLE_CSS.read_text(encoding="utf-8")
        assert "#" not in css, f"Zero-hash violated in {ELM_STYLE_CSS}"
        return css
    return ""


ITEM_FILE_RE = re.compile(r"^show-me-hn-(\d+)\.html$")
PUBLISHED_ITEM_RE = re.compile(r"^(\d+)\.html$")
OBS_JSON_RE = re.compile(
    r'<script\s+id=["\']observatoryData["\']\s+type=["\']application/json["\']>(.*?)</script>',
    flags=re.S,
)


def _format_utc_stamp(raw_utc: str) -> str:
    """Format an ISO timestamp as `YYYY-MM-DD HH:MM UTC`."""
    cleaned = str(raw_utc or "").strip()
    if cleaned:
        try:
            dt = datetime.fromisoformat(cleaned.replace("Z", "+00:00"))
            dt_utc = dt.astimezone(UTC) if dt.tzinfo else dt.replace(tzinfo=UTC)
            return dt_utc.strftime("%Y-%m-%d %H:%M UTC")
        except ValueError:
            return f"{cleaned[:16].replace('T', ' ')} UTC"
    return datetime.now(tz=UTC).strftime("%Y-%m-%d %H:%M UTC")


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
        "item_href": f"./item?id={item_id}",
        "points": points,
        "story_author": story_author,
        "total_comments": int(len(comments)),
        "epistemic_gold": int(tiers.get("epistemic_gold") or 0),
        "grounded_analysis": int(tiers.get("grounded_analysis") or 0),
        "t2_ref_utc": t2_utc,
        "size_kb": round(html_path.stat().st_size / 1024.0, 1),
    }


ROUTER_SHELL = HERE / "shells" / "item-router.html"
ROUTER_CONFIG_TOKEN = "<!-- ROUTER_CONFIG -->"


def render_item_router_html(*, repo: str, server_url: str, workflow_file: str) -> str:
    """Build zero-hash `item.html` / `404.html` by stamping config into static shell."""
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
    shell = ROUTER_SHELL.read_text(encoding="utf-8")
    assert ROUTER_CONFIG_TOKEN in shell, f"Missing {ROUTER_CONFIG_TOKEN} in {ROUTER_SHELL}"
    doc = shell.replace(ROUTER_CONFIG_TOKEN, cfg_json)
    assert "#" not in doc, f"Zero-hash violated in router HTML at {doc.find('#')}"
    return doc


def render_index_html(
    items: list[dict[str, Any]],
    *,
    repo: str = "",
    server_url: str = "",
    workflow_file: str = "",
    frontpage_ids: Sequence[int] = (),
    frontpage_synced_utc: str = "",
    updated_utc: str = "",
) -> str:
    """Build zero-hash Hacker News front-page index mounting Elm observatory."""
    by_id = {int(it["story_id"]): it for it in items}
    fp_ordered = [sid for sid in frontpage_ids if int(sid) in by_id]

    formatted_updated = _format_utc_stamp(updated_utc or frontpage_synced_utc)

    clean_items: list[dict[str, Any]] = []
    for it in items:
        clean_it = dict(it)
        clean_it["story_title"] = str(clean_it.get("story_title") or "")
        clean_it["item_href"] = f"./item?id={clean_it['story_id']}"
        clean_items.append(clean_it)

    catalog = {
        "updated_utc": formatted_updated,
        "total_published": len(clean_items),
        "total_size_mb": round(
            sum(float(it.get("size_kb") or 0.0) for it in clean_items) / 1024.0, 2
        ),
        "frontpage_synced_utc": frontpage_synced_utc,
        "frontpage_ids": fp_ordered,
        "uri_template": "./item?id={story_id}",
        "items": clean_items,
    }
    catalog_json = (
        json.dumps(catalog, ensure_ascii=False)
        .replace("#", "\\u0023")
    )
    observatory_js = _get_observatory_js()
    style_css = _get_style_css()

    doc = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Better Signal News</title>
  <link rel="apple-touch-icon" sizes="180x180" href="/apple-touch-icon.png">
  <link rel="icon" type="image/png" sizes="32x32" href="/favicon-32x32.png">
  <link rel="icon" type="image/png" sizes="16x16" href="/favicon-16x16.png">
  <link rel="manifest" href="/site.webmanifest">
  <style>
{style_css}
  </style>
</head>
<body>
<div id="elm-root"></div>
<script id="catalogData" type="application/json">{catalog_json}</script>
<script>
{observatory_js}
</script>
<script>
document.addEventListener("click", (ev) => {{
  const a = ev.target.closest("a");
  if (!a || !a.href || ev.ctrlKey || ev.metaKey || ev.shiftKey || ev.altKey || a.target === "_blank") return;
  const hrefAttr = a.getAttribute("href") || "";
  if (hrefAttr.startsWith("./item?id=") || hrefAttr.startsWith("/item?id=") || hrefAttr.startsWith("item?id=")) {{
    const m = hrefAttr.match(/[?&]id=(\\d+)/);
    if (m) {{
      ev.preventDefault();
      window.location.href = `./items/${{encodeURIComponent(m[1])}}.html`;
    }}
  }}
}});
document.addEventListener("submit", (ev) => {{
  if (ev.target && ev.target.id === "jumpForm") {{
    ev.preventDefault();
    const raw = (document.getElementById("hnInput")?.value || "").trim();
    const m = raw.match(/[?&]id=(\\d+)/) || raw.match(/^(\\d+)$/) || raw.match(/(\\d{{5,}})/);
    if (m) {{
      window.location.href = `./items/${{encodeURIComponent(m[1])}}.html`;
    }}
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

    # Copy favicon assets and PWA manifest to site root if present in elm/static/
    for fname in (
        "apple-touch-icon.png",
        "favicon-32x32.png",
        "favicon-16x16.png",
        "favicon.ico",
        "site.webmanifest",
        "android-chrome-192x192.png",
        "bs.svg",
    ):
        src_fav = ELM_STATIC_DIR / fname
        if src_fav.is_file():
            shutil.copyfile(src_fav, site_dir / fname)

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

    last_updated_utc = (
        resolved_fp_utc or ref_now.isoformat()
        if frontpage_ids is not None
        else ref_now.isoformat()
        if forced
        else resolved_fp_utc or ref_now.isoformat()
    )
    index_html = render_index_html(
        summaries,
        repo=repo,
        server_url=server_url,
        workflow_file=workflow_file,
        frontpage_ids=resolved_fp_ids,
        frontpage_synced_utc=resolved_fp_utc,
        updated_utc=last_updated_utc,
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
