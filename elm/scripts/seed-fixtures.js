/**
 * Seed dev fixtures for local Elm development.
 *
 * Extracts the real observatory payload from the root show-me-hn-50467087.html,
 * builds sample catalog and router fixtures, and writes self-contained dev HTML
 * pages into elm/static/.
 *
 * Run via: npm run fixtures
 */

import { readFileSync, writeFileSync, existsSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { execSync } from "node:child_process";

const __dirname = dirname(fileURLToPath(import.meta.url));
const elmDir = join(__dirname, "..");
const rootDir = join(elmDir, "..");
const staticDir = join(elmDir, "static");

// 1. Extract payload from canonical observatory or fallback to existing fixture.json
const fixtureJsonPath = join(staticDir, "fixture.json");
const candidateHtmlPaths = [
  join(rootDir, "hn-comments", "test-observatory-50467087.html"),
  join(rootDir, "hn-comments", "show-me-hn-50467087.html"),
  join(rootDir, "show-me-hn-50467087.html"),
];

let payload = null;
let showMeHtml = "";
const existingHtmlPath = candidateHtmlPaths.find(p => existsSync(p));

if (existingHtmlPath) {
  showMeHtml = readFileSync(existingHtmlPath, "utf-8");
  const match = showMeHtml.match(
    /<script\s+id=["']observatoryData["']\s+type=["']application\/json["']>(.*?)<\/script>/s
  );
  if (match) {
    try {
      payload = JSON.parse(match[1].trim());
      console.log(`✓ Extracted payload from ${existingHtmlPath}`);
    } catch (e) {
      console.warn(`Could not parse JSON from ${existingHtmlPath}:`, e.message);
    }
  }
}

if (!payload && existsSync(fixtureJsonPath)) {
  try {
    payload = JSON.parse(readFileSync(fixtureJsonPath, "utf-8"));
    console.log(`✓ Loaded existing payload from ${fixtureJsonPath}`);
  } catch (e) {
    console.warn(`Could not parse ${fixtureJsonPath}:`, e.message);
  }
}

if (!payload) {
  console.log("No fixture or HTML found — generating via build_dashboard.py 50467087...");
  try {
    execSync(`python3 hn-comments/build_dashboard.py 50467087 "${candidateHtmlPaths[0]}"`, { cwd: rootDir, stdio: "inherit" });
    if (existsSync(candidateHtmlPaths[0])) {
      showMeHtml = readFileSync(candidateHtmlPaths[0], "utf-8");
      const match = showMeHtml.match(
        /<script\s+id=["']observatoryData["']\s+type=["']application\/json["']>(.*?)<\/script>/s
      );
      if (match) payload = JSON.parse(match[1].trim());
    }
  } catch (err) {
    console.error("Failed to build dashboard fixture:", err.message);
    process.exit(1);
  }
}

if (!payload) {
  console.error("Could not obtain observatory payload for 50467087.");
  process.exit(1);
}

// Ensure manifest has points and story_author from header if not present
if (payload.manifest) {
  if (!payload.manifest.points) {
    const pointsMatch = showMeHtml.match(/<span class=["']score["']>(\d+)\s+points<\/span>/);
    if (pointsMatch) payload.manifest.points = parseInt(pointsMatch[1], 10);
  }
  if (!payload.manifest.story_author) {
    const authorMatch = showMeHtml.match(/by\s+<a\s+href=["'][^"']*\/user\?id=([^"']+)["']/);
    if (authorMatch) payload.manifest.story_author = authorMatch[1];
  }
}

const serializedPayloadJson = JSON.stringify(payload).replace(/#/g, "\\u0023");

// Write standalone fixture JSON
writeFileSync(join(staticDir, "fixture.json"), serializedPayloadJson, "utf-8");
console.log(`✓ Wrote elm/static/fixture.json (${(Buffer.byteLength(serializedPayloadJson) / 1024).toFixed(1)} KB)`);

// Verify canonical elm/static/style.css exists and maintains zero-hash invariant
const styleCssPath = join(staticDir, "style.css");
if (existsSync(styleCssPath)) {
  const css = readFileSync(styleCssPath, "utf-8");
  if (css.includes("#")) {
    console.error("FATAL: zero-hash violation in elm/static/style.css");
    process.exit(1);
  }
  console.log(`✓ Verified canonical elm/static/style.css (${(Buffer.byteLength(css) / 1024).toFixed(1)} KB, zero-hash)`);
} else {
  console.warn("WARNING: elm/static/style.css not found");
}

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
  repo: "ianchanning/hn",
  actions_url: "https://github.com/ianchanning/hn/actions",
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
  <link rel="apple-touch-icon" sizes="180x180" href="/apple-touch-icon.png">
  <link rel="icon" type="image/png" sizes="32x32" href="/favicon-32x32.png">
  <link rel="icon" type="image/png" sizes="16x16" href="/favicon-16x16.png">
  <link rel="manifest" href="/site.webmanifest">
  <link rel="stylesheet" href="style.css">
</head>
<body>
  <div id="elm-root"></div>

  <script id="devBundle" type="application/json">
${makeDevBundle(defaultPage)}
  </script>

  <script src="elm.js"></script>
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
      flags.q = new URLSearchParams(window.location.search).get('q') || '';
      var app = Elm.Main.init({ node: root, flags: flags });
      if (app && app.ports && app.ports.setUrlQuery) {
        app.ports.setUrlQuery.subscribe(function (q) {
          var u = new URL(window.location.href);
          if (q) { u.searchParams.set('q', q); } else { u.searchParams.delete('q'); }
          window.history.replaceState(null, '', u.toString());
        });
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
