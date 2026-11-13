#!/usr/bin/env python3
"""Story-agnostic CLI for the Hacker News Epistemic Observatory.

Examples:
    uv run --no-project python hn-comments/cli.py 50472038 --open
    uv run --no-project python hn-comments/cli.py "https://news.ycombinator.com/item?id=50471731" --open
    uv run --no-project python hn-comments/cli.py build 50467087 --offline
    uv run --no-project python hn-comments/cli.py rank 50472038 --top 10
"""

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

import build_dashboard
import corpus_science
from ingest import ingest_story, parse_hn_item_id
import ranker

KNOWN_SUBCOMMANDS = frozenset({"build", "ingest", "rank"})


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

    return parser


def normalize_argv(argv: list[str]) -> list[str]:
    """Default bare `<item_id_or_url>` invocations to the `build` subcommand."""
    if not argv:
        return argv
    first = argv[0]
    if first in KNOWN_SUBCOMMANDS or first in ("-h", "--help"):
        return argv
    return ["build", *argv]


def run_cli(argv: list[str] | None = None) -> dict[str, Any]:
    """Execute CLI command and return structured execution summary."""
    raw_args = list(sys.argv[1:] if argv is None else argv)
    args = build_parser().parse_args(normalize_argv(raw_args))
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

    # For frozen 50467087 without --refresh, use canonical corpus_v2.json if available
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

    if args.command == "rank":
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
    out_html = build_dashboard.build_html(
        story_id,
        corpus=None if use_frozen else rows,
        manifest=None if use_frozen else manifest,
        ranked_comments=ranked,
        out_path=args.out,
        data_dir=args.data_dir,
        offline=args.offline,
    )

    if args.open:
        subprocess.run(["open", str(out_html)], check=True)

    summary = {
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
    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        print(
            f"[HN {story_id}] Built zero-hash observatory: {out_html} "
            f"({summary['html_size_kb']} KB, {len(ranked)} comments, "
            f"gold={tiers.get('epistemic_gold', 0)}, grounded={tiers.get('grounded_analysis', 0)})"
        )
        for item in top_preview:
            print(
                f"  Signal {item['signal_rank']:2d} (was HN POS {str(item['live_dom_rank']):>4s}) "
                f"@{item['author']:16s} [{item['facet']}] {item['excerpt']}"
            )
    return summary


if __name__ == "__main__":
    run_cli()
