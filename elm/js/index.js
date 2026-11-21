/**
 * Elm application bootstrap and port wiring.
 *
 * In dev mode, Vite imports the .elm file directly.
 * In production, the compiled elm.min.js is inlined by Python.
 */
import { Elm } from "../src/Main.elm";
import { mountCanvasRenderer } from "./canvas.js";

// Read the observatory JSON payload embedded by Python (or dev fixture)
const dataEl = document.getElementById("observatoryData");
let flags = null;
if (dataEl) {
  try {
    flags = JSON.parse(dataEl.textContent);
  } catch (_e) {
    console.warn("[observatory] No valid observatoryData JSON found — running empty.");
  }
}

// Initialise the Elm app
const root = document.getElementById("elm-root");
const app = Elm.Main.init({
  node: root,
  flags: flags,
});

// Wire up canvas ports
mountCanvasRenderer(app);
