// Geometry of the home drawing, centred on (0, 0) in a box of 800 drawing units. The watch the intro starts from is
// 44 mm at 15 units per millimetre; the 3D disc that takes its place (25 mm, D53) is drawn at U_MM units per millimetre.
// Angles are clockwise from 12 o'clock.
import type { Section } from "@/lib/i18n";

export const R_CASE = 340; // outer edge of the case
export const R_PLATE = 300;
export const VIEW = 400; // half size of the drawing box
export const U_MM = 22; // drawing units per millimetre of the 3D disc at rest
/** The 3D canvas is this many times the drawing box, so the parts standing above the shell are not cut off. */
export const CANVAS = 1.5;

/** Rounded to 0.01 so the server and the browser print the same numbers. */
export const r2 = (v: number) => Math.round(v * 100) / 100;

export const polar = (deg: number, r: number): [number, number] => {
  const a = (deg * Math.PI) / 180;
  return [r2(r * Math.sin(a)), r2(-r * Math.cos(a))];
};

/** The two halves of a circle, both starting at 12 o'clock, so it draws down both sides and closes at 6. */
export const halves = (r: number) => [`M0 ${-r} A${r} ${r} 0 0 1 0 ${r}`, `M0 ${-r} A${r} ${r} 0 0 0 0 ${r}`];

export type Callout = {
  key: Section;
  /** Where the line leaves the disc at rest. The 3D scene moves it with the part (disc3d.ts, ANCHORS). */
  anchor: [number, number];
  elbow: [number, number];
  side: "l" | "r";
};

// Each leader leaves its part, runs to an elbow just outside the disc and then level to its label. Three labels hang on the
// left; the right has one, under the side view. None of the lines cross.
const E = 372;
export const CALLOUTS: Callout[] = [
  { key: "open", anchor: [-235, -128], elbow: polar(322, E), side: "l" }, // the edge of the shell
  { key: "wear", anchor: [-247, 37], elbow: [-E, 0], side: "l" }, // the pad, behind the left edge
  { key: "measure", anchor: [0, -31], elbow: polar(218, E), side: "l" }, // the sensor window
  { key: "app", anchor: [0, 151], elbow: polar(142, E), side: "r" }, // the antenna, inside under the mark
];

export const SHOULDER = 440;

export function leaderPoints(c: Callout, anchor = c.anchor): [number, number][] {
  return [anchor, c.elbow, [c.side === "l" ? -SHOULDER : SHOULDER, c.elbow[1]]];
}
