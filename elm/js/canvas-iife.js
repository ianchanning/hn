/**
 * Canvas 2D scatter-plot renderer — port bridge between Elm and <canvas>.
 *
 * Elm sends PlotCommand via `drawPlot` port.
 * User interactions fire back via `onCanvasProbe` port.
 *
 * IIFE version: no ES module imports/exports — works as a plain <script>
 * in both dev (static/index.html) and production (inlined by Python).
 */

// eslint-disable-next-line no-unused-vars
function mountCanvasRenderer(app) {
  if (!app.ports) return;

  // Outgoing port: Elm -> JS canvas draw
  if (app.ports.drawPlot) {
    app.ports.drawPlot.subscribe(renderPlot);
  }

  // Incoming port: JS canvas events -> Elm
  function emitProbe(canvasId, commentId) {
    if (app.ports.onCanvasProbe) {
      app.ports.onCanvasProbe.send({ canvasId: canvasId, commentId: commentId });
    }
  }

  /**
   * Render a scatter plot onto a <canvas> element.
   * @param {Object} cmd - PlotCommand from Elm
   */
  function renderPlot(cmd) {
    var canvas = document.getElementById(cmd.canvasId);
    if (!canvas || !canvas.getContext) return;

    var ctx = canvas.getContext("2d");
    var W = canvas.width;
    var H = canvas.height;

    ctx.clearRect(0, 0, W, H);

    // Grid lines
    ctx.strokeStyle = "rgb(30, 36, 44)";
    ctx.lineWidth = 1;
    for (var i = 1; i < 6; i++) {
      ctx.beginPath(); ctx.moveTo((W * i) / 6, 0); ctx.lineTo((W * i) / 6, H); ctx.stroke();
      ctx.beginPath(); ctx.moveTo(0, (H * i) / 6); ctx.lineTo(W, (H * i) / 6); ctx.stroke();
    }

    // Largest root subtree highlight (gravity canvas only)
    if (cmd.largestRoot && cmd.largestRoot.slots > 1) {
      var lr = cmd.largestRoot;
      var totalN = cmd.points.length || 1;
      var yStart = 20 + (lr.startDom / totalN) * (H - 44);
      var yEnd = 20 + (lr.endDom / totalN) * (H - 44);
      ctx.fillStyle = "rgba(255, 68, 0, 0.09)";
      ctx.fillRect(32, yStart, W - 48, Math.max(4, yEnd - yStart));
      ctx.fillStyle = "rgba(255, 110, 64, 0.75)";
      ctx.font = "10px ui-monospace, Menlo, monospace";
      ctx.fillText(
        "LARGEST SUBTREE (@" + lr.author + ": " + lr.slots + " SLOTS, HN POS " + lr.startDom + ".." + lr.endDom + ")",
        40,
        Math.min(H - 22, yStart + 13)
      );
    }

    // Plot points (draw back-to-front so gold renders on top)
    var pts = [];
    var drawOrder = cmd.points.slice().reverse();
    for (var j = 0; j < drawOrder.length; j++) {
      var p = drawOrder[j];
      var col = "rgba(" + p.colour.r + ", " + p.colour.g + ", " + p.colour.b + ", " + p.colour.a + ")";
      ctx.fillStyle = col;
      ctx.beginPath();
      ctx.arc(p.x, p.y, p.radius, 0, Math.PI * 2);
      ctx.fill();

      // Selection ring
      if (cmd.selectedId === p.commentId) {
        ctx.strokeStyle = "rgb(255, 255, 255)";
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.radius + 4, 0, Math.PI * 2);
        ctx.stroke();
      }

      pts.push({ x: p.x, y: p.y, id: p.commentId });
    }

    // Axis labels
    ctx.fillStyle = "rgb(140, 150, 162)";
    ctx.font = "10px ui-monospace, Menlo, monospace";
    if (cmd.axisConfig) {
      ctx.fillText(cmd.axisConfig.xLabel, W - 295, H - 7);
      ctx.fillText(cmd.axisConfig.yLabel, 8, 14);
    }

    // Attach interaction listeners (replace previous)
    var handler = makeCanvasHandler(canvas, pts, cmd.canvasId, emitProbe);
    if (canvas._hnCleanup) canvas._hnCleanup();
    canvas.addEventListener("click", handler.onClick);
    canvas.addEventListener("mousemove", handler.onMove);
    canvas._hnCleanup = function() {
      canvas.removeEventListener("click", handler.onClick);
      canvas.removeEventListener("mousemove", handler.onMove);
    };
  }

  function makeCanvasHandler(canvas, pts, canvasId, emit) {
    function findNearest(ev, maxDistSq) {
      var rect = canvas.getBoundingClientRect();
      if (!rect.width || !rect.height) return null;
      var sx = (ev.clientX - rect.left) * (canvas.width / rect.width);
      var sy = (ev.clientY - rect.top) * (canvas.height / rect.height);
      var best = null;
      var bestD = maxDistSq;
      for (var k = 0; k < pts.length; k++) {
        var pt = pts[k];
        var d = (pt.x - sx) * (pt.x - sx) + (pt.y - sy) * (pt.y - sy);
        if (d < bestD) { bestD = d; best = pt; }
      }
      return best;
    }

    return {
      onClick: function(ev) {
        var hit = findNearest(ev, 576);
        if (hit) emit(canvasId, hit.id);
      },
      onMove: function(ev) {
        var hit = findNearest(ev, 169);
        if (hit) emit(canvasId, hit.id);
      }
    };
  }
}
