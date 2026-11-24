# Hickey's Treasure Trove — Holistic Simplicity, Performance & UX Experiments

## The Sovereign Law
Simplicity is untangling complected seams (not making things "easy" by adding wrappers or duplicate copies). Never optimize a subjective "UX score" — lock a **Multi-State UX Floor** (desktop + mobile, interactive states, CLS = 0, contrast, zero-hash) and run tight micro-experiments targeting one hard physical metric at a time.

## The Trigger
When a micro-optimization reveals cross-stack coupling (tests ↔ CSS classes, Python ↔ duplicated `<style>`, static screenshots ↔ interactive states), record the untangling experiment here with a **Hard Gate + Scalar Score** before firing workers.

---

## The Workbench: 6-State Holistic UX Floor (Judge v2 Blueprint)
Upgrade the static 2-screenshot judge into a fast (~5s) headless-Chrome **6-State UX Matrix** so optimizations cannot break interactive or mobile UX:
- **Viewports:** Desktop (`1280px`) + Mobile (`375px`)
- **States:** (1) Default load, (2) Explore drawer open, (3) Evidence drawer open, (4) Scatter point probed (catches `.probe-box .hn-comhead`), (5) Search/Facet filtered, (6) Mode tab switched
- **Hard Invariants on every state:**
  - `CLS == 0.000` (zero layout shift on hydration, drawer toggle, tab switch, slider drag)
  - Zero horizontal overflow on `375px` mobile; visible `:focus-visible`; WCAG contrast ≥ 4.5:1
  - Zero `#` characters across HTML/CSS/JS; zero console errors; `elm make`, `elm-test`, `elm-review`, `pytest` green

---

## The Experiment Backlog (Hard Gate + Scalar Score)

### 1. Semantic Accessibility → True Zero-Class HTML (`class_attrs → 0`)
- **Untangles:** `elm/tests/` coupled to 13 CSS class names (`c-card`, `storylink`, `sitebit`, `subtext`, `kpi-cell`, etc.).
- **Experiment:** Migrate `elm/tests/` to ARIA roles, semantic tags, and `data-*` queries (Testing-Library style), then drive rendered `class=""` count from `222 → 0` and CSS toward `< 8 KB`.
- **Gate:** 6-State UX Matrix + 0 diff px + zero-hash + full test suite.

### 2. DOM Diet (Rendering Speed × Structural Simplicity)
- **Untangles:** Legacy bootstrap/grid wrapper `<div>`s inside comment cards and drawers.
- **Score:** Rendered DOM node count + max nesting depth per comment card & page.
- **Gate:** 6-State UX Matrix + 0 diff px (desktop & 375px mobile).

### 3. Slider Interaction Latency — 60fps Stress Test (INP)
- **Untangles:** Per-tick `List.sortBy` / full VDOM diffing / canvas redraws during Signal Tuner slider drags on 500–1,000 comments.
- **Score:** p95 ms from `input` on `sl_ig` → DOM + Canvas frame commit in headless Chrome (target `< 16 ms`).
- **Tactics:** `Html.Lazy`, `Html.Keyed`, `requestAnimationFrame` coalescing in `canvas-iife.js`, incremental scoring.

### 4. Zero-Flash Hydration & Single-File Artifact Byte Diet (`110 KB → < 45 KB`)
- **Untangles:** Redundant pre-hydration HTML shell in `build_dashboard.py` (immediately wiped on Elm boot), repeated JSON object keys in `observatoryData`, and un-mangled `elm.js`.
- **Score:** Gzipped + raw `items/<id>.html` bytes + First Contentful Paint (FCP) + Total Blocking Time (TBT).
- **Tactics:** Measure pre-hydration shell vs empty `#elm-root` on FCP/CLS; columnar/positional JSON encoding with 2dp float quantization; `elm make --optimize` + Terser `pure_funcs` minification.

### 5. Zero-Custom-JS Elm (Pure Inline SVG Scatter Plots vs `canvas-iife.js`)
- **Untangles:** The last 4.5 KB of custom JS glue + Elm ports (`canvas-iife.js`).
- **Experiment:** A/B pure Elm `elm/svg` scatter plots against `<canvas>` on bundle bytes, HiDPI sharpness, and slider drag frame-time across N = 100 / 500 / 1,000 comments.

### 6. Zero-Hash Shareable Epistemic Lenses (`?w=...` Query State)
- **Untangles:** Ephemeral slider calibrations that cannot be shared without `#hash` fragments.
- **Experiment:** Encode non-default tuner weights + active tab + facet into clean zero-hash query params (`?id=...&w=...&m=...`), verified by round-trip URL hydration tests.

### 7. Instant Zero-Backend Full-Archive Search (`catalog.json`)
- **Untangles:** External Algolia redirect vs searching all 660+ locally published observatories.
- **Score:** Client-side filter latency (`< 10 ms`) + zero extra network requests on `Pages/Index.elm`.

### 8. Out-of-Domain Generalization Tournament (`ranker.py`)
- **Untangles:** Overfitting to single-story benchmark heuristics across 660+ archived `gh-pages` stories.
- **Experiment:** Stratified cross-domain holdout (systems / AI / Show HN / politics); run `forget-team` minimizing feature complexity while maximizing unseen-story `judge_v1_1` score.

### 9. Agentic Meta-Experiments (Using `hn` as the Benchmark)
- **Wiki A/B Ablation (Testing Karpathy's LLM-Wiki Hypothesis):** Measure tokens, compile retries, and Goodhart escape rate across 3 arms on an identical Elm+Python task: (A) raw repo + tests only, (B) capped 15-line `AGENTS.md` epigenetic invariants only, (C) full `wiki/index.md` progressive disclosure.
- **Asymmetric `forget-team` (3 Builders + 1 Goodhart Hunter):** Dedicate worker `w4` solely to red-teaming `w1..w3` diffs and writing failing invariant tests to expose judge blind spots automatically.
### 10. Dreamer's dream
- Purity I guess
- The experiment is to continue the HTML/CSS simplicity experiment
- Perhaps we want to get the remaining CSS tags to match the bootstrap tags
	- we use 'rescued' instead of 'success'
	- we could use the nav styles instead of the hard-coded '|' separator
	- we can also work some of the vibe coded styles to get them consistent
		- the tables could probably match what we have in the mofo forms better
		- the orange uppercase headings should be corrected
- I keep wondering if some of those cool mobile UX AI skills could be used, but kind of goes against the HN minimalism?
- What modern CSS can we use
	- Its the fight between magic and minimalist simplicity
	- Something so smooth, but so simple
- Boring shit like removing that in-between page load flash
	- I think we have a separate tournament for that
- Obviously we can get the offline, web app going, pingolin style
- What else can we do with Elm?
	- Can we improve on the JSON testing that gets loaded?
- Can we do something to bring these cool new styles back to mofoforms?
	- Can we unlock some more power there?
	- Does it fit nicely with Elm CSS somehow?
	- Like if you can minimise the CSS, you have maximal control over the type surface
	- Make a beautiful site for the mofobootstrap
	- Maybe steal the tailwind styles for a classless CSS
	- Or maybe just make every site more beautiful
	- Find a better base for the internet
	- Make Edward Tufte happy
	- Bring LaTeX to everyone
- What can we do with the types?
	- Can we simplify those?
	- Can we make them more expressive?
	- Can we get more powerful tests from them?
	- Do we know what the test coverage is?
- Oooh... testing we need the Page Object Model tests
	- Bring in the learnings from pingolin to this
	- Apply this CSS tournament to pingolin
	- Need a mofobootstrap for pingolin


---

## Anti-Wiki-Rot Discipline (3-Tier Knowledge Split)
Observed live during the Nov 22 CSS tournament: prose rots within *hours* (`Elm-Details-Summary-And-CSS-Parity.md` still mandated `class "hn-summary"` + `style "display" "none"` the same afternoon PR #2 deleted them), while generic Elm trivia (`tuples max 3`, `Attr.min`) is permanent index token tax already known by model weights and the Elm compiler.

Route every discovery to the right tier — **never** build an append-only Confluence-for-LLMs:
1. **Enforceable invariants (`zero-hash`, locked hooks, CSS/JS sync)** → **Code / Tests / `judge.py` / `elm-review`** (gates fail loudly; prose rots silently).
2. **Repo-specific invisible traps (`index.html` 2.9 MB JSON bomb, cross-file landmines)** → **Capped `AGENTS.md` (≤ 15 lines, replace-not-append)** so every stateless worker sees them with zero retrieval miss.
3. **Lab Notebook (*why*, trade-offs, experiment scoreboards, backlog)** → **`wiki/`** for humans & Lead orchestrators across sessions. **GC rule:** delete generic language trivia and prune/update stale pages whenever code changes.
