// The disc in 3D. The model is public/models/disc.glb, written by hardware/mechanical/scripts/export_web.py from the
// Blender scene of design 1: millimetres, +Y towards the watch, one node per part in its assembled place, with ambient
// occlusion baked into the vertex colours. When the drawn watch turns over, this is what comes round on the other side:
// the skin face of the disc, engraved like a caseback, shrinking from the size of the watch. The camera then drops while
// the disc opens along its axis into an exploded view, and rises again to rest while the parts close up one by one in
// the order they go in. Times are seconds on the second clock of ./timeline (B).
//
// One rule for the motion: nothing starts or stops with a jerk. The turn is one cubic shared with the SVG dial (the dial
// takes the first half, the disc the second, so the speed is the same either side of edge-on), the camera follows
// monotone splines through a few poses, and what answers the pointer moves on critically damped springs.
//
// What makes it look photographed costs nothing per frame: the occlusion is baked, the studio the reflections come from is
// drawn once into an environment map, there are no shadow maps and no post-processing, and at rest it draws only when
// something moves.
import * as THREE from "three";
import type { Section } from "@/lib/i18n";
import { DEG, GLASS, createRenderer, disposeScene, loadModel, pixelRatio, precompile, prepare, s0, spring, track, type Spring } from "../three/core";
import { CASEBACK_Z, Ink, drawWatch } from "../three/sketch";
import { CANVAS, R_CASE, U_MM, VIEW } from "./geometry";
import { B, easeInOut, easeOut, introAt } from "./timeline";

const R = 12.5; // disc radius, mm
const H = 3.1; // thickness with the pad
const FOV = 20;
/** Camera distance that puts U_MM drawing units in a millimetre on the plane through the middle of the disc. */
const DIST = (VIEW * CANVAS) / U_MM / Math.tan((FOV / 2) * DEG);

/** How far each part stands from its seat in the exploded view (mm, towards the watch), and its step when they close. */
const STACK: Record<string, { lift: number; step: number }> = {
  window: { lift: 3.5, step: 0 },
  contacts: { lift: 3.5, step: 0 },
  board: { lift: 7.5, step: 1 },
  cell: { lift: 11.5, step: 2 },
  gasket: { lift: 15, step: 3 },
  lid: { lift: 18.5, step: 4 },
  pad: { lift: 22.5, step: 5 },
};
const PARTS = Object.keys(STACK).length;
/**
 * "How it's worn": the watch the intro turned into the disc comes back round it, drawn in lines, its caseback on the
 * disc's pad, while the disc comes down to this share of its size so the watch fits inside the lines to the sections.
 */
const WORN_SCALE = 0.62;
/** "The app": the disc turns a little towards its name, down on the right, while the readings go along the line to it. */
const APP_TURN = { yaw: 14, tilt: 8 };
/** How fast each hover answers (angular frequency of its spring): the drawing of "How it's worn" is slower. */
const HOVER_RATE: Record<Section, number> = { wear: 3.6, open: 6, measure: 6, app: 6 };

/**
 * Pose of the disc: yaw about the vertical and tilt about the horizontal, in degrees, and scale. Tilt -180 shows the skin
 * face square on; -180 - (90 - e) shows it from e degrees above. The spin about its own axis stays at 180: name upright.
 */
type Pose = { yaw: number; tilt: number; scale: number };
const SPIN = 180;
const REST: Pose = { yaw: 0, tilt: -215, scale: 1 }; // 55 degrees above
/** "Code and licences" opens the disc at rest, part of the way to the exploded view of the intro. */
const OPENED: Pose = { yaw: -12, tilt: -238, scale: 0.86 };
const OPENED_LIFT = 0.6;
/** Size of the disc when it comes round edge-on: the size of the watch it takes over from. */
const WATCH = R_CASE / (R * U_MM);
const HALF = B.turnDur / 2;

// After the turn the camera drops to 14 degrees above the skin face while the disc opens, low enough to see each layer
// on its own (the cell lies at the back, beside the board), drifts while the exploded view can be read, and rises to rest
// while the parts close. Yaw and scale move with it.
const TILT = track([[HALF + 0.12, -180], [B.open + B.openDur, -256], [B.close, -254], [B.rest, REST.tilt]]);
const YAW = track([[B.turnDur, 0], [B.open + B.openDur + 0.1, -20], [B.close + 0.25, -16], [B.rest, REST.yaw]]);
const SCALE = track([[HALF, WATCH], [B.turnDur + 0.05, 1], [B.open + B.openDur, 0.78], [B.close, 0.78], [B.rest, REST.scale]]);

/** The pose `b` seconds after the watch began to turn. */
function pose(b: number): Pose {
  if (b >= B.rest) return { ...REST };
  // the second half of the turn: edge-on to square on, slowing as the dial's half sped up
  const yaw = b < B.turnDur ? -90 + 90 * easeOut(introAt(b, HALF, HALF)) : YAW(b);
  return { yaw, tilt: TILT(b), scale: SCALE(b) };
}

/** Share 0..1 of its exploded height that a part stands at, `b` seconds after the turn began. */
function apart(b: number, step: number) {
  if (b >= B.rest) return 0;
  const open = easeInOut(introAt(b, B.open, B.openDur));
  const close = easeInOut(introAt(b, B.close + step * B.step, B.drop));
  return open * (1 - close);
}

/** Points the callouts leave from, in a part's own coordinates. Angles go from +x towards +z, seen from the watch side. */
type AnchorDef = { part: string; at: (box: THREE.Box3) => THREE.Vector3 } | { part: string; node: string };
const rim = (deg: number, r: number, y: number) => new THREE.Vector3(r * Math.cos(deg * DEG), y, r * Math.sin(deg * DEG));
const ANCHORS: Record<Section, AnchorDef> = {
  open: { part: "shell", at: () => rim(330, R, 0.3) }, // the edge of the shell, where the disc opens
  wear: { part: "pad", at: (b) => rim(10, b.max.x, b.max.y) }, // edge of the pad, on the watch side
  measure: { part: "window", at: (b) => new THREE.Vector3((b.min.x + b.max.x) / 2, b.min.y, (b.min.z + b.max.z) / 2) },
  app: { part: "board", node: "anchor_antenna" },
};

const GREEN = new THREE.Color("#3ddc84");

type Part = { node: THREE.Object3D; mats: THREE.MeshStandardMaterial[] };

export class Disc3D {
  private renderer: THREE.WebGLRenderer;
  private scene = new THREE.Scene();
  private camera = new THREE.PerspectiveCamera(FOV, 1, DIST / 4, DIST * 4);
  private pivot = new THREE.Group();
  private body = new THREE.Group();
  private parts = new Map<string, Part>();
  private points = new Map<Section, THREE.Object3D>();
  private env: THREE.Texture;
  private hover: Record<Section, Spring> = { wear: s0(), open: s0(), measure: s0(), app: s0() };
  private tiltX = s0();
  private tiltY = s0();
  private leave = s0();
  private target: Section | null = null;
  private aim: { x: number; y: number } | null = null;
  private towards: THREE.Vector3 | null = null;
  private leds: THREE.MeshStandardMaterial[] = [];
  private glass: THREE.MeshStandardMaterial[] = [];
  private ink = new Ink();
  private watch: THREE.Group;
  private css = { w: 1, h: 1 };
  private dirty = true;
  private wasRest = false;
  private size = "";
  private v = new THREE.Vector3();

  private constructor(canvas: HTMLCanvasElement, model: THREE.Object3D) {
    ({ renderer: this.renderer, env: this.env } = createRenderer(canvas, this.scene));

    this.camera.position.set(0, 0, DIST);
    this.camera.lookAt(0, 0, 0);
    this.scene.add(this.pivot);
    this.pivot.add(this.body);
    this.body.add(model);

    for (const name of ["shell", ...Object.keys(STACK)]) {
      const node = model.getObjectByName(name);
      if (!node) throw new Error(`disc.glb has no ${name}`);
      // Each part gets its own materials, so a part can glow on its own.
      const mats: THREE.MeshStandardMaterial[] = [];
      node.traverse((o) => {
        if (!(o instanceof THREE.Mesh)) return;
        const list = (Array.isArray(o.material) ? o.material : [o.material]).map((m: THREE.MeshStandardMaterial) => {
          const c = prepare(m, o.geometry.hasAttribute("color"));
          mats.push(c);
          if (/^led_(green|red|IR)$/.test(c.name)) this.leds.push(c);
          if (GLASS.test(c.name) && name === "window") this.glass.push(c);
          c.depthWrite = c.opacity > 0.98;
          return c;
        });
        o.material = Array.isArray(o.material) ? list : list[0];
      });
      this.parts.set(name, { node, mats });
    }

    model.updateMatrixWorld(true);
    for (const [key, def] of Object.entries(ANCHORS) as [Section, AnchorDef][]) {
      const part = this.parts.get(def.part)!;
      let point: THREE.Object3D | undefined;
      if ("node" in def) point = model.getObjectByName(def.node);
      else {
        const box = new THREE.Box3().setFromObject(part.node);
        point = new THREE.Object3D();
        point.position.copy(part.node.worldToLocal(def.at(box)));
        part.node.add(point);
      }
      if (!point) throw new Error(`disc.glb has no anchor for ${key}`);
      this.points.set(key, point);
    }

    // the watch of "How it's worn", in its own frame (dial towards +z) turned onto the disc's axis: its +z along the
    // disc's +y, its caseback plate on the pad; hidden until the hover draws it
    this.watch = drawWatch(this.ink, false);
    this.watch.rotation.set(-90 * DEG, 0, 0);
    this.watch.position.y = H - CASEBACK_Z;
    this.watch.visible = false;
    this.body.add(this.watch);
    this.scene.add(this.ink.liveLines);
  }

  /** `most`: the pixel ratio to start at (see resize). The disc is drawn once at the canvas's size before it is returned. */
  static async load(canvas: HTMLCanvasElement, most = 2) {
    const gltf = await loadModel("disc");
    const disc = new Disc3D(canvas, gltf.scene.clone(true));
    const r = canvas.getBoundingClientRect();
    if (r.width > 0) disc.resize(r.width, r.height, most);
    await disc.warm();
    return disc;
  }

  /**
   * Everything the first frames would otherwise stop for, done before the disc is handed over: the programs are compiled
   * (in parallel where the browser can) and the exploded view is drawn once, unseen, so every part's buffers are on the
   * GPU. Without it the turn stalls on its first frames, on a phone for a good part of a second.
   */
  private async warm() {
    await precompile(this.renderer, this.scene, this.camera);
    this.frame(B.open + B.openDur, 0, true);
    this.dirty = true;
  }

  setHover(section: Section | null) {
    this.target = section;
    this.dirty = true;
  }

  /** Pointer over the drawing, -1..1 across the drawing box; null when it leaves. */
  setPointer(p: { x: number; y: number } | null) {
    this.aim = p;
    this.dirty = true;
  }

  /** On the way to a section: the camera closes in on the part its line leaves from. */
  goTo(section: Section) {
    this.towards = this.points.get(section)!.getWorldPosition(new THREE.Vector3());
    this.dirty = true;
  }

  /** `most`: the highest pixel ratio to draw at (a phone draws the intro at less, and the disc at rest sharp). */
  resize(width: number, height: number, most = 2) {
    // setting a canvas to the size it has still clears and reallocates it, so an unchanged size is left alone
    const ratio = pixelRatio(width, height, most);
    const key = `${width}x${height}@${ratio}`;
    if (key === this.size) return;
    this.size = key;
    this.renderer.setPixelRatio(ratio);
    this.renderer.setSize(width, height, false);
    this.camera.aspect = width / height;
    this.camera.updateProjectionMatrix();
    this.css = { w: width, h: height };
    this.dirty = true;
  }

  /**
   * Draws the disc `b` seconds after the watch began to turn (Infinity at rest). `dt` is the frame time, for what follows
   * the pointer and the hover; `still` (reduced motion) puts them where they go at once. Returns false when nothing has
   * moved since the last frame, so nothing was drawn.
   */
  frame(b: number, dt: number, still = false) {
    const rest = b >= Math.max(B.rest, B.pulse + B.pulseDur);
    let moving = !rest || this.dirty || !this.wasRest;
    this.dirty = false;
    this.wasRest = rest;
    const step = (sp: Spring, to: number, w: number) => {
      if (still) Object.assign(sp, { x: to, v: 0 });
      else spring(sp, to, dt, w);
      if (sp.x !== to || sp.v !== 0) moving = true;
    };
    for (const s of Object.keys(this.hover) as Section[]) step(this.hover[s], this.target === s ? 1 : 0, HOVER_RATE[s]);
    const aim = rest && this.aim && !still ? this.aim : { x: 0, y: 0 };
    step(this.tiltX, aim.x, 4);
    step(this.tiltY, aim.y, 4);
    step(this.leave, this.towards ? 1 : 0, 7);
    if (!moving) return false;

    const h = Object.fromEntries(Object.entries(this.hover).map(([k, sp]) => [k, clamp01(sp.x)])) as Record<Section, number>;
    const p = pose(b);
    p.yaw += (OPENED.yaw - REST.yaw) * h.open + APP_TURN.yaw * h.app + this.tiltX.x * 6;
    p.tilt += (OPENED.tilt - REST.tilt) * h.open + APP_TURN.tilt * h.app + this.tiltY.x * 4;
    p.scale *= (1 + (OPENED.scale / REST.scale - 1) * h.open) * (1 - (1 - WORN_SCALE) * smooth01(h.wear / 0.7));

    // the parts: apart in the exploded view, and what the hover does to them
    let sum = 0;
    for (const [name, part] of this.parts) {
      const def = STACK[name];
      let lift = 0;
      if (def) {
        lift = def.lift * Math.max(apart(b, def.step), OPENED_LIFT * h.open);
        sum += lift;
      }
      part.node.position.y = lift;
    }

    // The LEDs light once as the disc closes; "What it measures" lights them and the green shows in the window.
    const glow = Math.max(Math.sin(Math.PI * introAt(b, B.pulse, B.pulseDur)), h.measure);
    for (const m of this.leds) {
      m.emissive.copy(m.color);
      m.emissiveIntensity = glow * (m.name === "led_IR" ? 1 : 5);
    }
    for (const m of this.glass) {
      m.emissive.copy(GREEN);
      m.emissiveIntensity = glow * 0.22;
    }

    // The middle of the stack stays in the middle of the drawing: the shell moves up as the parts behind it move away.
    this.body.position.y = -(H / 2 + sum / PARTS);
    this.pivot.quaternion
      .setFromAxisAngle(Y, p.yaw * DEG)
      .multiply(q1.setFromAxisAngle(X, p.tilt * DEG))
      .multiply(q1.setFromAxisAngle(X, 90 * DEG))
      .multiply(q1.setFromAxisAngle(Y, SPIN * DEG));
    const close = clamp01(this.leave.x);
    this.pivot.scale.setScalar(p.scale * (1 + 0.45 * close));
    this.pivot.position.set(0, 0, 0);
    // the part ends up half way to the middle of the drawing: (1 - close / 2) where it was, at 1 + 0.45 close the size
    if (this.towards) this.pivot.position.copy(this.towards).multiplyScalar(-0.95 * close);
    // "How it's worn": the watch draws itself round the disc while the disc comes down in size, and rubs out the other way
    const drawn = smooth01((h.wear - 0.15) / 0.85);
    this.watch.visible = this.ink.liveLines.visible = drawn > 0.002;
    if (this.watch.visible) {
      this.scene.updateMatrixWorld(true);
      this.ink.set(drawn, this.css.w, this.css.h);
      this.ink.update(this.camera.position);
    }
    this.renderer.render(this.scene, this.camera);
    return true;
  }

  /** Where each callout leaves from, in drawing units from the middle of the drawing box. */
  anchors() {
    const out = {} as Record<Section, [number, number]>;
    this.pivot.updateMatrixWorld(true);
    for (const [key, node] of this.points) {
      node.getWorldPosition(this.v).project(this.camera);
      out[key] = [this.v.x * VIEW * CANVAS, -this.v.y * VIEW * CANVAS];
    }
    return out;
  }

  dispose() {
    this.ink.dispose();
    disposeScene(this.scene, this.env, this.renderer);
  }

}

const X = new THREE.Vector3(1, 0, 0);
const Y = new THREE.Vector3(0, 1, 0);
const q1 = new THREE.Quaternion();
const clamp01 = (x: number) => Math.min(1, Math.max(0, x));
const smooth01 = (x: number) => {
  const s = clamp01(x);
  return s * s * (3 - 2 * s);
};
