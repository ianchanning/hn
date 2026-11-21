# Monorepo Architecture & Frontend Separation

## The Sovereign Law
The Elm frontend, Python pipeline, and Cloudflare Worker scheduler must coexist as decoupled workspaces under a single monorepo root, with legacy display files strictly quarantined to `archive/`.

## The Trigger
Import confusion, duplicate evaluation scripts, or untracked dependencies across the Python backend, Elm display layer, and Cloudflare Worker scheduler.

## The Pattern

### The WRONG Way
Dumping frontend HTML templates, backend ranking scripts, scheduler worker code, and duplicate evaluation judges all into the repository root:
```text
.
├── build_dashboard.py      # Monolithic f-string HTML generator mixed with backend
├── judge_v1_1.py           # Duplicate judge in root conflicting with judge/
├── show-me-hn-*.html       # Loose legacy outputs cluttering the workspace
```

### The RIGHT Way
Clear separation into distinct monorepo workspaces and canonical packages:
- `hn-comments/` — Python epistemic ranking, ingestion pipeline, data, and tests
- `elm/` — Pure Elm 0.19.3 TEA display layer
- `scheduler/` — Cloudflare Worker cron scheduler
- `judge/` — Canonical External Judge v1.1.0 suite and fixtures
- `archive/` — Quarantined pre-Elm legacy templates and HTML outputs
- Root `package.json` — npm workspaces orchestrating all targets (`npm test`, `npm run build`)
- Root `pyproject.toml` — Modern PEP 621 Python toolchain with zero-dependency runtime
- Root `cli.py` — Transparent forwarder to `hn-comments/cli.py` for root command ergonomics
