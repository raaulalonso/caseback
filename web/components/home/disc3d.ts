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
import { MeshoptDecoder } from "three/addons/libs/meshopt_decoder.module.js";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
import type { Section } from "@/lib/i18n";
import { CANVAS, R_CASE, U_MM, VIEW } from "./geometry";
import { B, easeInOut, easeOut, introAt } from "./timeline";

const DEG = Math.PI / 180;
const R = 12.5; // disc radius, mm
const H = 3.1; // thickness with the pad
const FOV = 20;
/** Camera distance that puts U_MM drawing units in a millimetre on the plane through the middle of the disc. */
const DIST = (VIEW * CANVAS) / U_MM / Math.tan((FOV / 2) * DEG);
/** Most device pixels the canvas may have; above this the pixel ratio comes down. */
const MAX_PIXELS = 2.4e6;

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
/** Lifted off the lid ("How it's worn"), the pad stands this far from it. */
const PAD_OFF = 8;
/** Parts that go see-through when the antenna is shown: everything between the skin face and the board. */
const XRAY = ["shell", "window", "contacts"];
const GLASS = /window_clear_resin|optical_gel|optical_silicone_clear/;

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

const LUME = new THREE.Color("#eef24b");
const GREEN = new THREE.Color("#3ddc84");

/** The baked occlusion (red channel of the vertex colour) darkens the light from the studio, as an aoMap would. */
const AO_GLSL = /* glsl */ `
  float ambientOcclusion = mix(1.0, vColor.r, 0.9);
  reflectedLight.indirectDiffuse *= ambientOcclusion;
  reflectedLight.directDiffuse *= mix(1.0, ambientOcclusion, 0.6);
  #if defined( USE_ENVMAP ) && defined( STANDARD )
    float dotNV = saturate( dot( geometryNormal, geometryViewDir ) );
    reflectedLight.indirectSpecular *= computeSpecularOcclusion( dotNV, ambientOcclusion, material.roughness );
  #endif
`;

type Part = { node: THREE.Object3D; mats: THREE.MeshStandardMaterial[] };
/** A value that follows its target on a critically damped spring: it sets off and arrives with no jerk and no overshoot. */
type Spring = { x: number; v: number };

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
  private antenna: THREE.MeshStandardMaterial[] = [];
  private dirty = true;
  private wasRest = false;
  private v = new THREE.Vector3();

  private constructor(canvas: HTMLCanvasElement, model: THREE.Object3D) {
    this.renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true, powerPreference: "high-performance" });
    this.renderer.setClearColor(0x000000, 0);
    this.renderer.toneMapping = THREE.ACESFilmicToneMapping;
    this.renderer.toneMappingExposure = 1.05;
    const pmrem = new THREE.PMREMGenerator(this.renderer);
    const room = studio();
    this.env = pmrem.fromScene(room, 0.02).texture;
    pmrem.dispose();
    room.traverse((o) => {
      if (o instanceof THREE.Mesh) {
        o.geometry.dispose();
        o.material.dispose();
      }
    });
    this.scene.environment = this.env;

    // Two lights that stay put while the disc turns: a soft key from the upper left for the shading of the faces, and a
    // rim from behind on the right that keeps the outline of the black shell on the black page.
    const key = new THREE.DirectionalLight(0xffffff, 0.5);
    key.position.set(-4, 6, 7);
    const back = new THREE.DirectionalLight(0xffffff, 1.6);
    back.position.set(6, 4, -6);
    this.scene.add(key, back);

    this.camera.position.set(0, 0, DIST);
    this.camera.lookAt(0, 0, 0);
    this.scene.add(this.pivot);
    this.pivot.add(this.body);
    this.body.add(model);

    for (const name of ["shell", ...Object.keys(STACK)]) {
      const node = model.getObjectByName(name);
      if (!node) throw new Error(`disc.glb has no ${name}`);
      // Each part gets its own materials, so a part can go see-through on its own.
      const mats: THREE.MeshStandardMaterial[] = [];
      node.traverse((o) => {
        if (!(o instanceof THREE.Mesh)) return;
        const list = (Array.isArray(o.material) ? o.material : [o.material]).map((m: THREE.MeshStandardMaterial) => {
          const c = m.clone();
          tune(c);
          c.userData.opacity = c.opacity;
          c.transparent = true;
          if (o.geometry.hasAttribute("color")) {
            c.vertexColors = true;
            c.onBeforeCompile = (sh) => {
              sh.fragmentShader = sh.fragmentShader
                .replace("#include <color_fragment>", "")
                .replace("#include <aomap_fragment>", AO_GLSL);
            };
            c.customProgramCacheKey = () => "baked-ao";
          }
          mats.push(c);
          if (/^led_(green|red|IR)$/.test(c.name)) this.leds.push(c);
          if (GLASS.test(c.name) && name === "window") this.glass.push(c);
          if (c.name === "ceramic_antenna") this.antenna.push(c);
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
  }

  static async load(canvas: HTMLCanvasElement, url: string) {
    const loader = new GLTFLoader();
    loader.setMeshoptDecoder(MeshoptDecoder);
    const gltf = await loader.loadAsync(url);
    return new Disc3D(canvas, gltf.scene);
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

  resize(width: number, height: number) {
    const ratio = Math.min(window.devicePixelRatio || 1, 2, Math.sqrt(MAX_PIXELS / (width * height)));
    this.renderer.setPixelRatio(ratio);
    this.renderer.setSize(width, height, false);
    this.camera.aspect = width / height;
    this.camera.updateProjectionMatrix();
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
    for (const s of Object.keys(this.hover) as Section[]) step(this.hover[s], this.target === s ? 1 : 0, 9);
    const aim = rest && this.aim && !still ? this.aim : { x: 0, y: 0 };
    step(this.tiltX, aim.x, 4);
    step(this.tiltY, aim.y, 4);
    step(this.leave, this.towards ? 1 : 0, 7);
    if (!moving) return false;

    const h = Object.fromEntries(Object.entries(this.hover).map(([k, sp]) => [k, clamp01(sp.x)])) as Record<Section, number>;
    const p = pose(b);
    p.yaw += (OPENED.yaw - REST.yaw) * h.open + this.tiltX.x * 6;
    p.tilt += (OPENED.tilt - REST.tilt) * h.open + this.tiltY.x * 4;
    p.scale *= 1 + (OPENED.scale / REST.scale - 1) * h.open;

    // the parts: apart in the exploded view, and what the hover does to them
    let sum = 0;
    for (const [name, part] of this.parts) {
      const def = STACK[name];
      let lift = 0;
      if (def) {
        lift = def.lift * Math.max(apart(b, def.step), OPENED_LIFT * h.open);
        sum += lift;
        if (name === "pad") lift += PAD_OFF * h.wear;
      }
      part.node.position.y = lift;
      const xray = XRAY.includes(name) ? 1 - 0.82 * h.app : 1;
      for (const m of part.mats) {
        m.opacity = m.userData.opacity * xray;
        m.depthWrite = m.opacity > 0.98;
      }
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
    for (const m of this.antenna) {
      m.emissive.copy(LUME);
      m.emissiveIntensity = h.app * 1.4;
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
    this.scene.traverse((o) => {
      if (o instanceof THREE.Mesh) {
        o.geometry.dispose();
        (Array.isArray(o.material) ? o.material : [o.material]).forEach((m) => m.dispose());
      }
    });
    this.env.dispose();
    this.renderer.dispose();
  }
}

const X = new THREE.Vector3(1, 0, 0);
const Y = new THREE.Vector3(0, 1, 0);
const q1 = new THREE.Quaternion();
const clamp01 = (x: number) => Math.min(1, Math.max(0, x));
const s0 = (): Spring => ({ x: 0, v: 0 });

/** Exact step of a critically damped spring of angular frequency `w` (it settles in about 5 / w seconds). */
function spring(s: Spring, to: number, dt: number, w: number) {
  const d = s.x - to;
  const e = Math.exp(-w * dt);
  const c = s.v + w * d;
  const x = (d + c * dt) * e;
  const v = (s.v - c * w * dt) * e;
  if (Math.abs(x) < 1e-4 && Math.abs(v) < 1e-3) Object.assign(s, { x: to, v: 0 });
  else Object.assign(s, { x: to + x, v });
}

/**
 * A value through timed keys on a monotone cubic (Fritsch–Butland tangents): it passes every key without overshooting,
 * keeps its speed through the keys between, and starts and ends at rest.
 */
function track(keys: [number, number][]) {
  const n = keys.length;
  const m = keys.map((_, i) => {
    if (i === 0 || i === n - 1) return 0;
    const [t0, v0] = keys[i - 1];
    const [t1, v1] = keys[i];
    const [t2, v2] = keys[i + 1];
    const h0 = t1 - t0;
    const h1 = t2 - t1;
    const d0 = (v1 - v0) / h0;
    const d1 = (v2 - v1) / h1;
    if (d0 * d1 <= 0) return 0;
    return (3 * (h0 + h1)) / ((2 * h1 + h0) / d0 + (h1 + 2 * h0) / d1);
  });
  return (t: number) => {
    if (t <= keys[0][0]) return keys[0][1];
    if (t >= keys[n - 1][0]) return keys[n - 1][1];
    let i = 0;
    while (t > keys[i + 1][0]) i++;
    const [t0, v0] = keys[i];
    const [t1, v1] = keys[i + 1];
    const h = t1 - t0;
    const s = (t - t0) / h;
    const s2 = s * s;
    const s3 = s2 * s;
    return (2 * s3 - 3 * s2 + 1) * v0 + (s3 - 2 * s2 + s) * h * m[i] + (-2 * s3 + 3 * s2) * v1 + (s3 - s2) * h * m[i + 1];
  };
}

/**
 * The studio the reflections come from, after the one of the app's watch (tools/watch3d/build_watch.py): a big soft box
 * above and to the left, a strip on the right and one behind and above for the far edge, a soft fill and a ring light
 * round the camera, in a dark room with a darker floor. The faces of the disc pick up the edge of the soft box as a
 * gradient; the rounded rim picks up the ring as a thin bright circle, so the disc comes round with the line of the watch
 * case still on it.
 */
function studio() {
  const room = new THREE.Scene();
  const shell = new THREE.Mesh(
    new THREE.SphereGeometry(20, 32, 16),
    new THREE.ShaderMaterial({
      side: THREE.BackSide,
      vertexShader: "varying vec3 d; void main() { d = normalize(position); gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }",
      fragmentShader:
        "varying vec3 d; void main() { float s = 0.004 + 0.03 * pow(clamp(d.y * 0.5 + 0.5, 0.0, 1.0), 2.0); gl_FragColor = vec4(vec3(d.y < -0.05 ? s * 0.3 : s), 1.0); }",
    }),
  );
  room.add(shell);
  const box = (dir: [number, number, number], w: number, h: number, power: number) => {
    const m = new THREE.Mesh(new THREE.PlaneGeometry(w, h), new THREE.MeshBasicMaterial({ color: new THREE.Color().setScalar(power), side: THREE.DoubleSide }));
    m.position.set(...dir).normalize().multiplyScalar(12);
    m.lookAt(0, 0, 0);
    room.add(m);
  };
  box([-0.6, 0.75, 0.45], 10, 7, 5); // key
  box([0.95, 0.15, 0.3], 1.6, 12, 4); // strip on the right
  box([0.1, 0.55, -0.85], 14, 1.2, 6); // strip behind and above
  box([0.1, -0.3, 1], 14, 5, 0.8); // soft fill from the front, low
  const ring = new THREE.Mesh(new THREE.TorusGeometry(7.5, 0.35, 12, 96), new THREE.MeshBasicMaterial({ color: new THREE.Color().setScalar(3) }));
  ring.position.set(0, 0, 11); // round the camera, about 34 degrees off its axis
  room.add(ring);
  return room;
}

/** The Blender materials are made for Cycles; a few need their web equivalent. */
function tune(m: THREE.MeshStandardMaterial) {
  if (m.name.startsWith("PEEK")) m.roughness = 0.42; // bead-blasted black PEEK: dark, with a satin sheen
  if (m.name === "silicone_pad") m.color.multiplyScalar(0.6);
  // No transmission pass (it would draw the scene twice a frame): what Cycles sees through is drawn see-through instead.
  const p = m as THREE.MeshPhysicalMaterial;
  if (p.transmission > 0) {
    m.opacity = 1 - 0.6 * p.transmission;
    p.transmission = 0;
  }
  if (GLASS.test(m.name)) {
    m.color.setScalar(0.04);
    m.opacity = 0.35;
    m.roughness = 0.05;
  }
}
