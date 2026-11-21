/**
 * Seed dev fixtures for local Elm development.
 *
 * Extracts the real observatory payload from the root show-me-hn-50467087.html,
 * builds sample catalog and router fixtures, and writes self-contained dev HTML
 * pages into elm/static/.
 *
 * Run via: npm run fixtures
 */

import { readFileSync, writeFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const elmDir = join(__dirname, "..");
const rootDir = join(elmDir, "..");
const staticDir = join(elmDir, "static");

// 1. Extract payload from canonical observatory
const showMeHtmlPath = join(rootDir, "show-me-hn-50467087.html");
const showMeHtml = readFileSync(showMeHtmlPath, "utf-8");

const match = showMeHtml.match(
  /<script\s+id=["']observatoryData["']\s+type=["']application\/json["']>(.*?)<\/script>/s
);

if (!match) {
  console.error("Could not find <script id=\"observatoryData\"> in show-me-hn-50467087.html");
  process.exit(1);
}

const rawPayloadJson = match[1].trim();
const payload = JSON.parse(rawPayloadJson);

// Write standalone fixture JSON
writeFileSync(join(staticDir, "fixture.json"), rawPayloadJson, "utf-8");
console.log(`✓ Wrote elm/static/fixture.json (${(Buffer.byteLength(rawPayloadJson) / 1024).toFixed(1)} KB)`);

// Common dev header navigation
const devNav = `
  <div style="background: rgb(246, 246, 239); border-bottom: 1px solid rgb(255, 102, 0); padding: 6px 12px; font-family: monospace; font-size: 12px; display: flex; gap: 14px; align-items: center; z-index: 9999; position: relative;">
    <span style="font-weight: bold; color: rgb(255, 102, 0);">ELM DEV PAGES:</span>
    <a href="index.html" style="color: rgb(34, 34, 34); text-decoration: underline; font-weight: bold;">1. Observatory (Comments)</a>
    <a href="catalog.html" style="color: rgb(34, 34, 34); text-decoration: underline; font-weight: bold;">2. Frontpage (Index)</a>
    <a href="router.html" style="color: rgb(34, 34, 34); text-decoration: underline; font-weight: bold;">3. SPA Router (/item?id=)</a>
  </div>
`;

// Boot script that loads whichever payload element is present
const devBootScript = `
  <script>
    (function() {
      var dataEl = document.getElementById("observatoryData") ||
                   document.getElementById("catalogData") ||
                   document.getElementById("routerConfig");
      var flags = null;
      if (dataEl) {
        try { flags = JSON.parse(dataEl.textContent); } catch(e) {
          console.error("Failed to parse fixture flags:", e);
        }
      }
      var root = document.getElementById("elm-root");
      var app = Elm.Main.init({ node: root, flags: flags });
      if (typeof mountCanvasRenderer === "function") {
        mountCanvasRenderer(app);
      }
    })();
  </script>
`;

// 2. Write static/index.html (Comments Observatory)
const indexHtml = `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>HN Epistemic Observatory — Comments View (Dev)</title>
  <link rel="stylesheet" href="style.css">
</head>
<body>
${devNav}
  <div id="elm-root"></div>

  <script id="observatoryData" type="application/json">
${rawPayloadJson}
  </script>

  <script src="elm.js"></script>
  <script src="../js/canvas-iife.js"></script>
${devBootScript}
</body>
</html>
`;
writeFileSync(join(staticDir, "index.html"), indexHtml, "utf-8");
console.log("✓ Updated elm/static/index.html with real HN 50467087 observatory fixture");

// 3. Write static/catalog.json and static/catalog.html (Frontpage Index)
const catalog = {
  updated_utc: "2026-11-21 09:00 UTC",
  total_published: 3,
  total_size_mb: 3.5,
  frontpage_synced_utc: "2026-11-21 09:00 UTC",
  frontpage_ids: [50467087, 50472038, 50469123],
  uri_template: "/item?id={story_id}",
  items: [
    {
      story_id: 50467087,
      story_title: payload.story_title || "Jensen Huang resigns as CEO of Nvidia",
      story_url: payload.story_url || "https://nvidianews.nvidia.com/news/leadership-transition",
      points: 3421,
      story_author: "sama",
      total_comments: payload.comments ? payload.comments.length : 856,
      epistemic_gold: payload.tiers ? (payload.tiers.epistemic_gold || 42) : 42,
      grounded_analysis: payload.tiers ? (payload.tiers.grounded_analysis || 128) : 128,
      t2_ref_utc: "2026-11-20 18:30 UTC",
      size_kb: 2147.2,
    },
    {
      story_id: 50472038,
      story_title: "Reflections on 10,000 Hours of Elm Architecture in Production",
      story_url: "https://elm-lang.org/news/architecture-at-scale",
      points: 892,
      story_author: "evancz",
      total_comments: 314,
      epistemic_gold: 18,
      grounded_analysis: 65,
      t2_ref_utc: "2026-11-21 07:15 UTC",
      size_kb: 890.5,
    },
    {
      story_id: 50469123,
      story_title: "Show HN: Nyx Epistemic Observatory for Hacker News",
      story_url: "",
      points: 512,
      story_author: "charpie",
      total_comments: 178,
      epistemic_gold: 25,
      grounded_analysis: 49,
      t2_ref_utc: "2026-11-21 08:00 UTC",
      size_kb: 512.0,
    },
  ],
};

const catalogJson = JSON.stringify(catalog, null, 2);
writeFileSync(join(staticDir, "catalog.json"), catalogJson, "utf-8");

const catalogHtml = `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>HN Epistemic News — Frontpage Index (Dev)</title>
  <link rel="stylesheet" href="style.css">
</head>
<body>
${devNav}
  <div id="elm-root"></div>

  <script id="catalogData" type="application/json">
${catalogJson}
  </script>

  <script src="elm.js"></script>
${devBootScript}
</body>
</html>
`;
writeFileSync(join(staticDir, "catalog.html"), catalogHtml, "utf-8");
console.log("✓ Created elm/static/catalog.html (Frontpage Index)");

// 4. Write static/router.html (Router SPA)
const routerConfig = {
  repo: "ian/hn",
  actions_url: "https://github.com/ian/hn/actions",
  workflow_file: "hn-observatory-pages.yml",
};

const routerConfigJson = JSON.stringify(routerConfig, null, 2);
const routerHtml = `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>HN Epistemic Observatory — SPA Router (Dev)</title>
  <link rel="stylesheet" href="style.css">
</head>
<body>
${devNav}
  <div id="elm-root"></div>

  <script id="routerConfig" type="application/json">
${routerConfigJson}
  </script>

  <script src="elm.js"></script>
${devBootScript}
</body>
</html>
`;
writeFileSync(join(staticDir, "router.html"), routerHtml, "utf-8");
console.log("✓ Created elm/static/router.html (SPA Router)");
