"use client";

// A plate of "How it's worn" (./scenes.ts: the 3D disc in a drawing) with lines from its parts to their names, as on the
// home page. The scene plays as the plate comes up the screen: its progress is how far the middle of the figure has risen,
// from the bottom of the screen to 58 % of its height, so scrolling back plays it backwards. Three.js and the model load
// when the figure is near; the canvas draws only while it is on screen and something moves. Pointing at a name lights its
// line and moves its part; on a narrow figure the names go into a numbered key below, where a tap does the same. Without
// WebGL the key is all that shows.
import { useEffect, useRef, useState, type PointerEvent as ReactPointerEvent } from "react";
import type { WearKind, WearScene } from "./scenes";

export type WearLabel = { key: string; name: string; value?: string };

const NARROW = 560; // px of figure width under which the names go below
const ROWS = [0.2, 0.4, 0.6, 0.8]; // label rows, as shares of the height

export function WearArt({ kind, labels, label, caption }: { kind: WearKind; labels: WearLabel[]; label: string; caption?: string }) {
  const boxRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const linesRef = useRef<SVGGElement>(null);
  const labelsRef = useRef<HTMLOListElement>(null);
  const sceneRef = useRef<WearScene | null>(null);
  const [size, setSize] = useState({ w: 0, h: 0 });
  const [hover, setHover] = useState<number | null>(null);
  const [failed, setFailed] = useState(false);
  const narrow = size.w > 0 && size.w < NARROW;

  useEffect(() => {
    const box = boxRef.current!;
    const canvas = canvasRef.current!;
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    let scene: WearScene | null = null;
    let disposed = false;
    let started = false;
    let visible = false;
    let raf = 0;
    let last = 0;
    let dims = { w: 0, h: 0, narrow: false };

    const fit = () => {
      const r = box.getBoundingClientRect();
      dims = { w: r.width, h: r.height, narrow: r.width < NARROW };
      setSize({ w: r.width, h: r.height });
      scene?.resize(r.width, r.height, !dims.narrow);
    };
    const ro = new ResizeObserver(fit);
    ro.observe(box);

    const draw = () => {
      if (!scene) return;
      const a = scene.anchors();
      const reveal = Math.min(1, Math.max(0, (scene.progress - 0.82) / 0.18));
      const g = linesRef.current;
      if (g) {
        g.style.opacity = String(reveal);
        labels.forEach((l, i) => {
          const [x, y] = a[l.key] ?? [0, 0];
          const line = g.querySelector<SVGPolylineElement>(`[data-k="${l.key}"] polyline`);
          const dot = g.querySelector<SVGCircleElement>(`[data-k="${l.key}"] circle`);
          const num = g.querySelector<SVGTextElement>(`[data-k="${l.key}"] text`);
          if (dims.narrow) line?.setAttribute("points", "");
          else {
            const lx = dims.w * 0.66 - 10;
            const ry = dims.h * ROWS[i];
            const ex = Math.max(lx - 36, Math.min(x + 16, lx - 6)); // the elbow never falls behind a mark close to the names
            line?.setAttribute("points", `${x.toFixed(1)},${y.toFixed(1)} ${ex.toFixed(1)},${ry.toFixed(1)} ${lx.toFixed(1)},${ry.toFixed(1)}`);
          }
          dot?.setAttribute("cx", x.toFixed(1));
          dot?.setAttribute("cy", y.toFixed(1));
          num?.setAttribute("x", x.toFixed(1));
          num?.setAttribute("y", y.toFixed(1));
        });
      }
      if (labelsRef.current) labelsRef.current.style.opacity = dims.narrow ? "1" : String(reveal);
    };

    const loop = (now: number) => {
      const dt = Math.min(0.05, last ? (now - last) / 1000 : 0.016);
      last = now;
      if (scene) {
        const r = box.getBoundingClientRect();
        const vh = window.innerHeight;
        const centre = r.top + r.height / 2;
        const target = reduced ? 1 : Math.min(1, Math.max(0, (vh - centre) / (vh * 0.42)));
        if (scene.frame(target, dt, reduced)) draw();
      }
      raf = visible ? requestAnimationFrame(loop) : 0;
    };

    const start = () => {
      started = true;
      import("./scenes")
        .then((m) => m.WearScene.create(kind, canvas, box.getBoundingClientRect().width >= NARROW))
        .then((s) => {
          if (disposed) return s.dispose();
          scene = sceneRef.current = s;
          fit();
          box.dataset.ready = "";
        })
        .catch(() => setFailed(true));
    };
    const io = new IntersectionObserver(
      ([e]) => {
        visible = e.isIntersecting;
        if (visible && !started) start();
        if (visible && !raf) {
          last = 0;
          raf = requestAnimationFrame(loop);
        }
      },
      { rootMargin: "900px 0px" }, // a plate is ready (loaded, compiled, drawn once) before it scrolls in
    );
    io.observe(box);

    const toBox = (e: PointerEvent) => {
      const r = box.getBoundingClientRect();
      return { x: ((e.clientX - r.left) / r.width) * 2 - 1, y: ((e.clientY - r.top) / r.height) * 2 - 1 };
    };
    const onMove = (e: PointerEvent) => {
      if (e.pointerType !== "touch") scene?.setPointer(toBox(e));
    };
    const onLeave = () => scene?.setPointer(null);
    box.addEventListener("pointermove", onMove);
    box.addEventListener("pointerleave", onLeave);
    return () => {
      disposed = true;
      cancelAnimationFrame(raf);
      io.disconnect();
      ro.disconnect();
      box.removeEventListener("pointermove", onMove);
      box.removeEventListener("pointerleave", onLeave);
      scene?.dispose();
      sceneRef.current = null;
    };
  }, [kind, labels]);

  useEffect(() => {
    sceneRef.current?.setFocus(hover === null ? null : labels[hover].key);
  }, [hover, labels]);

  // a mouse points, a finger taps a name on and off
  const point = (i: number) => ({
    onPointerEnter: (e: ReactPointerEvent) => e.pointerType !== "touch" && setHover(i),
    onPointerLeave: (e: ReactPointerEvent) => e.pointerType !== "touch" && setHover(null),
    onPointerUp: (e: ReactPointerEvent) => e.pointerType === "touch" && setHover((h) => (h === i ? null : i)),
  });

  return (
    <figure className={`figure wear-figure${narrow ? " narrow" : ""}${failed ? " failed" : ""}`}>
      <div ref={boxRef} className="wear-stage" role="img" aria-label={label}>
        <canvas ref={canvasRef} className="wear-canvas" aria-hidden />
        <svg className="wear-lines" viewBox={`0 0 ${Math.max(1, size.w)} ${Math.max(1, size.h)}`} aria-hidden>
          <g ref={linesRef} style={{ opacity: 0 }}>
            {labels.map((l, i) => (
              <g key={l.key} data-k={l.key} className={hover === i ? "on" : undefined}>
                <polyline />
                <circle r={narrow ? 9 : 3.5} />
                {narrow && <text dy="0.36em">{i + 1}</text>}
              </g>
            ))}
          </g>
        </svg>
        {!narrow && (
          <ol ref={labelsRef} className="wear-labels" style={{ opacity: 0 }}>
            {labels.map((l, i) => (
              <li key={l.key} style={{ top: `${ROWS[i] * 100}%` }} className={hover === i ? "on" : undefined} {...point(i)}>
                <span className="name">{l.name}</span>
                {l.value && <span className="value mono">{l.value}</span>}
              </li>
            ))}
          </ol>
        )}
      </div>
      {(narrow || failed) && (
        <ol className="wear-key">
          {labels.map((l, i) => (
            <li key={l.key} className={hover === i ? "on" : undefined} {...point(i)}>
              <span className="num mono">{i + 1}</span>
              <span className="name">{l.name}</span>
              {l.value && <span className="value mono">{l.value}</span>}
            </li>
          ))}
        </ol>
      )}
      {caption && !failed && <figcaption>{caption}</figcaption>}
    </figure>
  );
}
