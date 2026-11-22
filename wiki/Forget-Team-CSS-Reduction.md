# Forget-Team CSS Reduction Experiment

## The Sovereign Law
When running a multi-agent `forget-team` tournament, the External Judge must enforce **every** production invariant (including downstream Python `assert "#" not in css` and immutable `elm/tests/`), workers must be guarded against context-bomb files (`elm/static/index.html` > line 25), and every HTML emitter (`build_pages_site.py` and `build_dashboard.py`) must read `elm/static/style.css` as the single source of truth.

## The Trigger
- `Error: 429: {"code":"token_quota_exceeded"}` / `97%/131k` KV saturation in 2 turns (workers reading 2.9 MB `elm/static/index.html`)
- `AssertionError: Zero-hash violated in elm/static/style.css` (CSS `#id` selectors passing Elm-only visual judge)
- `Query.findAll [ class "plot" ] — 0 matches found` (workers stripping test-locked classes or editing `elm/tests/`)
- Live `gh-pages/items/<id>.html` renders unstyled cards after Elm CSS refactor (`build_dashboard.py` embedding hardcoded legacy `<style>` alongside new `elm/dist/observatory.js`)

## Experiment Summary (Nov 22, 2026)
4 isolated Git worktrees + Herdr 2×2 panes running `pi --model cerebras/qwen-3.8-27b --thinking max`, orchestrated by a Lead External Judge (`elm make`, `npm test`, `npx elm-review`, headless Chrome pixel diff ≤ 0.05%, identical DOM text).

- **Score formula (lower is better):** `style.css bytes + <style> bytes + rendered inline style= bytes + 16 × rendered class= attrs` (across `?page=index` and `?page=observatory`).
- **Trajectory:**

| Milestone | Commit | Score | `style.css` | Inline `style=` | `class=` attrs | Diff px |
|---|---|---:|---:|---:|---:|---:|
| Baseline | `8b9a6e4` | 34,115 | 19,990 B | 5,069 B | 566 | 0 |
| Round 1 Best (`w4`) | `717518c` | 24,319 | 17,098 B | 2,725 B | 281 | 0 |
| Round 2 Best (`w4`) | `6f1c91f` | 15,773 | 11,194 B | 1,027 B | 222 | 0 |
| **Shipped (PR #2 + audit)** | `7293b80` | **16,001** | **11,422 B** | **1,027 B** | **222** | **0** |

- **Net gain:** **−18,114 pts (−53.1%)**, `style.css` −42.9%, inline styles −79.7%, rendered `class=` attrs −60.8%, **0 differing pixels** on both pages, 37/37 `elm-test`, 0 `elm-review` errors, 16/16 Python tests.

## The Pattern (5 Hard-Won Invariants)

### 1. Zero-Hash CSS Selectors (`#id` → `[id="..."]`)
CSS `#id` selectors break `assert "#" not in css` in `hn-comments/build_pages_site.py`.
```css
/* WRONG — breaks Python zero-hash gate */
#cards > article > div:first-child { color: var(--g); }

/* RIGHT — zero `#`, identical styling */
[id="cards"] > article > div:first-child { color: var(--g); }
```

### 2. Context Guard & Staggered Kicks for TPM-Limited Providers
Reading `elm/static/index.html` unbounded dumps 50 KB of `devBundle` JSON into KV cache, saturating 131k windows in 2 turns and triggering Cerebras `429`/`402`.
```text
WRONG: Spawn 4 parallel prompts with no file-read guard; let workers read index.html freely.
RIGHT: Add `NEVER read elm/static/index.html past line 25` to AGENTS.md, stagger prompts (10-15s)
       with 429 backoff, and hard-wipe panes once KV > 80% (distilling invariants into AGENTS.md first).
```

### 3. Anti-Goodhart Lead Harness & Forensic Pre-Ship Audit
Initial-load screenshots cannot see interactive states or test tampering.
- Stage ONLY allowed paths (`elm/src`, `elm/static/style.css`) when committing candidates — never let workers edit `elm/tests/` to pass `npm test`.
- Document test-locked classes in `AGENTS.md`: `storylink`, `sitebit`, `subtext`, `list-pad`, `story-title`, `mode-tab`, `kpi-cell`, `slider-row`, `plot`, `c-card`, `hn-quote`, `wrap`, `sheet-foot`.
- Before shipping, diff dropped CSS selectors against Elm source to catch unrendered interactive states (e.g. `.probe-box .hn-comhead` on canvas click, `.pagetop a:hover`).

### 4. Single Source of Truth for Production CSS (`7d73cfd`)
```python
# WRONG — build_dashboard.py hardcodes a 620-line legacy <style> while embedding new observatory.js
head_doc = f"<style> .card-list {{ ... }} </style>"

# RIGHT — embed elm/static/style.css whenever use_elm=True (+ heal mismatched archived items in build_pages_site.py)
elm_style_css = _get_style_css() if use_elm else ""
```

### 5. Isolated Worktree Symlinks
Fresh worktrees lack gitignored build artifacts; symlink `elm/node_modules`, `elm/static/canvas-iife.js`, and `elm/static/fixture.json`, and exclude `elm/node_modules` (without trailing slash) in `.git/info/exclude` so `git status` and `git clean -fd` leave symlinks intact.
