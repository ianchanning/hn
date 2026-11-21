# HN Epistemic Observatory

**Replace Hacker News's recency-and-snark sorting with information-theoretic, citation-grounded epistemic ranking — for any HN thread.**

Zero-dependency Python (`>= 3.11`, stdlib only) ingestion pipeline, five-potential epistemic ranker, anti-Goodhart evaluation harness, self-contained HTML observatory compiler, and a GitHub Pages mirror serving every analyzed thread at its exact Hacker News relative URI (`/item?id=<id>`).

---

## Why Live Hacker News Buries Primary Signal

Auditing full Hacker News comment trees exposes four structural failure modes in production `news.arc` ranking:

1. **`(T + 2)^1.8` Gravity Mirage** — Steep age decay lets a 40-minute-old surf-riding conspiracy take or punchline leapfrog a 10-hour-old primary-sourced engineering breakdown.
2. **Subtree Monopoly (Tree-Lock)** — Depth-first rendering under an early top-level comment allows a single flamewar subtree to swallow hundreds of consecutive DOM slots (e.g., `862` slots `HN POS 132..994` on `HN 50467087`), burying domain experts below `HN POS 1,500`.
3. **Authority Halo & Meme Velocity** — High-karma accounts posting one-liner gags or bare rumor links accumulate rapid early votes with zero falsifiable content.
4. **Single-Downvote (`c5A`) Collateral Damage** — A single partisan downvote fades (`c5A`) civil, primary-sourced rebuttals alongside genuinely toxic or moderator-rebuked (`c73..cDD`) noise.

---

## Quickstart

Requires **Python 3.11+** (zero third-party packages; works with `python3` or `uv run --no-project python`).

```bash
# Run from inside this directory (or prefix paths with `hn-comments/` from a parent monorepo)

# 1. Build & open a self-contained HTML observatory for any HN item ID or URL
uv run --no-project python cli.py 50472038 --open
uv run --no-project python cli.py "https://news.ycombinator.com/item?id=50471731" --open

# 2. Build all 30 stories currently on the live HN Front Page
uv run --no-project python cli.py frontpage --limit 30 --refresh

# 3. Rank comments in the terminal (or pass --json for structured output)
uv run --no-project python cli.py rank 50472038 --top 15

# 4. Rebuild offline from cached snapshots + 7-day SQLite author cache
uv run --no-project python cli.py 50472038 --offline

# 5. Run the full unit, contract, and generalization test suite
uv run --no-project python -m unittest discover -s hn-comments/tests -v
# (Or from the root via npm)
npm test
```

---

## GitHub Pages `/item?id=<id>` Mirror

The included GitHub Actions workflow (`.github/workflows/hn-observatory-pages.yml`) and static site builder (`build_pages_site.py`) publish observatories to a persistent `gh-pages` branch with **exact Hacker News URI parity** — swap the host and keep `/item?id=<id>`:

| Surface | URL |
| :--- | :--- |
| **Original Hacker News** | `https://news.ycombinator.com/item?id=50472038` |
| **GitHub.com Pages** | `https://<owner>.github.io/<repo>/item?id=50472038` |
| **Custom Domain** | `https://<domain>/item?id=50472038` |
| **GitHub Enterprise Pages** | `https://pages.<ghes-host>/<owner>/<repo>/item?id=50472038` |
| **Published Directory Index** | `https://<pages-base>/` |

### Scheduled Front-Page Sync & On-Demand Builds

- **Automatic twice-daily Front-Page sync:** Runs automatically at **08:00 London (`Europe/London`, GMT/BST)** and **08:00 San Francisco (`America/Los_Angeles`, PST/PDT)** year-round via a DST-aware `zoneinfo` schedule gate (`build_pages_site.py --check-schedule`), building/updating all **30 live HN Front Page stories** (`v0/topstories.json`, skipping YC job ads) and pinning them in live `FP 01..30` order at the top of `index.html`.
- **Safe `< 1 GB` archive retention:** Keeps all published `/item?id=<id>` pages until `items/` reaches `500 MB`, then prunes unpinned items older than `90` days (and caps total archive size at `750 MB`) while squashing `gh-pages` into a single commit so Git history never bloats.

```bash
# Sync all 30 live Front Page stories on demand (default target)
gh workflow run hn-observatory-pages.yml -f target=frontpage

# Or build/refresh a single HN item ID or URL
gh workflow run hn-observatory-pages.yml -f target=50472038
gh workflow run hn-observatory-pages.yml -f target="https://news.ycombinator.com/item?id=50471731"
```

### Standalone Repository Setup

1. Ensure `.github/workflows/hn-observatory-pages.yml` is at `.github/workflows/hn-observatory-pages.yml` in the repository root (the workflow auto-detects whether `cli.py` lives at `.` or `hn-comments/`).
2. In **Settings → Pages**, set **Source** to **Deploy from a branch → `gh-pages` / `/ (root)`**.
3. Trigger **HN Epistemic Observatory Pages** from the **Actions** tab (or via `gh workflow run`). Previously published `/item?id=<id>` pages are preserved across runs and indexed at `/` and `/catalog.json`.

### Cloudflare Workers Cron Scheduler (`scheduler/`)

To eliminate GitHub Actions native cron queue delays (which can lag 30–90 minutes) and prevent automatic 60-day inactivity disablement, scheduled runs are triggered deterministically by a Cloudflare Worker on a **minute 14 and 44 past every hour (`14,44 * * * *`)** cadence that dispatches `hn-observatory-pages.yml` via the GitHub API.

```bash
cd scheduler

# 1. Set GitHub token secret (requires repo or actions:write permissions)
gh auth token | npx wrangler secret put GITHUB_TOKEN

# 2. Deploy Cloudflare Worker
npx wrangler deploy
# Or via deploy script:
./deploy.sh

# 3. Inspect worker health & status
curl https://hn-observatory-scheduler.<your-subdomain>.workers.dev/status

# 4. Test manual trigger
curl -X POST https://hn-observatory-scheduler.<your-subdomain>.workers.dev/trigger

# 5. Tail live cron execution logs
npx wrangler tail
```

---

## How the Epistemic Engine Works

### Stage 1 — Multi-Source Ingestion & Unsupervised Corpus Science

- **Paginated Live HTML (`ingest.py`, `parse_corpus.py`)** — Crawls `?p=1..N` via HN `morelink` anchors, reconstructing exact live DOM order (`1..N`), continuous cross-page reply indentation stacks, and `news.css` downvote fade tiers (`c00`, `c5A`, `c73..cDD`).
- **Algolia & Linked Story Grounding** — Merges flagged/dead items from Algolia's tree API, reconciles cross-page parent pointers, and extracts readable prose from the story's external URL (falling back cleanly to `Ask HN` / `Show HN` `toptext` and title metadata).
- **7-Day SQLite Author Cache (`author_cache.py`)** — Resolves commenter karma, account age, and submission volume (`karma / post`) concurrently against Firebase v0 + Algolia v1, persisted in WAL-mode `data/author_cache.db`.
- **Cross-Domain Source Registry (`source_registry.py`)** — Classifies external citations into:
  - **Tier 3 (Primary / Verifiable Artifacts):** IETF `RFC`s & W3C specs, `arXiv`/preprints, `DOI` & peer-reviewed journals, `GitHub`/GitLab/kernel commits, blobs, PRs & issues, `LWN`, `.gov`/`.mil`, `SEC` EDGAR filings, court opinions, official cloud status pages, PDFs, and web archives.
  - **Tier 2 (Investigative Press, Academic `.edu` & Code Repositories):** Reuters, AP, FT, Ars Technica, AnandTech, Quanta, `.edu`/`.ac.uk`, and top-level open-source repositories.
  - **Tier 1 / Tier -1:** General web links vs. low-credibility/joke drops (YouTube gags, `lmgtfy`, meme subreddits, reaction hosts).
- **Unsupervised Story Adaptation (`corpus_science.py`)** — Extracts thread-specific **TF-IDF + multi-root consensus story anchors**, **vector-space subtree drift** (detecting deep branches that wander off-topic), **unsupervised short-quip running gags**, and **5 deterministic spherical k-means++ auto-labeled topic facets**.

### Stage 2 — Five-Potential Scorer & Submodular Portfolio Selection (`ranker.py`)

Every comment is decomposed into five interpretable potentials:

1. **Specific Information Gain (`+`)** — Shannon/IDF lexical mass and Jelinek-Mercer interpolated bigram crowd surprisal, gated on story grounding and discounted for cliché crowd clusters.
2. **Popperian Falsifiability (`+`)** — Context-coupled Tier 2/3 citations, pinpointed documentary quotes, quantitative measurements, and causal/evidential structure.
3. **Inverse `news.arc` Physics & Tree-Lock Rescue (`+`)** — Isotonic sibling-order vote inversion removing `(T + 2)^1.8` recency distortion, Bayesian author precision (`karma/post` gated on clean analytical prose), constructive progeny, and deep-DOM rescue.
4. **Frankfurtian Bullshit & Flamewar Load (`-`)** — Suppresses unfalsifiable conspiracy posturing, ad-hominem swipes, running memes, dyadic `A -> B -> A -> B` ping-pong flamewars, subtree topic drift, and near-duplicate copy-pastes.
5. **Downvote & Moderation Sink with `c5A` Rescue (`-`)** — Pushes `c73..cDD` faded noise and moderator (`dang` / `tomhow`) guideline rebukes out of top ranks while rescuing civil, primary-sourced `c5A` counter-evidence.

Finally, **Hinged Greedy Submodular MMR** reranks the top candidate pool across pairwise TF-IDF cosine similarity, root-thread counts, and discovered topic facets so no single root subtree or repetitive talking point monopolizes the top 55.

---

## CLI Reference

```text
python3 cli.py [build|frontpage|ingest|rank] [<item_id_or_url>] [options]

Positional (for build / ingest / rank):
  target              HN item ID (50472038), URL, or `frontpage`

Subcommands (defaults to `build` when omitted):
  build               Ingest, extract scientific features, rank, and emit show-me-hn-<id>.html
  frontpage           Fetch all live HN Front Page stories (Top 30) and build observatories
  ingest              Fetch ?p=1..N HTML, Algolia tree, article prose, and SQLite author profiles
  rank                Print top-ranked epistemic comments vs. Live HN positions in terminal

Options:
  --limit N           Max front-page stories for `frontpage` (default: 30)
  --out-dir DIR       Output directory for `frontpage` HTML builds (default: .)
  --frontpage-manifest PATH
                      Write JSON manifest of synced front-page IDs for `build_pages_site.py`
  --open              Open generated show-me-hn-<id>.html in default browser
  --offline           Build from local snapshots and SQLite cache without network calls
  --refresh           Force live re-fetch of HTML pages, Algolia JSON, and linked article
  --max-pages N       Maximum ?p=1..N HTML pages to crawl (default: 25)
  --top N             Number of top comments to summarize (default: 5 for build, 15 for rank)
  --out PATH          Custom output HTML path
  --data-dir DIR      Custom data/cache directory (default: ./data)
  --json              Emit machine-readable JSON summary on stdout
```

---

## Monorepo Architecture

This repository is organized as a unified monorepo coordinating the Python epistemic ingestion and ranking pipeline, Elm display layer, Cloudflare Workers scheduler, and external judge evaluation suite:

```text
.
├── pyproject.toml             # Python package configuration (PEP 621, ruff, mypy, pytest)
├── package.json               # Root monorepo workspace orchestrating elm and scheduler
├── cli.py                     # Root CLI forwarder delegating to hn-comments/cli.py
├── CONTRACT.md                # Ranker output schema & hard anti-Goodhart invariants
├── hn-comments/               # Python epistemic ranking & ingestion workspace
│   ├── pyproject.toml         # Python package manifest (hn-observatory)
│   ├── cli.py                 # Story-agnostic CLI entry point (build / ingest / rank / frontpage)
│   ├── ranker.py              # Five-potential epistemic scorer + hinged submodular MMR
│   ├── ingest.py              # ?p=1..N HTML crawler, Algolia client & article extractor
│   ├── parse_corpus.py        # DOM-order comment parser & cross-page tree reconstructor
│   ├── author_cache.py        # 7-day TTL SQLite WAL author reputation cache
│   ├── source_registry.py     # Cross-domain Tier 3 / 2 / 1 / -1 URL classifier
│   ├── corpus_science.py      # TF-IDF story anchors, drift & spherical k-means++ facets
│   ├── ablation.py            # 8-stage controlled ablation harness
│   ├── build_dashboard.py     # Zero-hash HTML observatory compiler (embeds Elm bundle)
│   ├── build_pages_site.py    # Incremental GitHub Pages `/item?id=<id>` mirror builder
│   ├── data/                  # Frozen corpus, SQLite cache, and ingested snapshots
│   ├── benchmark/             # Illustrative development samples
│   └── tests/                 # Automated Python test suite
├── elm/                       # Elm 0.19.3 display layer (TEA architecture)
│   ├── elm.json               # Elm project manifest
│   ├── elm-watch.json         # Dev HMR target config
│   ├── package.json           # npm scripts: dev, build, test, review, diff
│   ├── src/                   # Elm source modules (Main, Observatory/*, Pages/*)
│   ├── js/canvas-iife.js      # Canvas 2D port bridge (~130 lines)
│   ├── tests/                 # elm-test suites (Decode, Weights, Tier, View, Pages)
│   └── scripts/bundle.js      # Production bundle: elm.min.js + canvas + boot → observatory.js
├── scheduler/                 # Cloudflare Workers cron schedule trigger
│   ├── src/index.ts           # Worker script triggering twice-daily frontpage builds
│   ├── wrangler.toml          # Cloudflare Worker configuration
│   └── package.json           # Worker dependencies
├── judge/                     # External Judge evaluation harness
│   ├── epistemic_fixtures_v1.json
│   ├── judge_v1.py            # Graded NDCG@20, pairwise concordance, trap & rescue metrics
│   └── judge_v1_1.py          # Official External Judge v1.1.0 + hard invariant gate
├── archive/                   # Preserved pre-Elm legacy display artifacts
│   ├── legacy_html/           # Pre-Elm static HTML builds (50471731, 50472038, 50500963)
│   └── legacy_display/        # Legacy monolithic Python f-string dashboard compiler
└── wiki/                      # Machine-studying knowledge base
    ├── index.md               # Wiki page index
    ├── TYPES.md               # Complete Elm type catalogue & build pipeline spec
    └── Monorepo-Architecture.md
```

### Monorepo Quick Commands

```bash
# Run full monorepo test suite (Elm test suite + Python unittest suite)
npm test

# Build all monorepo targets (Elm production bundle + Cloudflare Worker scheduler)
npm run build

# Validate Elm code (type check, tests, and elm-review) and Python tests
npm run validate

# Run automated Elm vs Python visual and structural parity differ
npm run diff
```

---

## Benchmark & Empirical Validation

### Verified Observatories

Every generated HTML observatory enforces `assert "#" not in html_doc` (`rgb()`/`rgba()` colors and `\u0023` JSON escaping) so artifacts render identically via `file://`, GitHub Pages, or inline `data:text/html,` URIs, with interactive client-side weight sliders and dual 2D phase-plane / gravity canvases.

| HN Item | Domain | Comments | Useful Signal | Portfolio Diversity | Artifact |
| :--- | :--- | ---: | ---: | ---: | :--- |
| `50467087` — *Jensen Huang resigns* | Governance / Export Controls (Frozen Benchmark) | `3,010` | `204` (`59` Gold) | `0.980` (Judge **`89.38`**, Unsupervised **`88.48`**) | `show-me-hn-50467087.html` |
| `50472038` — *Rust 1.100* | Programming Languages / Compilers (Live) | `254` | `49` (`19` Gold) | `0.971` (`abi_stable`, `code_function`, `bool_method`, ...) | `show-me-hn-50472038.html` |
| `50471731` — *Service degradation on Microsoft 365* | Cloud Infrastructure / SRE Outage (Live) | `762` | `98` (`23` Gold) | `0.974` (`outlook_email`, `microsoft_cloud`, `status_servers`, ...) | `show-me-hn-50471731.html` |

### Controlled Ablation & Holdout Generalization (`External Judge v1.1.0` on `HN 50467087`)

Evaluated across `112` human-graded comments (`dev` + locked `holdout`), `23` adversarial traps (high-karma memes, bare rumor URLs, surf-riders), and `6` hard anti-Goodhart gates (zero `c73..cDD` in Top 35, zero mod-rebuked in Top 60, zero bare `<8`-word stubs in Top 50, zero `>=0.85` near-duplicates in Top 40, deterministic `<4.0s` runtime):

| Stage | Full Score | Dev | Locked Holdout | NDCG@20 | Pairwise Concordance | Buried Gold Recall@45 |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: |
| Live Hacker News (`news.arc` + Secret Sauce) | `41.02` | `41.20` | `40.85` | `0.325` | `0.554` | `0.0%` |
| `v0` Naive Keyword/Verbosity Draft | `51.83` | `55.01` | `48.17` | `0.544` | `0.576` | `13.6%` |
| `v1.0` Epistemic Engine Seed | `83.72` | `83.77` | `84.99` | `0.792` | `0.882` | `59.1%` |
| `forget-team` Round 1 Winner (`w2` `7e4063b`) | `87.61` | `87.04` | `90.24` | `0.832` | `0.930` | `68.2%` |
| `forget-team` Round 2 Champion (`w3` `94eb7b3`) | **`89.38`** | **`89.32`** | **`90.63`** | **`0.840`** | **`0.939`** | **`77.3%` (`100%` Adv Traps)** |
| Unsupervised Story-Agnostic Pipeline (Zero `50467087` Lexicons) | **`88.48`** | **`89.17`** | **`90.45`** | **`0.810`** | **`0.924`** | **`81.8%` (`100%` Adv Traps)** |

```bash
# Run External Judge v1.1.0 & 8-stage ablation study directly
uv run --no-project python judge/judge_v1_1.py .
uv run --no-project python ablation.py
```

---

## Elm Display Layer Rewrite (`elm/`)

> **Branch:** `elm-display-layer` · **Status:** Complete — All views implemented, build_dashboard wired, CI gate verified

The interactive HTML/CSS/JS display layer — currently generated inline by `build_dashboard.py` (~2,000 lines of Python f-string templates + embedded `<script>`) and `build_pages_site.py` (~1,100 lines) — is being rewritten in **Elm 0.19.3** for type safety, maintainability, and the Elm Architecture's clean separation of Model/Update/View.

### Architecture

The Python pipeline is **unchanged** — it still ingests, ranks, and serialises the JSON payload into `<script id="observatoryData">`. The Elm app replaces only the display layer:

```text
Python pipeline (unchanged)              Elm display layer (new)
─────────────────────────                ────────────────────────
ingest.py → corpus_science.py           elm make --optimize
  → ranker.py                             → terser minify
    → build_dashboard.py ─── reads ───►     → dist/observatory.js
      (embeds JSON payload)                   (inlined into HTML)
        → show-me-hn-<id>.html              Elm.Main.init({ flags: payload })
                                              → ports → canvas-iife.js
```

### What's Implemented

- **Full type catalogue** in [`wiki/TYPES.md`](wiki/TYPES.md) — 20 sections covering every domain type, the `Msg` union, `Model`, JSON decoders, canvas port interop, colour palette, directory structure, and build pipeline
- **All 16 Elm source modules** with complete TEA architecture:
  - `Observatory.Types` — all domain types (`ObservatoryPayload`, `CompactComment`, `Tier`, `Weights`, `Catalog`, `RouterConfig`, etc.)
  - `Observatory.Decode` — complete JSON decoders for the Python payload
  - `Observatory.Model` — `init` + `recomputeLiveList` (slider weight reranking)
  - `Observatory.Update` — all `Msg` state transitions and plot command dispatch
  - `Observatory.Ports` — `drawPlot` / `onCanvasProbe` port declarations and encoders
  - `Observatory.Subscriptions` — probe and window event listeners
  - `Observatory.View.Style` — zero-hash `rgb()` colour constants, formatters, and tier styles
  - `Observatory.View.Header` — HN topbar + story fatitem box + 6 mode tabs
  - `Observatory.View.Cards` — comment card list with search, facet filter, badge rendering
  - `Observatory.View.Evidence` — collapsible drawer: ablation/tournament table, KPI strip, facet diagnostics
  - `Observatory.View.Explore` — collapsible drawer: 5 weight sliders, dual OLED bays (phase + gravity)
  - `Observatory.View` — top-level layout orchestrating all sub-views and footer
  - `Pages.Index` — front-page HN-style item list (`render_index_html`)
  - `Pages.Router` — `/item?id=<id>` SPA resolution (`render_item_router_html`)
- **Canvas port bridge** (`js/canvas-iife.js`) — scatter-plot renderer, replaces ~170 lines of inline `<script>`
- **5 test suites (26 tests)** — decoder round-trips, weight recomputation ranking, tier enum coverage, view rendering, pages routing
- **Automated zero-hash verification** — zero `#` characters in emitted HTML/CSS/JS
- **Pinned Nov 2026 toolchain** — `elm-watch` 1.2.9 for dev HMR (not Vite), `elm-test` 0.19.3-0, `elm-review` 2.13.5

### Implementation Status

| Priority | Module | Replaces | Status |
| :---: | :--- | :--- | :---: |
| 1 | `Observatory.View.Header` | HN topbar + story fatitem box + mode tabs | Done |
| 2 | `Observatory.View.Cards` | Comment card list with search, facet filter, and 6 view modes | Done |
| 3 | `Observatory.View.Evidence` | Collapsible drawer: ablation table, facet diagnostics, source registry | Done |
| 4 | `Observatory.View.Explore` | Collapsible drawer: 5 weight tuner sliders, phase plane + gravity canvas | Done |
| 5 | `Pages.Index` | Front-page HN-style item list (`render_index_html`) | Done |
| 6 | `Pages.Router` | `/item?id=<id>` SPA resolution (`render_item_router_html`) | Done |
| 7 | `build_dashboard.py` modification | Read `elm/dist/observatory.js` instead of inline `<script>` | Done |
| 8 | CI integration | Add `cd elm && npm run build && npm run validate` to GitHub Actions | Done |

### Dev Quickstart

```bash
cd elm
npm install

# Dev mode — elm-watch hot-reloads on save, serve hosts on :3000
# Paste a real observatory JSON blob into static/index.html first
npm run dev

# Tests
npm test

# Production build → dist/observatory.js (for Python inlining)
npm run build

# Full CI gate (compile + test + review)
npm run validate
```
