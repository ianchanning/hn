"""Tests for the `/item?id=<id>` GitHub Pages site builder and workflow security."""

from datetime import UTC, datetime
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re
import sys
import tempfile
import threading
import unittest
import urllib.request

HERE = Path(__file__).resolve().parents[1]
REPO_ROOT = HERE.parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from build_pages_site import build_pages_site, evaluate_schedule_window


class _QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        return


class TestGitHubPagesMirror(unittest.TestCase):
    """Verify `/item?id=<id>` URI mirror generation, incremental retention, and workflow safety."""

    def test_build_pages_site_incremental_and_zero_hash(self) -> None:
        """Preserve prior `items/<id>.html` builds, emit zero-hash routers, and serve via HTTP."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            src_dir = tmp_path / "src"
            site_dir = tmp_path / "site"
            src_dir.mkdir()
            (site_dir / "items").mkdir(parents=True)

            # Simulate an already-published item on gh-pages from an earlier workflow run
            prior_payload = json.dumps(
                {
                    "story_id": 50000001,
                    "story_title": "Prior Published Thread",
                    "story_url": "https://example.org/prior",
                    "manifest": {"story_title": "Prior Published Thread"},
                    "tiers": {"epistemic_gold": 4, "grounded_analysis": 9},
                    "comments": [{"id": 1}, {"id": 2}],
                }
            )
            (site_dir / "items" / "50000001.html").write_text(
                f'<!doctype html><script id="observatoryData" type="application/json">{prior_payload}</script>',
                encoding="utf-8",
            )

            # Simulate newly built observatory in source_dir
            new_payload = json.dumps(
                {
                    "story_id": 50472038,
                    "story_title": "Rust 1.100",
                    "story_url": "https://blog.rust-lang.org/2026/11/12/Rust-1.100.0/",
                    "manifest": {"story_title": "Rust 1.100"},
                    "tiers": {"epistemic_gold": 19, "grounded_analysis": 30},
                    "comments": [{"id": i} for i in range(10)],
                }
            )
            (src_dir / "show-me-hn-50472038.html").write_text(
                f'<!doctype html><title>HN 50472038</title><script id="observatoryData" type="application/json">{new_payload}</script>',
                encoding="utf-8",
            )

            res = build_pages_site(
                site_dir=site_dir,
                source_dir=src_dir,
                repo="GMA-Storm/cli-utils",
                server_url="https://github.tools.digital.engie.com",
            )
            self.assertEqual(res["copied_ids"], [50472038])
            self.assertEqual(res["published_ids"], [50472038, 50000001])
            self.assertTrue((site_dir / ".nojekyll").is_file())

            for name in ("index.html", "item.html", "404.html", "items/50472038.html", "items/50000001.html"):
                content = (site_dir / name).read_text(encoding="utf-8")
                self.assertNotIn("#", content, msg=f"Zero-hash violated in {name}")

            catalog = json.loads((site_dir / "catalog.json").read_text(encoding="utf-8"))
            self.assertEqual(catalog["uri_template"], "/item?id={story_id}")
            self.assertEqual(catalog["total_published"], 2)

            index_txt = (site_dir / "index.html").read_text(encoding="utf-8")
            self.assertIn("./item?id=50472038", index_txt)
            self.assertIn("./item?id=50000001", index_txt)

            # Serve static tree over local HTTP to verify router & item artifact resolution
            handler = partial(_QuietHandler, directory=str(site_dir))
            with ThreadingHTTPServer(("127.0.0.1", 0), handler) as httpd:
                port = httpd.server_address[1]
                thread = threading.Thread(target=httpd.serve_forever, daemon=True)
                thread.start()
                try:
                    with urllib.request.urlopen(f"http://127.0.0.1:{port}/item.html?id=50472038", timeout=5) as r1:
                        self.assertEqual(r1.status, 200)
                        self.assertIn("routerConfig", r1.read().decode("utf-8"))
                    with urllib.request.urlopen(f"http://127.0.0.1:{port}/items/50472038.html", timeout=5) as r2:
                        self.assertEqual(r2.status, 200)
                        self.assertIn("Rust 1.100", r2.read().decode("utf-8"))
                finally:
                    httpd.shutdown()

    def test_refresh_updates_target_and_never_regresses_fresher_gh_pages_item(self) -> None:
        """Overwrite an explicitly refreshed story while protecting newer gh-pages items from older git snapshots."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            src_dir = tmp_path / "src"
            site_dir = tmp_path / "site"
            src_dir.mkdir()
            (site_dir / "items").mkdir(parents=True)

            # gh-pages already has a refreshed 600-comment version of 50472038 from yesterday
            fresher_gh_pages = json.dumps(
                {
                    "story_id": 50472038,
                    "story_title": "Rust 1.100",
                    "manifest": {"t2_ref_utc": "2026-11-14T12:00:00+00:00"},
                    "tiers": {"epistemic_gold": 35},
                    "comments": [{"id": i} for i in range(600)],
                }
            )
            (site_dir / "items" / "50472038.html").write_text(
                f'<!doctype html><script id="observatoryData" type="application/json">{fresher_gh_pages}</script>',
                encoding="utf-8",
            )

            # Repo checkout (`main`) still has the older 254-comment baseline of 50472038 + a newly built 50499999
            stale_repo_copy = json.dumps(
                {
                    "story_id": 50472038,
                    "story_title": "Rust 1.100",
                    "manifest": {"t2_ref_utc": "2026-11-13T09:00:00+00:00"},
                    "tiers": {"epistemic_gold": 19},
                    "comments": [{"id": i} for i in range(254)],
                }
            )
            (src_dir / "show-me-hn-50472038.html").write_text(
                f'<!doctype html><script id="observatoryData" type="application/json">{stale_repo_copy}</script>',
                encoding="utf-8",
            )
            new_story = json.dumps(
                {
                    "story_id": 50499999,
                    "story_title": "New Story",
                    "manifest": {"t2_ref_utc": "2026-11-15T08:00:00+00:00"},
                    "tiers": {"epistemic_gold": 8},
                    "comments": [{"id": i} for i in range(90)],
                }
            )
            (src_dir / "show-me-hn-50499999.html").write_text(
                f'<!doctype html><script id="observatoryData" type="application/json">{new_story}</script>',
                encoding="utf-8",
            )

            # Run 1: building 50499999 must NOT clobber the fresher 600-comment 50472038 on gh-pages
            res1 = build_pages_site(site_dir=site_dir, source_dir=src_dir, force_ids={50499999})
            self.assertEqual(res1["skipped_fresher_ids"], [50472038])
            cat1 = json.loads((site_dir / "catalog.json").read_text(encoding="utf-8"))
            by_id1 = {x["story_id"]: x for x in cat1["items"]}
            self.assertEqual(by_id1[50472038]["total_comments"], 600)

            # Run 2: explicitly re-running workflow for 50472038 (`force_ids={50472038}`) updates it in-place
            even_newer = json.dumps(
                {
                    "story_id": 50472038,
                    "story_title": "Rust 1.100",
                    "manifest": {"t2_ref_utc": "2026-11-15T10:00:00+00:00"},
                    "tiers": {"epistemic_gold": 42},
                    "comments": [{"id": i} for i in range(720)],
                }
            )
            (src_dir / "show-me-hn-50472038.html").write_text(
                f'<!doctype html><script id="observatoryData" type="application/json">{even_newer}</script>',
                encoding="utf-8",
            )
            res2 = build_pages_site(site_dir=site_dir, source_dir=src_dir, force_ids={50472038})
            self.assertIn(50472038, res2["copied_ids"])
            cat2 = json.loads((site_dir / "catalog.json").read_text(encoding="utf-8"))
            by_id2 = {x["story_id"]: x for x in cat2["items"]}
            self.assertEqual(by_id2[50472038]["total_comments"], 720)

    def test_dst_schedule_window_london_and_sf_year_round(self) -> None:
        """Fire at exact 08:00 London and 08:00 San Francisco across GMT/BST, PST/PDT, and runner delays."""
        # 1. Winter (Nov 14: London GMT UTC+0, SF PST UTC-8), including a 75-minute delayed 07:00 UTC job
        winter_delayed_07 = datetime(2026, 11, 14, 8, 15, tzinfo=UTC)
        self.assertFalse(evaluate_schedule_window("0 7 * * *", now_utc=winter_delayed_07)["should_run"])
        w_lon = evaluate_schedule_window("0 8 * * *", now_utc=datetime(2026, 11, 14, 8, 12, tzinfo=UTC))
        self.assertTrue(w_lon["should_run"])
        self.assertEqual(w_lon["matched_slot"], "london_0800")
        self.assertFalse(
            evaluate_schedule_window("0 15 * * *", now_utc=datetime(2026, 11, 14, 15, 5, tzinfo=UTC))["should_run"]
        )
        w_sf = evaluate_schedule_window("0 16 * * *", now_utc=datetime(2026, 11, 14, 16, 22, tzinfo=UTC))
        self.assertTrue(w_sf["should_run"])
        self.assertEqual(w_sf["matched_slot"], "sf_0800")

        # 2. Summer (Jul 14: London BST UTC+1, SF PDT UTC-7)
        s_lon = evaluate_schedule_window("0 7 * * *", now_utc=datetime(2026, 7, 14, 7, 4, tzinfo=UTC))
        self.assertTrue(s_lon["should_run"])
        self.assertEqual(s_lon["matched_slot"], "london_0800")
        self.assertFalse(
            evaluate_schedule_window("0 8 * * *", now_utc=datetime(2026, 7, 14, 8, 4, tzinfo=UTC))["should_run"]
        )
        s_sf = evaluate_schedule_window("0 15 * * *", now_utc=datetime(2026, 7, 14, 15, 9, tzinfo=UTC))
        self.assertTrue(s_sf["should_run"])
        self.assertEqual(s_sf["matched_slot"], "sf_0800")
        self.assertFalse(
            evaluate_schedule_window("0 16 * * *", now_utc=datetime(2026, 7, 14, 16, 9, tzinfo=UTC))["should_run"]
        )

        # 3. Asymmetric March transition week (Mar 15, 2026: UK still GMT UTC+0, US already PDT UTC-7)
        self.assertTrue(
            evaluate_schedule_window("0 8 * * *", now_utc=datetime(2026, 3, 15, 8, 1, tzinfo=UTC))["should_run"]
        )
        self.assertTrue(
            evaluate_schedule_window("0 15 * * *", now_utc=datetime(2026, 3, 15, 15, 1, tzinfo=UTC))["should_run"]
        )

    def test_frontpage_ranking_persistence_and_archive_pruning(self) -> None:
        """Render exact Front Page 1..N order, persist frontpage.json, and prune >90d unpinned items when over threshold."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            src_dir = tmp_path / "src"
            site_dir = tmp_path / "site"
            src_dir.mkdir()
            (site_dir / "items").mkdir(parents=True)

            def _mk_item(
                sid: int,
                title: str,
                ts_iso: str,
                pad_chars: int = 800,
                story_url: str = "",
                points: int = 128,
                author: str = "pg",
            ) -> str:
                payload = json.dumps(
                    {
                        "story_id": sid,
                        "story_title": title,
                        "story_url": story_url,
                        "manifest": {"t2_ref_utc": ts_iso, "points": points, "story_author": author},
                        "tiers": {"epistemic_gold": 5, "grounded_analysis": 8},
                        "comments": [{"id": i} for i in range(20)],
                        "pad": "x" * pad_chars,
                    }
                )
                return f'<!doctype html><script id="observatoryData" type="application/json">{payload}</script>'

            # Old >90d unpinned item on gh-pages + two current front-page items (including a `#fragment` URL)
            (site_dir / "items" / "49000001.html").write_text(
                _mk_item(49000001, "Ancient Archived Story", "2026-06-01T08:00:00+00:00", pad_chars=2400),
                encoding="utf-8",
            )
            (site_dir / "items" / "50400001.html").write_text(
                _mk_item(
                    50400001,
                    "Lower ID But Rank 1 On HN #1",
                    "2026-11-14T08:00:00+00:00",
                    story_url="https://blog.rust-lang.org/2026/11/12/post/#sec-2",
                    points=342,
                    author="steveklabnik",
                ),
                encoding="utf-8",
            )
            (site_dir / "items" / "50499999.html").write_text(
                _mk_item(50499999, "Higher ID But Rank 2 On HN", "2026-11-14T08:00:00+00:00"),
                encoding="utf-8",
            )

            ref_now = datetime(2026, 11, 14, 16, 0, tzinfo=UTC)
            res = build_pages_site(
                site_dir=site_dir,
                source_dir=src_dir,
                frontpage_ids=[50400001, 50499999],
                frontpage_synced_utc="2026-11-14T16:00:00+00:00",
                prune_older_than_days=90,
                prune_trigger_mb=0.001,  # ~1 KB trigger to exercise >90d retention check
                max_site_mb=10.0,
                now_utc=ref_now,
            )
            self.assertEqual(res["pruned_ids"], [49000001])
            self.assertFalse((site_dir / "items" / "49000001.html").exists())
            self.assertEqual(res["frontpage_ids"], [50400001, 50499999])

            idx_html = (site_dir / "index.html").read_text(encoding="utf-8")
            self.assertNotIn("#", idx_html)
            self.assertIn('class="hnmain"', idx_html)
            self.assertIn("Epistemic News", idx_html)
            self.assertIn('<div class="topbar-right">Updated 2026-11-14 16:00 UTC</div>', idx_html)
            self.assertIn(">blog.rust-lang.org</a>)", idx_html)
            self.assertIn("342 points by steveklabnik", idx_html)
            self.assertIn("35% bullshit", idx_html)
            # Rank 1 (`50400001`) appears before Rank 2 (`50499999`) despite smaller numeric ID
            self.assertLess(idx_html.index("50400001"), idx_html.index("50499999"))

            # Subsequent single-story run without frontpage_ids preserves frontpage.json, publishes item, & updates UTC stamp
            (src_dir / "show-me-hn-50511111.html").write_text(
                _mk_item(50511111, "Manual Single Dispatch", "2026-11-14T17:00:00+00:00"),
                encoding="utf-8",
            )
            later_now = datetime(2026, 11, 14, 17, 5, tzinfo=UTC)
            res2 = build_pages_site(
                site_dir=site_dir,
                source_dir=src_dir,
                force_ids={50511111},
                now_utc=later_now,
            )
            self.assertEqual(res2["frontpage_ids"], [50400001, 50499999])
            self.assertTrue((site_dir / "items" / "50511111.html").is_file())
            idx_html2 = (site_dir / "index.html").read_text(encoding="utf-8")
            self.assertNotIn("#", idx_html2)
            self.assertIn('<div class="topbar-right">Updated 2026-11-14 17:05 UTC</div>', idx_html2)

    def test_workflow_yaml_exists_and_avoids_shell_injection(self) -> None:
        """Ensure workflow_dispatch passes inputs strictly via env vars rather than inline run interpolation."""
        local_wf = HERE / ".github" / "workflows" / "hn-observatory-pages.yml"
        root_wf = REPO_ROOT / ".github" / "workflows" / "hn-observatory-pages.yml"
        wf_path = local_wf if local_wf.is_file() else root_wf
        self.assertTrue(wf_path.is_file())
        wf_text = wf_path.read_text(encoding="utf-8")
        if local_wf.is_file() and root_wf.is_file():
            self.assertEqual(local_wf.read_text(encoding="utf-8"), root_wf.read_text(encoding="utf-8"))

        self.assertIn("schedule:", wf_text)
        self.assertIn('cron: "0 7 * * *"', wf_text)
        self.assertIn('cron: "0 8 * * *"', wf_text)
        self.assertIn('cron: "0 15 * * *"', wf_text)
        self.assertIn('cron: "0 16 * * *"', wf_text)
        self.assertIn("workflow_dispatch:", wf_text)
        self.assertIn("target:", wf_text)
        self.assertIn("build_pages_site.py", wf_text)
        self.assertIn("gh-pages", wf_text)

        # Extract all `run: |` blocks and verify `${{ inputs.` never appears directly inside shell scripts
        run_blocks = re.findall(r"run:\s*\|\n((?: {10,}.*\n|\n)+)", wf_text)
        self.assertGreaterEqual(len(run_blocks), 4)
        for block in run_blocks:
            self.assertNotIn("${{ inputs.", block)
            self.assertNotIn("${{ github.event.inputs.", block)


if __name__ == "__main__":
    unittest.main()
