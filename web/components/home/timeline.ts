// The intro on two clocks. `T` times the watch, from the moment the page starts it; `B` times what comes after, from the
// moment the watch begins to turn over. The turn waits for the disc model if it has not loaded by `T.flip`, so the second
// clock starts at `T.flip` or later. CSS animations get their start and length as `--d` and `--dur`: the watch's under
// data-run="intro", the rest under data-run="build", each set started in the same frame. The 3D disc reads `B` in JS.
import type { CSSProperties } from "react";

export const T = {
  ring: 0.1, // case ring draws from 12 down both sides
  ticks: 0.55,
  indices: 0.5, // pairs from 12 outward, 70 ms apart
  hands: 0.7, // the hands find the visitor's time
  flip: 1.8, // the watch turns over, as soon as the disc model is there
} as const;

export const B = {
  turn: 0, // one cubic in-out: the dial turns away to edge-on in the first half, the disc comes round in the second
  turnDur: 0.9,
  open: 0.78, // the disc opens along its axis while the camera drops to the exploded view
  openDur: 1.05,
  close: 2.3, // the parts close up in the order they go in, 160 ms apart, while the camera rises to rest
  step: 0.16,
  drop: 0.62,
  rest: 3.95, // the camera is at rest
  pulse: 3.62, // the LEDs light once as the last part closes
  pulseDur: 0.7,
  callouts: 3.8,
  done: 4.75,
  doneCompact: 4.0, // on a phone only the central drawing moves; the rest arrives once it is finished
  // side view: the disc goes up onto the caseback as it closes, then the wrist comes up to meet it
  side: 3.2,
  sideDur: 0.8,
  wrist: 3.75,
} as const;

/** Cubic in-out, the one ease for drawing and for travel. */
export const easeInOut = (u: number) => (u < 0.5 ? 4 * u * u * u : 1 - Math.pow(-2 * u + 2, 3) / 2);
/** Cubic out, for something that arrives already moving (the shell coming round after the dial). */
export const easeOut = (u: number) => 1 - Math.pow(1 - u, 3);

/** Progress 0..1 of a part that starts at `start` and lasts `dur`, at `time` seconds on its clock. */
export const introAt = (time: number, start: number, dur: number) => Math.min(1, Math.max(0, (time - start) / dur));

/** Inline style for a CSS-animated part. Extra custom properties ride along. */
export const at = (start: number, dur: number, extra?: Record<string, string | number>): CSSProperties =>
  ({ "--d": `${start.toFixed(3)}s`, "--dur": `${dur.toFixed(3)}s`, ...extra }) as CSSProperties;
