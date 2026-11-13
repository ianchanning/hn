"""Unit and integration tests for story-agnostic HN ingestion, caching, science, and CLI."""

from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parents[1]
JUDGE_DIR = HERE / "judge"
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
if str(JUDGE_DIR) not in sys.path:
    sys.path.insert(0, str(JUDGE_DIR))

from author_cache import DEFAULT_TTL_SECONDS, AuthorCache
import build_dashboard
import cli
import corpus_science
from ingest import (
    extract_readable_article_text,
    fetch_hn_html_pages,
    fetch_story_article,
    parse_hn_item_id,
)
from judge_v1 import score_ordering
from judge_v1_1 import check_invariants_v1_1
from parse_corpus import (
    extract_next_page_num,
    merge_algolia_dead_comments,
    parse_live_html_pages,
)
import ranker
from source_registry import classify_single_url, classify_urls_detailed


class TestGeneralizationPipeline(unittest.TestCase):
    """Verify story-agnostic modules, 7-day SQLite author cache, pagination, and zero-hash UI."""

    def test_parse_hn_item_id_variants(self) -> None:
        """Accept integer IDs, query strings, full HN URLs, and reject non-HN hosts."""
        self.assertEqual(parse_hn_item_id(50472038), 50472038)
        self.assertEqual(parse_hn_item_id("50472038"), 50472038)
        self.assertEqual(
            parse_hn_item_id("https://news.ycombinator.com/item?id=50472038&p=2#50472100"),
            50472038,
        )
        self.assertEqual(parse_hn_item_id("item?id=50471731"), 50471731)
        self.assertEqual(
            parse_hn_item_id("https://hn.algolia.com/api/v1/items/50472490"),
            50472490,
        )
        for bad in ("", "0", -5, "https://example.com/item?id=123", "https://news.ycombinator.com/news"):
            with self.assertRaises(ValueError):
                parse_hn_item_id(bad)

    def test_cross_domain_source_registry(self) -> None:
        """Classify RFC, arXiv, DOI, GitHub artifacts vs repos, LWN, .gov, SEC, and joke links."""
        cases = [
            ("https://datatracker.ietf.org/doc/html/rfc9110", 3, "rfc_standard"),
            ("https://www.rfc-editor.org/rfc/rfc9000", 3, "rfc_standard"),
            ("https://arxiv.org/abs/2610.20563", 3, "arxiv_preprint"),
            ("https://doi.org/10.1145/3580305.3599421", 3, "doi_peer_reviewed"),
            ("https://github.com/rust-lang/rust/pull/131000", 3, "github_artifact"),
            ("https://github.com/rust-lang/rust/commit/abcdef1234", 3, "github_artifact"),
            ("https://github.com/rust-lang/rust/blob/master/compiler/rustc/src/main.rs", 3, "github_artifact"),
            ("https://github.com/rust-lang/rust/issues/42", 3, "github_artifact"),
            ("https://github.com/rust-lang/rust", 2, "code_repository"),
            ("https://lwn.net/Articles/987654/", 3, "lwn_systems"),
            ("https://www.sec.gov/ix?doc=/Archives/edgar/data/1045810/8k.htm", 3, "sec_filing"),
            ("https://nvd.nist.gov/vuln/detail/CVE-2026-1234", 3, "gov_legal"),
            ("https://reuters.com/technology/some-report/", 2, "investigative_or_tech_press"),
            ("https://cs.stanford.edu/~knuth/fasc1.html", 2, "investigative_or_tech_press"),
            ("https://en.wikipedia.org/wiki/ Borrow_checker", 1, "general_web"),
            ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", -1, "low_cred_or_joke"),
            ("https://lmgtfy.com/?q=rust", -1, "low_cred_or_joke"),
        ]
        for url, expected_tier, expected_cat in cases:
            match = classify_single_url(url)
            self.assertEqual(match.tier, expected_tier, msg=f"Tier mismatch for {url}: {match}")
            self.assertEqual(match.category, expected_cat, msg=f"Category mismatch for {url}: {match}")

        agg = classify_urls_detailed(
            [
                "item?id=100",
                "https://news.ycombinator.com/newsguidelines.html",
                "https://lwn.net/Articles/999/",
                "https://youtu.be/abc",
            ]
        )
        self.assertEqual(agg["url_tier"], 3)
        self.assertEqual(agg["primary_url_count"], 1)
        self.assertEqual(agg["low_cred_url_count"], 1)
        self.assertIn("lwn_systems", agg["url_categories"])

    def test_author_cache_sqlite_7day_ttl(self) -> None:
        """Serve fresh (<7d) profiles from SQLite and re-fetch only expired (>=7d) or missing users."""
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "author_cache.db"
            cache = AuthorCache(db_path=db_path, ttl_seconds=DEFAULT_TTL_SECONDS)
            t0 = 1_790_000_000.0
            calls: list[str] = []

            def fake_fetch(uname: str) -> dict[str, object]:
                calls.append(uname)
                return {
                    "id": uname,
                    "created": 1_500_000_000,
                    "karma": 4200 if len(calls) == 1 else 4900,
                    "submitted_count": 300,
                    "has_about": True,
                }

            # Initial miss populates SQLite
            res1 = cache.resolve_authors(["alice", "[deleted]"], now=t0, max_workers=1, fetcher=fake_fetch)
            self.assertEqual(calls, ["alice"])
            self.assertEqual(res1["alice"]["karma"], 4200)
            self.assertNotIn("[deleted]", res1)

            # Within 7-day TTL (6.9 days later): zero network calls
            res2 = cache.resolve_authors(["alice"], now=t0 + 6.9 * 86400.0, max_workers=1, fetcher=fake_fetch)
            self.assertEqual(calls, ["alice"])
            self.assertEqual(res2["alice"]["karma"], 4200)

            # Past 7-day TTL (7 days + 5s later): re-fetches and updates SQLite
            res3 = cache.resolve_authors(["alice"], now=t0 + DEFAULT_TTL_SECONDS + 5.0, max_workers=1, fetcher=fake_fetch)
            self.assertEqual(calls, ["alice", "alice"])
            self.assertEqual(res3["alice"]["karma"], 4900)

    def test_multipage_html_pagination_and_cross_page_tree(self) -> None:
        """Crawl ?p=1..N via morelink, deduplicate shifted IDs, and preserve subtree stacks."""
        p1 = """
        <html op="item"><head><title>Compiler Escape Analysis | Hacker News</title></head><body>
        <table class="fatitem"><tr class="athing submission" id="9000">
          <td class="title"><span class="titleline"><a href="https://blog.rust-lang.org/post">Compiler Escape Analysis</a></span></td>
        </tr><tr><td class="subtext"><span class="subline"><span class="score">312 points</span> by <a href="user?id=graydon">graydon</a> <span class="age" title="2026-11-13T01:00:00">2h</span></span></td></tr></table>
        <table class="comment-tree">
          <tr class="athing comtr" id="9001"><td><table><tr><td class="ind" indent="0"></td><td>
            <a href="user?id=u1">u1</a><span class="age" title="2026-11-13T01:10:00">1h</span>
            <div class="commtext c00">Root compiler comment on page 1.</div><div class="reply"></div>
          </td></tr></table></td></tr>
          <tr class="athing comtr" id="9002"><td><table><tr><td class="ind" indent="1"></td><td>
            <a href="user?id=u2">u2</a><span class="age" title="2026-11-13T01:15:00">1h</span>
            <div class="commtext c00">Depth-1 child at end of page 1.</div><div class="reply"></div>
          </td></tr></table></td></tr>
        </table>
        <a href="item?id=9000&amp;p=2" class="morelink" rel="next">More</a>
        </body></html>
        """
        p2 = """
        <html><body><table class="comment-tree">
          <tr class="athing comtr" id="9002"><td><table><tr><td class="ind" indent="1"></td><td>
            <a href="user?id=u2">u2</a><span class="age" title="2026-11-13T01:15:00">1h</span>
            <div class="commtext c00">Duplicate shifted comment across page boundary.</div><div class="reply"></div>
          </td></tr></table></td></tr>
          <tr class="athing comtr" id="9003"><td><table><tr><td class="ind" indent="2"></td><td>
            <a href="user?id=u3">u3</a><span class="age" title="2026-11-13T01:20:00">1h</span>
            <div class="commtext c5A">Depth-2 grandchild continuing on page 2 with <a href="https://arxiv.org/abs/2501.00001">paper</a>.</div><div class="reply"></div>
          </td></tr></table></td></tr>
        </table></body></html>
        """
        self.assertEqual(extract_next_page_num(p1, current_page=1), 2)
        self.assertIsNone(extract_next_page_num(p2, current_page=2))

        fetched = fetch_hn_html_pages(9000, page_fetcher=lambda _sid, p: p1 if p == 1 else p2)
        self.assertEqual(len(fetched), 2)

        rows, _ref_ts, meta = parse_live_html_pages(fetched, story_id=9000)
        self.assertEqual(meta["story_title"], "Compiler Escape Analysis")
        self.assertEqual([r["id"] for r in rows], [9001, 9002, 9003])
        self.assertEqual([r["live_dom_rank"] for r in rows], [1, 2, 3])
        by_id = {r["id"]: r for r in rows}
        self.assertEqual(by_id[9003]["parent_id"], 9002)
        self.assertEqual(by_id[9003]["root_id"], 9001)
        self.assertEqual(by_id[9003]["downvote_tier"], 1)

        # Verify Algolia dead comment merge uses story_id=9000 (never hardcoded 50467087)
        alg = {
            "id": 9000,
            "children": [
                {"id": 9004, "author": "dead_user", "text": "flagged text", "parent_id": 9000, "children": []}
            ],
        }
        merged = merge_algolia_dead_comments(rows, alg, 1_794_532_800.0, story_id=9000)
        dead_row = next(r for r in merged if r["id"] == 9004)
        self.assertTrue(dead_row["is_dead"])
        self.assertEqual(dead_row["parent_id"], 9000)

    def test_article_extractor_and_fallback(self) -> None:
        """Strip boilerplate tags from article HTML and degrade gracefully on network errors."""
        sample_html = """
        <html><head><title>MIR Borrowck Benchmarks</title>
        <meta property="og:description" content="Polonius reduces compile latency by 18%."></head>
        <body><nav>Menu Login Subscribe</nav>
        <article><p>Polonius dataflow solver cuts borrow-check memory usage by 34% across crates.</p></article>
        <script>const secret = '#bad';</script></body></html>
        """
        txt = extract_readable_article_text(sample_html)
        self.assertIn("Polonius dataflow solver", txt)
        self.assertNotIn("const secret", txt)

        def failing_fetcher(_url: str) -> tuple[bytes, str]:
            raise TimeoutError("upstream blocked")

        fb = fetch_story_article(
            "https://paywall.example.com/systems/kernel-ebpf-verifier",
            story_title="Kernel eBPF Verifier Scaling",
            toptext="Ask HN context note",
            article_fetcher=failing_fetcher,
        )
        self.assertEqual(fb["article_source"], "fallback_metadata")
        self.assertIn("Kernel eBPF Verifier Scaling", fb["article_text"])
        self.assertIn("ebpf", fb["article_text"].lower())

    def test_zero_hardcoded_50467087_lexicons_and_unsupervised_judge_gate(self) -> None:
        """Ensure corpus_science.py has zero 50467087 lexicons yet still scores >= 88.0 on 50467087."""
        src = (HERE / "corpus_science.py").read_text(encoding="utf-8").lower()
        for forbidden in ("megaspeed", "colette", "kress", "leather jacket", "epstein", "wozniak", "spatula"):
            self.assertNotIn(forbidden, src)

        rows, manifest = corpus_science.build_story_corpus(50467087, offline=True, write_output=False)
        self.assertEqual(len(rows), 3010)
        self.assertEqual(len(manifest["facet_clusters"]), 5)
        self.assertGreaterEqual(len(manifest["story_anchors"]), 20)

        ranked = ranker.rank_comments(rows)
        inv_errors = check_invariants_v1_1(ranked, {c["id"] for c in rows})
        self.assertEqual(inv_errors, [])

        fixtures = json.loads((JUDGE_DIR / "epistemic_fixtures_v1.json").read_text(encoding="utf-8"))
        metrics = score_ordering(ranked, fixtures)
        self.assertGreaterEqual(metrics["score"], 88.0, msg=f"Unsupervised 50467087 metrics: {metrics}")

    def test_zero_hash_dashboard_and_cli_on_synthetic_story(self) -> None:
        """Build parameterized zero-hash HTML when title, URLs, and prose contain `#` characters."""
        raw_page = """
        <html op="item"><head><title>RFC #9110 HTTP Semantics | Hacker News</title></head><body>
        <table class="fatitem"><tr class="athing submission" id="777001">
          <td class="title"><span class="titleline"><a href="https://datatracker.ietf.org/doc/html/rfc9110#section-9">RFC #9110 HTTP Semantics</a></span></td>
        </tr></table>
        <table class="comment-tree">
          <tr class="athing comtr" id="777010"><td><table><tr><td class="ind" indent="0"></td><td>
            <a href="user?id=fielding">fielding</a><span class="age" title="2026-11-13T04:00:00">2h</span>
            <div class="commtext c00">According to <a href="https://datatracker.ietf.org/doc/html/rfc9110#section-9.3">RFC 9110 #section-9.3</a>, idempotent PUT retry semantics reduce tail latency by 24% under 150 ms RTTs.</script></div><div class="reply"></div>
          </td></tr></table></td></tr>
          <tr class="athing comtr" id="777011"><td><table><tr><td class="ind" indent="0"></td><td>
            <a href="user?id=troll">troll</a><span class="age" title="2026-11-13T05:30:00">30m</span>
            <div class="commtext c88">Sir, this is a Wendy's #yolo</div><div class="reply"></div>
          </td></tr></table></td></tr>
        </table></body></html>
        """
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp) / "data"
            item_dir = data_dir / "items" / "777001"
            item_dir.mkdir(parents=True)
            (item_dir / "live_p1.html").write_text(raw_page, encoding="utf-8")
            (item_dir / "algolia.json").write_text(json.dumps({"id": 777001, "children": []}), encoding="utf-8")
            (item_dir / "story_article.txt").write_text("HTTP RFC 9110 caching and idempotent methods.", encoding="utf-8")
            out_html = Path(tmp) / "show-me-hn-777001.html"

            with redirect_stdout(io.StringIO()):
                res = cli.run_cli(
                    [
                        "https://news.ycombinator.com/item?id=777001#frag",
                        "--data-dir",
                        str(data_dir),
                        "--offline",
                        "--out",
                        str(out_html),
                        "--json",
                    ]
                )
            self.assertEqual(res["story_id"], 777001)
            self.assertTrue(res["zero_hash_verified"])
            html_text = out_html.read_text(encoding="utf-8")
            self.assertNotIn("#", html_text)
            self.assertIn('id="modeSelect"', html_text)
            self.assertNotIn('id="presetBar"', html_text)
            self.assertIn('<details class="proof-drawer" id="kpiDrawer">', html_text)
            self.assertIn('<details class="proof-drawer" id="proofDrawer">', html_text)
            self.assertIn('<details class="proof-drawer" id="labDrawer">', html_text)
            self.assertIn('<details class="graph-drawer" id="tunerDrawer">', html_text)
            self.assertEqual(res["top"][0]["id"], 777010)


if __name__ == "__main__":
    unittest.main()
