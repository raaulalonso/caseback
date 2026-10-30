// The line drawing that the 3D disc of "How it's worn" sits in: the watch, the charger and the band are drawn as lines, in
// the scene and with the camera of the disc, so they turn with it. The disc is the only part shown as a model.
//
// Hidden lines are left out as in a technical drawing. Each drawn body also has an invisible stand-in (a "solid") that
// writes depth and no colour, so lines behind it fail the depth test; the disc writes depth as it draws, so lines behind
// it go too. Draw order: the disc first, then the solids, then the lines. The solids come after the disc, so they hide
// lines and never the disc: the drawing is see-through where the disc is behind it, as a cut-away would be.
//
// A curved side has no edge to draw where it turns away from the eye, so those outlines (Side) are worked out each frame
// from where the camera is. Each stroke is measured from 0 at its start to 1 at its end, so the whole drawing can grow
// along its strokes at once (the dash of the line material is the share drawn).
import * as THREE from "three";
import { LineMaterial } from "three/addons/lines/LineMaterial.js";
import { LineSegments2 } from "three/addons/lines/LineSegments2.js";
import { LineSegmentsGeometry } from "three/addons/lines/LineSegmentsGeometry.js";

export const TAU = Math.PI * 2;
export const v = (x: number, y: number, z: number) => new THREE.Vector3(x, y, z);
export const X = v(1, 0, 0);
export const Y = v(0, 1, 0);
export const Z = v(0, 0, 1);

/** Order of drawing within the scene (see the top of the file). */
const ORDER = { solid: 1, line: 2 };

/** Strokes in the frame of the node they will be added to. */
export class Pen {
  readonly pos: number[] = [];
  readonly dist: number[] = [];

  /** A polyline; `closed` joins the last point to the first. */
  stroke(pts: THREE.Vector3[], closed = false) {
    const p = closed ? [...pts, pts[0]] : pts;
    let total = 0;
    for (let i = 1; i < p.length; i++) total += p[i].distanceTo(p[i - 1]);
    if (total === 0) return this;
    let d = 0;
    for (let i = 1; i < p.length; i++) {
      const a = p[i - 1];
      const b = p[i];
      const l = a.distanceTo(b);
      this.pos.push(a.x, a.y, a.z, b.x, b.y, b.z);
      this.dist.push(d / total, (d + l) / total);
      d += l;
    }
    return this;
  }

  line(a: THREE.Vector3, b: THREE.Vector3) {
    return this.stroke([a, b]);
  }

  /** An arc about `c` in the plane of the unit vectors `u` (angle 0) and `w` (angle 90 degrees), angles in radians. */
  arc(c: THREE.Vector3, u: THREE.Vector3, w: THREE.Vector3, r: number, a0 = 0, a1 = TAU) {
    return this.stroke(arcPoints(c, u, w, r, a0, a1));
  }
}

export function arcPoints(c: THREE.Vector3, u: THREE.Vector3, w: THREE.Vector3, r: number, a0 = 0, a1 = TAU) {
  const n = Math.max(6, Math.ceil((Math.abs(a1 - a0) / TAU) * 128));
  const pts: THREE.Vector3[] = [];
  for (let i = 0; i <= n; i++) {
    const a = a0 + ((a1 - a0) * i) / n;
    pts.push(c.clone().addScaledVector(u, r * Math.cos(a)).addScaledVector(w, r * Math.sin(a)));
  }
  return pts;
}

/**
 * A round side whose outline is drawn each frame: the surface of radius `r` about the axis through `c` along the unit
 * vector `axis`, from `h0` to `h1` along it, in the frame of `node`. `u` is any unit vector across the axis.
 */
export type Side = { node: THREE.Object3D; c: THREE.Vector3; axis: THREE.Vector3; u: THREE.Vector3; r: number; h0: number; h1: number };

/**
 * Lines across a strip where it turns away from the eye: `pts` along its middle, `n` the normal of its face at each point,
 * `across` the unit vector along its width and `half` its half width at each point, in the frame of `node`.
 */
export type Strip = { node: THREE.Object3D; pts: THREE.Vector3[]; n: THREE.Vector3[]; across: THREE.Vector3; half: number[] };

/** The two tones of the drawing: outlines, and the detail inside them. */
export type Tone = "edge" | "fine";
const TONES: Record<Tone, { opacity: number; width: number }> = {
  edge: { opacity: 0.78, width: 1.25 },
  fine: { opacity: 0.42, width: 1 },
};

/** The materials of one drawing and the lines worked out each frame. */
export class Ink {
  private grow: Record<Tone, LineMaterial>;
  private live: LineMaterial;
  private liveGeometry = new LineSegmentsGeometry();
  readonly liveLines: LineSegments2;
  readonly sides: Side[] = [];
  readonly strips: Strip[] = [];
  private eye = new THREE.Vector3();
  private a = new THREE.Vector3();
  private b = new THREE.Vector3();

  constructor() {
    const make = (tone: Tone, dashed: boolean) =>
      new LineMaterial({
        color: 0xffffff,
        opacity: TONES[tone].opacity,
        linewidth: TONES[tone].width,
        transparent: true,
        depthWrite: false,
        dashed,
        dashSize: 1,
        gapSize: 4,
        toneMapped: false,
      });
    this.grow = { edge: make("edge", true), fine: make("fine", true) };
    this.live = make("edge", false);
    this.liveLines = new LineSegments2(this.liveGeometry, this.live);
    this.liveLines.renderOrder = ORDER.line;
    this.liveLines.frustumCulled = false;
  }

  /** Adds the pen's strokes to `node`. */
  draw(node: THREE.Object3D, pen: Pen, tone: Tone) {
    if (!pen.pos.length) return;
    const g = new LineSegmentsGeometry();
    g.setPositions(pen.pos);
    const buf = new THREE.InstancedInterleavedBuffer(new Float32Array(pen.dist), 2, 1);
    g.setAttribute("instanceDistanceStart", new THREE.InterleavedBufferAttribute(buf, 1, 0));
    g.setAttribute("instanceDistanceEnd", new THREE.InterleavedBufferAttribute(buf, 1, 1));
    const lines = new LineSegments2(g, this.grow[tone]);
    lines.renderOrder = ORDER.line;
    node.add(lines);
  }

  /** `drawn`: the share of each stroke drawn (0..1); the size of the canvas in CSS pixels, which line widths are in. */
  set(drawn: number, width: number, height: number) {
    for (const m of [this.grow.edge, this.grow.fine, this.live]) m.resolution.set(width, height);
    const d = drawn >= 1 ? 1.001 : drawn;
    this.grow.edge.dashSize = this.grow.fine.dashSize = d;
    this.live.opacity = TONES.edge.opacity * Math.min(1, Math.max(0, (drawn - 0.5) / 0.5));
  }

  /** Works out the outlines of the round sides and strips for the camera at `eye` (world); the scene's matrices are current. */
  update(eye: THREE.Vector3) {
    const out: number[] = [];
    for (const s of this.sides) {
      this.eye.copy(eye);
      s.node.worldToLocal(this.eye).sub(s.c);
      const w = this.a.crossVectors(s.axis, s.u);
      const eu = this.eye.dot(s.u);
      const ew = this.eye.dot(w);
      const rho = Math.hypot(eu, ew);
      if (rho <= s.r) continue;
      const phi = Math.atan2(ew, eu);
      const delta = Math.acos(s.r / rho);
      for (const t of [phi - delta, phi + delta]) {
        const p = s.c.clone().addScaledVector(s.u, s.r * Math.cos(t)).addScaledVector(w, s.r * Math.sin(t));
        const p0 = s.node.localToWorld(p.clone().addScaledVector(s.axis, s.h0));
        const p1 = s.node.localToWorld(p.addScaledVector(s.axis, s.h1));
        out.push(p0.x, p0.y, p0.z, p1.x, p1.y, p1.z);
      }
    }
    for (const s of this.strips) {
      this.eye.copy(eye);
      s.node.worldToLocal(this.eye);
      let prev = 0;
      for (let i = 0; i < s.pts.length; i++) {
        const f = s.n[i].dot(this.a.subVectors(s.pts[i], this.eye));
        if (i > 0 && Math.sign(f) !== Math.sign(prev)) {
          const k = prev / (prev - f);
          const p = s.pts[i - 1].clone().lerp(s.pts[i], k);
          const h = s.half[i - 1] + (s.half[i] - s.half[i - 1]) * k;
          const p0 = s.node.localToWorld(this.b.copy(p).addScaledVector(s.across, -h));
          out.push(p0.x, p0.y, p0.z);
          const p1 = s.node.localToWorld(p.addScaledVector(s.across, h));
          out.push(p1.x, p1.y, p1.z);
        }
        prev = f;
      }
    }
    // a geometry needs at least one segment; a segment of no length draws nothing
    this.liveGeometry.setPositions(out.length ? out : [0, 0, 0, 0, 0, 0]);
  }

  dispose() {
    this.grow.edge.dispose();
    this.grow.fine.dispose();
    this.live.dispose();
    this.liveGeometry.dispose();
  }
}

/** Writes depth and no colour, after the disc and before the lines; set back a little so lines on its faces stay in front. */
const HIDE = new THREE.MeshBasicMaterial({
  colorWrite: false,
  transparent: true,
  side: THREE.DoubleSide,
  polygonOffset: true,
  polygonOffsetFactor: 2,
  polygonOffsetUnits: 2,
});

/** An invisible stand-in for a drawn body, in the frame of `node`. */
export function solid(node: THREE.Object3D, geometry: THREE.BufferGeometry) {
  const m = new THREE.Mesh(geometry, HIDE);
  m.renderOrder = ORDER.solid;
  node.add(m);
  return m;
}

/** A solid cylinder about the axis through `c` along `axis` (unit), from `h0` to `h1` along it. */
export function solidCylinder(node: THREE.Object3D, c: THREE.Vector3, axis: THREE.Vector3, r: number, h0: number, h1: number) {
  const g = new THREE.CylinderGeometry(r, r, h1 - h0, 48);
  g.applyQuaternion(new THREE.Quaternion().setFromUnitVectors(Y, axis));
  g.translate(c.x + axis.x * ((h0 + h1) / 2), c.y + axis.y * ((h0 + h1) / 2), c.z + axis.z * ((h0 + h1) / 2));
  return solid(node, g);
}

/** A solid strip along `pts`, `half` wide either side along `across` at each point. */
export function solidStrip(node: THREE.Object3D, pts: THREE.Vector3[], across: THREE.Vector3, half: number[]) {
  const pos: number[] = [];
  const index: number[] = [];
  pts.forEach((p, i) => {
    pos.push(p.x - across.x * half[i], p.y - across.y * half[i], p.z - across.z * half[i]);
    pos.push(p.x + across.x * half[i], p.y + across.y * half[i], p.z + across.z * half[i]);
    if (i > 0) index.push(2 * i - 2, 2 * i - 1, 2 * i, 2 * i - 1, 2 * i + 1, 2 * i);
  });
  const g = new THREE.BufferGeometry();
  g.setAttribute("position", new THREE.Float32BufferAttribute(pos, 3));
  g.setIndex(index);
  return solid(node, g);
}

/** A solid box between two corners, in the frame of `node`. */
export function solidBox(node: THREE.Object3D, min: THREE.Vector3, max: THREE.Vector3) {
  const g = new THREE.BoxGeometry(max.x - min.x, max.y - min.y, max.z - min.z);
  g.translate((min.x + max.x) / 2, (min.y + max.y) / 2, (min.z + max.z) / 2);
  return solid(node, g);
}

/** A solid ring of rectangular section about the axis +Y: radii r0 to r1, heights y0 to y1. */
export function solidRing(node: THREE.Object3D, r0: number, r1: number, y0: number, y1: number) {
  const profile = [new THREE.Vector2(r0, y0), new THREE.Vector2(r1, y0), new THREE.Vector2(r1, y1), new THREE.Vector2(r0, y1), new THREE.Vector2(r0, y0)];
  return solid(node, new THREE.LatheGeometry(profile, 64));
}
