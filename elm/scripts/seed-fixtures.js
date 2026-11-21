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

// Copy canvas-iife.js into static/ so static file server serves it directly
const canvasIifePath = join(elmDir, "js", "canvas-iife.js");
const canvasIifeContent = readFileSync(canvasIifePath, "utf-8");
writeFileSync(join(staticDir, "canvas-iife.js"), canvasIifeContent, "utf-8");
console.log("✓ Copied elm/js/canvas-iife.js -> elm/static/canvas-iife.js");

// 2. Build sample catalog and router configs
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

const catalogJson = JSON.stringify(catalog, null, 2).replace(/#/g, "\\u0023");
writeFileSync(join(staticDir, "catalog.json"), catalogJson, "utf-8");

const routerConfig = {
  repo: "ian/hn",
  actions_url: "https://github.com/ian/hn/actions",
  workflow_file: "hn-observatory-pages.yml",
};
const routerConfigJson = JSON.stringify(routerConfig, null, 2).replace(/#/g, "\\u0023");

function makeDevBundle(page) {
  return JSON.stringify({
    observatory: payload,
    catalog: catalog,
    router: routerConfig,
    page: page,
  }, null, 2).replace(/#/g, "\\u0023");
}

// Boot script that passes the unified devBundle into Elm flags
function makeHtml(title, defaultPage) {
  return `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>${title}</title>
  <link rel="stylesheet" href="style.css">
</head>
<body>
  <div id="elm-root"></div>

  <script id="devBundle" type="application/json">
${makeDevBundle(defaultPage)}
  </script>

  <script src="elm.js"></script>
  <script src="canvas-iife.js"></script>
  <script>
    (function() {
      var bundleEl = document.getElementById("devBundle");
      var flags = null;
      if (bundleEl) {
        try {
          flags = JSON.parse(bundleEl.textContent);
          var params = new URLSearchParams(window.location.search);
          var p = params.get("page") || params.get("view");
          if (!p && window.location.pathname.includes("catalog")) p = "catalog";
          if (!p && window.location.pathname.includes("router")) p = "router";
          if (p) flags.page = p;
        } catch(e) {
          console.error("Failed to parse devBundle:", e);
        }
      }
      var root = document.getElementById("elm-root");
      var app = Elm.Main.init({ node: root, flags: flags });
      if (typeof mountCanvasRenderer === "function") {
        mountCanvasRenderer(app);
      }
    })();
  </script>
</body>
</html>
`;
}

// 3. Write static HTML dev entry points
writeFileSync(join(staticDir, "index.html"), makeHtml("HN Epistemic Observatory — Comments View (Dev)", "observatory"), "utf-8");
console.log("✓ Updated elm/static/index.html with unified dev bundle (default: observatory)");

writeFileSync(join(staticDir, "catalog.html"), makeHtml("HN Better Signal News — Frontpage Index (Dev)", "catalog"), "utf-8");
console.log("✓ Updated elm/static/catalog.html with unified dev bundle (default: catalog)");

writeFileSync(join(staticDir, "router.html"), makeHtml("HN Epistemic Observatory — SPA Router (Dev)", "router"), "utf-8");
console.log("✓ Updated elm/static/router.html with unified dev bundle (default: router)");
