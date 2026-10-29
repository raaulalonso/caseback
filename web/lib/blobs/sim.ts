// Spring physics of the app's blob field (apps/ios/Caseback/Blobs/BlobSimulator.swift), in drawing units per second.
import type { BlobShape, MarkKind } from "./field";

export const METRICS = [
  { key: "hr", color: "#FF4F7B", kind: 0 },
  { key: "hrv", color: "#D79BFF", kind: 1 },
  { key: "sleep", color: "#4D6BFF", kind: 2 },
  { key: "readiness", color: "#EEF24B", kind: 6 },
  { key: "steps", color: "#3DDC84", kind: 3 },
  { key: "spo2", color: "#3CC8F5", kind: 4 },
  { key: "temp", color: "#FF9A3D", kind: 5 },
] as const satisfies readonly { key: string; color: string; kind: MarkKind }[];

/** The fused disc of the app (`BlobScenes.discLayout`): seven blobs of different sizes packed unevenly, in disc radii. */
export const DISC_LAYOUT: readonly [number, number, number][] = [
  [0.48, -0.45, 0.33],
  [-0.57, -0.33, 0.31],
  [-0.04, 0.03, 0.36],
  [-0.11, 0.67, 0.3],
  [0.6, 0.28, 0.32],
  [-0.64, 0.38, 0.27],
  [0.06, -0.74, 0.24],
];

export type Target = { x: number; y: number; r: number; morph?: number; rotation?: number; wobble?: number };

type State = {
  x: number; y: number; vx: number; vy: number;
  r: number; vr: number;
  morph: number; vm: number;
  rot: number; vrot: number;
  wobble: number;
  stretch: number; stretchAngle: number;
};

export class BlobSim {
  states: State[];
  /** Drawing units that correspond to one app point; scales forces and speeds. */
  unit: number;
  pointer: { x: number; y: number } | null = null;
  /** Reach of the pointer's push, in drawing units. */
  reach: number;
  beat = 0;

  constructor(count: number, unit: number, reach: number) {
    this.unit = unit;
    this.reach = reach;
    this.states = Array.from({ length: count }, () => ({
      x: 0, y: 0, vx: 0, vy: 0, r: 0, vr: 0, morph: 0, vm: 0, rot: 0, vrot: 0, wobble: 0.05, stretch: 0, stretchAngle: 0,
    }));
  }

  place(i: number, x: number, y: number, r = 0) {
    const s = this.states[i];
    s.x = x; s.y = y; s.vx = 0; s.vy = 0; s.r = r; s.vr = 0;
  }

  /** A tangential kick around `c`, neighbours in opposite senses, so the field shears and merges on the way. */
  whirl(cx: number, cy: number, strength = 1) {
    this.states.forEach((s, i) => {
      const dx = s.x - cx, dy = s.y - cy;
      const len = Math.max(Math.hypot(dx, dy), 1);
      const sign = i % 2 === 0 ? 1 : -1;
      const v = (520 + i * 45) * this.unit * strength * sign;
      s.vx += (-dy / len) * v;
      s.vy += (dx / len) * v;
    });
  }

  step(dt: number, targets: Target[], heartIndex = 0) {
    const u = this.unit;
    this.beat = Math.max(0, this.beat - dt * 4.5);
    this.states.forEach((s, i) => {
      const t = targets[i];
      const k = 46 + i * 9;
      const c = 2 * 0.55 * Math.sqrt(k);
      let fx = (t.x - s.x) * k - s.vx * c;
      let fy = (t.y - s.y) * k - s.vy * c;
      if (this.pointer) {
        const dx = s.x - this.pointer.x, dy = s.y - this.pointer.y;
        const len = Math.hypot(dx, dy);
        if (len < this.reach && len > 0.01) {
          const q = 1 - len / this.reach;
          fx += (dx / len) * 14000 * u * q * q;
          fy += (dy / len) * 14000 * u * q * q;
        }
      }
      s.vx += fx * dt; s.vy += fy * dt;
      s.x += s.vx * dt; s.y += s.vy * dt;

      const critical = (x: number, v: number, target: number, omega: number): [number, number] => {
        const f = (target - x) * omega * omega - 2 * omega * v;
        v += f * dt;
        return [x + v * dt, v];
      };
      const pulse = i === heartIndex ? this.beat * 0.06 : 0;
      [s.r, s.vr] = critical(s.r, s.vr, Math.max(t.r * (1 + pulse), 0), 9 + i * 0.6);
      if (s.r < 0) s.r = 0;
      [s.morph, s.vm] = critical(s.morph, s.vm, t.morph ?? 0, 7);
      s.morph = Math.min(Math.max(s.morph, 0), 1);
      [s.rot, s.vrot] = critical(s.rot, s.vrot, t.rotation ?? 0, 6);
      s.wobble += ((t.wobble ?? 0.05) - s.wobble) * Math.min(1, dt * 4);

      const speed = Math.hypot(s.vx, s.vy) / u;
      const wanted = Math.min(speed / 1500, 0.55) * (1 - s.morph);
      s.stretch += (wanted - s.stretch) * Math.min(1, dt * 14);
      if (speed > 30) {
        let da = Math.atan2(s.vy, s.vx) - s.stretchAngle;
        while (da > Math.PI) da -= 2 * Math.PI;
        while (da < -Math.PI) da += 2 * Math.PI;
        s.stretchAngle += da * Math.min(1, dt * 18);
      }
    });
  }

  shapes(): BlobShape[] {
    return this.states.map((s, i) => ({
      x: s.x, y: s.y, r: s.r, morph: s.morph, kind: METRICS[i].kind, rotation: s.rot,
      wobble: s.wobble, stretch: s.stretch, stretchAngle: s.stretchAngle, phase: i * 1.7,
    }));
  }
}

/** One blob of the disc with a slow independent breath, as `BlobScenes.discBlob`. */
export function discTarget(i: number, time: number, cx: number, cy: number, R: number): Target {
  const [lx, ly, lr] = DISC_LAYOUT[i];
  const ph = i * 1.7;
  return {
    x: cx + R * (lx + 0.018 * Math.sin(time * 0.9 + ph)),
    y: cy + R * (ly + 0.018 * Math.cos(time * 0.8 + ph * 1.3)),
    r: R * lr * (1 + 0.03 * Math.sin(time * 1.3 + ph)),
  };
}
