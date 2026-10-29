"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState, type CSSProperties } from "react";
import { fieldPaths } from "@/lib/blobs/field";
import { BlobSim, METRICS, discTarget, type Target } from "@/lib/blobs/sim";
import type { Dict, Locale } from "@/lib/i18n";
import { Back, DiscEtching, DiscMark, Front, SideView } from "./Drawing";
import { CALLOUTS, R_CASE, R_DISC, R_KNURL_IN, VIEW, leaderPoints } from "./geometry";
import { T, at, easeInOut, introAt } from "./timeline";

const SEEN_KEY = "caseback-intro-seen";
/** The blobs are laid out a little wider than the disc and clipped to it, so the fused field fills it edge to edge. */
const LAYOUT_R = R_DISC * 1.2;
const FILL = 1.2; // blobs a little larger than their layout, so no black shows at the rim
const UNIT = 2; // drawing units per app point
const K = 46; // neck of the smooth union
const BOX = `${-VIEW} ${-VIEW} ${2 * VIEW} ${2 * VIEW}`;

type Run = "pending" | "intro" | "done";

export function HomeStage({ lang, t }: { lang: Locale; t: Dict }) {
  const router = useRouter();
  const rootRef = useRef<HTMLDivElement>(null);
  const overRef = useRef<SVGSVGElement>(null);
  const secondRef = useRef<SVGGElement>(null);
  const pathRefs = useRef<(SVGPathElement | null)[]>([]);
  const hoverRef = useRef<number | null>(null);
  const skipRef = useRef<() => void>(() => {});
  const [run, setRun] = useState<Run>("pending");
  const [hover, setHover] = useState<number | null>(null);
  const [leaving, setLeaving] = useState(false);
  // 10:10:30 until the browser says what time it is.
  const [hands, setHands] = useState({ h: 305, m: 60, s: 180 });

  useEffect(() => {
    hoverRef.current = hover;
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
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    let seen = false;
    try {
      seen = sessionStorage.getItem(SEEN_KEY) === "1" && !/[?&]intro/.test(location.search);
    } catch {}
    const now = new Date();
    setHands({
      h: ((now.getHours() % 12) + now.getMinutes() / 60) * 30,
      m: (now.getMinutes() + now.getSeconds() / 60) * 6,
      s: now.getSeconds() * 6,
    });

    const sim = new BlobSim(METRICS.length, UNIT, 240);
    const place = (time: number, grow: (i: number) => number) =>
      METRICS.forEach((_, i) => {
        const d = discTarget(i, time, 0, 0, LAYOUT_R);
        const g = grow(i);
        sim.place(i, d.x * g, d.y * g, d.r * g * FILL);
      });
    const draw = (time: number) => {
      const paths = fieldPaths(sim.shapes(), { k: K, step: 5, time, unit: UNIT });
      paths.forEach((d, i) => pathRefs.current[i]?.setAttribute("d", d));
    };
    const setSecond = (date: Date) => {
      // Seen from the back, the seconds run anticlockwise.
      secondRef.current?.setAttribute("transform", `rotate(${-date.getSeconds() * 6})`);
    };

    // On a phone (the layout of the media query in globals.css) only the central drawing plays; the intro ends with it.
    const compact = window.matchMedia("(max-width: 1100px), (max-aspect-ratio: 1/1)").matches;
    const END = compact ? T.doneCompact : T.done;
    let settled = reduced || seen;
    const finish = (time: number) => {
      settled = true;
      place(time, () => 1);
      setRun("done");
      try {
        sessionStorage.setItem(SEEN_KEY, "1");
      } catch {}
    };
    if (settled) {
      setRun("done");
      place(0, () => 1);
      draw(0);
      setSecond(new Date());
      if (reduced) return;
    }

    let raf = 0;
    let start = 0;
    let last = 0;
    let lastBeat = 0;
    let lastSecond = -1;
    skipRef.current = () => {
      if (!settled) finish((performance.now() - start) / 1000);
    };

    const frame = (nowMs: number) => {
      if (!start) {
        start = last = nowMs;
        if (!settled) setRun("intro");
      }
      const dt = Math.min(0.033, (nowMs - last) / 1000);
      last = nowMs;
      const time = (nowMs - start) / 1000;

      let growing = false;
      if (!settled) {
        if (time >= END) finish(time);
        else if (time < T.disc + 1.1) {
          // The blobs grow from the middle of the disc, one after another, and fuse as they grow.
          growing = true;
          place(time, (i) => easeInOut(introAt(time, T.disc + i * 0.05, 0.75)));
        }
      }
      if (!growing) {
        const h = hoverRef.current;
        const targets: Target[] = METRICS.map((_, i) => {
          const d = discTarget(i, time, 0, 0, LAYOUT_R);
          d.r *= FILL;
          if (h !== null && CALLOUTS[h].blob === i) d.r *= 1.18;
          return { ...d, wobble: 0.05 };
        });
        sim.step(dt, targets, 0);
        if (nowMs - lastBeat > 1000) {
          lastBeat = nowMs; // 60 beats a minute on the heart-rate blob
          sim.beat = 1;
        }
      }
      if (settled || time >= T.disc) draw(time);

      const d = new Date();
      if (d.getSeconds() !== lastSecond) {
        lastSecond = d.getSeconds();
        setSecond(d);
      }
      raf = requestAnimationFrame(frame);
    };

    const toUnits = (e: PointerEvent) => {
      const r = overRef.current?.getBoundingClientRect();
      if (!r || !r.width) return null;
      return { x: ((e.clientX - r.left) / r.width) * 2 * VIEW - VIEW, y: ((e.clientY - r.top) / r.height) * 2 * VIEW - VIEW };
    };
    const onMove = (e: PointerEvent) => {
      if (settled && e.pointerType !== "touch") sim.pointer = toUnits(e);
    };
    const onLeave = () => (sim.pointer = null);
    const onDown = (e: PointerEvent) => {
      if (settled && e.pointerType === "touch") sim.pointer = toUnits(e);
    };
    const onUp = (e: PointerEvent) => {
      if (e.pointerType === "touch") sim.pointer = null;
    };
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
    window.addEventListener("pointerdown", onDown);
    window.addEventListener("pointerup", onUp);
    document.documentElement.addEventListener("pointerleave", onLeave);
    window.addEventListener("keydown", onKey);
    document.addEventListener("visibilitychange", onVisibility);
    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerdown", onDown);
      window.removeEventListener("pointerup", onUp);
      document.documentElement.removeEventListener("pointerleave", onLeave);
      window.removeEventListener("keydown", onKey);
      document.removeEventListener("visibilitychange", onVisibility);
    };
  }, []);

  const open = (e: React.MouseEvent, href: string) => {
    if (e.metaKey || e.ctrlKey || e.shiftKey || e.button !== 0) return;
    e.preventDefault();
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return router.push(href);
    setLeaving(true);
    router.prefetch(href);
    window.setTimeout(() => router.push(href), 240);
  };

  return (
    <div
      ref={rootRef}
      className="home"
      data-run={run}
      data-hover={hover === null ? undefined : CALLOUTS[hover].key}
      data-leaving={leaving ? "" : undefined}
    >
      <div className="seal">
        <div className="card a-flip" style={at(T.flip, T.flipDur)}>
          <svg className="face face-front" viewBox={BOX} data-w={2 * VIEW} aria-hidden>
            <Front hands={hands} />
          </svg>
          <svg className="face face-back" viewBox={BOX} data-w={2 * VIEW} aria-hidden>
            <Back />
          </svg>
        </div>
        <svg ref={overRef} className="over" viewBox={BOX} data-w={2 * VIEW} role="img" aria-label={t.home.drawing}>
          <defs>
            <clipPath id="disc-clip">
              <circle r={R_DISC} />
            </clipPath>
          </defs>
          <DiscMark />
          <g className="disc a-land" style={at(T.land, T.landDur)}>
            <circle className="disc-body a-fade" r={R_DISC} style={at(T.disc, 0.6)} />
            <g clipPath="url(#disc-clip)">
              {METRICS.map((m, i) => (
                <path key={m.key} ref={(el) => { pathRefs.current[i] = el; }} fill={m.color} fillRule="evenodd" stroke="#000" strokeWidth={3.5} strokeLinejoin="round" paintOrder="stroke" />
              ))}
            </g>
            <DiscEtching />
          </g>
          <g ref={secondRef} className="second">
            <line className="ln w15" x1={0} y1={-R_KNURL_IN - 3} x2={0} y2={-R_CASE + 3} />
          </g>
          <g className="leaders">
            {CALLOUTS.map((c, i) => {
              const pts = leaderPoints(c).map((p) => p.join(",")).join(" ");
              const start = T.callouts + i * 0.1;
              return (
                <g key={c.key} className={`leader${hover === i ? " on" : ""}`}>
                  <polyline className="leader-line a-draw" points={pts} pathLength={1} style={at(start, 0.55)} />
                  <polyline className="leader-hot" points={pts} pathLength={1} />
                  <circle className="node a-pop" cx={c.anchor[0]} cy={c.anchor[1]} r={4.5} style={at(start, 0.3)} />
                </g>
              );
            })}
          </g>
        </svg>
      </div>

      <nav className="callouts" aria-label={t.nav.sections}>
        <ol>
          {CALLOUTS.map((c, i) => {
            const end = leaderPoints(c)[2];
            const href = `/${lang}/${c.key}`;
            const copy = t.home.callouts[c.key];
            return (
              <li
                key={c.key}
                className={`callout callout-${c.side}`}
                style={{ "--x": end[0], "--y": end[1], ...at(T.callouts + i * 0.1 + 0.45, 1.1) } as CSSProperties}
              >
                <Link
                  href={href}
                  onClick={(e) => open(e, href)}
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
