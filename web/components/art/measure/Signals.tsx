"use client";

// Plate 2: the three answers of the app on the left, the signals they are built from on the right, joined by lines. The
// marks are the blobs of the disc (lib/blobs) traced once in their final shape, as in the app. Still; hovering a name
// brings forward the lines and names it is joined to.
import { useState, type CSSProperties } from "react";
import { fieldPaths, type BlobShape } from "@/lib/blobs/field";
import { METRICS } from "@/lib/blobs/sim";
import type { Dict } from "@/lib/i18n";
import { ArtFrame } from "../ArtFrame";

type T = Dict["measure"]["art"]["signals"];
type Key = "recovery" | "sleep" | "movement" | "hr" | "hrv" | "temp" | "spo2" | "motion";
type State = "trend";
type Spec = { key: Key; metric: number | null; side: "l" | "r"; row: number; state: State | null };

// Rows are in sixths of the drawing: each answer sits level with what it is built from.
const SPECS: Spec[] = [
  { key: "recovery", metric: 3, side: "l", row: 0.5, state: null },
  { key: "sleep", metric: 2, side: "l", row: 2, state: null },
  { key: "movement", metric: 4, side: "l", row: 3.5, state: null },
  { key: "temp", metric: 6, side: "r", row: 0, state: "trend" },
  { key: "hrv", metric: 1, side: "r", row: 1, state: null },
  { key: "hr", metric: 0, side: "r", row: 2, state: null },
  { key: "motion", metric: null, side: "r", row: 3, state: null },
  { key: "spo2", metric: 5, side: "r", row: 4, state: "trend" },
];
const EDGES: [Key, Key][] = [
  ["recovery", "temp"], ["recovery", "hrv"], ["recovery", "hr"], ["recovery", "sleep"],
  ["sleep", "hr"], ["sleep", "motion"], ["movement", "motion"],
];

type Layout = { W: number; H: number; XL: number; XR: number; R: number; top: number; pitch: number; stub: number; wrapName: number; wrapSub: number; line: number; step: number; axis: number };
const WIDE: Layout = { W: 860, H: 590, XL: 250, XR: 610, R: 30, top: 84, pitch: 112, stub: 36, wrapName: 99, wrapSub: 22, line: 17, step: 2.2, axis: 22 };
const NARROW: Layout = { W: 350, H: 440, XL: 124, XR: 226, R: 16, top: 70, pitch: 84, stub: 8, wrapName: 12, wrapSub: 15, line: 15.5, step: 1.2, axis: 14 };

type Node = Spec & { x: number; y: number };
const nodesFor = (L: Layout): Node[] => SPECS.map((s) => ({ ...s, x: s.side === "l" ? L.XL : L.XR, y: L.top + s.row * L.pitch }));

const markPaths = (L: Layout) => {
  const nodes = nodesFor(L);
  return METRICS.map((m, i) => {
    const n = nodes.find((q) => q.metric === i)!;
    const shape: BlobShape = { x: n.x, y: n.y, r: L.R, morph: 1, kind: m.kind, rotation: 0, wobble: 0, stretch: 0, stretchAngle: 0, phase: i * 1.7 };
    return fieldPaths([shape], { k: 1, step: L.step, time: 0, unit: 2 })[0];
  });
};
const PATHS = { wide: markPaths(WIDE), narrow: markPaths(NARROW) };

/** Breaks a text over as few lines of at most `max` characters as it takes, with the lines about equally long. */
function wrap(text: string, max: number) {
  const words = text.split(" ");
  const lines = Math.ceil(text.length / max);
  const width = lines > 1 ? Math.max(Math.ceil(text.length / lines) + 1, ...words.map((w) => w.length)) : max;
  const out: string[] = [];
  let cur = "";
  for (const w of words) {
    if (cur && cur.length + 1 + w.length > width) {
      out.push(cur);
      cur = w;
    } else cur = cur ? `${cur} ${w}` : w;
  }
  if (cur) out.push(cur);
  return out;
}

export function SignalsArt({ t }: { t: T }) {
  const [hot, setHot] = useState<Key | null>(null);
  return (
    <figure className="figure">
      <div className="only-wide"><Diagram t={t} L={WIDE} paths={PATHS.wide} hot={hot} setHot={setHot} /></div>
      <div className="only-narrow"><Diagram t={t} L={NARROW} paths={PATHS.narrow} hot={hot} setHot={setHot} narrow /></div>
      <p className="legend">
        <span><i className="mark-filled" />{t.legendFilled}</span>
        <span><i className="mark-open" />{t.legendOpen}</span>
      </p>
    </figure>
  );
}

function Diagram({ t, L, paths, hot, setHot, narrow }: { t: T; L: Layout; paths: string[]; hot: Key | null; setHot: (k: Key | null) => void; narrow?: boolean }) {
  const nodes = nodesFor(L);
  const by = Object.fromEntries(nodes.map((n) => [n.key, n])) as Record<Key, Node>;
  const names: Record<Key, string> = { recovery: t.recovery, sleep: t.sleep, movement: t.movement, hr: t.hr, hrv: t.hrv, temp: t.temp, spo2: t.spo2, motion: t.motion };
  const subs: Partial<Record<Key, string>> = { recovery: t.recoverySub, sleep: t.sleepSub, movement: t.movementSub };

  const lit = (a: Key, b: Key) => hot !== null && (a === hot || b === hot);
  const related = (k: Key) => hot === null || k === hot || EDGES.some(([a, b]) => lit(a, b) && (a === k || b === k));

  const gap = L.R + 8;
  const edge = (a: Node, b: Node) => {
    if (a.side === b.side) return `M${a.x} ${a.y + gap + 2} V${b.y - gap - 2}`;
    return `M${a.x + gap} ${a.y} H${a.x + gap + L.stub} L${b.x - gap - L.stub} ${b.y} H${b.x - gap}`;
  };

  return (
    <ArtFrame w={L.W} h={L.H} label={t.label} className="art-signals">
      {/* column heads */}
      {[
        { x: L.XL + L.R, anchor: "end" as const, text: t.headAnswers, from: narrow ? 0 : 20 },
        { x: L.XR - L.R, anchor: "start" as const, text: t.headSignals, from: L.XR - L.R },
      ].map((h) => (
        <g key={h.text}>
          <text className="head" x={h.x} y={narrow ? 12 : 16} textAnchor={h.anchor}>{h.text}</text>
          <line className="ln w075 dim" x1={h.anchor === "end" ? h.from : h.x} y1={narrow ? 24 : 30} x2={h.anchor === "end" ? h.x : L.W - (narrow ? 0 : 20)} y2={narrow ? 24 : 30} />
        </g>
      ))}

      {EDGES.map(([a, b]) => (
        <path
          key={`${a}${b}`}
          className={`edge${lit(a, b) ? " on" : ""}${hot && !lit(a, b) ? " off" : ""}`}
          d={edge(by[a], by[b])}
          strokeDasharray={b === "temp" ? "4 4" : undefined}
        />
      ))}

      {nodes.map((n) => {
        const left = n.side === "l";
        const lx = left ? n.x - gap - 2 : n.x + gap + 2;
        const lines = [
          ...wrap(names[n.key], L.wrapName).map((text) => ({ text, cls: "name" })),
          ...(subs[n.key] ? wrap(subs[n.key]!, L.wrapSub) : []).map((text) => ({ text, cls: "sub" })),
        ];
        const y0 = n.y - ((lines.length - 1) * L.line) / 2;
        return (
          <g
            key={n.key}
            className={`sig${related(n.key) ? "" : " off"}`}
            tabIndex={0}
            onPointerEnter={() => setHot(n.key)}
            onPointerLeave={() => setHot(null)}
            onFocus={() => setHot(n.key)}
            onBlur={() => setHot(null)}
          >
            <rect x={left ? 0 : n.x - gap} y={n.y - L.pitch / 2 + 4} width={left ? n.x + gap : L.W - n.x + gap} height={L.pitch - 8} fill="transparent" />
            {n.metric === null && (
              <g>
                {[[1, 0], [0, -1], [-0.62, 0.62]].map(([dx, dy]) => {
                  const a = L.axis;
                  const ex = n.x + dx * a, ey = n.y + dy * a;
                  const h = a * 0.3;
                  const len = Math.hypot(dx, dy);
                  const ux = dx / len, uy = dy / len;
                  return (
                    <g key={`${dx}${dy}`}>
                      <line className="ln w15" x1={n.x} y1={n.y} x2={ex} y2={ey} />
                      <path className="ln w15" d={`M${ex - ux * h - uy * h * 0.6} ${ey - uy * h + ux * h * 0.6} L${ex} ${ey} L${ex - ux * h + uy * h * 0.6} ${ey - uy * h - ux * h * 0.6}`} />
                    </g>
                  );
                })}
                <circle cx={n.x} cy={n.y} r={3} fill="var(--ink-1)" />
              </g>
            )}
            {lines.map((l, i) => (
              <text key={i} className={l.cls} x={lx} y={y0 + i * L.line} dy="0.34em" textAnchor={left ? "end" : "start"}>{l.text}</text>
            ))}
          </g>
        );
      })}

      <g aria-hidden>
        {METRICS.map((m, i) => {
          const n = nodes.find((q) => q.metric === i)!;
          return (
            <path
              key={m.key}
              className={`mk${n.state === "trend" ? " open" : ""}${related(n.key) ? "" : " off"}`}
              d={paths[i]}
              style={{ "--c": m.color } as CSSProperties}
              fillRule="evenodd"
            />
          );
        })}
      </g>
    </ArtFrame>
  );
}
