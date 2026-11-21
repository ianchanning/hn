# Canvas Ports Pattern

## The Sovereign Law
Elm cannot draw directly to an HTML5 `<canvas>`. TEA view functions must emit canvas elements with static dimensions, while rendering commands (`drawPlot`) and canvas hover probe interactions (`onCanvasProbe`) communicate via typed ports connected to an external IIFE canvas renderer (`canvas-iife.js`).

## The Trigger
Attempting to get a 2D rendering context or call `ctx.fillRect()` / `ctx.arc()` from inside Elm view functions.

## The Pattern
### WRONG
```elm
-- Trying to execute imperative canvas draw calls inside Elm view
canvas [ id "phaseBay", onClick DrawPoints ] []
```

### RIGHT
```elm
-- Elm side: Ports.elm
port drawPlot : E.Value -> Cmd msg
port onCanvasProbe : (D.Value -> msg) -> Sub msg

-- JS side: canvas-iife.js
app.ports.drawPlot.subscribe(function(cmd) {
    renderCanvasPlot(cmd);
});
```
