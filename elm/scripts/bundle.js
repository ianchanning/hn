/**
 * Production build script: compiles Elm and bundles the output for
 * Python to inline into self-contained observatory HTML files.
 *
 * Usage: node scripts/bundle.js
 *
 * Outputs:
 *   dist/elm.min.js        — Optimised + minified Elm app
 *   dist/canvas-bridge.js  — Canvas port bridge (copied verbatim)
 *   dist/boot.js           — Minimal bootstrap glue (Elm.Main.init + port wiring)
 *   dist/observatory.js    — All-in-one concatenation for Python to inline
 */

import { readFileSync, writeFileSync, copyFileSync } from "node:fs";
import { execSync } from "node:child_process";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const root = join(__dirname, "..");
const dist = join(root, "dist");

// 1. Elm compile (--optimize already run via npm run build:elm)
//    Just verify the file exists
const elmJs = join(dist, "elm.js");
try {
  readFileSync(elmJs);
} catch {
  console.error("dist/elm.js not found — run `npm run build:elm` first.");
  process.exit(1);
}

// 2. Minify (runs via npm postbuild, but we can also do it here)
try {
  execSync("npx terser dist/elm.js --compress 'pure_funcs=[F2,F3,F4,F5,F6,F7,F8,F9,A2,A3,A4,A5,A6,A7,A8,A9],pure_getters,passes=2' --mangle --output dist/elm.min.js", {
    cwd: root,
    stdio: "inherit",
  });
} catch {
  console.warn("terser minification failed — using unminified elm.js");
  copyFileSync(elmJs, join(dist, "elm.min.js"));
}

// 3. Copy canvas bridge
copyFileSync(join(root, "js", "canvas.js"), join(dist, "canvas-bridge.js"));

// 4. Generate boot.js (production bootstrap without Vite/module imports)
const boot = `
(function() {
  var dataEl = document.getElementById("observatoryData");
  var flags = null;
  if (dataEl) {
    try { flags = JSON.parse(dataEl.textContent); } catch(e) {}
  }
  var root = document.getElementById("elm-root");
  var app = Elm.Main.init({ node: root, flags: flags });
  if (typeof mountCanvasRenderer === "function") {
    mountCanvasRenderer(app);
  }
})();
`.trim();
writeFileSync(join(dist, "boot.js"), boot);

// 5. Concatenate into single observatory.js for Python inlining
const elmMin = readFileSync(join(dist, "elm.min.js"), "utf-8");
const canvasBridge = readFileSync(join(dist, "canvas-bridge.js"), "utf-8");
// Strip ES module export for IIFE context
const canvasIIFE = canvasBridge
  .replace(/^export\s+/gm, "")
  .replace(/import\s+.*;\s*/g, "");

const combined = [
  "/* HN Epistemic Observatory — Elm Display Layer */",
  elmMin,
  canvasIIFE,
  boot,
].join("\n");

writeFileSync(join(dist, "observatory.js"), combined);

const sizeKb = (Buffer.byteLength(combined) / 1024).toFixed(1);
console.log(`✓ dist/observatory.js (${sizeKb} KB) — ready for Python inlining`);
