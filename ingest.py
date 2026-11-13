"""Live & cached Hacker News multi-page HTML, Algolia tree, and story-URL ingester.

Supports any HN item ID (`50472038`) or URL (`https://news.ycombinator.com/item?id=50472038`),
crawling `?p=1..N` paginated HTML for exact `news.arc` DOM ranks and fade classes (`c00..cDD`),
Algolia's item API for complete comment/dead-comment structure, the story's external article text
(with clean fallback to HN `toptext` + title), and SQLite-cached author profiles.
"""

from collections.abc import Callable
import html
import json
from pathlib import Path
import re
import time
from typing import Any
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
        url = f"https://news.ycombinator.com/item?id={sid}&p={p}"
        for attempt in range(3):
            try:
                raw_bytes, _ = fetch_url_bytes(url, timeout=20.0, max_bytes=8_000_000)
                return raw_bytes.decode("utf-8", errors="replace")
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
        raw_pages = fetch_hn_html_pages(story_id, max_pages=max_pages)
        for old_p in item_dir.glob("live_p*.html"):
            old_p.unlink()
        existing_pages = []
        for idx, page_html in enumerate(raw_pages, start=1):
            p_path = item_dir / f"live_p{idx}.html"
            p_path.write_text(page_html, encoding="utf-8")
            existing_pages.append(p_path)

        alg_data = fetch_algolia_item(story_id)
        alg_file.write_text(json.dumps(alg_data, ensure_ascii=False), encoding="utf-8")
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
