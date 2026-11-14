"""Live & cached Hacker News multi-page HTML, Algolia tree, and story-URL ingester.

Supports any HN item ID (`50472038`) or URL (`https://news.ycombinator.com/item?id=50472038`),
crawling `?p=1..N` paginated HTML for exact `news.arc` DOM ranks and fade classes (`c00..cDD`),
Algolia's item API for complete comment/dead-comment structure, the story's external article text
(with clean fallback to HN `toptext` + title), and SQLite-cached author profiles.
"""

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
import html
import json
from pathlib import Path
import re
import time
from typing import Any
import urllib.error
from urllib.parse import parse_qs, urlparse
import urllib.request

from author_cache import AuthorCache, build_ssl_context
from parse_corpus import (
    DATA_DIR,
    extract_next_page_num,
    extract_story_metadata_from_html,
    parse_live_html_pages,
)

BROWSER_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

# Remember within a batch process if news.ycombinator.com blocks datacenter IPs (HTTP 403/419/429)
_HN_HTML_BLOCKED_IN_PROCESS = False


def parse_hn_item_id(target: str | int) -> int:
    """Extract positive integer HN item ID from bare ID, HN URL, or `item?id=` query string.

    Args:
        target: Integer ID, numeric string, or Hacker News item URL.

    Returns:
        Positive integer HN item ID.

    Raises:
        ValueError: If no valid positive HN item ID can be parsed.
    """
    if isinstance(target, int):
        if target <= 0:
            raise ValueError(f"HN item ID must be positive, got {target}")
        return target

    raw = str(target).strip()
    if not raw:
        raise ValueError("Empty HN target")
    if raw.isdigit():
        val = int(raw)
        if val <= 0:
            raise ValueError(f"HN item ID must be positive, got {val}")
        return val

    parsed = urlparse(raw if "://" in raw else f"https://news.ycombinator.com/{raw.lstrip('/')}")
    host = parsed.netloc.lower().removeprefix("www.")
    if host and host not in ("news.ycombinator.com", "hn.algolia.com"):
        raise ValueError(f"Unsupported non-HN URL host '{host}' in '{raw}'")

    qs = parse_qs(parsed.query)
    if "id" in qs and qs["id"] and qs["id"][0].isdigit():
        val = int(qs["id"][0])
        if val > 0:
            return val

    alg_m = re.search(r"/items/(\d+)\b", parsed.path)
    if alg_m:
        return int(alg_m.group(1))

    raise ValueError(f"Could not parse HN item ID from '{target}'")


def fetch_url_bytes(
    url: str,
    *,
    timeout: float = 15.0,
    max_bytes: int = 4_000_000,
    accept: str = "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
) -> tuple[bytes, str]:
    """Fetch up to `max_bytes` from `url` with verified TLS context."""
    ctx = build_ssl_context()
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": BROWSER_UA,
            "Accept": accept,
            "Accept-Language": "en-US,en;q=0.9",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
        ctype = str(resp.headers.get("Content-Type") or "")
        body = resp.read(max_bytes)
    return body, ctype


def fetch_hn_html_pages(
    story_id: int,
    *,
    max_pages: int = 25,
    polite_delay_sec: float = 0.20,
    page_fetcher: Callable[[int, int], str] | None = None,
) -> list[str]:
    """Fetch `?p=1..N` HTML pages from `news.ycombinator.com` until pagination terminates."""
    pages: list[str] = []
    seen_cids: set[int] = set()
    cur_page = 1

    def _default_fetch(sid: int, p: int) -> str:
        global _HN_HTML_BLOCKED_IN_PROCESS
        if _HN_HTML_BLOCKED_IN_PROCESS:
            return ""
        url = f"https://news.ycombinator.com/item?id={sid}&p={p}"
        for attempt in range(3):
            try:
                raw_bytes, _ = fetch_url_bytes(url, timeout=15.0, max_bytes=8_000_000)
                return raw_bytes.decode("utf-8", errors="replace")
            except urllib.error.HTTPError as exc:
                # Fail fast on datacenter IP blocks (403/419/429) so Algolia+Firebase fallback runs immediately
                if exc.code in (403, 419, 429):
                    _HN_HTML_BLOCKED_IN_PROCESS = True
                    raise
                if attempt == 2:
                    raise
                time.sleep(0.5 * (attempt + 1))
            except Exception:
                if attempt == 2:
                    raise
                time.sleep(0.5 * (attempt + 1))
        return ""

    fetch_fn = page_fetcher or _default_fetch

    while len(pages) < max_pages:
        if pages and page_fetcher is None and polite_delay_sec > 0:
            time.sleep(polite_delay_sec)
        raw_html = fetch_fn(story_id, cur_page)
        if not raw_html:
            break
        page_cids = {int(m.group(1)) for m in re.finditer(r'<tr[^>]*\bcomtr\b[^>]*\bid=["\'](\d+)["\']', raw_html)}
        new_cids = page_cids - seen_cids
        # Always keep page 1 (even for 0-comment stories); for p >= 2 require unseen comments
        if cur_page > 1 and not new_cids:
            break
        pages.append(raw_html)
        seen_cids.update(page_cids)

        next_p = extract_next_page_num(raw_html, current_page=cur_page)
        if next_p is None:
            break
        cur_page = next_p

    return pages


def fetch_algolia_item(story_id: int) -> dict[str, Any]:
    """Fetch structured item + comment tree from Algolia HN API (with Firebase metadata fallback)."""
    alg_url = f"https://hn.algolia.com/api/v1/items/{story_id}"
    try:
        raw_bytes, _ = fetch_url_bytes(alg_url, timeout=20.0, max_bytes=16_000_000, accept="application/json")
        data = json.loads(raw_bytes.decode("utf-8", errors="replace"))
        if isinstance(data, dict) and data.get("id"):
            return data
    except Exception:
        pass

    fb_url = f"https://hacker-news.firebaseio.com/v0/item/{story_id}.json"
    try:
        raw_bytes, _ = fetch_url_bytes(fb_url, timeout=12.0, max_bytes=2_000_000, accept="application/json")
        fb = json.loads(raw_bytes.decode("utf-8", errors="replace"))
        if isinstance(fb, dict) and fb.get("id"):
            return {
                "id": int(fb["id"]),
                "title": fb.get("title") or "",
                "url": fb.get("url") or "",
                "author": fb.get("by") or "",
                "points": int(fb.get("score") or 0),
                "created_at_i": int(fb.get("time") or 0),
                "text": fb.get("text") or "",
                "children": [],
            }
    except Exception:
        pass
    return {"id": story_id, "children": []}


def fetch_firebase_items_batch(
    item_ids: list[int],
    *,
    max_workers: int = 24,
    item_fetcher: Callable[[int], dict[str, Any] | None] | None = None,
) -> dict[int, dict[str, Any]]:
    """Concurrently fetch official Firebase v0 item records (`kids` news.arc rank order & metadata)."""
    if not item_ids:
        return {}
    ctx = build_ssl_context()

    def _fetch_one(iid: int) -> dict[str, Any] | None:
        fb_url = f"https://hacker-news.firebaseio.com/v0/item/{iid}.json"
        try:
            req = urllib.request.Request(fb_url, headers={"User-Agent": BROWSER_UA, "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=8.0, context=ctx) as resp:
                data = json.loads(resp.read(1_500_000).decode("utf-8", errors="replace"))
            return data if isinstance(data, dict) and data.get("id") else None
        except Exception:
            return None

    fn = item_fetcher or _fetch_one
    unique_ids = list(dict.fromkeys(item_ids))
    out: dict[int, dict[str, Any]] = {}
    workers = max(1, min(max_workers, len(unique_ids)))
    if workers == 1:
        for iid in unique_ids:
            rec = fn(iid)
            if rec is not None:
                out[iid] = rec
        return out

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futs = {pool.submit(fn, iid): iid for iid in unique_ids}
        for fut in as_completed(futs):
            iid = futs[fut]
            try:
                rec = fut.result()
            except Exception:
                rec = None
            if rec is not None:
                out[iid] = rec
    return out


def synthesize_hn_html_from_api(
    story_id: int,
    algolia_data: dict[str, Any],
    *,
    firebase_items: dict[int, dict[str, Any]] | None = None,
) -> str:
    """Synthesize canonical HN item HTML from Algolia tree + Firebase `kids` `news.arc` ordering.

    Used automatically when `news.ycombinator.com` blocks datacenter/CI runner IPs (e.g. HTTP 419
    on GitHub Actions) while official Algolia + Firebase APIs remain unrestricted.
    """
    fb_map = firebase_items or {}
    story_fb = fb_map.get(story_id) or {}

    title = html.escape(str(algolia_data.get("title") or story_fb.get("title") or f"HN Item {story_id}"))
    raw_url = str(algolia_data.get("url") or story_fb.get("url") or f"item?id={story_id}")
    href = html.escape(raw_url, quote=True)
    points = int(algolia_data.get("points") or story_fb.get("score") or 0)
    author = html.escape(str(algolia_data.get("author") or story_fb.get("by") or "hn"))
    created_i = int(algolia_data.get("created_at_i") or story_fb.get("time") or 0)
    created_iso = (
        str(algolia_data.get("created_at") or "")
        or (datetime.fromtimestamp(created_i, tz=UTC).strftime("%Y-%m-%dT%H:%M:%S") if created_i else "")
    )
    toptext_raw = str(story_fb.get("text") or algolia_data.get("text") or "")

    kids_order_map: dict[int, dict[int, int]] = {}
    dead_ids: set[int] = set()
    for iid, rec in fb_map.items():
        if rec.get("dead") or rec.get("deleted"):
            dead_ids.add(iid)
        kids = rec.get("kids")
        if isinstance(kids, list) and kids:
            kids_order_map[iid] = {int(cid): idx for idx, cid in enumerate(kids) if isinstance(cid, int)}

    def _ordered_children(parent_id: int, children: list[dict[str, Any]]) -> list[dict[str, Any]]:
        rank_lookup = kids_order_map.get(parent_id)
        if not rank_lookup or len(children) <= 1:
            return children
        return sorted(
            children,
            key=lambda ch: (rank_lookup.get(int(ch.get("id") or 0), 10**9), int(ch.get("id") or 0)),
        )

    def _live_subtree_size(node: dict[str, Any]) -> int:
        total = 1
        for ch in node.get("children") or []:
            cid = int(ch.get("id") or 0)
            if not cid or cid in dead_ids or (not ch.get("text") and not ch.get("author")):
                continue
            total += _live_subtree_size(ch)
        return total

    tr_rows: list[str] = []

    def _walk(children: list[dict[str, Any]], parent_id: int, depth: int) -> None:
        for ch in _ordered_children(parent_id, children):
            raw_cid = ch.get("id")
            if raw_cid is None:
                continue
            cid = int(raw_cid)
            if cid in dead_ids:
                continue
            raw_text = str(ch.get("text") or "")
            raw_au = str(ch.get("author") or "")
            if not raw_text and not raw_au:
                continue
            au_esc = html.escape(raw_au or "[deleted]", quote=True)
            c_ts = int(ch.get("created_at_i") or created_i)
            c_iso = str(ch.get("created_at") or "") or (
                datetime.fromtimestamp(c_ts, tz=UTC).strftime("%Y-%m-%dT%H:%M:%S") if c_ts else ""
            )
            age_title = html.escape(f"{c_iso} {c_ts}".strip(), quote=True)
            sub_n = _live_subtree_size(ch)
            tr_rows.append(
                f'<tr class="athing comtr" id="{cid}"><td><table><tr>'
                f'<td class="ind" indent="{depth}"></td>'
                f'<td class="default"><span class="comhead">'
                f'<a href="user?id={au_esc}">{au_esc}</a> '
                f'<span class="age" title="{age_title}">1h</span> '
                f'<a class="togg clicky" id="{cid}" n="{sub_n}" href="javascript:void(0)">[-]</a>'
                f'</span><div class="comment"><div class="commtext c00">{raw_text}</div>'
                f'<div class="reply"></div></div></td></tr></table></td></tr>'
            )
            _walk(list(ch.get("children") or []), cid, depth + 1)

    _walk(list(algolia_data.get("children") or []), story_id, 0)
    toptext_div = f'<div class="toptext">{toptext_raw}</div>' if toptext_raw else ""
    story_age = html.escape(f"{created_iso} {created_i}".strip(), quote=True)
    return (
        f'<html lang="en" op="item"><head><title>{title} | Hacker News</title></head><body>'
        f'<table class="fatitem"><tr class="athing submission" id="{story_id}">'
        f'<td class="title"><span class="titleline"><a href="{href}">{title}</a></span></td></tr>'
        f'<tr><td class="subtext"><span class="subline"><span class="score">{points} points</span> '
        f'by <a href="user?id={author}">{author}</a> '
        f'<span class="age" title="{story_age}">1h</span></span></td></tr>'
        f'<tr><td>{toptext_div}</td></tr></table>'
        f'<table class="comment-tree">{"".join(tr_rows)}</table></body></html>'
    )


def build_api_fallback_html(
    story_id: int,
    algolia_data: dict[str, Any],
    *,
    max_parent_nodes: int = 350,
    firebase_fetcher: Callable[[int], dict[str, Any] | None] | None = None,
) -> str:
    """Fetch Firebase `kids` ordering for multi-child branches and synthesize HN item HTML."""
    # Collect multi-child parent IDs breadth-first so root & shallow subtrees get exact news.arc order
    bfs_queue: list[dict[str, Any]] = [algolia_data]
    parent_ids: list[int] = [story_id]
    while bfs_queue and len(parent_ids) < max_parent_nodes + 1:
        node = bfs_queue.pop(0)
        children = list(node.get("children") or [])
        nid = int(node.get("id") or 0)
        if nid and nid != story_id and len(children) >= 2:
            parent_ids.append(nid)
        bfs_queue.extend(children)

    fb_items = fetch_firebase_items_batch(parent_ids, item_fetcher=firebase_fetcher)
    return synthesize_hn_html_from_api(story_id, algolia_data, firebase_items=fb_items)


def fetch_frontpage_story_ids(
    limit: int = 30,
    *,
    skip_jobs: bool = True,
    top_ids_fetcher: Callable[[], list[int]] | None = None,
    item_fetcher: Callable[[int], dict[str, Any] | None] | None = None,
) -> list[int]:
    """Fetch the live Hacker News Front Page story IDs (`1..limit`) via Firebase v0 + Algolia fallback.

    Filters out deleted/dead items and YC job postings (`type == "job"`, which have no comment
    threads) while preserving exact live HN front-page ordering.
    """
    target_limit = max(1, int(limit))
    candidate_ids: list[int] = []

    if top_ids_fetcher is not None:
        candidate_ids = [int(x) for x in top_ids_fetcher() if int(x) > 0]
    else:
        try:
            raw_bytes, _ = fetch_url_bytes(
                "https://hacker-news.firebaseio.com/v0/topstories.json",
                timeout=15.0,
                max_bytes=2_000_000,
                accept="application/json",
            )
            parsed = json.loads(raw_bytes.decode("utf-8", errors="replace"))
            if isinstance(parsed, list):
                candidate_ids = [int(x) for x in parsed if isinstance(x, int) and x > 0]
        except Exception:
            candidate_ids = []

        if not candidate_ids:
            try:
                alg_bytes, _ = fetch_url_bytes(
                    f"https://hn.algolia.com/api/v1/search?tags=front_page&hitsPerPage={max(30, target_limit + 10)}",
                    timeout=15.0,
                    max_bytes=4_000_000,
                    accept="application/json",
                )
                alg_json = json.loads(alg_bytes.decode("utf-8", errors="replace"))
                for hit in alg_json.get("hits") or []:
                    oid = str(hit.get("objectID") or "")
                    if oid.isdigit() and int(oid) > 0:
                        candidate_ids.append(int(oid))
            except Exception:
                candidate_ids = []

    if not candidate_ids:
        return []

    # Probe slightly beyond `target_limit` so skipping 1-2 YC job ads still yields a full Top 30
    probe_slice = candidate_ids[: target_limit + (12 if skip_jobs else 0)]
    if not skip_jobs and item_fetcher is None:
        return probe_slice[:target_limit]

    fb_meta = fetch_firebase_items_batch(probe_slice, max_workers=16, item_fetcher=item_fetcher)
    selected: list[int] = []
    seen: set[int] = set()
    for sid in probe_slice:
        if sid in seen:
            continue
        seen.add(sid)
        meta = fb_meta.get(sid)
        if isinstance(meta, dict):
            if meta.get("deleted") or meta.get("dead"):
                continue
            if skip_jobs and str(meta.get("type") or "story").lower() == "job":
                continue
        selected.append(sid)
        if len(selected) >= target_limit:
            break
    return selected


def extract_readable_article_text(raw_html: str, max_chars: int = 32_000) -> str:
    """Extract clean article prose, title, and meta descriptions from arbitrary web HTML."""
    title_m = re.search(r"<title[^>]*>(.*?)</title>", raw_html, flags=re.S | re.I)
    title_txt = html.unescape(re.sub(r"<[^>]+>", " ", title_m.group(1))).strip() if title_m else ""

    metas: list[str] = []
    for meta_m in re.finditer(
        r'<meta[^>]+(?:name|property)=["\'](?:description|og:description|twitter:description|og:title)["\'][^>]*>',
        raw_html,
        flags=re.I,
    ):
        c_m = re.search(r'content=["\']([^"\']+)["\']', meta_m.group(0), flags=re.I)
        if c_m:
            metas.append(html.unescape(c_m.group(1)).strip())

    # Remove non-prose containers before tag stripping
    cleaned = re.sub(r"<!--.*?-->", " ", raw_html, flags=re.S)
    cleaned = re.sub(
        r"<(script|style|noscript|svg|canvas|iframe|nav|footer|aside|form)\b[^>]*>.*?</\1>",
        " ",
        cleaned,
        flags=re.S | re.I,
    )

    # Prefer <article> or <main> if it carries substantive prose
    focus = cleaned
    for tag_name in ("article", "main"):
        blocks = re.findall(rf"<{tag_name}\b[^>]*>(.*?)</{tag_name}>", cleaned, flags=re.S | re.I)
        joined = "\n\n".join(blocks)
        if len(re.sub(r"<[^>]+>", " ", joined).split()) >= 80:
            focus = joined
            break

    focus = re.sub(r"<(?:p|div|section|li|h[1-6]|tr|br)\b[^>]*>", "\n", focus, flags=re.I)
    prose = html.unescape(re.sub(r"<[^>]+>", " ", focus))
    lines = [re.sub(r"[ \t]+", " ", ln).strip() for ln in prose.splitlines()]
    # Keep informative lines while dropping tiny nav crumbs
    good_lines = [ln for ln in lines if len(ln) >= 25 or (len(ln.split()) >= 4)]
    combined = "\n".join([x for x in [title_txt, *metas, *good_lines] if x])
    return combined[:max_chars].strip()


def fetch_story_article(
    story_url: str | None,
    *,
    story_title: str = "",
    toptext: str = "",
    article_fetcher: Callable[[str], tuple[bytes, str]] | None = None,
) -> dict[str, Any]:
    """Fetch and extract plain text from the linked story URL with graceful fallback."""
    url = (story_url or "").strip()
    url_slug_words = re.sub(r"[^a-zA-Z0-9]+", " ", urlparse(url).path) if url else ""
    base_parts = [p for p in (story_title, toptext, url_slug_words) if p.strip()]

    if not url or url.startswith("item?id="):
        return {
            "story_url": "",
            "article_source": "toptext" if toptext.strip() else "title_only",
            "article_text": "\n\n".join(base_parts).strip(),
        }

    fetch_fn = article_fetcher or (lambda u: fetch_url_bytes(u, timeout=12.0, max_bytes=2_500_000))
    try:
        raw_bytes, ctype = fetch_fn(url)
        ctype_l = ctype.lower()
        if "pdf" in ctype_l or url.lower().endswith(".pdf"):
            return {
                "story_url": url,
                "article_source": "pdf_slug_fallback",
                "article_text": "\n\n".join(base_parts).strip(),
            }
        decoded = raw_bytes.decode("utf-8", errors="replace")
        if "html" in ctype_l or "<html" in decoded[:1000].lower() or "<body" in decoded[:1500].lower():
            extracted = extract_readable_article_text(decoded)
        else:
            extracted = decoded[:32_000].strip()

        if len(extracted.split()) >= 20:
            full_text = "\n\n".join([*base_parts, extracted]).strip()
            return {
                "story_url": url,
                "article_source": "fetched_url",
                "article_text": full_text[:36_000],
            }
    except Exception:
        pass

    return {
        "story_url": url,
        "article_source": "fallback_metadata",
        "article_text": "\n\n".join(base_parts).strip(),
    }


def ingest_story(
    target: str | int,
    *,
    data_dir: Path = DATA_DIR,
    author_cache: AuthorCache | None = None,
    offline: bool = False,
    refresh: bool = False,
    max_pages: int = 25,
) -> dict[str, Any]:
    """Ingest any HN story into `data_dir/items/<story_id>/` (or resolve frozen 50467087).

    Args:
        target: HN item ID or URL.
        data_dir: Base `data/` directory.
        author_cache: Optional `AuthorCache` instance (defaults to `data_dir/author_cache.db`).
        offline: If True, never make network requests; read existing local snapshots only.
        refresh: If True, re-fetch live HTML/Algolia even if cached files exist in `items/<id>/`.
        max_pages: Upper bound on `?p=1..N` HTML pagination pages.

    Returns:
        Dictionary containing paths, parsed story metadata, HTML pages, Algolia dict,
        article text, and resolved author profiles.
    """
    story_id = parse_hn_item_id(target)
    cache = author_cache or AuthorCache(db_path=data_dir / "author_cache.db")

    # Seed SQLite author cache once from frozen authors.json if empty
    legacy_authors = data_dir / "authors.json"
    if legacy_authors.is_file() and cache.count() == 0:
        cache.seed_from_json(legacy_authors)

    # Support frozen dual-snapshot 50467087 directly when offline or not refreshing
    frozen_t2 = data_dir / "hn_50467087_live_t2.html"
    if story_id == 50467087 and frozen_t2.is_file() and not refresh:
        t1_path = data_dir / "hn_50467087_live.html"
        alg_path = data_dir / "hn_50467087_algolia.json"
        art_path = data_dir / "article_ap_jensen_huang.md"
        authors_map = (
            json.loads(legacy_authors.read_text(encoding="utf-8"))
            if legacy_authors.is_file()
            else {}
        )
        t2_rows, _ref_ts, meta = parse_live_html_pages([frozen_t2], story_id=50467087)
        alg_data = json.loads(alg_path.read_text(encoding="utf-8")) if alg_path.is_file() else {}
        return {
            "story_id": 50467087,
            "is_frozen_benchmark": True,
            "item_dir": data_dir,
            "html_pages_t1": [t1_path] if t1_path.is_file() else [],
            "html_pages_t2": [frozen_t2],
            "algolia": alg_data,
            "authors": authors_map,
            "article_text": art_path.read_text(encoding="utf-8") if art_path.is_file() else "",
            "article_source": "frozen_ap_wire",
            "story_meta": {
                **meta,
                "story_title": meta.get("story_title") or alg_data.get("title") or "Jensen Huang resigns",
                "story_url": meta.get("story_url") or alg_data.get("url") or "",
            },
        }

    item_dir = data_dir / "items" / str(story_id)
    item_dir.mkdir(parents=True, exist_ok=True)
    existing_pages = sorted(
        item_dir.glob("live_p*.html"),
        key=lambda p: int(re.search(r"live_p(\d+)\.html$", p.name).group(1)),  # type: ignore[union-attr]
    )
    alg_file = item_dir / "algolia.json"
    art_file = item_dir / "story_article.txt"
    meta_file = item_dir / "story_meta.json"

    if (not existing_pages or refresh) and not offline:
        alg_data = fetch_algolia_item(story_id)
        alg_file.write_text(json.dumps(alg_data, ensure_ascii=False), encoding="utf-8")
        try:
            raw_pages = fetch_hn_html_pages(story_id, max_pages=max_pages)
        except Exception:
            raw_pages = []
        has_live_rows = any("<tr" in p and "comtr" in p for p in raw_pages)
        if not raw_pages or (alg_data.get("children") and not has_live_rows):
            raw_pages = [build_api_fallback_html(story_id, alg_data)]
        for old_p in item_dir.glob("live_p*.html"):
            old_p.unlink()
        existing_pages = []
        for idx, page_html in enumerate(raw_pages, start=1):
            p_path = item_dir / f"live_p{idx}.html"
            p_path.write_text(page_html, encoding="utf-8")
            existing_pages.append(p_path)
    else:
        if not existing_pages:
            raise FileNotFoundError(
                f"No cached HTML pages found for HN item {story_id} under {item_dir} (offline={offline})"
            )
        alg_data = json.loads(alg_file.read_text(encoding="utf-8")) if alg_file.is_file() else {"id": story_id}

    rows, _ref_ts, html_meta = parse_live_html_pages(existing_pages, story_id=story_id)
    story_title = (
        html_meta.get("story_title")
        or str(alg_data.get("title") or "")
        or f"HN Item {story_id}"
    )
    story_url = html_meta.get("story_url") or str(alg_data.get("url") or "")
    toptext = html_meta.get("toptext") or ""

    if (not art_file.is_file() or refresh) and not offline:
        art_info = fetch_story_article(story_url, story_title=story_title, toptext=toptext)
        art_file.write_text(art_info["article_text"], encoding="utf-8")
        article_source = art_info["article_source"]
        article_text = art_info["article_text"]
    else:
        article_text = art_file.read_text(encoding="utf-8") if art_file.is_file() else f"{story_title}\n\n{toptext}".strip()
        article_source = "cached_article"

    # Collect all comment authors from both HTML and Algolia tree
    usernames: set[str] = {r["author"] for r in rows if not r["author"].startswith("[")}

    def _collect_alg_authors(node: dict[str, Any]) -> None:
        au = node.get("author")
        if isinstance(au, str) and au and not au.startswith("["):
            usernames.add(au)
        for ch in node.get("children") or []:
            _collect_alg_authors(ch)

    _collect_alg_authors(alg_data)
    authors_map = cache.resolve_authors(usernames, offline=offline)

    story_meta = {
        **html_meta,
        "story_id": story_id,
        "story_title": story_title,
        "story_url": story_url,
        "points": int(html_meta.get("points") or alg_data.get("points") or 0),
        "story_author": html_meta.get("story_author") or str(alg_data.get("author") or ""),
        "pages_fetched": len(existing_pages),
        "article_source": article_source,
    }
    meta_file.write_text(json.dumps(story_meta, indent=2, ensure_ascii=False), encoding="utf-8")

    return {
        "story_id": story_id,
        "is_frozen_benchmark": False,
        "item_dir": item_dir,
        "html_pages_t1": [],
        "html_pages_t2": existing_pages,
        "algolia": alg_data,
        "authors": authors_map,
        "article_text": article_text,
        "article_source": article_source,
        "story_meta": story_meta,
    }
