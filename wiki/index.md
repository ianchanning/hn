# Wiki Index — Elm Machine Studying

Persistent knowledge base for the Elm rewrite of the HN Epistemic Observatory display layer.

## Pages

- [[Elm-019-Compat]] - Elm 0.19.3 has zero breaking changes from 0.19.1; just bump elm.json.
- [[Zero-Hash-Invariant]] - All colours must use rgb()/rgba() — no hex `#` literals in generated HTML.
- [[Canvas-Ports-Pattern]] - Elm cannot draw to `<canvas>`; use ports to send PlotCommand, subscribe to CanvasProbeEvent.
- [[Elm-Min-Max-Ambiguity]] - Qualify Attr.min/Attr.max to avoid collision with Basics prelude.
- [[Elm-Port-Module-Declaration]] - Only modules actually declaring ports can use `port module`.
- [[Payload-Hydration]] - Python emits JSON in `<script>` tag; Elm reads via `Browser.element` flags + `Json.Decode.Value`.
