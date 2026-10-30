"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState, type CSSProperties } from "react";
import type { Dict, Locale, Section } from "@/lib/i18n";
import type { Disc3D } from "./disc3d";
import { Front, SideView } from "./Drawing";
import { CALLOUTS, VIEW, leaderPoints } from "./geometry";
import { B, T, at, introAt } from "./timeline";

const SEEN_KEY = "caseback-intro-seen";
const MODEL = "/models/disc.glb";
/** How long the drawn watch waits for the disc model before the sections come in without it. */
const WAIT = 8;
const BOX = `${-VIEW} ${-VIEW} ${2 * VIEW} ${2 * VIEW}`;

type Run = "pending" | "intro" | "build" | "done";

export function HomeStage({ lang, t }: { lang: Locale; t: Dict }) {
  const router = useRouter();
  const rootRef = useRef<HTMLDivElement>(null);
  const overRef = useRef<SVGSVGElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const discRef = useRef<Disc3D | null>(null);
  const lineRefs = useRef<(SVGPolylineElement | null)[]>([]);
  const nodeRefs = useRef<(SVGCircleElement | null)[]>([]);
  const skipRef = useRef<() => void>(() => {});
  const [run, setRun] = useState<Run>("pending");
  const [ready, setReady] = useState(false);
  const [fallback, setFallback] = useState(false);
  const [hover, setHover] = useState<number | null>(null);
  const [leaving, setLeaving] = useState(false);
  // 10:10:30 until the browser says what time it is.
  const [hands, setHands] = useState({ h: 305, m: 60, s: 180 });

  useEffect(() => {
    discRef.current?.setHover(hover === null ? null : CALLOUTS[hover].key);
  }, [hover]);

  // Line weights stay the same on screen whatever the size of the drawing: each SVG gets --px, drawing units per pixel.
  useEffect(() => {
    const root = rootRef.current;
    if (!root) return;
    const svgs = Array.from(root.querySelectorAll<SVGSVGElement>("svg[data-w]"));
    const ro = new ResizeObserver((entries) => {
      for (const e of entries) {
        const svg = e.target as SVGSVGElement;
        const w = e.contentRect.width;
        if (w > 0) svg.style.setProperty("--px", (Number(svg.dataset.w) / w).toFixed(4));
      }
    });
    svgs.forEach((s) => ro.observe(s));
    return () => ro.disconnect();
  }, []);

  useEffect(() => {
    const canvas = canvasRef.current!;
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    let seen = false;
    try {
      seen = sessionStorage.getItem(SEEN_KEY) === "1" && !/[?&]intro/.test(location.search);
    } catch {}
    // Development only: ?t=4.2 holds the intro at 4.2 s on the first clock, for screenshots.
    const hold = process.env.NODE_ENV !== "production" ? Number(new URLSearchParams(location.search).get("t") ?? NaN) : NaN;
    const now = new Date();
    setHands({
      h: ((now.getHours() % 12) + now.getMinutes() / 60) * 30,
      m: (now.getMinutes() + now.getSeconds() / 60) * 6,
      s: now.getSeconds() * 6,
    });

    // On a phone (the layout of the media query in globals.css) only the central drawing plays; the intro ends with it.
    const compact = window.matchMedia("(max-width: 1100px), (max-aspect-ratio: 1/1)").matches;
    const END = compact ? B.doneCompact : B.done;
    let settled = (reduced || seen) && isNaN(hold);
    // The disc fades in when it first shows at rest: back on the page from a section, or after a skip.
    let fade = settled;
    const finish = (skipped = false) => {
      settled = true;
      fade ||= skipped;
      setRun("done");
      try {
        sessionStorage.setItem(SEEN_KEY, "1");
      } catch {}
    };
    if (settled) setRun("done");

    // The disc model loads while the watch draws itself; the watch turns over once it is there.
    let disc: Disc3D | null = null;
    let failed = false;
    let disposed = false;
    const fit = () => {
      const r = canvas.getBoundingClientRect();
      if (disc && r.width > 0) disc.resize(r.width, r.height);
    };
    import("./disc3d")
      .then((m) => m.Disc3D.load(canvas, MODEL))
      .then((d) => {
        if (disposed) return d.dispose();
        disc = discRef.current = d;
        fit();
      })
      .catch(() => {
        failed = true;
        setFallback(true);
      });
    const ro = new ResizeObserver(fit);
    ro.observe(canvas);
    // Nothing is drawn while the drawing is scrolled off (phones) or the tab is hidden.
    let onScreen = true;
    const io = new IntersectionObserver(([e]) => (onScreen = e.isIntersecting));
    io.observe(canvas);

    // Leaders leave from the parts wherever the 3D scene has put them.
    const follow = (d: Disc3D) => {
      const a = d.anchors();
      CALLOUTS.forEach((c, i) => {
        const pts = leaderPoints(c, a[c.key]).map((p) => `${p[0].toFixed(1)},${p[1].toFixed(1)}`).join(" ");
        lineRefs.current[2 * i]?.setAttribute("points", pts);
        lineRefs.current[2 * i + 1]?.setAttribute("points", pts);
        nodeRefs.current[i]?.setAttribute("cx", a[c.key][0].toFixed(1));
        nodeRefs.current[i]?.setAttribute("cy", a[c.key][1].toFixed(1));
      });
    };

    let raf = 0;
    let start = 0;
    let last = 0;
    let built: number | null = null; // performance.now() when the second clock started
    let shown = false;
    skipRef.current = () => {
      if (!settled) finish(true);
    };

    const frame = (nowMs: number) => {
      if (!start) {
        start = last = nowMs;
        if (!settled) setRun("intro");
      }
      const dt = Math.min(0.05, (nowMs - last) / 1000);
      last = nowMs;
      const time = isNaN(hold) ? (nowMs - start) / 1000 : hold;

      if (!settled) {
        if (built === null) {
          if (time >= T.flip && disc) {
            built = nowMs - Math.max(0, time - T.flip) * 1000;
            setRun("build");
          } else if (failed || time >= T.flip + WAIT) finish(); // no 3D: the watch stays and the sections come in
        } else if ((isNaN(hold) ? (nowMs - built) / 1000 : hold - T.flip) >= END) finish();
      }
      const b = settled ? Infinity : built === null ? -1 : isNaN(hold) ? (nowMs - built) / 1000 : hold - T.flip;
      if (!isNaN(hold) && !settled) holdCss(built === null ? time : b);

      if (disc && b >= 0 && onScreen && disc.frame(b, dt, reduced)) {
        follow(disc);
        if (!settled) {
          // from the moment the dial is edge-on, in the time of about six frames
          canvas.style.transition = "none";
          canvas.style.opacity = String(introAt(b, B.turnDur / 2, 0.1));
        } else if (fade) {
          fade = false;
          canvas.style.transition = "none";
          canvas.style.opacity = "0";
          void canvas.offsetWidth;
          canvas.style.transition = "opacity 0.7s var(--ease)";
          canvas.style.opacity = "1";
        } else canvas.style.opacity = "1";
        if (!shown) {
          shown = true;
          setReady(true);
        }
      }
      raf = requestAnimationFrame(frame);
    };

    const toBox = (e: PointerEvent) => {
      const r = overRef.current?.getBoundingClientRect();
      if (!r || !r.width) return null;
      return { x: ((e.clientX - r.left) / r.width) * 2 - 1, y: ((e.clientY - r.top) / r.height) * 2 - 1 };
    };
    const onMove = (e: PointerEvent) => {
      if (settled && e.pointerType !== "touch") disc?.setPointer(toBox(e));
    };
    const onLeave = () => disc?.setPointer(null);
    const onKey = (e: KeyboardEvent) => {
      if (!settled && e.key === "Escape") skipRef.current();
    };
    const onVisibility = () => {
      if (document.hidden) {
        cancelAnimationFrame(raf);
        raf = 0;
      } else if (!raf) {
        last = performance.now();
        raf = requestAnimationFrame(frame);
      }
    };

    raf = requestAnimationFrame(frame);
    window.addEventListener("pointermove", onMove);
    document.documentElement.addEventListener("pointerleave", onLeave);
    window.addEventListener("keydown", onKey);
    document.addEventListener("visibilitychange", onVisibility);
    return () => {
      disposed = true;
      cancelAnimationFrame(raf);
      ro.disconnect();
      io.disconnect();
      disc?.dispose();
      discRef.current = null;
      window.removeEventListener("pointermove", onMove);
      document.documentElement.removeEventListener("pointerleave", onLeave);
      window.removeEventListener("keydown", onKey);
      document.removeEventListener("visibilitychange", onVisibility);
    };
  }, []);

  // On the way to a section the camera closes in on the part the line leaves from while the page fades.
  const open = (e: React.MouseEvent, href: string, key: Section) => {
    if (e.metaKey || e.ctrlKey || e.shiftKey || e.button !== 0) return;
    e.preventDefault();
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return router.push(href);
    setLeaving(true);
    discRef.current?.goTo(key);
    router.prefetch(href);
    window.setTimeout(() => router.push(href), 480);
  };

  return (
    <div
      ref={rootRef}
      className="home"
      data-run={run}
      data-ready={ready ? "" : undefined}
      data-fallback={fallback ? "" : undefined}
      data-hover={hover === null ? undefined : CALLOUTS[hover].key}
      data-leaving={leaving ? "" : undefined}
    >
      <div className="seal">
        <div className="card a-flip" style={at(B.turn, B.turnDur)}>
          <svg className="face face-front" viewBox={BOX} data-w={2 * VIEW} aria-hidden>
            <Front hands={hands} />
          </svg>
        </div>
        <canvas ref={canvasRef} className="disc3d" aria-hidden />
        <svg ref={overRef} className="over" viewBox={BOX} data-w={2 * VIEW} role="img" aria-label={t.home.drawing}>
          <g className="leaders late">
            {CALLOUTS.map((c, i) => {
              const pts = leaderPoints(c).map((p) => p.join(",")).join(" ");
              const start = B.callouts + i * 0.1;
              return (
                <g key={c.key} className={`leader${hover === i ? " on" : ""}`}>
                  <polyline ref={(el) => { lineRefs.current[2 * i] = el; }} className="leader-line a-draw" points={pts} pathLength={1} style={at(start, 0.55)} />
                  <polyline ref={(el) => { lineRefs.current[2 * i + 1] = el; }} className="leader-hot" points={pts} pathLength={1} />
                  <circle ref={(el) => { nodeRefs.current[i] = el; }} className="node a-pop" cx={c.anchor[0]} cy={c.anchor[1]} r={4.5} style={at(start, 0.3)} />
                </g>
              );
            })}
          </g>
        </svg>
      </div>

      <nav className="callouts late" aria-label={t.nav.sections}>
        <ol>
          {CALLOUTS.map((c, i) => {
            const end = leaderPoints(c)[2];
            const href = `/${lang}/${c.key}`;
            const copy = t.home.callouts[c.key];
            return (
              <li
                key={c.key}
                className={`callout callout-${c.side} callout-key-${c.key}`}
                style={{ "--x": end[0], "--y": end[1], ...at(B.callouts + i * 0.1 + 0.45, 1.1) } as CSSProperties}
              >
                <Link
                  href={href}
                  onClick={(e) => open(e, href, c.key)}
                  onPointerEnter={() => setHover(i)}
                  onPointerLeave={() => setHover(null)}
                  onFocus={() => setHover(i)}
                  onBlur={() => setHover(null)}
                >
                  <span className="num" aria-hidden>{i + 1}</span>
                  <span className="label">{copy.label}</span>
                </Link>
              </li>
            );
          })}
        </ol>
      </nav>

      <figure className="side">
        <SideView t={t.home.side} />
        <figcaption>{t.home.side.title}</figcaption>
      </figure>

      {run !== "done" && (
        <button type="button" className="skip" onClick={() => skipRef.current()}>
          {t.nav.skip}
        </button>
      )}
    </div>
  );
}

/** Development only: puts every CSS animation of the intro at `time` seconds on its clock (see `hold`). */
function holdCss(time: number) {
  for (const a of document.getAnimations()) {
    if (!(a instanceof CSSAnimation)) continue;
    a.pause();
    a.currentTime = time * 1000;
  }
}

