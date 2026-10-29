// Logo proposals for Caseback built from the same flat-colour metaball idea as the onboarding blob field.
// Each proposal is a list of circles; the silhouette is the smooth union and each colour owns the region where its circle is nearest.
// Contours come from marching squares so the output is plain vector paths (no filters, no gradients).
//
//   node tools/illustrations/logo.mjs        writes out/logo-<name>.svg and out/logo-sheet${setNo}.html
import { writeFileSync, mkdirSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
import { S, render } from "./blobkit.mjs";
const C = { hr: "#FF4F7B", hrv: "#D79BFF", sleep: "#4D6BFF", ready: "#EEF24B", steps: "#3DDC84", spo2: "#3CC8F5", temp: "#FF9A3D", white: "#F2F2F4" };

// ---------------------------------------------------------------- proposals
const rosette = () => { // A: seven metrics fused into one disc
  const cols = [C.hr, C.hrv, C.sleep, C.spo2, C.steps, C.ready, C.temp];
  return { blobs: cols.map((c, i) => { const a = -Math.PI / 2 + i * 2 * Math.PI / 7; return { x: 256 + 98 * Math.cos(a), y: 256 + 98 * Math.sin(a), r: 50, c }; }), k: 44 };
};
const pair = () => ({ blobs: [ // B: two blobs becoming one
  { x: 196, y: 276, r: 104, c: C.steps }, { x: 332, y: 214, r: 78, c: C.hr }], k: 70 });
const four = () => ({ blobs: [ // C: four metrics in a square, necks between
  { x: 190, y: 190, r: 74, c: C.hr }, { x: 322, y: 190, r: 74, c: C.sleep },
  { x: 190, y: 322, r: 74, c: C.steps }, { x: 322, y: 322, r: 74, c: C.ready }], k: 52 });
const disc = () => ({ blobs: [ // D: the disc (white) with the sensor colours budding off it
  { x: 236, y: 266, r: 128, c: C.white }, { x: 366, y: 156, r: 58, c: C.hr }, { x: 408, y: 262, r: 34, c: C.steps }, { x: 346, y: 364, r: 22, c: C.spo2 }], k: 44 });
const open = () => { // E: an open O made of blobs; the gap is the "open"
  const cols = [C.ready, C.steps, C.spo2, C.sleep, C.hrv, C.hr];
  return { blobs: cols.map((c, i) => { const a = -Math.PI / 2 + 0.75 + i * (2 * Math.PI - 1.5) / 5; return { x: 256 + 118 * Math.cos(a), y: 256 + 118 * Math.sin(a), r: 54, c }; }), k: 50 };
};
const drops = () => ({ blobs: [ // F: a falling trail, big to small, diagonal
  { x: 176, y: 188, r: 92, c: C.hr }, { x: 292, y: 270, r: 70, c: C.temp }, { x: 372, y: 350, r: 48, c: C.ready }], k: 64 });
const tri = () => { // G: three metrics meeting in a triangle
  const cols = [C.hr, C.sleep, C.steps];
  return { blobs: cols.map((c, i) => { const a = -Math.PI / 2 + i * 2 * Math.PI / 3; return { x: 256 + 82 * Math.cos(a), y: 262 + 82 * Math.sin(a), r: 84, c }; }), k: 60 };
};
const drop = () => ({ blobs: [ // H: one drop of light, bands of colour from tip to base
  { x: 256, y: 150, r: 34, c: C.ready }, { x: 256, y: 224, r: 62, c: C.temp }, { x: 256, y: 336, r: 100, c: C.hr }], k: 90 });
const orbit = () => ({ blobs: [ // I: a body and three satellites about to detach
  { x: 232, y: 280, r: 112, c: C.sleep }, { x: 352, y: 156, r: 46, c: C.hrv }, { x: 138, y: 138, r: 30, c: C.spo2 }, { x: 396, y: 330, r: 26, c: C.steps }], k: 46 });
const pulse = () => ({ blobs: [ // J: small, big, small along one line, like a beat
  { x: 108, y: 256, r: 48, c: C.hrv }, { x: 256, y: 256, r: 104, c: C.hr }, { x: 410, y: 256, r: 40, c: C.spo2 }], k: 62 });
const spiral = () => { // K: blobs shrinking round a spiral
  const cols = [C.sleep, C.hr, C.temp, C.ready];
  return { blobs: cols.map((c, i) => { const a = -2.4 + i * 1.5, d = 96 - i * 26, r = 104 - i * 24; return { x: 262 + d * Math.cos(a), y: 262 + d * Math.sin(a), r, c }; }), k: 40 };
};
const twin = () => ({ blobs: [ // L: two equal lobes joined by a neck, a sideways 8
  { x: 158, y: 256, r: 98, c: C.steps }, { x: 354, y: 256, r: 98, c: C.hr }], k: 80 });
// Centre a proposal on the canvas and scale it so its widest side takes `fill` of the canvas (circles only; the smooth union adds a little).
const fit = (p, fill) => {
  const x0 = Math.min(...p.blobs.map((b) => b.x - b.r)), x1 = Math.max(...p.blobs.map((b) => b.x + b.r));
  const y0 = Math.min(...p.blobs.map((b) => b.y - b.r)), y1 = Math.max(...p.blobs.map((b) => b.y + b.r));
  const s = (fill * S) / Math.max(x1 - x0, y1 - y0), cx = (x0 + x1) / 2, cy = (y0 + y1) / 2;
  return { ...p, k: p.k * s, blobs: p.blobs.map((b) => ({ ...b, x: S / 2 + (b.x - cx) * s, y: S / 2 + (b.y - cy) * s, r: b.r * s })) };
};
const sets = {
  1: { fusion: rosette(), pair: pair(), four: four(), disc: disc(), open: open(), trail: drops() },
  2: { tri: tri(), drop: drop(), orbit: orbit(), pulse: pulse(), spiral: fit(spiral(), 0.8), twin: twin() },
};
const setNo = process.argv[2] ?? "1";
const proposals = sets[setNo];

mkdirSync(resolve(here, "out"), { recursive: true });
const names = {
  fusion: "A · Fusion", pair: "B · Pair", four: "C · Four", disc: "D · Disc", open: "E · Open O", trail: "F · Trail",
  tri: "G · Triad", drop: "H · Drop", orbit: "I · Orbit", pulse: "J · Pulse", spiral: "K · Spiral", twin: "L · Twin",
};
const tiles = [];
for (const [name, p] of Object.entries(proposals)) {
  const body = render(p);
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${S} ${S}" width="${S}" height="${S}"><rect width="${S}" height="${S}" fill="#000"/>\n${body}\n</svg>\n`;
  writeFileSync(resolve(here, `out/logo-${name}.svg`), svg);
  tiles.push(`<figure><div class="ic">${svg}</div><div class="sm"><div class="ic s">${svg}</div><div class="ic xs">${svg}</div></div><figcaption>${names[name]}</figcaption></figure>`);
}
writeFileSync(resolve(here, `out/logo-sheet${setNo}.html`), `<!doctype html><meta charset="utf-8"><style>
body{margin:0;background:#0b0b0c;color:#b8b8b8;font:15px -apple-system,Helvetica;padding:28px;width:1240px}
.g{display:grid;grid-template-columns:repeat(3,1fr);gap:34px 30px}
figure{margin:0}.ic svg{width:100%;height:100%;display:block}
.ic{width:380px;height:380px;border-radius:84px;overflow:hidden}
.sm{display:flex;gap:16px;align-items:flex-end;margin-top:12px}.s{width:60px;height:60px;border-radius:13px}.xs{width:29px;height:29px;border-radius:6.5px}
figcaption{margin-top:8px;color:#fff}
</style><div class="g">${tiles.join("")}</div>`);
console.log("ok");
