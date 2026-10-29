// Shared metaball helpers for the illustrations: smooth-union silhouettes with flat colour regions, as vector paths.
export const S = 512;
const N = 256, step = S / N;
export const smin = (a, b, k) => { const h = Math.max(k - Math.abs(a - b), 0) / k; return Math.min(a, b) - h * h * k * 0.25; };

function contours(field) {
  // Marching squares with linear interpolation; returns closed polygons.
  const v = (i, j) => field(i * step, j * step);
  const segs = [];
  const lerp = (p, q, a, b) => { const t = a / (a - b); return [p[0] + (q[0] - p[0]) * t, p[1] + (q[1] - p[1]) * t]; };
  for (let j = 0; j < N; j++) for (let i = 0; i < N; i++) {
    const p = [[i, j], [i + 1, j], [i + 1, j + 1], [i, j + 1]].map(([a, b]) => [a * step, b * step]);
    const val = [v(i, j), v(i + 1, j), v(i + 1, j + 1), v(i, j + 1)];
    let idx = 0; val.forEach((x, k) => { if (x < 0) idx |= 1 << k; });
    if (idx === 0 || idx === 15) continue;
    const e = (a, b) => lerp(p[a], p[b], val[a], val[b]);
    const E = [() => e(0, 1), () => e(1, 2), () => e(2, 3), () => e(3, 0)];
    const table = { 1: [[3, 0]], 2: [[0, 1]], 3: [[3, 1]], 4: [[1, 2]], 5: [[3, 0], [1, 2]], 6: [[0, 2]], 7: [[3, 2]], 8: [[2, 3]], 9: [[0, 2]], 10: [[0, 1], [2, 3]], 11: [[1, 2]], 12: [[1, 3]], 13: [[0, 1]], 14: [[3, 0]] };
    for (const [a, b] of table[idx]) segs.push([E[a](), E[b]()]);
  }
  // Chain segments by matching end points.
  const key = (p) => `${Math.round(p[0] * 50)},${Math.round(p[1] * 50)}`;
  const map = new Map();
  segs.forEach((s, n) => { for (const p of s) { const k = key(p); (map.get(k) ?? map.set(k, []).get(k)).push(n); } });
  const used = new Set(), polys = [];
  for (let n = 0; n < segs.length; n++) {
    if (used.has(n)) continue;
    used.add(n);
    let poly = [segs[n][0], segs[n][1]], cur = segs[n][1];
    for (;;) {
      const next = (map.get(key(cur)) ?? []).find((m) => !used.has(m));
      if (next === undefined) break;
      used.add(next);
      const s = segs[next];
      cur = key(s[0]) === key(cur) ? s[1] : s[0];
      poly.push(cur);
    }
    if (poly.length > 8) polys.push(poly);
  }
  return polys;
}
export const pathOf = (polys) => polys.map((p) => "M" + p.map((q) => `${q[0].toFixed(1)} ${q[1].toFixed(1)}`).join("L") + "Z").join("");

export function render({ blobs, k = 34, bg = "#000" }) {
  const sd = (b, x, y) => Math.hypot(x - b.x, y - b.y) - b.r;
  const union = (x, y) => blobs.reduce((m, b) => smin(m, sd(b, x, y), k), 1e9);
  const out = [];
  const colours = [...new Set(blobs.map((b) => b.c))];
  for (const c of colours) {
    const mine = blobs.filter((b) => b.c === c), other = blobs.filter((b) => b.c !== c);
    const field = (x, y) => {
      const dm = Math.min(...mine.map((b) => sd(b, x, y)));
      const dn = other.length ? Math.min(...other.map((b) => sd(b, x, y))) : 1e9;
      return Math.max(union(x, y), dm - dn);
    };
    out.push(`<path d="${pathOf(contours(field))}" fill="${c}"/>`);
  }
  return out.join("\n");
}

