/**
 * Production build script: compiles Elm and bundles the output for
 * Python to inline into self-contained observatory HTML files.
 *
 * Usage: node scripts/bundle.js
 *
 * Outputs:
 *   dist/elm.min.js        — Optimised + minified Elm app
 *   dist/observatory.js    — All-in-one concatenation for Python inlining
 */

import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { execSync } from "node:child_process";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const root = join(__dirname, "..");
const dist = join(root, "dist");

mkdirSync(dist, { recursive: true });

// 1. Verify elm make output exists
const elmJs = join(dist, "elm.js");
try {
  readFileSync(elmJs);
} catch {
  console.error("dist/elm.js not found — run `npm run build:elm` first.");
  process.exit(1);
}

// 2. Minify
try {
  execSync(
    "npx terser dist/elm.js" +
    " --compress 'pure_funcs=[F2,F3,F4,F5,F6,F7,F8,F9,A2,A3,A4,A5,A6,A7,A8,A9],pure_getters,passes=2'" +
    " --mangle --output dist/elm.min.js",
    { cwd: root, stdio: "inherit" }
  );
} catch {
  console.warn("terser minification failed — using unminified elm.js");
  writeFileSync(join(dist, "elm.min.js"), readFileSync(elmJs));
}

// 3. Read components
const elmMin = readFileSync(join(dist, "elm.min.js"), "utf-8");

// 4. Production boot glue (no ES modules, no bundler)
const boot = `
(function() {
  var dataEl = document.getElementById("observatoryData") ||
               document.getElementById("catalogData") ||
               document.getElementById("routerConfig");
  var flags = null;
  if (dataEl) {
    try { flags = JSON.parse(dataEl.textContent); } catch(e) {}
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
`.trim();

// 5. Concatenate into single observatory.js for Python inlining
const combined = [
  "/* HN Epistemic Observatory — Elm Display Layer */",
  elmMin,
  boot,
].join("\n");

writeFileSync(join(dist, "observatory.js"), combined);

const sizeKb = (Buffer.byteLength(combined) / 1024).toFixed(1);
console.log(`✓ dist/observatory.js (${sizeKb} KB) — ready for Python inlining`);
