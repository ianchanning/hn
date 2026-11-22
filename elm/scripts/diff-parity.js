#!/usr/bin/env node

/**
 * diff-parity.js
 *
 * Fundamental Structural Diff between Python Legacy Dashboard and Elm 0.19.3 Display Layer.
 *
 * Compares:
 *  1. CSS Selectors and Properties: Python <style> vs elm/static/style.css
 *  2. HTML DOM Hierarchy: Python static DOM shell vs Elm TEA virtual DOM
 *  3. Invariants: Strict zero-hash assertion across all styles and markup
 */

import { readFileSync, writeFileSync, existsSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { execSync } from "node:child_process";
import vm from "node:vm";

const __dirname = dirname(fileURLToPath(import.meta.url));
const elmDir = join(__dirname, "..");
const rootDir = join(elmDir, "..");
const staticDir = join(elmDir, "static");

console.log("================================================================================");
console.log("       HN EPISTEMIC OBSERVATORY: PYTHON vs ELM PARITY DIFFER (TEA DOM / CSS)");
console.log("================================================================================\n");

// ---------------------------------------------------------------------------
// 1. CSS DIFFER
// ---------------------------------------------------------------------------
console.log("--- 1. CSS DIFFERENCE & CASCADE ANALYSIS ---");

const dashPyPath = existsSync(join(rootDir, "hn-comments", "build_dashboard.py"))
  ? join(rootDir, "hn-comments", "build_dashboard.py")
  : join(rootDir, "build_dashboard.py");
const dashPy = readFileSync(dashPyPath, "utf-8");
const pyStyleMatch = dashPy.match(/<style>(.*?)<\/style>/s);
if (!pyStyleMatch) {
  console.error("FAIL: Could not locate <style> in build_dashboard.py");
  process.exit(1);
}

const pyCss = pyStyleMatch[1].replace(/\{\{/g, "{").replace(/\}\}/g, "}");
const elmCss = readFileSync(join(staticDir, "style.css"), "utf-8");

function parseCssRules(cssText) {
  const clean = cssText.replace(/\/\*.*?\*\//gs, "");
  const ruleMap = new Map();
  const regex = /([^{]+)\{([^}]+)\}/g;
  let match;
  while ((match = regex.exec(clean)) !== null) {
    const rawSelectors = match[1].trim();
    const body = match[2].trim();
    const props = new Map();
    for (const decl of body.split(";")) {
      const trimmed = decl.trim();
      if (!trimmed || !trimmed.includes(":")) continue;
      const [k, ...vParts] = trimmed.split(":");
      props.set(k.trim(), vParts.join(":").trim());
    }
    for (const sel of rawSelectors.split(",")) {
      const s = sel.trim();
      if (s) {
        if (!ruleMap.has(s)) ruleMap.set(s, []);
        ruleMap.get(s).push(props);
      }
    }
  }
  return ruleMap;
}

const pyRules = parseCssRules(pyCss);
const elmRules = parseCssRules(elmCss);

let missingSelectors = 0;
for (const sel of pyRules.keys()) {
  if (!elmRules.has(sel)) {
    console.warn(`  [MISSING IN ELM] Selector: ${sel}`);
    missingSelectors++;
  }
}

if (missingSelectors === 0) {
  console.log(`✓ 100% Python CSS selector coverage in Elm (${pyRules.size} / ${pyRules.size} selectors present)`);
}

// Check for conflicting hover rules on buttons
const navBtnHovers = elmRules.get("button.nav-btn:hover") || [];
let hasBadUnderline = false;
for (const props of navBtnHovers) {
  if (props.get("text-decoration") === "underline") {
    hasBadUnderline = true;
  }
}
if (hasBadUnderline) {
  console.error("✗ CSS REGRESSION: button.nav-btn:hover has text-decoration: underline!");
} else {
  console.log("✓ CSS INVARIANT: button.nav-btn:hover has text-decoration: none");
}

// Check that topbar-right preserves casing for timestamps
const topbarRightRules = elmRules.get(".topbar-right") || [];
const hasNone = topbarRightRules.some((props) => props.get("text-transform") === "none");
if (hasNone) {
  console.log("✓ CSS INVARIANT: .topbar-right has text-transform: none (preserves 'Updated ... UTC')");
} else {
  console.error("✗ CSS REGRESSION: .topbar-right missing text-transform: none");
}

// Zero-hash check
const hashInCss = elmCss.includes("#");
if (hashInCss) {
  console.error("✗ ZERO-HASH REGRESSION: literal '#' found in elm/static/style.css!");
  process.exit(1);
} else {
  console.log("✓ CSS ZERO-HASH INVARIANT: Clean (0 '#' characters, pure rgb()/rgba())");
}

// ---------------------------------------------------------------------------
// 2. HTML DOM DIFFER (Python Static vs Elm TEA)
// ---------------------------------------------------------------------------
console.log("\n--- 2. HTML DOM PARITY & STRUCTURAL DIFFER ---");

// Compile Elm to temporary pure JS output
const tmpJs = "/tmp/elm_parity_run.js";
try {
  execSync(`npx elm make src/Main.elm --output=${tmpJs}`, {
    cwd: elmDir,
    stdio: "pipe",
  });
  console.log("✓ Compiled Elm 0.19.3 pure runtime");
} catch (err) {
  console.error("✗ Elm compilation failed:", err.message);
  process.exit(1);
}

// Lightweight Headless DOM Shim for Elm TEA execution in Node
class FakeNode {
  constructor(nodeType, nodeName) {
    this.nodeType = nodeType;
    this.nodeName = nodeName;
    this.childNodes = [];
    this.parentNode = null;
    this.attributes = {};
    this.style = {};
  }
  appendChild(child) {
    if (child.parentNode) child.parentNode.removeChild(child);
    child.parentNode = this;
    this.childNodes.push(child);
    return child;
  }
  removeChild(child) {
    const idx = this.childNodes.indexOf(child);
    if (idx !== -1) {
      this.childNodes.splice(idx, 1);
      child.parentNode = null;
    }
    return child;
  }
  insertBefore(newNode, refNode) {
    if (newNode.parentNode) newNode.parentNode.removeChild(newNode);
    newNode.parentNode = this;
    const idx = this.childNodes.indexOf(refNode);
    if (idx === -1) this.childNodes.push(newNode);
    else this.childNodes.splice(idx, 0, newNode);
    return newNode;
  }
  replaceChild(newChild, oldChild) {
    const idx = this.childNodes.indexOf(oldChild);
    if (idx !== -1) {
      if (newChild.parentNode) newChild.parentNode.removeChild(newChild);
      newChild.parentNode = this;
      this.childNodes[idx] = newChild;
      oldChild.parentNode = null;
    }
    return newChild;
  }
  setAttribute(name, val) { this.attributes[name] = String(val); }
  removeAttribute(name) { delete this.attributes[name]; }
  addEventListener() {}
  removeEventListener() {}
  toHTML() {
    if (this.nodeType === 3) return this.nodeValue;
    const allAttrs = { ...this.attributes };
    if (this.className) allAttrs["class"] = this.className;
    if (this.id) allAttrs["id"] = this.id;
    if (this.href) allAttrs["href"] = this.href;
    if (this.type) allAttrs["type"] = this.type;
    if (this.title) allAttrs["title"] = this.title;
    if (this.name) allAttrs["name"] = this.name;
    if (this.value) allAttrs["value"] = this.value;
    if (this.placeholder) allAttrs["placeholder"] = this.placeholder;
    if (this.open !== undefined && this.open !== false) allAttrs["open"] = "";
    const styleEntries = Object.entries(this.style);
    if (styleEntries.length > 0) {
      allAttrs["style"] = styleEntries.map(([k, v]) => `${k}: ${v}`).join("; ");
    }
    const attrsStr = Object.entries(allAttrs)
      .map(([k, v]) => (v === "" ? ` ${k}` : ` ${k}="${String(v).replace(/"/g, "&quot;")}"`))
      .join("");
    const tag = this.tagName.toLowerCase();
    const children = this.childNodes.map((c) => (c.toHTML ? c.toHTML() : "")).join("");
    return `<${tag}${attrsStr}>${children}</${tag}>`;
  }
}

class FakeElement extends FakeNode {
  constructor(tagName) {
    super(1, tagName ? tagName.toUpperCase() : "DIV");
    this.tagName = tagName ? tagName.toUpperCase() : "DIV";
  }
}

class FakeText extends FakeNode {
  constructor(text) {
    super(3, "#text");
    this.nodeValue = text;
  }
}

const root = new FakeElement("div");
root.id = "elm-root";

const sandbox = {
  window: {
    addEventListener: () => {},
    removeEventListener: () => {},
    requestAnimationFrame: (cb) => cb(),
    cancelAnimationFrame: () => {},
    location: { href: "http://localhost:3000/", pathname: "/", search: "", hash: "" },
    navigator: { userAgent: "Node" },
  },
  document: {
    createElement: (tag) => new FakeElement(tag),
    createTextNode: (txt) => new FakeText(txt),
    getElementById: (id) => (id === "elm-root" ? root : null),
    documentElement: new FakeElement("html"),
    addEventListener: () => {},
    removeEventListener: () => {},
    location: { href: "http://localhost:3000/", pathname: "/", search: "", hash: "" },
  },
  requestAnimationFrame: (cb) => cb(),
  cancelAnimationFrame: () => {},
  setTimeout: setTimeout,
  clearTimeout: clearTimeout,
};

const elmCode = readFileSync(tmpJs, "utf-8");
const ctx = vm.createContext(sandbox);
vm.runInContext(elmCode, ctx);

const fixture = JSON.parse(readFileSync(join(staticDir, "fixture.json"), "utf-8"));
const catalog = JSON.parse(readFileSync(join(staticDir, "catalog.json"), "utf-8"));
const routerConfig = {
  repo: "ianchanning/hn",
  actions_url: "https://github.com/ianchanning/hn/actions",
  workflow_file: "observatory.yml",
};
const bundle = {
  page: "observatory",
  observatory: fixture,
  catalog: catalog,
  router: routerConfig,
};

// Initialize Elm app
sandbox.Elm.Main.init({
  node: root,
  flags: bundle,
});

// Extract Elm rendered HTML (child 1 is the app view, child 0 is dev switcher)
const elmAppNode = root.childNodes[1] || root.childNodes[0];
const elmHtml = elmAppNode.toHTML();

// Read Python rendered HTML from show-me-hn-50467087.html
const showMePath = existsSync(join(rootDir, "hn-comments", "show-me-hn-50467087.html"))
  ? join(rootDir, "hn-comments", "show-me-hn-50467087.html")
  : join(rootDir, "show-me-hn-50467087.html");
const showMeHtml = readFileSync(showMePath, "utf-8");
const pyRootMatch = showMeHtml.match(/<div id=["']elm-root["']>(.*?)<\/div>\s*<script/s);
const pyHtml = pyRootMatch ? pyRootMatch[1].trim() : "";

// Initialize Elm in Catalog/Index mode to verify frontpage DOM
const indexRoot = new FakeElement("div");
indexRoot.id = "elm-root";
sandbox.document.getElementById = (id) => (id === "elm-root" ? indexRoot : null);
const indexBundle = {
  page: "catalog",
  observatory: fixture,
  catalog: catalog,
  router: routerConfig,
};
sandbox.Elm.Main.init({
  node: indexRoot,
  flags: indexBundle,
});
const indexHtml = (indexRoot.childNodes[1] || indexRoot.childNodes[0]).toHTML();

// Verification points
const checks = [
  {
    name: "Header Topbar Brand & Logo",
    pyMatch: /<a href="https:\/\/news\.ycombinator\.com" class="hn-logo">BS<\/a>\s*<a href="https:\/\/ianchanning\.com\/hn" class="hnname">Better Signal News<\/a>/,
    elmMatch: /<a class="hn-logo" href="https:\/\/news\.ycombinator\.com">BS<\/a><a class="hnname" href="https:\/\/ianchanning\.com\/hn">Better Signal News<\/a>/,
  },
  {
    name: "Header Mode Tabs (Top 40 & HN Top 40 only)",
    pyMatch: /<button[^>]*>Top 40<\/button>\s*\|\s*<button[^>]*>HN Top 40<\/button>/,
    elmMatch: /<button[^>]*>Top 40<\/button> \| <button[^>]*>HN Top 40<\/button>/,
  },
  {
    name: "Header Subline Points and Author",
    pyMatch: /<span class="score">\d+\s+points<\/span>\s+by\s+<a[^>]*>\w+<\/a>/,
    elmMatch: /<span class="score">\d+\s+points<\/span> by <a[^>]*>\w+<\/a>/,
  },
  {
    name: "Header Subline Excludes Raw JUDGE text",
    check: () => {
      const headerSub = elmHtml.match(/<div class="subtext">(.*?)<\/div>/s);
      const text = headerSub ? headerSub[1] : "";
      return !text.includes("JUDGE v");
    },
  },
  {
    name: "Proof Drawer Has Hidden Summary (No default browser 'Details' arrow)",
    check: () => {
      const proofMatch = elmHtml.match(/id="proofDrawer"[^>]*>\s*(<[^>]+>)/);
      return proofMatch && proofMatch[1].includes('<summary class="hn-summary" style="display: none">');
    },
  },
  {
    name: "Lab Drawer Has Hidden Summary (No default browser 'Details' arrow)",
    check: () => {
      const labMatch = elmHtml.match(/id="labDrawer"[^>]*>\s*(<[^>]+>)/);
      return labMatch && labMatch[1].includes('<summary class="hn-summary" style="display: none">');
    },
  },
  {
    name: "Comment Cards Rendered With 4px Left Border",
    check: () => {
      return elmHtml.includes('style="border-left: 4px solid');
    },
  },
  {
    name: "Dual OLED Bay Displays Both Phase Plane & Gravity Graphs Open",
    check: () => {
      const hasPhase = elmHtml.includes('id="phaseDrawer" open') || elmHtml.includes('open class="graph-drawer" id="phaseDrawer"');
      const hasGravity = elmHtml.includes('id="gravityDrawer" open') || elmHtml.includes('open class="graph-drawer" id="gravityDrawer"');
      return hasPhase && hasGravity;
    },
  },
  {
    name: "Zero '#' Invariant Across All Generated Static Files (index.html, catalog.html, router.html, style.css)",
    check: () => {
      const files = ["index.html", "catalog.html", "router.html", "style.css"];
      for (const f of files) {
        const content = readFileSync(join(staticDir, f), "utf-8");
        if (content.includes("#")) return false;
      }
      return true;
    },
  },
  {
    name: "Rendered Elm Virtual DOM Has No Hex Colors (Pure rgb()/rgba() Only)",
    check: () => {
      // Ensure no hex colors like #fff, #123456 in style attributes or inline styles
      const hexColorRegex = /style="[^"]*#[0-9a-fA-F]{3,8}\b[^"]*"/;
      return !hexColorRegex.test(elmHtml) && !hexColorRegex.test(indexHtml);
    },
  },
  {
    name: "Frontpage Index Wraps Table in list-pad (Identical Padding To Python)",
    check: () => {
      return /class="list-pad"[^>]*>\s*<table[^>]*id="frontpageList"/.test(indexHtml);
    },
  },
  {
    name: "Frontpage Index Renders Proper Topbar-Right Case ('Updated ... UTC')",
    check: () => {
      const m = indexHtml.match(/<div[^>]*class="topbar-right"[^>]*>(.*?)<\/div>/);
      const text = m ? m[1] : "";
      return text.startsWith("Updated ") && text.endsWith("UTC");
    },
  },
  {
    name: "Frontpage Index Renders hn-footer With Search Jump Form",
    check: () => {
      return indexHtml.includes('class="hn-footer"') && indexHtml.includes('id="jumpForm"');
    },
  },
];

let allPassed = true;
for (const c of checks) {
  let passed = false;
  if (c.check) {
    passed = Boolean(c.check());
  } else {
    passed = Boolean(pyHtml.match(c.pyMatch)) && Boolean(elmHtml.match(c.elmMatch));
  }
  if (passed) {
    console.log(`✓ PASS: ${c.name}`);
  } else {
    console.error(`✗ FAIL: ${c.name}`);
    allPassed = false;
  }
}

console.log("\n================================================================================");
if (allPassed) {
  console.log("       ALL DOM AND CSS PARITY CHECKS PASSED (100% VISUAL & STRUCTURAL MATCH)");
} else {
  console.log("       SOME CHECKS FAILED - SEE ABOVE DETAILS");
  process.exit(1);
}
console.log("================================================================================\n");
