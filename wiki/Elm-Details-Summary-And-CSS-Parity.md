# Elm `<details>` `<summary>` and CSS Parity Invariants

## 1. Browser Default Disclosure Synthesis on `<details>`
In HTML5, every `<details>` element implicitly expects a `<summary>` element child as its first child.
If `<summary>` is omitted:
- The browser (Firefox, Chromium, WebKit) synthesizes an automatic `<summary>Details</summary>` element.
- An unwanted default disclosure triangle arrow appears alongside the text "Details".

### Invariant Fix:
Always include an explicit hidden `<summary>` child for drawers controlled via external TEA UI buttons:
```elm
details (class "proof-drawer" :: id "proofDrawer" :: openAttr)
    [ summary [ class "hn-summary", style "display" "none" ] []
    , content
    ]
```

## 2. Nav Button Hover Underline Cascade
When concatenating CSS sheets (e.g. `build_dashboard.py` and `build_pages_site.py` into `style.css`):
- `button.nav-btn:hover` must NOT specify `text-decoration: underline`.
- Mode tabs (`Top 40`, `HN Top 40`) and topbar toggles (`explore`, `evidence`) use `.nav-btn` and must maintain `text-decoration: none` and transition color to white (`color: rgb(255, 255, 255)`).

## 3. Automated Parity Differ (`npm run diff`)
Run `npm run diff` in `elm/` (`elm/scripts/diff-parity.js`) to execute a fundamental comparison:
- 100% CSS selector and property coverage against Python's `<style>` block.
- Exact virtual DOM tree structure, attributes, and text tokens between Elm TEA output and Python static shell.
- Strict zero-hash invariant across all generated static assets.

## 4. Frontpage Index Padding & Timestamp Casing
- Frontpage item rows must be wrapped in `<div class="list-pad">` (CSS padding: `10px 8px 4px 4px`), never styling padding directly on `<table>` with `border-collapse: collapse`.
- Frontpage footer uses `<div class="hn-footer">` (`border-top: 2px solid rgb(255, 102, 0); padding: 12px 10px 18px;`), not `.sheet-foot`.
- Topbar timestamp casing: `.topbar-right` must have `text-transform: none;` on pages site stylesheets so `"Updated YYYY-MM-DD HH:MM UTC"` retains uppercase `'Updated'` and `'UTC'`, avoiding inheritance of the comments observatory's lowercase transform.

