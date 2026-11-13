# Handoff: Generalize HN epistemic observatory to any post

Branch: feat/hn-epistemic-observatory
Base SHA: ade025c
Completed SHA: 447e071
Mode: completed
Tracker: hnc-zpn (closed)

## Task
Widen `hn-comments/` from single-thread `50467087` to any HN item ID or URL: build `cli.py`, `?p=1..N` HTML + Algolia + story-URL `ingest.py`, SQLite `author_cache.py` (7-day TTL), cross-domain `source_registry.py` (RFC/arXiv/DOI/GitHub commit|blob|issue/LWN/gov/SEC), unsupervised TF-IDF story anchors + subtree drift + auto-labeled 5-cluster facets in `corpus_science.py`, parameterized zero-hash `build_dashboard.py`, unit tests, and live builds on 2 non-scandal HN threads.

## Gate
- Baseline: `uv run --no-project python hn-comments/judge/judge_v1_1.py hn-comments`
- Done: `uv run --no-project python -m unittest discover -s hn-comments/tests -v && uv run --no-project python hn-comments/judge/judge_v1_1.py hn-comments` (`score >= 88.0`, `valid == true`, plus 2 live zero-hash `show-me-hn-<id>.html` builds opened via `open`)

## Boundaries
- Own: `hn-comments/` (update `README.md`, close `hnc-zpn`, set `Mode: completed`, and commit locally on `feat/hn-epistemic-observatory` when Done passes)
- Off-limits: `specs/remit_outages_scraping/*` (leave untouched); no `git push`, PR, `epistemic_fixtures_v1.json` edits, or `forget-team` tournament

## Entry
- `hn-comments/README.md` — current commands and architecture
- `hn-comments/corpus_science.py` — 4 hardcoded 50467087 seams to generalize
- `hn-comments/parse_corpus.py` — HTML row parser to extend for `?p=1..N` pagination
- `hn-comments/ranker.py` — five-potential epistemic scorer + hinged MMR
- `hn-comments/build_dashboard.py` — zero-hash `rgb()` observatory generator
