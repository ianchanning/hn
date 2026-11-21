"""Parse Hacker News item HTML (?p=1..N pagination), story headers, and Algolia trees."""

from collections.abc import Sequence
from datetime import UTC, datetime
import html
import json
from pathlib import Path
import re
from typing import Any

DATA_DIR = Path(__file__).resolve().parent / "data"

FADE_TIER_MAP: dict[str, int] = {
    "c00": 0,
    "c5a": 1,
    "c73": 2,
    "c88": 3,
    "c9c": 4,
    "cae": 5,
    "cbe": 6,
    "cce": 7,
    "cdd": 8,
}


def strip_html(raw_html: str) -> tuple[str, list[str], int]:
    """Convert HN comment HTML into plain text, extracted URLs, and quote line count.

    Args:
        raw_html: Raw inner HTML inside HN commtext container.

    Returns:
        Tuple of (clean_text, urls, quote_lines).
    """
    urls = [html.unescape(u) for u in re.findall(r'href=["\']([^"\']+)["\']', raw_html)]
    text = re.sub(r"<p\s*/?>", "\n\n", raw_html, flags=re.I)
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)
    text = html.unescape(text).strip()
    quote_lines = sum(
        1 for line in text.splitlines() if line.lstrip().startswith(">")
    )
    return text, urls, quote_lines


def extract_next_page_num(raw_html: str, current_page: int = 1) -> int | None:
    """Detect HN `morelink` pagination anchor and return the next `?p=N` page integer if > current_page."""
    for tag_m in re.finditer(r"<a\b[^>]*>", raw_html, flags=re.I):
        tag = tag_m.group(0)
        if not re.search(r'\bclass=["\'][^"\']*\bmorelink\b', tag, flags=re.I):
            continue
        href_m = re.search(r'\bhref=["\']([^"\']+)["\']', tag, flags=re.I)
        if not href_m:
            continue
        href = html.unescape(href_m.group(1))
        p_m = re.search(r"[?&]p=(\d+)\b", href)
        if p_m:
            next_p = int(p_m.group(1))
            if next_p > current_page:
                return next_p
    return None


def extract_story_metadata_from_html(raw_html: str, default_story_id: int = 0) -> dict[str, Any]:
    """Extract story ID, title, external URL, points, author, timestamp, and toptext from HN item HTML."""
    story_id = default_story_id
    sub_m = re.search(r'<tr[^>]*\bclass=["\'][^"\']*\bsubmission\b[^"\']*["\'][^>]*\bid=["\'](\d+)["\']', raw_html)
    if sub_m:
        story_id = int(sub_m.group(1))
    elif not story_id:
        canon_m = re.search(r'item\?id=(\d+)', raw_html)
        if canon_m:
            story_id = int(canon_m.group(1))

    title = ""
    story_url = ""
    tl_m = re.search(
        r'<span[^>]*\bclass=["\']titleline["\'][^>]*>\s*<a[^>]*\bhref=["\']([^"\']+)["\'][^>]*>(.*?)</a>',
        raw_html,
        flags=re.S | re.I,
    )
    if tl_m:
        raw_href = html.unescape(tl_m.group(1)).strip()
        title = html.unescape(re.sub(r"<[^>]+>", "", tl_m.group(2))).strip()
        if not raw_href.startswith("item?id="):
            story_url = raw_href
    if not title:
        t_m = re.search(r"<title>(.*?)</title>", raw_html, flags=re.S | re.I)
        if t_m:
            title = html.unescape(t_m.group(1)).removesuffix(" | Hacker News").strip()

    pts_m = re.search(r'<span[^>]*\bclass=["\']score["\'][^>]*>(\d+)\s+points?</span>', raw_html, flags=re.I)
    points = int(pts_m.group(1)) if pts_m else 0

    subline_m = re.search(r'<span[^>]*\bclass=["\']subline["\'][^>]*>(.*?)</span>\s*</td>', raw_html, flags=re.S | re.I)
    sub_block = subline_m.group(1) if subline_m else ""
    auth_m = re.search(r'<a[^>]*href=["\']user\?id=([^"\'&>]+)["\'][^>]*>([^<]+)</a>', sub_block)
    author = html.unescape(auth_m.group(2)) if auth_m else ""

    story_iso = ""
    story_ts = 0.0
    age_m = re.search(r'<span[^>]*class=["\']age["\'][^>]*title=["\']([^"\']+)["\']', sub_block)
    if age_m:
        parts = age_m.group(1).split()
        story_iso = parts[0]
        if len(parts) > 1 and parts[1].isdigit():
            story_ts = float(parts[1])
        else:
            try:
                dt = datetime.fromisoformat(story_iso.replace("Z", "+00:00"))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=UTC)
                story_ts = dt.timestamp()
            except ValueError:
                story_ts = 0.0

    toptext_m = re.search(r'<div[^>]*\bclass=["\']toptext["\'][^>]*>(.*?)</div>', raw_html, flags=re.S | re.I)
    toptext_html = toptext_m.group(1) if toptext_m else ""
    toptext_clean, toptext_urls, _ = strip_html(toptext_html) if toptext_html else ("", [], 0)

    return {
        "story_id": story_id,
        "story_title": title,
        "story_url": story_url,
        "points": points,
        "story_author": author,
        "story_created_iso": story_iso,
        "story_unix_ts": story_ts,
        "toptext_html": toptext_html,
        "toptext": toptext_clean,
        "toptext_urls": toptext_urls,
    }


def _parse_comment_rows_from_raw(
    raw: str,
    *,
    seen_ids: set[int],
    rows: list[dict[str, Any]],
    page_num: int,
) -> float:
    """Append unseen comment rows from a single HN HTML page and return max unix_ts seen."""
    parts = re.split(r'(?=<tr[^>]*\bcomtr\b[^>]*>)', raw)
    max_ts = 0.0

    for part in parts[1:]:
        id_m = re.match(r'<tr[^>]*\bid=["\'](\d+)["\']', part)
        if not id_m:
            continue
        cid = int(id_m.group(1))
        if cid in seen_ids:
            continue
        seen_ids.add(cid)

        ind_m = re.search(r'<td[^>]*class=["\']ind["\'][^>]*indent=["\'](\d+)["\']', part)
        if not ind_m:
            w_m = re.search(r'<img[^>]*src=["\']s\.gif["\'][^>]*width=["\'](\d+)["\']', part)
            depth = int(w_m.group(1)) // 40 if w_m else 0
        else:
            depth = int(ind_m.group(1))

        user_m = re.search(r'<a[^>]*href=["\']user\?id=([^"\'&>]+)["\'][^>]*>([^<]+)</a>', part)
        author = html.unescape(user_m.group(2)) if user_m else "[deleted]"

        age_m = re.search(r'<span[^>]*class=["\']age["\'][^>]*title=["\']([^"\']+)["\']', part)
        iso_str = ""
        unix_ts = 0.0
        if age_m:
            title_parts = age_m.group(1).split()
            iso_str = title_parts[0]
            if len(title_parts) > 1 and title_parts[1].isdigit():
                unix_ts = float(title_parts[1])
            else:
                dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=UTC)
                unix_ts = dt.timestamp()
            if unix_ts > max_ts:
                max_ts = unix_ts

        togg_m = re.search(r'<a[^>]*class=["\']togg[^"\']*["\'][^>]*\bn=["\'](\d+)["\']', part)
        subtree_n = int(togg_m.group(1)) if togg_m else 1

        comm_m = re.search(
            r'<div[^>]*class=["\']commtext\s+([a-zA-Z0-9]+)["\'][^>]*>(.*?)</div>\s*<div[^>]*class=["\']reply["\']',
            part,
            flags=re.S,
        )
        if not comm_m:
            comm_m = re.search(
                r'<span[^>]*class=["\']commtext\s+([a-zA-Z0-9]+)["\'][^>]*>(.*?)</span>',
                part,
                flags=re.S,
            )

        fade_class = comm_m.group(1) if comm_m else "c00"
        comm_html = comm_m.group(2) if comm_m else ""
        text, urls, quote_lines = strip_html(comm_html)
        downvote_tier = FADE_TIER_MAP.get(fade_class.lower(), 0)

        rows.append(
            {
                "id": cid,
                "author": author,
                "created_iso": iso_str,
                "unix_ts": unix_ts,
                "depth": depth,
                "live_dom_rank": len(rows) + 1,
                "page": page_num,
                "subtree_size": subtree_n,
                "fade_class": fade_class,
                "downvote_tier": downvote_tier,
                "is_dead": False,
                "text": text,
                "urls": urls,
                "quote_lines": quote_lines,
            }
        )
    return max_ts


def parse_live_html_pages(
    html_pages: Sequence[Path | str],
    story_id: int | None = None,
) -> tuple[list[dict[str, Any]], float, dict[str, Any]]:
    """Parse 1..N paginated HN HTML pages in exact DOM order with continuous tree reconstruction.

    Args:
        html_pages: Ordered sequence of saved `Path` objects or raw HTML strings (`?p=1..N`).
        story_id: Optional explicit story ID override; otherwise auto-detected from page 1 HTML.

    Returns:
        Tuple of (ordered comment dicts, snapshot reference unix timestamp, story metadata dict).
    """
    if not html_pages:
        return [], 0.0, {"story_id": story_id or 0, "pages_parsed": 0}

    rows: list[dict[str, Any]] = []
    seen_ids: set[int] = set()
    max_ts = 0.0
    meta: dict[str, Any] = {}

    for idx, src in enumerate(html_pages, start=1):
        raw = src.read_text(encoding="utf-8", errors="replace") if isinstance(src, Path) else str(src)
        if idx == 1:
            meta = extract_story_metadata_from_html(raw, default_story_id=story_id or 0)
        page_max_ts = _parse_comment_rows_from_raw(raw, seen_ids=seen_ids, rows=rows, page_num=idx)
        if page_max_ts > max_ts:
            max_ts = page_max_ts

    resolved_story_id = int(story_id or meta.get("story_id") or 0)
    meta["story_id"] = resolved_story_id
    meta["pages_parsed"] = len(html_pages)
    if max_ts == 0.0 and meta.get("story_unix_ts"):
        max_ts = float(meta["story_unix_ts"])

    # Reconstruct parent_id and root_id continuously across ?p=1..N
    stack: list[int] = []
    root_id = 0
    for row in rows:
        d = int(row["depth"])
        if d <= len(stack):
            stack = stack[:d]
        parent_id = stack[-1] if stack else resolved_story_id
        if d == 0 or not root_id:
            root_id = row["id"]
        row["parent_id"] = parent_id
        row["root_id"] = root_id
        if d < len(stack):
            stack[d] = row["id"]
        else:
            stack.append(row["id"])

    return rows, max_ts, meta


def parse_live_html(
    html_path: Path,
    story_id: int | None = None,
) -> tuple[list[dict[str, Any]], float]:
    """Parse all comment rows in exact HN DOM rank order from a single live item HTML file."""
    rows, max_ts, _meta = parse_live_html_pages([html_path], story_id=story_id)
    return rows, max_ts


def merge_algolia_dead_comments(
    rows: list[dict[str, Any]],
    algolia_source: Path | dict[str, Any],
    ref_ts: float,
    story_id: int | None = None,
) -> list[dict[str, Any]]:
    """Reconcile cross-page parent pointers and append dead/flagged comments from Algolia JSON."""
    raw_alg = (
        json.loads(algolia_source.read_text(encoding="utf-8"))
        if isinstance(algolia_source, Path)
        else algolia_source
    )
    if not raw_alg:
        return rows

    resolved_story_id = int(story_id or raw_alg.get("id") or 0)
    by_id = {r["id"]: r for r in rows}
    seen_ids = set(by_id)

    def walk(node: dict[str, Any], depth: int, root_id: int) -> None:
        raw_id = node.get("id")
        if raw_id is None:
            return
        cid = int(raw_id)
        cur_root = cid if depth == 1 else root_id
        alg_parent = int(node.get("parent_id") or resolved_story_id)

        if depth >= 1:
            if cid in by_id:
                # Reconcile any cross-page split orphan whose parent_id defaulted to story_id despite depth > 0
                existing = by_id[cid]
                if existing["depth"] > 0 and existing["parent_id"] == resolved_story_id and alg_parent != resolved_story_id:
                    existing["parent_id"] = alg_parent
                if cur_root and (not existing.get("root_id") or (existing["depth"] > 0 and existing["root_id"] == cid)):
                    existing["root_id"] = cur_root
            elif cid not in seen_ids:
                raw_text = node.get("text") or ""
                text, urls, quote_lines = strip_html(raw_text)
                ts = float(node.get("created_at_i") or ref_ts)
                rows.append(
                    {
                        "id": cid,
                        "author": node.get("author") or "[flagged]",
                        "created_iso": node.get("created_at") or "",
                        "unix_ts": ts,
                        "depth": depth - 1,
                        "live_dom_rank": None,
                        "page": None,
                        "subtree_size": 1 + len(node.get("children") or []),
                        "fade_class": "dead",
                        "downvote_tier": 9,
                        "is_dead": True,
                        "text": text or "[dead/flagged]",
                        "urls": urls,
                        "quote_lines": quote_lines,
                        "parent_id": alg_parent,
                        "root_id": cur_root or cid,
                    }
                )
                seen_ids.add(cid)
        for child in node.get("children") or []:
            walk(child, depth + 1, cur_root)

    walk(raw_alg, 0, 0)
    return rows
