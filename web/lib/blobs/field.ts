// The blob field of the iOS app (apps/ios/Caseback/Blobs/Blobs.metal) drawn as SVG paths instead of pixels.
// Same model: each blob is a signed distance (circle with a slow wobble, or its metric mark when morphed), the shapes
// join with a log-sum-exp smooth union, and every point takes the colour of the nearest blob. The field is sampled on a
// grid, each blob's region is traced with marching squares and the outline is smoothed into cubic curves.

export type MarkKind = 0 | 1 | 2 | 3 | 4 | 5 | 6; // circle, diamond, square, triangle up, open circle, triangle down, bar

export type BlobShape = {
  x: number;
  y: number;
  r: number;
  /** 0 = blob, 1 = mark */
  morph: number;
  kind: MarkKind;
  rotation: number;
  /** Outline wobble amplitude, as a fraction of r. */
  wobble: number;
  /** Elongation along `stretchAngle` (0 = none). */
  stretch: number;
  stretchAngle: number;
  phase: number;
};

const SQ3 = Math.sqrt(3);

function sdTriangleUp(px: number, py: number, r: number) {
  py = -py;
  px = Math.abs(px) - r;
  py = py + r / SQ3;
  if (px + SQ3 * py > 0) {
    const nx = (px - SQ3 * py) * 0.5;
    const ny = (-SQ3 * px - py) * 0.5;
    px = nx;
    py = ny;
  }
  px -= Math.min(Math.max(px, -2 * r), 0);
  return -Math.hypot(px, py) * Math.sign(py);
}

function sdBox(px: number, py: number, hx: number, hy: number) {
  const qx = Math.abs(px) - hx;
  const qy = Math.abs(py) - hy;
  return Math.hypot(Math.max(qx, 0), Math.max(qy, 0)) + Math.min(Math.max(qx, qy), 0);
}

/** Distance to a metric mark; sizes match the app so every mark has about the same visual weight. */
export function sdMark(px: number, py: number, r: number, kind: MarkKind, unit: number) {
  switch (kind) {
    case 1: return (Math.abs(px) + Math.abs(py) - r * 1.12) * 0.70710678;
    case 2: return sdBox(px, py, r * 0.8, r * 0.8) - 1.5 * unit;
    case 3: return sdTriangleUp(px, py + r * 0.12, r * 0.92) - unit;
    case 4: return Math.abs(Math.hypot(px, py) - r * 0.7) - r * 0.22;
    case 5: return sdTriangleUp(px, -py + r * 0.12, r * 0.92) - unit;
    case 6: return sdBox(px, py, r * 0.3, r * 1.05) - 1.5 * unit;
    default: return Math.hypot(px, py) - r;
  }
}

function blobDistance(b: BlobShape, x: number, y: number, time: number, unit: number) {
  let px = x - b.x;
  let py = y - b.y;
  if (b.stretch > 0.001) {
    const c = Math.cos(b.stretchAngle), s = Math.sin(b.stretchAngle);
    let qx = c * px + s * py;
    let qy = -s * px + c * py;
    qx /= 1 + b.stretch;
    qy *= 1 + 0.7 * b.stretch;
    px = c * qx - s * qy;
    py = s * qx + c * qy;
  }
  if (b.rotation) {
    const c = Math.cos(b.rotation), s = Math.sin(b.rotation);
    const rx = c * px + s * py;
    py = -s * px + c * py;
    px = rx;
  }
  const len = Math.hypot(px, py);
  let blob = len - b.r;
  // The wobble only matters near the outline; far points skip the atan2.
  if (b.wobble > 0.0005 && len < b.r * 1.8) {
    const a = Math.atan2(py, px);
    const w = b.wobble * (0.7 * Math.sin(3 * a + time * 0.9 + b.phase) + 0.3 * Math.sin(5 * a - time * 1.3 + b.phase * 2));
    blob = len - b.r * (1 + w);
  }
  if (b.morph <= 0.001) return blob;
  const m = Math.min(Math.max(b.morph, 0), 1);
  return blob + (sdMark(px, py, b.r, b.kind, unit) - blob) * m;
}

export type FieldOptions = {
  /** Neck width of the smooth union, in drawing units. */
  k: number;
  /** Grid step in drawing units (smaller is smoother and slower). */
  step: number;
  time: number;
  /** Size of one app point in drawing units, for the mark offsets. */
  unit?: number;
};

/** Returns one SVG path per blob (empty string when the blob has no area). */
export function fieldPaths(blobs: BlobShape[], o: FieldOptions): string[] {
  const n = blobs.length;
  const out: string[] = new Array(n).fill("");
  if (!n) return out;
  const unit = o.unit ?? 1;

  // Bounding box of everything that can be inside, padded so every contour closes inside the grid.
  let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
  for (const b of blobs) {
    if (b.r <= 0.01) continue;
    const reach = b.r * (1.6 + b.stretch) + o.k * 2;
    x0 = Math.min(x0, b.x - reach); x1 = Math.max(x1, b.x + reach);
    y0 = Math.min(y0, b.y - reach); y1 = Math.max(y1, b.y + reach);
  }
  if (!isFinite(x0)) return out;
  const step = o.step;
  x0 -= step * 2; y0 -= step * 2; x1 += step * 2; y1 += step * 2;
  const nx = Math.ceil((x1 - x0) / step) + 1;
  const ny = Math.ceil((y1 - y0) / step) + 1;
  const N = nx * ny;

  const D = new Float32Array(N * n); // per-blob distance
  const U = new Float32Array(N); // union
  const m1 = new Float32Array(N); // nearest distance
  const m2 = new Float32Array(N); // second nearest
  const arg = new Uint8Array(N);
  const k = Math.max(o.k, 0.5);

  for (let j = 0; j < ny; j++) {
    const y = y0 + j * step;
    for (let i = 0; i < nx; i++) {
      const x = x0 + i * step;
      const idx = j * nx + i;
      let a = Infinity, b2 = Infinity, ai = 0;
      for (let q = 0; q < n; q++) {
        const bl = blobs[q];
        const d = bl.r <= 0.01 ? 1e6 : blobDistance(bl, x, y, o.time, unit);
        D[idx * n + q] = d;
        if (d < a) { b2 = a; a = d; ai = q; } else if (d < b2) b2 = d;
      }
      let sum = 0;
      for (let q = 0; q < n; q++) sum += Math.exp(-(D[idx * n + q] - a) / k);
      // The border of the grid is always outside, so contours close.
      const border = i === 0 || j === 0 || i === nx - 1 || j === ny - 1;
      U[idx] = border ? 1e6 : a - k * Math.log(Math.max(sum, 1e-6));
      m1[idx] = a; m2[idx] = b2; arg[idx] = ai;
    }
  }

  const g = new Float32Array(N);
  for (let q = 0; q < n; q++) {
    if (blobs[q].r <= 0.01) continue;
    let any = false;
    for (let idx = 0; idx < N; idx++) {
      const other = arg[idx] === q ? m2[idx] : m1[idx];
      const v = Math.max(U[idx], D[idx * n + q] - other);
      g[idx] = v;
      if (v < 0) any = true;
    }
    if (any) out[q] = trace(g, nx, ny, x0, y0, step);
  }
  return out;
}

/** Marching squares on `g < 0`, chained into closed loops and smoothed into cubic curves. */
function trace(g: Float32Array, nx: number, ny: number, x0: number, y0: number, step: number): string {
  // Edge keys: horizontal edge from (i,j) to (i+1,j) = 2*(j*nx+i); vertical edge from (i,j) to (i,j+1) = 2*(j*nx+i)+1.
  const pos = new Map<number, [number, number]>();
  const link = new Map<number, number[]>();
  const point = (key: number): [number, number] => {
    let p = pos.get(key);
    if (p) return p;
    const base = key >> 1;
    const i = base % nx, j = (base - i) / nx;
    const a = g[base];
    const b = key & 1 ? g[base + nx] : g[base + 1];
    const t = a / (a - b);
    p = key & 1 ? [x0 + i * step, y0 + (j + t) * step] : [x0 + (i + t) * step, y0 + j * step];
    pos.set(key, p);
    return p;
  };
  const join = (a: number, b: number) => {
    point(a); point(b);
    let la = link.get(a); if (!la) link.set(a, (la = []));
    let lb = link.get(b); if (!lb) link.set(b, (lb = []));
    la.push(b); lb.push(a);
  };

  for (let j = 0; j < ny - 1; j++) {
    for (let i = 0; i < nx - 1; i++) {
      const idx = j * nx + i;
      const tl = g[idx] < 0, tr = g[idx + 1] < 0, br = g[idx + nx + 1] < 0, bl = g[idx + nx] < 0;
      const c = (tl ? 8 : 0) | (tr ? 4 : 0) | (br ? 2 : 0) | (bl ? 1 : 0);
      if (c === 0 || c === 15) continue;
      const top = 2 * idx, left = 2 * idx + 1, bottom = 2 * (idx + nx), right = 2 * (idx + 1) + 1;
      switch (c) {
        case 1: case 14: join(left, bottom); break;
        case 2: case 13: join(bottom, right); break;
        case 3: case 12: join(left, right); break;
        case 4: case 11: join(top, right); break;
        case 6: case 9: join(top, bottom); break;
        case 7: case 8: join(left, top); break;
        case 5: case 10: {
          const centre = (g[idx] + g[idx + 1] + g[idx + nx] + g[idx + nx + 1]) / 4 < 0;
          if ((c === 5) === centre) { join(left, top); join(bottom, right); } else { join(left, bottom); join(top, right); }
          break;
        }
      }
    }
  }

  const seen = new Set<number>();
  let d = "";
  for (const start of link.keys()) {
    if (seen.has(start)) continue;
    const loop: [number, number][] = [];
    let prev = -1, cur = start;
    while (cur !== undefined && !seen.has(cur)) {
      seen.add(cur);
      loop.push(pos.get(cur)!);
      const nb = link.get(cur)!;
      const next = nb[0] !== prev ? nb[0] : nb[1];
      prev = cur;
      cur = next;
    }
    if (loop.length >= 3) d += smooth(loop, step * 0.45);
  }
  return d;
}

/** Closed Catmull-Rom spline through the points, as cubic Béziers; drops points closer than `minGap`. */
function smooth(raw: [number, number][], minGap: number): string {
  const p: [number, number][] = [];
  for (const q of raw) {
    const last = p[p.length - 1];
    if (!last || Math.hypot(q[0] - last[0], q[1] - last[1]) >= minGap) p.push(q);
  }
  const n = p.length;
  if (n < 3) return "";
  const f = (v: number) => (Math.round(v * 10) / 10).toString();
  let d = `M${f(p[0][0])} ${f(p[0][1])}`;
  for (let i = 0; i < n; i++) {
    const a = p[(i - 1 + n) % n], b = p[i], c = p[(i + 1) % n], e = p[(i + 2) % n];
    d += `C${f(b[0] + (c[0] - a[0]) / 6)} ${f(b[1] + (c[1] - a[1]) / 6)} ${f(c[0] - (e[0] - b[0]) / 6)} ${f(c[1] - (e[1] - b[1]) / 6)} ${f(c[0])} ${f(c[1])}`;
  }
  return d + "Z";
}
