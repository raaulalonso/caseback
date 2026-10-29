// Geometry of the home seal: a 44 mm watch seen from the wrist, 15 drawing units per millimetre, centred on (0, 0).
// The disc is 25 mm (D53, 2026-10-28) and its microsuction pad 17 mm (D12). Angles are clockwise from 12 o'clock.
import type { Section } from "@/lib/i18n";

export const R_CASE = 340; // outer edge of the case, drawn on both faces
export const R_KNURL_IN = 324; // the knurled rim of the caseback, back only
export const R_BEVEL = 318;
export const R_PLATE = 300;
export const R_RING = 278; // screws
export const R_INNER = 256;
export const R_DISC = 187.5; // 25 mm disc
export const R_PAD = 127.5; // 17 mm pad (0.68 of the disc radius), hidden behind the disc
export const VIEW = 400; // half size of the drawing box

/** Rounded to 0.01 so the server and the browser print the same numbers. */
export const r2 = (v: number) => Math.round(v * 100) / 100;

export const polar = (deg: number, r: number): [number, number] => {
  const a = (deg * Math.PI) / 180;
  return [r2(r * Math.sin(a)), r2(-r * Math.cos(a))];
};

/** The two halves of a circle, both starting at 12 o'clock, so it draws down both sides and closes at 6. */
export const halves = (r: number) => [`M0 ${-r} A${r} ${r} 0 0 1 0 ${r}`, `M0 ${-r} A${r} ${r} 0 0 0 0 ${r}`];

/** Six screws on the ring; `slot` is the angle the slot ends at once tightened. */
export const SCREWS = [30, 90, 150, 210, 270, 330].map((deg, i) => ({ deg, slot: [28, -14, 52, 8, -40, 70][i], at: polar(deg, R_RING) }));

export type Callout = {
  key: Section;
  anchor: [number, number];
  elbow: [number, number];
  side: "l" | "r";
  /** Blob that swells when the line is hovered. */
  blob: number;
};

/** Knurled rim: 120 ridges between R_KNURL_IN and R_CASE. */
export const KNURL = 120;

/** Part etched on the disc that a callout starts from: the Bluetooth antenna, at 38 degrees. */
export const ANTENNA = polar(38, 160);

// Each leader leaves its part and crosses the caseback ring, then runs level to its label.
const E = 372; // radius of the elbows, just outside the case
export const CALLOUTS: Callout[] = [
  { key: "wear", anchor: polar(322, R_PAD), elbow: polar(322, E), side: "l", blob: 1 },
  { key: "open", anchor: [SCREWS[4].at[0] - 12, 0], elbow: [-E, 0], side: "l", blob: 5 },
  { key: "measure", anchor: [-50.5, 23.6], elbow: polar(218, E), side: "l", blob: 2 },
  { key: "app", anchor: ANTENNA, elbow: polar(38, E), side: "r", blob: 4 },
];

export const SHOULDER = 440;

export function leaderPoints(c: Callout): [number, number][] {
  return [c.anchor, c.elbow, [c.side === "l" ? -SHOULDER : SHOULDER, c.elbow[1]]];
}
