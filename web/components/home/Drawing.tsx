// The watch, drawn by hand in SVG. `Front` is the dial the intro starts from (the disc that takes its place when it turns
// over is 3D, ./disc3d.ts) and `SideView` the watch, disc and wrist in profile. Stroke weights: `w15` for the outline of an
// object, `w1` for its details, `w075` for background marks. Timings come from ./timeline.
import type { Dict } from "@/lib/i18n";
import { R_CASE, R_PLATE, halves, polar } from "./geometry";
import { B, T, at } from "./timeline";

/** A circle drawn in two halves from 12 o'clock, closing at 6, with a lume dot at the head of each half. */
function Ring({ r, cls, start, dur, wick = false }: { r: number; cls: string; start: number; dur: number; wick?: boolean }) {
  const [right, left] = halves(r);
  return (
    <g>
      <path className={`ln ${cls} a-draw`} d={right} pathLength={1} style={at(start, dur)} />
      <path className={`ln ${cls} a-draw`} d={left} pathLength={1} style={at(start, dur)} />
      {wick &&
        [180, -180].map((a) => (
          <g key={a} className="wick a-wick" style={at(start, dur, { "--a": `${a}deg` })}>
            <circle cy={-r} r={5} />
          </g>
        ))}
    </g>
  );
}

/** Order of a part from 12 o'clock outward, the same on both sides: 0 at 12, 1 for the next pair, and so on. */
const fromTwelve = (deg: number, step: number) => Math.floor((Math.min(deg, 360 - deg) + 0.001) / step);

export function Front({ hands }: { hands: { h: number; m: number; s: number } }) {
  return (
    <g className="front">
      <Ring r={R_CASE} cls="w15" start={T.ring} dur={0.9} wick />
      <Ring r={R_PLATE} cls="w075 dim" start={T.ring + 0.3} dur={0.8} />
      <g className="a-fade" style={at(T.ticks, 0.5)}>
        {Array.from({ length: 60 }, (_, i) => {
          if (i % 5 === 0) return null;
          const [x1, y1] = polar(i * 6, 284);
          const [x2, y2] = polar(i * 6, 294);
          return <line key={i} className="ln w075 dim" x1={x1} y1={y1} x2={x2} y2={y2} />;
        })}
      </g>
      {Array.from({ length: 12 }, (_, h) => (
        <g key={h} transform={`rotate(${h * 30})`}>
          <g className="a-fade" style={at(T.indices + fromTwelve(h * 30, 30) * 0.07, 0.24)}>
            {h === 0 ? (
              <>
                <rect className="fill-ink" x={-14} y={-286} width={9} height={52} />
                <rect className="fill-ink" x={5} y={-286} width={9} height={52} />
              </>
            ) : (
              <rect className="fill-ink" x={-4.5} y={-286} width={9} height={h % 3 ? 36 : 52} />
            )}
          </g>
        </g>
      ))}
      <g className="hand a-hand" style={at(T.hands, 0.95, { "--to": `${hands.h}deg` })}>
        <path className="fill-ink" d="M-7 20 L-6 -150 Q0 -160 6 -150 L7 20 Z" />
      </g>
      <g className="hand a-hand" style={at(T.hands + 0.05, 0.95, { "--to": `${hands.m}deg` })}>
        <path className="fill-ink" d="M-5 24 L-4 -236 Q0 -244 4 -236 L5 24 Z" />
      </g>
      <g className="hand a-hand" style={at(T.hands + 0.1, 0.95, { "--to": `${hands.s}deg` })}>
        <rect className="fill-lume" x={-1.4} y={-270} width={2.8} height={326} />
        <circle className="fill-lume" r={8} />
      </g>
      <circle className="fill-ground" r={2.5} />
    </g>
  );
}

/** Skin as a technical section: a gentle surface line with hatching under it. y of the surface at x, for x in 10..330. */
const skinY = (x: number) => {
  const u = (x - 10) / 320;
  return (1 - u) ** 2 * 158 + 2 * (1 - u) * u * 90 + u * u * 158;
};
const HATCH = Array.from({ length: 21 }, (_, i) => 24 + i * 14.4).map((x) => {
  const y = skinY(x);
  return `M${x.toFixed(1)} ${(y + 7).toFixed(1)} L${(x - 9).toFixed(1)} ${(y + 18).toFixed(1)}`;
});

/** The disc in profile: 25 mm wide and 3.1 mm high with the pad, the watch side on top (edge radius 0.6 mm) and the skin side below (1.2 mm). */
const DISC_SIDE = "M98.6 106 H241.4 A3.6 3.6 0 0 1 245 109.6 V117.4 A7.2 7.2 0 0 1 237.8 124.6 H102.2 A7.2 7.2 0 0 1 95 117.4 V109.6 A3.6 3.6 0 0 1 98.6 106 Z";

/**
 * The watch from the side at 6 units per millimetre: 44 mm case, 25 × 3.1 mm disc, 23 mm pad. The watch draws with the
 * main one; the disc goes up onto its caseback once the 3D disc is closed, then the wrist comes up to meet it. The parts
 * in `late` wait for the second clock (B).
 */
export function SideView({ t }: { t: Dict["home"]["side"] }) {
  return (
    <svg className="side-svg" viewBox="0 0 480 190" data-w={480} role="img" aria-label={t.label}>
      <g className="side-watch">
        <rect className="ln w15 a-draw" x={38} y={46} width={264} height={54} rx={12} pathLength={1} style={at(T.ring, 0.9)} />
        <path className="ln w1 a-draw" d="M60 46 Q170 28 280 46" pathLength={1} style={at(T.ring + 0.3, 0.6)} />
        <rect className="ln w1 a-draw" x={62} y={100} width={216} height={6} rx={2} pathLength={1} style={at(T.ring + 0.5, 0.6)} />
      </g>
      <g className="late">
        <g className="side-disc a-rise" style={at(B.side, B.sideDur)}>
          <g className="a-fade" style={at(B.side, 0.4)}>
            <path className="side-disc-body" d={DISC_SIDE} />
            <line className="ln w075 dim" x1={101} y1={108} x2={239} y2={108} strokeDasharray="4 4" />
          </g>
        </g>
        <path className="ln w15 a-draw" d="M10 158 Q170 90 330 158" pathLength={1} style={at(B.wrist, 0.8)} />
        <path className="ln w075 dim a-fade" d={HATCH.join(" ")} style={at(B.wrist + 0.3, 0.6)} />
      </g>
      <g className="side-labels">
        <g className="a-fade" style={at(T.ring + 0.8, 0.3)}>
          <line className="ln w075" x1={302} y1={50} x2={350} y2={50} />
          <text x={358} y={50} dy="0.34em">{t.watch}</text>
        </g>
        <g className="late">
          <g className="a-fade" style={at(B.side + B.sideDur, 0.3)}>
            <line className="ln w075" x1={245} y1={114} x2={350} y2={114} />
            <text x={358} y={114} dy="0.34em">{t.disc}</text>
          </g>
          <g className="a-fade" style={at(B.wrist + 0.5, 0.3)}>
            <line className="ln w075" x1={300} y1={146} x2={350} y2={146} />
            <text x={358} y={146} dy="0.34em">{t.wrist}</text>
          </g>
        </g>
      </g>
    </svg>
  );
}
