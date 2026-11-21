/**
 * Canvas 2D scatter-plot renderer — port bridge between Elm and <canvas>.
 *
 * Elm sends PlotCommand via `drawPlot` port.
 * User interactions fire back via `onCanvasProbe` port.
 *
 * This replaces ~170 lines of inline <script> from build_dashboard.py
 * with a clean, testable module.
 */

/**
 * @param {Object} app - Elm app instance with ports
 */
export function mountCanvasRenderer(app) {
  if (!app.ports) return;

  // Outgoing port: Elm → JS canvas draw
  if (app.ports.drawPlot) {
    app.ports.drawPlot.subscribe(renderPlot);
  }

  // Incoming port: JS canvas events → Elm
  function emitProbe(canvasId, commentId) {
    if (app.ports.onCanvasProbe) {
      app.ports.onCanvasProbe.send({ canvasId, commentId });
    }
  }

  /**
   * Render a scatter plot onto a <canvas> element.
   * @param {Object} cmd - PlotCommand from Elm
   */
  function renderPlot(cmd) {
    const canvas = document.getElementById(cmd.canvasId);
    if (!canvas || !canvas.getContext) return;

    const ctx = canvas.getContext("2d");
    const W = canvas.width;
    const H = canvas.height;

    ctx.clearRect(0, 0, W, H);

    // Grid lines
    ctx.strokeStyle = "rgb(30, 36, 44)";
    ctx.lineWidth = 1;
    for (let i = 1; i < 6; i++) {
      ctx.beginPath(); ctx.moveTo((W * i) / 6, 0); ctx.lineTo((W * i) / 6, H); ctx.stroke();
      ctx.beginPath(); ctx.moveTo(0, (H * i) / 6); ctx.lineTo(W, (H * i) / 6); ctx.stroke();
    }

    // Largest root subtree highlight (gravity canvas only)
    if (cmd.largestRoot && cmd.largestRoot.slots > 1) {
      const lr = cmd.largestRoot;
      const totalN = cmd.points.length || 1;
      const yStart = 20 + (lr.startDom / totalN) * (H - 44);
      const yEnd = 20 + (lr.endDom / totalN) * (H - 44);
      ctx.fillStyle = "rgba(255, 68, 0, 0.09)";
      ctx.fillRect(32, yStart, W - 48, Math.max(4, yEnd - yStart));
      ctx.fillStyle = "rgba(255, 110, 64, 0.75)";
      ctx.font = "10px ui-monospace, Menlo, monospace";
      ctx.fillText(
        `LARGEST SUBTREE (@${lr.author}: ${lr.slots} SLOTS, HN POS ${lr.startDom}..${lr.endDom})`,
        40,
        Math.min(H - 22, yStart + 13)
      );
    }

    // Plot points
    const pts = [];
    const drawOrder = [...cmd.points].reverse();
    drawOrder.forEach((p) => {
      const col = `rgba(${p.colour.r}, ${p.colour.g}, ${p.colour.b}, ${p.colour.a})`;
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
    });

    // Axis labels
    ctx.fillStyle = "rgb(140, 150, 162)";
    ctx.font = "10px ui-monospace, Menlo, monospace";
    if (cmd.axisConfig) {
      ctx.fillText(cmd.axisConfig.xLabel, W - 295, H - 7);
      ctx.fillText(cmd.axisConfig.yLabel, 8, 14);
    }

    // Attach interaction listeners (replace previous)
    const handler = makeCanvasHandler(canvas, pts, cmd.canvasId, emitProbe);
    canvas._hnCleanup?.();
    canvas.addEventListener("click", handler.onClick);
    canvas.addEventListener("mousemove", handler.onMove);
    canvas._hnCleanup = () => {
      canvas.removeEventListener("click", handler.onClick);
      canvas.removeEventListener("mousemove", handler.onMove);
    };
  }

  function makeCanvasHandler(canvas, pts, canvasId, emit) {
    function findNearest(ev, maxDistSq) {
      const rect = canvas.getBoundingClientRect();
      if (!rect.width || !rect.height) return null;
      const sx = (ev.clientX - rect.left) * (canvas.width / rect.width);
      const sy = (ev.clientY - rect.top) * (canvas.height / rect.height);
      let best = null;
      let bestD = maxDistSq;
      for (const p of pts) {
        const d = (p.x - sx) ** 2 + (p.y - sy) ** 2;
        if (d < bestD) { bestD = d; best = p; }
      }
      return best;
    }

    return {
      onClick(ev) {
        const hit = findNearest(ev, 576);
        if (hit) emit(canvasId, hit.id);
      },
      onMove(ev) {
        const hit = findNearest(ev, 169);
        if (hit) emit(canvasId, hit.id);
      },
    };
  }
}
