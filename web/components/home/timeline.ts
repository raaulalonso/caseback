// The intro on one clock. Every timed part of the home reads its start and length from here: CSS animations get them
// as `--d` and `--dur` (all started in the same frame by data-run="intro"), and the blobs read the same numbers in JS.
import type { CSSProperties } from "react";

export const T = {
  ring: 0.1, // case ring draws from 12 down both sides
  ticks: 0.55,
  indices: 0.5, // pairs from 12 outward, 70 ms apart
  hands: 0.7, // the hands find the visitor's time
  flip: 1.85, // the watch turns over
  flipDur: 0.95,
  rings: 2.6, // caseback rings, knurl, screws
  knurl: 2.7,
  screws: 2.85,
  mark: 3.3, // where the disc will go
  disc: 3.45, // the disc forms, held above the caseback
  land: 4.2, // it comes down onto the caseback
  landDur: 0.8,
  etch: 4.95,
  wrist: 5.0, // side view: the wrist comes up to the disc
  callouts: 5.15,
  done: 6.4,
  doneCompact: 5.7, // on a phone only the central drawing moves; the rest arrives once it is finished
} as const;

/** Cubic in-out, the one ease for drawing. */
export const easeInOut = (u: number) => (u < 0.5 ? 4 * u * u * u : 1 - Math.pow(-2 * u + 2, 3) / 2);

/** Progress 0..1 of a part that starts at `start` and lasts `dur`, at `time` seconds into the intro. */
export const introAt = (time: number, start: number, dur: number) => Math.min(1, Math.max(0, (time - start) / dur));

/** Inline style for a CSS-animated part. Extra custom properties ride along. */
export const at = (start: number, dur: number, extra?: Record<string, string | number>): CSSProperties =>
  ({ "--d": `${start.toFixed(3)}s`, "--dur": `${dur.toFixed(3)}s`, ...extra }) as CSSProperties;
