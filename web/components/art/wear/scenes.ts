// The 3D plates of "How it's worn": the disc going onto the back of a watch, the disc clicking into its charger, and the
// disc going into the band. The disc is the model of the home page (public/models/disc.glb, from
// hardware/mechanical/scripts/export_web.py); the watch, the charger and the band are drawn round it in lines (./sketch.ts),
// to the numbers of their designs, in millimetres: the charger of D59 (generate_disc.py, build_puck) and the band of D58
// (generate_band.py, band_v01.py).
//
// Each scene is driven by one number, `p`, from 0 to 1: how far the plate has come up the screen (WearArt). It follows on a
// slow critically damped spring, so scrolling back plays the plate backwards and a fling never jerks it, and every pose is
// a monotone spline of p. The drawing draws itself first, then the disc comes in. Pointing at a name moves its part on a
// second spring, `f`: the disc comes off the caseback, out of the charger, out of its holder. Nothing moves on its own.
import * as THREE from "three";
import { DEG, createRenderer, disposeScene, loadModel, pixelRatio, precompile, prepareAll, s0, spring, track } from "../../three/core";
import { Ink, Pen, TAU, X, Y, Z, solid, solidBox, solidCylinder, solidRing, solidStrip, v } from "./sketch";

export type WearKind = "caseback" | "charge" | "band";
type Track = (t: number) => number;
type Pose = { yaw: Track; tilt: Track; zoom: Track };

const FOV = 22;
/** The disc in the watch's frame: its pad (y = 3.1 in its own frame) on the caseback plate, 4.4 mm behind the middle of the case. */
const CASEBACK_Z = -4.4;
const DISC_H = 3.1;
/** The dish floor of the charger, where the skin face of the disc rests (generate_disc.py, P_FLOOR). */
const DISH = 5.8;
/** How far the button stands out of the charger's rim, which is how far the latch moves (D59). */
const BUTTON = 0.8;
/** The drawing draws itself over the first part of the progress; the disc moves over the rest. */
const DRAWN = track([[0.02, 0], [0.45, 1]]);

type Built = {
  rig: THREE.Group;
  pose: Pose;
  /** Radius in millimetres that fills the height of the canvas at zoom 1. */
  fit: number;
  /** Share of the width the subject moves left by, to leave the labels room on the right. */
  shift: number;
  /** On a narrow (square) figure: how far the subject moves left, and how much closer (or further) the camera is. */
  narrowShift: number;
  narrowZoom: number;
  anchors: Record<string, THREE.Object3D>;
  /** Places the parts for progress `p` and for `f`, how far the part whose name is pointed at has moved (0..1). */
  update: (p: number, f: number) => void;
  /** The names that move a part. */
  focusable: string[];
  ink: Ink;
};

export class WearScene {
  private renderer: THREE.WebGLRenderer;
  private env: THREE.Texture;
  private scene = new THREE.Scene();
  private camera = new THREE.PerspectiveCamera(FOV, 4 / 3, 1, 4000);
  private built: Built;
  private p = s0();
  private tiltX = s0();
  private tiltY = s0();
  private focus = s0();
  private focusKey: string | null = null;
  private aim: { x: number; y: number } | null = null;
  private size = { w: 1, h: 1 };
  private sized = "";
  private narrow = false;
  private dirty = true;
  private v = new THREE.Vector3();

  private constructor(canvas: HTMLCanvasElement, built: Built) {
    ({ renderer: this.renderer, env: this.env } = createRenderer(canvas, this.scene));
    this.built = built;
    this.scene.add(built.rig, built.ink.liveLines);
  }

  /** `narrow`: see resize. The scene is drawn once at the canvas's size before it is returned (see warm). */
  static async create(kind: WearKind, canvas: HTMLCanvasElement, narrow: boolean) {
    const disc = (await loadModel("disc")).scene.clone(true);
    prepareAll(disc);
    const built = kind === "caseback" ? caseback(disc) : kind === "charge" ? charge(disc) : band(disc);
    const scene = new WearScene(canvas, built);
    const r = canvas.getBoundingClientRect();
    if (r.width > 0) scene.resize(r.width, r.height, narrow);
    await scene.warm();
    return scene;
  }

  /** Compiles the programs (in parallel where the browser can) and draws the plate once, finished and unseen. */
  private async warm() {
    await precompile(this.renderer, this.scene, this.camera);
    this.p = s0(1);
    this.frame(1, 0, true);
    this.p = s0();
    this.dirty = true;
  }

  /** Pointer over the figure, -1..1 across it; null when it leaves. */
  setPointer(p: { x: number; y: number } | null) {
    this.aim = p;
    this.dirty = true;
  }

  /** The name pointed at, or null. */
  setFocus(key: string | null) {
    this.focusKey = key;
    this.dirty = true;
  }

  /** The names stand on the right of the picture, so the subject moves left to leave them room; `narrow`: a phone's. */
  resize(w: number, h: number, narrow: boolean) {
    const ratio = pixelRatio(w, h);
    const key = `${w}x${h}@${ratio}/${narrow}`;
    if (key === this.sized) return;
    this.sized = key;
    this.size = { w, h };
    this.narrow = narrow;
    this.renderer.setPixelRatio(ratio);
    this.renderer.setSize(w, h, false);
    this.camera.aspect = w / h;
    this.camera.setViewOffset(w, h, (narrow ? this.built.narrowShift : this.built.shift) * w, 0, w, h);
    this.camera.updateProjectionMatrix();
    this.dirty = true;
  }

  /**
   * One frame: `target` is where p should go (0..1), `dt` the frame time. `still` (reduced motion) puts everything where it
   * goes at once. Returns false when nothing moved, so nothing was drawn.
   */
  frame(target: number, dt: number, still: boolean) {
    let moving = this.dirty;
    this.dirty = false;
    const step = (sp: { x: number; v: number }, to: number, w: number) => {
      if (still) Object.assign(sp, { x: to, v: 0 });
      else spring(sp, to, dt, w);
      if (sp.x !== to || sp.v !== 0) moving = true;
    };
    step(this.p, target, 3.2);
    const aim = this.aim && !still ? this.aim : { x: 0, y: 0 };
    step(this.tiltX, aim.x, 4);
    step(this.tiltY, aim.y, 4);
    step(this.focus, this.focusKey && this.built.focusable.includes(this.focusKey) ? 1 : 0, 5);
    if (!moving) return false;

    const p = Math.min(1, Math.max(0, this.p.x));
    const { rig, pose, fit, ink } = this.built;
    this.built.update(p, Math.min(1, Math.max(0, this.focus.x)));
    rig.rotation.set((pose.tilt(p) + this.tiltY.x * 3) * DEG, (pose.yaw(p) + this.tiltX.x * 5) * DEG, 0, "XYZ");
    const zoom = pose.zoom(p) * (this.narrow ? this.built.narrowZoom : 1);
    const dist = fit / zoom / Math.tan((FOV / 2) * DEG);
    this.camera.position.set(0, 0, dist);
    this.camera.lookAt(0, 0, 0);
    this.scene.updateMatrixWorld(true);
    ink.set(DRAWN(p), this.size.w, this.size.h);
    ink.update(this.camera.position);
    this.renderer.render(this.scene, this.camera);
    return true;
  }

  /** Where each label's line starts, in CSS pixels from the top left of the canvas. */
  anchors() {
    const out: Record<string, [number, number]> = {};
    this.scene.updateMatrixWorld(true);
    for (const [key, node] of Object.entries(this.built.anchors)) {
      node.getWorldPosition(this.v).project(this.camera);
      out[key] = [(this.v.x * 0.5 + 0.5) * this.size.w, (-this.v.y * 0.5 + 0.5) * this.size.h];
    }
    return out;
  }

  /** Progress the scene has reached (0..1), for what the page draws over it. */
  get progress() {
    return Math.min(1, Math.max(0, this.p.x));
  }

  dispose() {
    this.built.ink.dispose();
    disposeScene(this.scene, this.env, this.renderer);
  }
}

/** A point fixed to `node` at `at`, in its own frame. */
function mark(node: THREE.Object3D, at: THREE.Vector3) {
  const o = new THREE.Object3D();
  o.position.copy(at);
  node.add(o);
  return o;
}

/** A point on the round edge of the disc, in its own frame: angle from +x towards +z, radius, height above the skin face. */
const rim = (deg: number, r: number, y: number) => v(r * Math.cos(deg * DEG), y, r * Math.sin(deg * DEG));

const smooth = (x: number) => {
  const s = Math.min(1, Math.max(0, x));
  return s * s * (3 - 2 * s);
};

// ------------------------------------------------------------------------------------------------------------ the watch
/**
 * A watch of 44 mm in lines, in its own frame: dial towards +z, 12 o'clock towards +y, crown towards +x, the middle of the
 * case at z = 0 and the caseback plate, where the disc goes, at z = -4.4, with its straps.
 */
function drawWatch(ink: Ink) {
  const g = new THREE.Group();
  const edge = new Pen();
  const fine = new Pen();
  const R = 22; // case
  const BACK = -3.4; // back of the case, round the caseback plate
  const TOP = 3.6; // top of the case side, under the bezel
  const BEZEL = 4.6;
  const PLATE = 16.5; // caseback plate
  const at = (z: number) => v(0, 0, z);

  edge.arc(at(BACK), X, Y, R).arc(at(TOP), X, Y, R).arc(at(BEZEL), X, Y, 20.8).arc(at(BEZEL), X, Y, 18.6);
  edge.arc(at(CASEBACK_Z), X, Y, PLATE).arc(at(BACK), X, Y, PLATE);
  fine.arc(at(BACK), X, Y, 18.6);
  for (let k = 0; k < 4; k++) {
    const a = (45 + 90 * k) * DEG;
    fine.arc(v(20.3 * Math.cos(a), 20.3 * Math.sin(a), BACK), X, Y, 0.75);
  }
  ink.sides.push(
    { node: g, c: at(0), axis: Z, u: X, r: R, h0: BACK, h1: TOP },
    { node: g, c: at(0), axis: Z, u: X, r: 21.2, h0: TOP, h1: BEZEL },
    { node: g, c: at(0), axis: Z, u: X, r: PLATE, h0: CASEBACK_Z, h1: BACK },
  );
  // the case is solid up to just under the crystal, and the bezel is a ring round it
  solidCylinder(g, at(0), Z, R - 0.12, BACK + 0.1, TOP - 0.15);
  solidRing(g, 18.75, 20.7, TOP - 0.15, BEZEL - 0.12).rotation.x = 90 * DEG;
  solidCylinder(g, at(0), Z, PLATE - 0.12, CASEBACK_Z + 0.1, BACK + 0.1);

  // crown at 3 o'clock
  const crown = v(0, 0, 0.3);
  edge.arc(v(25.2, 0, 0.3), Y, Z, 2.6).arc(v(22.6, 0, 0.3), Y, Z, 2.6);
  ink.sides.push({ node: g, c: crown, axis: X, u: Y, r: 2.6, h0: 22.6, h1: 25.2 });
  solidCylinder(g, crown, X, 2.45, 22.4, 25.1);

  // lugs: a slab either side of each strap, its side curving down towards the strap
  const LUG: [number, number][] = [[17.6, 3.1], [21, 2.95], [23.6, 2.45], [25.2, 1.7], [25.8, 0.6], [25.6, -0.8], [24.4, -1.7], [21, -2.3], [17.6, -2.6]];
  const LUG_X = [10.9, 13.5];
  for (const sx of [-1, 1]) {
    for (const sy of [-1, 1]) {
      for (const x of LUG_X) edge.stroke(LUG.map(([y, z]) => v(sx * x, sy * y, z)));
      for (const i of [3, 5]) fine.line(v(sx * LUG_X[0], sy * LUG[i][0], LUG[i][1]), v(sx * LUG_X[1], sy * LUG[i][0], LUG[i][1]));
      const shape = new THREE.Shape(LUG.map(([y, z]) => new THREE.Vector2(y, z)));
      const geo = new THREE.ExtrudeGeometry(shape, { depth: LUG_X[1] - LUG_X[0] - 0.2, bevelEnabled: false, curveSegments: 4 });
      geo.applyMatrix4(new THREE.Matrix4().set(0, 0, sx, sx * (LUG_X[0] + 0.1), sy, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 1));
      solid(g, geo);
    }
  }

  // straps: out from the spring bars between the lugs, then round towards the wrist, which is behind the caseback
  const HALF = 10.4;
  for (const sy of [-1, 1]) {
    const pts: THREE.Vector3[] = [];
    const n: THREE.Vector3[] = [];
    for (let y = 22.6; y < 28.5; y += 1) {
      pts.push(v(0, sy * y, 0.3));
      n.push(v(0, 0, 1));
    }
    for (let a = 0; a <= 125; a += 4) {
      const t = a * DEG;
      pts.push(v(0, sy * (28.5 + 15 * Math.sin(t)), -14.7 + 15 * Math.cos(t)));
      n.push(v(0, sy * Math.sin(t), Math.cos(t)));
    }
    for (const x of [-HALF, HALF]) edge.stroke(pts.map((p) => v(x, p.y, p.z)));
    edge.line(v(-HALF, pts[0].y, pts[0].z), v(HALF, pts[0].y, pts[0].z));
    const half = pts.map(() => HALF);
    ink.strips.push({ node: g, pts, n, across: X, half });
    solidStrip(g, pts, X, half.map((h) => h - 0.12));
  }

  ink.draw(g, edge, "edge");
  ink.draw(g, fine, "fine");
  return g;
}

// ---------------------------------------------------------------------------------------------------------- the charger
/**
 * The charger of D59 in lines, in its own frame: y up from the table, the button towards +z. A round body of 34 by 7 mm,
 * rounded 0.8 mm at the foot and 0.5 mm at the top, with a dish 25.6 mm across and 1.2 mm deep (its edge chamfered 0.4 mm),
 * two spring pins in its floor, the hook in its wall at -z, the latch's slot at +z with the button standing 0.8 mm out of
 * the rim under it, and the USB-C socket at -z. Its body hides the disc where the rim of the dish is in front of it.
 */
function drawCharger(ink: Ink) {
  const g = new THREE.Group();
  const edge = new Pen();
  const fine = new Pen();
  const R = 17;
  const H = 7;
  const DR = 12.8;
  const at = (y: number) => v(0, y, 0);
  edge.arc(at(H), X, Z, R - 0.5).arc(at(0), X, Z, R - 0.8).arc(at(H), X, Z, DR + 0.4).arc(at(DISH), X, Z, DR);
  fine.arc(at(H - 0.5), X, Z, R).arc(at(0.8), X, Z, R).arc(at(H - 0.4), X, Z, DR);
  ink.sides.push({ node: g, c: at(0), axis: Y, u: X, r: R, h0: 0.8, h1: H - 0.5 }, { node: g, c: at(0), axis: Y, u: X, r: DR, h0: DISH, h1: H - 0.4 });
  for (const x of [-9, 9]) fine.arc(v(x, DISH + 0.01, 1), X, Z, 0.75); // the spring pins, under the disc's contacts
  const slot = (x: number, r: number) => v(x, H, Math.sqrt(r * r - x * x));
  for (const x of [-2.2, 2.2]) fine.line(slot(x, DR + 0.4), slot(x, R - 0.5)); // the latch's slot, open through the rim
  const hook = -DR + 0.05;
  fine.stroke([v(-1.5, DISH + 0.15, hook), v(-1.5, DISH + 0.75, hook), v(1.5, DISH + 0.75, hook), v(1.5, DISH + 0.15, hook)], true);
  const usb: THREE.Vector3[] = [];
  for (let i = 0; i <= 40; i++) {
    const a = (i / 40) * TAU;
    const c = Math.cos(a) > 0 ? 3.25 : -3.25;
    usb.push(v(c + 1.2 * Math.cos(a), 2.6 + 1.2 * Math.sin(a), -R + 0.3));
  }
  fine.stroke(usb, true);
  solidCylinder(g, at(0), Y, R - 0.12, 0.1, DISH - 0.1, true);
  solidRing(g, DR + 0.12, R - 0.12, DISH + 0.05, H - 0.1, true);

  // the button: its face 0.8 mm out of the rim, and its sides back to the wall; it moves with the latch
  const button = new THREE.Group();
  const bp = new Pen();
  const wall = Math.sqrt(R * R - 4) - 0.1;
  const face = R + BUTTON;
  const corners: [number, number][] = [[-2, 3.7], [-2, 5.7], [2, 5.7], [2, 3.7]];
  bp.stroke(corners.map(([x, y]) => v(x, y, face)), true);
  for (const [x, y] of corners) bp.line(v(x, y, wall), v(x, y, face));
  ink.draw(button, bp, "edge");
  solidBox(button, v(-1.9, 3.8, wall), v(1.9, 5.6, face - 0.1));
  g.add(button);

  ink.draw(g, edge, "edge");
  ink.draw(g, fine, "fine");
  return { group: g, button };
}

// ------------------------------------------------------------------------------------------------------------- the band
/**
 * The band of D58 in lines, in the frame the page shows it in: standing on its edge, the loop in the xy plane with the
 * holder on its right wall and the buckle at the top right, the width of the strap along z. The strap follows the path of
 * generate_band.py: its inner line (quarter ellipses with flat lengths on top and at the bottom), offset by half the strap,
 * from its end moulded into the holder once round, through the buckle, and back over the holder and over its own start to
 * the hook-and-loop tip, which narrows over its last 9 mm.
 */
function drawBand(ink: Ink) {
  const g = new THREE.Group();
  const edge = new Pen();
  const fine = new Pen();
  const A = 31.5;
  const B = 26.5;
  const FLAT_TOP = 19.5;
  const FLAT_BOTTOM = 9;
  const W = 27.4; // strap
  const T = 1.4;
  const HOOK_T = 0.35;
  const O1 = T / 2;
  const O2 = T + HOOK_T + T / 2;
  const LEN = 245;
  const HOLDER = { L: 38, corner: 7, proud: 1.3, roof: 0.6, push: 4, strapIn: 5, sink: 0.15 };
  const BUCKLE = { depth: 2.6, wall: 0.85, slot: 2.3 };
  // generate_band.py draws the loop with the strap width along y and stands it up; this is its frame turned into the page's
  const LIFT = A + O2 + T / 2;
  const P = (x: number, y: number, z: number) => v(z, LIFT - x, -y);
  const D = (x: number, z: number) => v(z, -x, 0);

  // the inner line, clockwise (seen with z up) from the right end of the flat top
  const quad = (c: number, sx: number, sz: number) =>
    Array.from({ length: 61 }, (_, k) => {
      const t = (Math.PI / 2) * (k / 60);
      return [sx * (c + (A - c) * Math.cos(t)), sz * B * Math.sin(t)] as [number, number];
    });
  const raw: [number, number][] = [
    ...quad(FLAT_TOP, 1, 1).reverse().slice(0, -1),
    ...quad(FLAT_BOTTOM, 1, -1).slice(0, -1),
    ...Array.from({ length: 20 }, (_, k) => [FLAT_BOTTOM - (2 * FLAT_BOTTOM * k) / 20, -B] as [number, number]),
    ...quad(FLAT_BOTTOM, -1, -1).reverse().slice(0, -1),
    ...quad(FLAT_TOP, -1, 1).slice(0, -1),
    ...Array.from({ length: 31 }, (_, k) => [-FLAT_TOP + (2 * FLAT_TOP * k) / 30, B] as [number, number]),
  ];
  const S = [0];
  for (let i = 1; i < raw.length; i++) S.push(S[i - 1] + Math.hypot(raw[i][0] - raw[i - 1][0], raw[i][1] - raw[i - 1][1]));
  const LOOP = S[S.length - 1];
  /** Point of the inner line at arc length s, its outward normal and its tangent. */
  const on = (s: number) => {
    s = ((s % LOOP) + LOOP) % LOOP;
    let i = 1;
    while (i < S.length - 1 && S[i] < s) i++;
    const f = (s - S[i - 1]) / Math.max(S[i] - S[i - 1], 1e-9);
    const x = raw[i - 1][0] + f * (raw[i][0] - raw[i - 1][0]);
    const z = raw[i - 1][1] + f * (raw[i][1] - raw[i - 1][1]);
    const a = raw[Math.max(i - 3, 0)];
    const b = raw[Math.min(i + 2, raw.length - 1)];
    const l = Math.hypot(b[0] - a[0], b[1] - a[1]);
    const tx = (b[0] - a[0]) / l;
    const tz = (b[1] - a[1]) / l;
    return { x, z, nx: -tz, nz: tx, tx, tz };
  };
  const topAt = (x: number) => LOOP - FLAT_TOP + x;
  const hx = HOLDER.L / 2;
  const sStart = topAt(hx - HOLDER.strapIn);
  const sOut = topAt(hx);
  const sBuckle = topAt(-(hx + BUCKLE.depth / 2 - BUCKLE.wall)) + LOOP;
  const sEnd = sStart + LEN;
  const offset = (s: number) =>
    s < sOut
      ? O1 - HOLDER.sink
      : s < sBuckle - 4
        ? O1 - HOLDER.sink * (1 - smooth((s - sOut) / 3))
        : O1 + (O2 - O1) * smooth((s - (sBuckle - 4)) / 4.3);

  // the strap: its two edges, the line across its moulded end and its tip, and outlines where it turns away
  const mid: THREE.Vector3[] = [];
  const n: THREE.Vector3[] = [];
  const half: number[] = [];
  for (let s = sStart; s <= sEnd + 1e-6; s += 0.6) {
    const q = on(s);
    const o = offset(s);
    const k = (s - (sEnd - 9)) / 9;
    mid.push(P(q.x + q.nx * o, 0, q.z + q.nz * o));
    n.push(D(q.nx, q.nz));
    half.push((W / 2) * (k > 0 ? Math.max(Math.sqrt(Math.max(0, 1 - k * k)), 0.06) : 1));
  }
  for (const side of [-1, 1]) edge.stroke(mid.map((p, i) => p.clone().addScaledVector(Z, side * half[i])));
  const last = mid.length - 1;
  for (const i of [0, last]) edge.line(mid[i].clone().addScaledVector(Z, -half[i]), mid[i].clone().addScaledVector(Z, half[i]));
  ink.strips.push({ node: g, pts: mid, n, across: Z, half });
  solidStrip(g, mid, Z, half.map((h) => h - 0.12));

  // the holder: a block of silicone the width of the strap, rounded at the corners, its skin side 1.3 mm short of the
  // disc's skin face, with a hole in its back to push the disc out
  const zTop = B + T + HOOK_T;
  const zSkin = zTop - HOLDER.roof - DISC_H;
  const z0 = zSkin + HOLDER.proud;
  const rounded = (z: number) => {
    const pts: THREE.Vector3[] = [];
    const cx = hx - HOLDER.corner;
    const cy = W / 2 - HOLDER.corner;
    for (const [sx, sy, a0] of [[1, 1, 0], [-1, 1, 90], [-1, -1, 180], [1, -1, 270]] as const) {
      for (let k = 0; k <= 12; k++) {
        const a = (a0 + (90 * k) / 12) * DEG;
        pts.push(P(sx * cx + HOLDER.corner * Math.cos(a), sy * cy + HOLDER.corner * Math.sin(a), z));
      }
    }
    return pts;
  };
  edge.stroke(rounded(z0), true).stroke(rounded(zTop), true);
  fine.arc(P(0, 0, zTop), Y, Z, HOLDER.push);
  const c0 = P(hx - 0.15, W / 2 - 0.15, z0 + 0.1);
  const c1 = P(-hx + 0.15, -W / 2 + 0.15, zTop - 0.1);
  solidBox(g, c0.clone().min(c1), c0.clone().max(c1));

  // the buckle: a steel frame round the strap where it comes back over the holder
  const b = on(sBuckle);
  const oc = O2 - 0.3;
  const bx = b.x + b.nx * oc;
  const bz = b.z + b.nz * oc;
  const bw = W + 0.6 + 2 * BUCKLE.wall;
  const bh = BUCKLE.slot + 2 * BUCKLE.wall;
  const corner = (u: number, w: number, y: number) => P(bx + b.tx * u + b.nx * w, y, bz + b.tz * u + b.nz * w);
  const face: [number, number][] = [[-1.3, -bh / 2], [1.3, -bh / 2], [1.3, bh / 2], [-1.3, bh / 2]];
  for (const y of [-bw / 2, bw / 2]) edge.stroke(face.map(([u, w]) => corner(u, w, y)), true);
  for (const [u, w] of face) edge.line(corner(u, w, -bw / 2), corner(u, w, bw / 2));
  const box = new THREE.BoxGeometry(2.4, bw - 0.2, bh - 0.2);
  box.applyMatrix4(new THREE.Matrix4().makeBasis(D(b.tx, b.tz), v(0, 0, -1), D(b.nx, b.nz)).setPosition(P(bx, 0, bz)));
  solid(g, box);

  ink.draw(g, edge, "edge");
  ink.draw(g, fine, "fine");
  // where the disc sits: its skin face on the inside of the loop, its own +y (towards a watch) out through the holder
  const seat = new THREE.Group();
  seat.position.copy(P(0, 0, zSkin));
  seat.rotation.z = -90 * DEG;
  g.add(seat);
  return { group: g, seat };
}

// -------------------------------------------------------------------------------------------------------------- plates
/** Plate 1: the back of the watch, three quarters on, and the disc coming up to it and onto it along the axis, pad first. */
function caseback(disc: THREE.Object3D): Built {
  const rig = new THREE.Group();
  const ink = new Ink();
  const watch = drawWatch(ink);
  const holder = new THREE.Group();
  holder.add(disc);
  holder.rotation.x = 90 * DEG; // the disc's +y, towards the watch, along the watch's +z, towards the dial
  rig.add(watch, holder);
  // the disc rises from below the picture to just behind the caseback, then goes onto it along the axis, pad first
  const seat = CASEBACK_Z - DISC_H;
  const rise = track([[0.3, -78], [0.7, 0]]);
  const near = track([[0.3, -18], [0.68, -7], [0.88, 0]]);
  const update = (p: number, f: number) => {
    holder.position.y = rise(p);
    holder.position.z = seat + near(p) - 9 * f;
  };
  update(1, 0);
  // Seen from the back the watch's -x is on the right of the picture and its +y up; on the disc (turned onto the watch's
  // axis) the angle 180 is on the right, 270 up and 90 down. The marks go down the right side in the order of the names.
  const anchors = {
    caseback: mark(watch, v(-12.7, 12.7, -3.4)),
    pad: mark(disc, rim(232, 11.45, 3.0)),
    disc: mark(disc, rim(188, 12.5, 1.7)),
    thick: mark(disc, rim(146, 12.1, 0.25)),
  };
  return {
    rig,
    ink,
    fit: 34,
    shift: 0.1,
    narrowShift: 0.2,
    narrowZoom: 0.8,
    anchors,
    update,
    focusable: ["pad", "disc", "thick"],
    pose: { yaw: track([[0, 200], [1, 128]]), tilt: track([[0, 2], [1, 14]]), zoom: track([[0, 0.92], [1, 1]]) },
  };
}

/**
 * Plate 2: the charger seen from above, and the disc coming down into its dish skin face first, its contacts over the pins,
 * until the latch clicks; the camera comes down a little as it goes in. Pointing at the disc, the latch or the button
 * presses the button: the latch draws back and the disc comes up out of the dish.
 */
function charge(disc: THREE.Object3D): Built {
  const rig = new THREE.Group();
  const ink = new Ink();
  const charger = drawCharger(ink);
  const holder = new THREE.Group(); // the disc keeps the charger's frame: its contacts over the pins, its pockets on the hook and the latch
  holder.add(disc);
  rig.add(charger.group, holder);
  rig.position.y = -4.5;
  const drop = track([[0.25, 34], [0.85, 0]]);
  const update = (p: number, f: number) => {
    const press = Math.min(1, f / 0.35);
    const rise = f <= 0.35 ? 0 : (f - 0.35) / 0.65;
    const h = drop(p) + 5 * rise * rise * (3 - 2 * rise);
    holder.position.y = DISH + h;
    // the rim of the disc pushes the latch back as it passes, and the spring snaps it in when the disc is down
    charger.button.position.z = BUTTON * Math.max(press, 1 - Math.abs(h - 0.55) / 0.55, 0);
  };
  update(1, 0);
  // the camera looks down from the side of the button: the top of the disc, the latch's slot, the button, the foot of the body
  const anchors = {
    disc: mark(disc, rim(330, 12.3, DISC_H)),
    latch: mark(charger.group, v(0, 7, 15.2)),
    button: mark(charger.button, v(0, 4.7, 17 + BUTTON)),
    charger: mark(charger.group, v(16.4 * Math.cos(75 * DEG), 0.2, 16.4 * Math.sin(75 * DEG))),
  };
  return {
    rig,
    ink,
    fit: 25,
    shift: 0.19,
    narrowShift: 0.21,
    narrowZoom: 0.82,
    anchors,
    update,
    focusable: ["disc", "latch", "button"],
    pose: { yaw: track([[0, 70], [1, 28]]), tilt: track([[0, 58], [1, 34]]), zoom: track([[0, 0.92], [1, 1]]) },
  };
}

/**
 * Plate 3: the band standing on its edge, and the disc going into its holder from the inside of the loop, skin face last.
 * Pointing at the holder takes the disc part of the way out again.
 */
function band(disc: THREE.Object3D): Built {
  const rig = new THREE.Group();
  const ink = new Ink();
  const drawn = drawBand(ink);
  const holder = new THREE.Group();
  holder.add(disc);
  drawn.seat.add(holder);
  rig.add(drawn.group);
  drawn.group.position.set(-0.9, -33.7, 0);
  const off = track([[0.3, -16], [0.85, 0]]);
  const update = (p: number, f: number) => {
    holder.position.y = off(p) - 9 * f; // along the disc's own axis: from the inside of the loop out into the holder
  };
  update(1, 0);
  // In the band's frame the loop stands in the xy plane, 63 mm wide inside and 53 mm tall, with the holder on its right
  // wall (x = 26 to 28, y = 16 to 54) and the buckle over it; z runs across the strap, +z towards the camera. The marks go
  // down the right side in the order of the names.
  const at = (x: number, y: number, z: number) => mark(drawn.group, v(x, y, z));
  const anchors = {
    buckle: at(29.5, 54.2, 14.2),
    holder: at(25.8, 26, 12.5),
    strap: at(28.6, 11, 13.7),
    hook: at(14, 2.4, 11),
  };
  return {
    rig,
    ink,
    fit: 47,
    shift: 0.15,
    narrowShift: 0.2,
    narrowZoom: 0.86,
    anchors,
    update,
    focusable: ["holder"],
    pose: { yaw: track([[0, 78], [1, 46]]), tilt: track([[0, 6], [1, 12]]), zoom: track([[0, 0.92], [1, 1]]) },
  };
}
