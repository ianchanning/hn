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

# 2. Rank comments in the terminal (or pass --json for structured output)
uv run --no-project python cli.py rank 50472038 --top 15

# 3. Rebuild offline from cached snapshots + 7-day SQLite author cache
uv run --no-project python cli.py 50472038 --offline

# 4. Run the full unit, contract, and generalization test suite
uv run --no-project python -m unittest discover -s tests -v
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

### Triggering a Pages Build

```bash
# Trigger by item ID or full HN URL
gh workflow run hn-observatory-pages.yml -f target=50472038
gh workflow run hn-observatory-pages.yml -f target="https://news.ycombinator.com/item?id=50471731"
```

### Standalone Repository Setup

1. Ensure `.github/workflows/hn-observatory-pages.yml` is at `.github/workflows/hn-observatory-pages.yml` in the repository root (the workflow auto-detects whether `cli.py` lives at `.` or `hn-comments/`).
2. In **Settings → Pages**, set **Source** to **Deploy from a branch → `gh-pages` / `/ (root)`**.
3. Trigger **HN Epistemic Observatory Pages** from the **Actions** tab (or via `gh workflow run`). Previously published `/item?id=<id>` pages are preserved across runs and indexed at `/` and `/catalog.json`.

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
python3 cli.py [build|ingest|rank] <item_id_or_url> [options]

Positional:
  target              HN item ID (50472038) or URL (https://news.ycombinator.com/item?id=50472038)

Subcommands (defaults to `build` when omitted):
  build               Ingest, extract scientific features, rank, and emit show-me-hn-<id>.html
  ingest              Fetch ?p=1..N HTML, Algolia tree, article prose, and SQLite author profiles
  rank                Print top-ranked epistemic comments vs. Live HN positions in terminal

Options:
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

## Repository Layout

```text
.
├── cli.py                     # Story-agnostic CLI entry point (build / ingest / rank)
├── ingest.py                  # ?p=1..N HTML crawler, Algolia client & readable article extractor
├── parse_corpus.py            # DOM-order comment parser & cross-page tree reconstructor
├── author_cache.py            # 7-day TTL SQLite WAL author reputation cache
├── source_registry.py         # Cross-domain Tier 3 / 2 / 1 / -1 URL classifier
├── corpus_science.py          # Information-theoretic features, drift & 5-cluster k-means++ facets
├── ranker.py                  # Five-potential epistemic scorer + hinged submodular MMR
├── build_dashboard.py         # Zero-hash (`rgb()`-only) interactive HTML observatory compiler
├── build_pages_site.py        # Incremental GitHub Pages `/item?id=<id>` mirror builder
├── ablation.py                # 8-stage controlled ablation harness on frozen HN 50467087
├── CONTRACT.md                # Ranker output schema & hard anti-Goodhart invariants
├── benchmark/
│   └── dev_sample.json        # Illustrative 24-item development sample
├── judge/
│   ├── epistemic_fixtures_v1.json
│   ├── judge_v1.py            # Graded NDCG@20, pairwise concordance, trap & rescue metrics
│   └── judge_v1_1.py          # Official External Judge v1.1.0 + hard invariant gate
├── data/
│   ├── corpus_v2.json         # Frozen 3,010-comment benchmark corpus (SHA-verified)
│   ├── author_cache.db        # Local 7-day SQLite author cache (gitignored)
│   └── items/<story_id>/      # Per-story ingested snapshots & provenance manifests
└── tests/
    ├── test_ranker.py         # Contract & anti-Goodhart invariant tests
    ├── test_generalization.py # Pagination, TTL cache, source registry & unsupervised gate tests
    └── test_pages_site.py     # GitHub Pages `/item?id=` router & workflow security tests
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
