#!/usr/bin/env python3
"""Story-agnostic CLI for the Hacker News Epistemic Observatory.

Examples:
    uv run --no-project python hn-comments/cli.py 50472038 --open
    uv run --no-project python hn-comments/cli.py "https://news.ycombinator.com/item?id=50471731" --open
    uv run --no-project python hn-comments/cli.py build 50467087 --offline
    uv run --no-project python hn-comments/cli.py rank 50472038 --top 10
"""

from datetime import UTC, datetime
import argparse
from collections import Counter
import copy
import json
from pathlib import Path
import subprocess
import sys
from typing import Any

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from author_cache import AuthorCache
import build_dashboard
import corpus_science
from ingest import fetch_frontpage_story_ids, ingest_story, parse_hn_item_id
import ranker

KNOWN_SUBCOMMANDS = frozenset({"build", "ingest", "rank", "frontpage"})
FRONTPAGE_TOKENS = frozenset({"frontpage", "front-page", "topstories"})


def _add_common_flags(p: argparse.ArgumentParser) -> None:
    p.add_argument(
        "target",
        help="Hacker News item ID (e.g. 50472038) or URL (https://news.ycombinator.com/item?id=50472038)",
    )
    p.add_argument(
        "--data-dir",
        type=Path,
        default=HERE / "data",
        help="Directory for cached story snapshots and SQLite author_cache.db",
    )
    p.add_argument(
        "--offline",
        action="store_true",
        help="Use existing local snapshots and cached authors without network requests",
    )
    p.add_argument(
        "--refresh",
        action="store_true",
        help="Force live re-fetch of HTML pages, Algolia tree, and story article",
    )
    p.add_argument(
        "--max-pages",
        type=int,
        default=25,
        help="Maximum ?p=1..N HTML pagination pages to crawl (default: 25)",
    )
    p.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON summary on stdout",
    )


def build_parser() -> argparse.ArgumentParser:
    """Construct CLI argument parser supporting `build`, `ingest`, and `rank`."""
    parser = argparse.ArgumentParser(
        prog="hn-comments/cli.py",
        description="Ingest, rank, and compile a zero-hash Epistemic Observatory for any HN post.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_build = sub.add_parser("build", help="Ingest story, extract features, rank, and build zero-hash HTML")
    _add_common_flags(p_build)
    p_build.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Explicit output path (defaults to hn-comments/show-me-hn-<id>.html)",
    )
    p_build.add_argument(
        "--top",
        type=int,
        default=5,
        help="Number of top epistemic comments to summarize in terminal output",
    )
    p_build.add_argument(
        "--open",
        action="store_true",
        help="Open generated show-me-hn-<id>.html in default browser via `open`",
    )

    p_ingest = sub.add_parser("ingest", help="Fetch and cache ?p=1..N HTML, Algolia JSON, article, and authors")
    _add_common_flags(p_ingest)

    p_rank = sub.add_parser("rank", help="Rank comments and print top epistemic signal vs Live HN order")
    _add_common_flags(p_rank)
    p_rank.add_argument("--top", type=int, default=15, help="Number of top ranked comments to display")

    p_fp = sub.add_parser(
        "frontpage",
        help="Fetch all live HN Front Page stories (Top 30) and build zero-hash observatories",
    )
    p_fp.add_argument(
        "--limit",
        type=int,
        default=30,
        help="Maximum number of live front-page stories to build (default: 30)",
    )
    p_fp.add_argument(
        "--data-dir",
        type=Path,
        default=HERE / "data",
        help="Directory for cached story snapshots and SQLite author_cache.db",
    )
    p_fp.add_argument(
        "--out-dir",
        type=Path,
        default=HERE,
        help="Directory where show-me-hn-<id>.html files are written (default: hn-comments/)",
    )
    p_fp.add_argument(
        "--frontpage-manifest",
        type=Path,
        default=None,
        help="Optional path to write frontpage sync manifest JSON (ordered frontpage_ids + built_ids)",
    )
    p_fp.add_argument(
        "--offline",
        action="store_true",
        help="Build from existing local snapshots without network requests",
    )
    p_fp.add_argument(
        "--refresh",
        action="store_true",
        help="Force live re-fetch of HTML/API trees and story articles",
    )
    p_fp.add_argument(
        "--max-pages",
        type=int,
        default=25,
        help="Maximum ?p=1..N HTML pagination pages per story (default: 25)",
    )
    p_fp.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON summary on stdout",
    )

    return parser


def normalize_argv(argv: list[str]) -> list[str]:
    """Default bare `<item_id_or_url>` invocations to the `build` subcommand."""
    if not argv:
        return argv
    first = argv[0]
    if first in KNOWN_SUBCOMMANDS or first in ("-h", "--help"):
        return argv
    return ["build", *argv]


def _build_single_observatory(
    story_id: int,
    *,
    data_dir: Path,
    out_path: Path | None = None,
    offline: bool = False,
    refresh: bool = False,
    max_pages: int = 25,
    top_k: int = 5,
) -> dict[str, Any]:
    """Ingest, extract features, rank, and emit zero-hash `show-me-hn-<id>.html` for one story."""
    use_frozen = (
        story_id == 50467087
        and not refresh
        and (data_dir / "corpus_v2.json").is_file()
        and (data_dir / "manifest_v2.json").is_file()
    )
    if use_frozen:
        rows = json.loads((data_dir / "corpus_v2.json").read_text(encoding="utf-8"))
        manifest = json.loads((data_dir / "manifest_v2.json").read_text(encoding="utf-8"))
    else:
        rows, manifest = corpus_science.build_story_corpus(
            story_id,
            data_dir=data_dir,
            offline=offline,
            refresh=refresh,
            max_pages=max_pages,
            write_output=True,
        )

    ranked = ranker.rank_comments(copy.deepcopy(rows))
    tiers = Counter(c["tier"] for c in ranked)
    top_preview = [
        {
            "signal_rank": c["signal_rank"],
            "live_dom_rank": c["live_dom_rank"],
            "id": c["id"],
            "author": c["author"],
            "signal_score": c["signal_score"],
            "tier": c["tier"],
            "facet": c["facet"],
            "excerpt": c["text"].replace("\n", " ")[:120],
        }
        for c in ranked[: max(0, int(top_k))]
    ]

    out_html = build_dashboard.build_html(
        story_id,
        corpus=None if use_frozen else rows,
        manifest=None if use_frozen else manifest,
        ranked_comments=ranked,
        out_path=out_path,
        data_dir=data_dir,
        offline=offline,
    )
    return {
        "command": "build",
        "story_id": story_id,
        "story_title": manifest.get("story_title", f"HN {story_id}"),
        "total_comments": len(ranked),
        "pages_fetched": int((manifest.get("counts") or {}).get("pages_fetched", 1)),
        "tiers": dict(tiers),
        "facets": list((manifest.get("facet_labels") or {}).values()),
        "html_path": str(out_html),
        "html_size_kb": round(out_html.stat().st_size / 1024.0, 1),
        "zero_hash_verified": "#" not in out_html.read_text(encoding="utf-8"),
        "top": top_preview,
    }


def run_frontpage_batch(
    *,
    limit: int = 30,
    data_dir: Path = HERE / "data",
    out_dir: Path = HERE,
    frontpage_manifest: Path | None = None,
    offline: bool = False,
    refresh: bool = True,
    max_pages: int = 25,
    story_ids: list[int] | None = None,
    emit_stdout: bool = True,
    as_json: bool = False,
) -> dict[str, Any]:
    """Build or refresh observatories for all stories on the live HN Front Page."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    data_dir = Path(data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)

    # Ensure author cache DB is initialized once before batch loop
    _ = AuthorCache(db_path=data_dir / "author_cache.db")

    fp_ids = list(story_ids) if story_ids is not None else fetch_frontpage_story_ids(limit=limit)
    built_items: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []

    for rank_idx, sid in enumerate(fp_ids, start=1):
        try:
            out_file = out_dir / f"show-me-hn-{sid}.html"
            item_res = _build_single_observatory(
                sid,
                data_dir=data_dir,
                out_path=out_file,
                offline=offline,
                refresh=refresh,
                max_pages=max_pages,
                top_k=3,
            )
            item_res["frontpage_rank"] = rank_idx
            built_items.append(item_res)
            if emit_stdout and not as_json:
                print(
                    f"[FP {rank_idx:02d}/{len(fp_ids):02d}] HN {sid} — {item_res['story_title']} "
                    f"({item_res['total_comments']} comments, {item_res['html_size_kb']} KB)"
                )
        except Exception as exc:
            errors.append({"story_id": sid, "frontpage_rank": rank_idx, "error": str(exc)})
            if emit_stdout and not as_json:
                print(f"[FP {rank_idx:02d}/{len(fp_ids):02d}] WARN HN {sid} failed: {exc}", file=sys.stderr)

    if fp_ids and not built_items:
        raise RuntimeError(f"All {len(fp_ids)} front-page story builds failed: {errors[:3]}")

    synced_utc = datetime.now(tz=UTC).isoformat()
    built_ids = [int(it["story_id"]) for it in built_items]
    summary = {
        "command": "frontpage",
        "synced_utc": synced_utc,
        "requested_limit": int(limit),
        "frontpage_ids": [int(sid) for sid in fp_ids if int(sid) in set(built_ids)],
        "built_ids": built_ids,
        "built_count": len(built_items),
        "error_count": len(errors),
        "errors": errors,
        "items": [
            {
                "frontpage_rank": it["frontpage_rank"],
                "story_id": it["story_id"],
                "story_title": it["story_title"],
                "total_comments": it["total_comments"],
                "html_size_kb": it["html_size_kb"],
            }
            for it in built_items
        ],
    }

    if frontpage_manifest is not None:
        Path(frontpage_manifest).parent.mkdir(parents=True, exist_ok=True)
        Path(frontpage_manifest).write_text(
            json.dumps(summary, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    if emit_stdout and as_json:
        print(json.dumps(summary, indent=2))
    elif emit_stdout:
        print(
            f"[Frontpage Sync] Built {len(built_items)}/{len(fp_ids)} front-page observatories "
            f"(errors={len(errors)}) at {synced_utc}"
        )
    return summary


def run_cli(argv: list[str] | None = None) -> dict[str, Any]:
    """Execute CLI command and return structured execution summary."""
    raw_args = list(sys.argv[1:] if argv is None else argv)
    args = build_parser().parse_args(normalize_argv(raw_args))

    if args.command == "frontpage" or (
        args.command == "build" and str(args.target).strip().lower() in FRONTPAGE_TOKENS
    ):
        limit_val = int(getattr(args, "limit", 30))
        out_dir_val = args.out.parent if getattr(args, "out", None) is not None else getattr(args, "out_dir", HERE)
        fp_manifest = getattr(args, "frontpage_manifest", None)
        return run_frontpage_batch(
            limit=limit_val,
            data_dir=args.data_dir,
            out_dir=out_dir_val,
            frontpage_manifest=fp_manifest,
            offline=args.offline,
            refresh=args.refresh,
            max_pages=args.max_pages,
            emit_stdout=True,
            as_json=args.json,
        )

    story_id = parse_hn_item_id(args.target)

    if args.command == "ingest":
        ing = ingest_story(
            story_id,
            data_dir=args.data_dir,
            offline=args.offline,
            refresh=args.refresh,
            max_pages=args.max_pages,
        )
        summary = {
            "command": "ingest",
            "story_id": story_id,
            "story_title": ing["story_meta"].get("story_title", ""),
            "story_url": ing["story_meta"].get("story_url", ""),
            "pages_fetched": len(ing["html_pages_t2"]),
            "authors_resolved": len(ing["authors"]),
            "article_source": ing["article_source"],
            "item_dir": str(ing["item_dir"]),
        }
        if args.json:
            print(json.dumps(summary, indent=2))
        else:
            print(
                f"[HN {story_id}] Ingested '{summary['story_title']}' "
                f"({summary['pages_fetched']} page(s), {summary['authors_resolved']} authors, "
                f"article={summary['article_source']})"
            )
        return summary

    if args.command == "rank":
        use_frozen = (
            story_id == 50467087
            and not args.refresh
            and (args.data_dir / "corpus_v2.json").is_file()
            and (args.data_dir / "manifest_v2.json").is_file()
        )
        if use_frozen:
            rows = json.loads((args.data_dir / "corpus_v2.json").read_text(encoding="utf-8"))
            manifest = json.loads((args.data_dir / "manifest_v2.json").read_text(encoding="utf-8"))
        else:
            rows, manifest = corpus_science.build_story_corpus(
                story_id,
                data_dir=args.data_dir,
                offline=args.offline,
                refresh=args.refresh,
                max_pages=args.max_pages,
                write_output=True,
            )
        ranked = ranker.rank_comments(copy.deepcopy(rows))
        tiers = Counter(c["tier"] for c in ranked)
        top_preview = [
            {
                "signal_rank": c["signal_rank"],
                "live_dom_rank": c["live_dom_rank"],
                "id": c["id"],
                "author": c["author"],
                "signal_score": c["signal_score"],
                "tier": c["tier"],
                "facet": c["facet"],
                "excerpt": c["text"].replace("\n", " ")[:120],
            }
            for c in ranked[: max(0, int(args.top))]
        ]
        summary = {
            "command": "rank",
            "story_id": story_id,
            "story_title": manifest.get("story_title", f"HN {story_id}"),
            "total_comments": len(ranked),
            "tiers": dict(tiers),
            "top": top_preview,
        }
        if args.json:
            print(json.dumps(summary, indent=2))
        else:
            print(f"[HN {story_id}] {summary['story_title']} — {len(ranked)} comments ranked")
            for item in top_preview:
                print(
                    f"  #{item['signal_rank']:2d} (HN POS {str(item['live_dom_rank']):>4s}) "
                    f"@{item['author']:16s} [{item['tier']}] score={item['signal_score']:6.2f} | {item['excerpt']}"
                )
        return summary

    # Default: `build`
    summary = _build_single_observatory(
        story_id,
        data_dir=args.data_dir,
        out_path=args.out,
        offline=args.offline,
        refresh=args.refresh,
        max_pages=args.max_pages,
        top_k=int(args.top),
    )

    if args.open:
        subprocess.run(["open", summary["html_path"]], check=True)

    tiers = summary["tiers"]
    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        print(
            f"[HN {story_id}] Built zero-hash observatory: {summary['html_path']} "
            f"({summary['html_size_kb']} KB, {summary['total_comments']} comments, "
            f"gold={tiers.get('epistemic_gold', 0)}, grounded={tiers.get('grounded_analysis', 0)})"
        )
        for item in summary["top"]:
            print(
                f"  Signal {item['signal_rank']:2d} (was HN POS {str(item['live_dom_rank']):>4s}) "
                f"@{item['author']:16s} [{item['facet']}] {item['excerpt']}"
            )
    return summary


if __name__ == "__main__":
    run_cli()
