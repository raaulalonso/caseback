// What the 3D scenes of the site share: the renderer, the studio the reflections come from, the materials as they come out
// of Blender (hardware/mechanical/scripts/export_web.py) with their baked occlusion, the models, and the two kinds of motion
// (monotone splines through timed keys, critically damped springs). See components/home/disc3d.ts for why the look costs
// nothing per frame.
import * as THREE from "three";
import { MeshoptDecoder } from "three/addons/libs/meshopt_decoder.module.js";
import { GLTFLoader, type GLTF } from "three/addons/loaders/GLTFLoader.js";

export const DEG = Math.PI / 180;
/** Most device pixels a canvas may have; above this the pixel ratio comes down. */
export const MAX_PIXELS = 2.4e6;
export const GLASS = /window_clear_resin|optical_gel|optical_silicone_clear/;

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

/** A renderer on a transparent canvas, with the studio as its environment and the tone of the site. */
export function createRenderer(canvas: HTMLCanvasElement, scene: THREE.Scene) {
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true, powerPreference: "high-performance" });
  renderer.setClearColor(0x000000, 0);
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.05;
  const pmrem = new THREE.PMREMGenerator(renderer);
  const room = studio();
  const env = pmrem.fromScene(room, 0.02).texture;
  pmrem.dispose();
  room.traverse((o) => {
    if (o instanceof THREE.Mesh) {
      o.geometry.dispose();
      o.material.dispose();
    }
  });
  scene.environment = env;
  // Two lights that stay put while the models turn: a soft key from the upper left for the shading of the faces, and a
  // rim from behind on the right that keeps the outline of black parts on the black page.
  const key = new THREE.DirectionalLight(0xffffff, 0.5);
  key.position.set(-4, 6, 7);
  const back = new THREE.DirectionalLight(0xffffff, 1.6);
  back.position.set(6, 4, -6);
  scene.add(key, back);
  return { renderer, env };
}

/**
 * Compiles the programs a scene will draw with, before it is shown: in parallel where the browser can
 * (KHR_parallel_shader_compile), so the page's thread is not held, and all at once otherwise.
 */
export async function precompile(renderer: THREE.WebGLRenderer, scene: THREE.Scene, camera: THREE.Camera) {
  if (renderer.extensions.has("KHR_parallel_shader_compile")) await renderer.compileAsync(scene, camera);
  else renderer.compile(scene, camera);
}

/** Pixel ratio for a canvas of this size: the screen's, at most `most`, and less if the canvas would pass MAX_PIXELS. */
export const pixelRatio = (width: number, height: number, most = 2) =>
  Math.min(window.devicePixelRatio || 1, most, Math.sqrt(MAX_PIXELS / Math.max(1, width * height)));

/**
 * A material as the site draws it: its own copy (so a part can fade or glow on its own), the web equivalent of its Cycles
 * settings, transparent so it can fade, and the baked occlusion read from the vertex colours when the mesh has them.
 */
export function prepare(m: THREE.MeshStandardMaterial, withOcclusion: boolean) {
  const c = m.clone();
  tune(c);
  c.userData.opacity = c.opacity;
  c.transparent = true;
  // A see-through double-sided material is drawn twice by default, back faces first. Here the parts are solid but for the
  // moments one fades, so one pass is enough and the draws per frame are halved.
  c.forceSinglePass = true;
  if (withOcclusion) {
    c.vertexColors = true;
    c.onBeforeCompile = (sh) => {
      sh.fragmentShader = sh.fragmentShader.replace("#include <color_fragment>", "").replace("#include <aomap_fragment>", AO_GLSL);
    };
    c.customProgramCacheKey = () => "baked-ao";
  }
  return c;
}

/** Every mesh under `root` gets prepared materials; returns them, for the callers that fade or light some of them. */
export function prepareAll(root: THREE.Object3D) {
  const all: THREE.MeshStandardMaterial[] = [];
  root.traverse((o) => {
    if (!(o instanceof THREE.Mesh)) return;
    const occ = o.geometry.hasAttribute("color");
    const list = (Array.isArray(o.material) ? o.material : [o.material]).map((m: THREE.MeshStandardMaterial) => prepare(m, occ));
    all.push(...list);
    o.material = Array.isArray(o.material) ? list : list[0];
  });
  return all;
}

const models = new Map<string, Promise<GLTF>>();
let workers = false;
/** A model from public/models, loaded once for the whole page; callers clone its scene. */
export function loadModel(name: string) {
  let p = models.get(name);
  if (!p) {
    // the compressed buffers are decoded in two workers, so the page's own thread keeps drawing while a model comes in
    if (!workers && typeof Worker !== "undefined") {
      MeshoptDecoder.useWorkers(2);
      workers = true;
    }
    const loader = new GLTFLoader();
    loader.setMeshoptDecoder(MeshoptDecoder);
    p = loader.loadAsync(`/models/${name}.glb`);
    p.catch(() => models.delete(name));
    models.set(name, p);
  }
  return p;
}

/** Frees what a scene holds on the GPU. Geometries are shared between clones of a model, so only materials go. */
export function disposeScene(scene: THREE.Scene, env: THREE.Texture, renderer: THREE.WebGLRenderer) {
  scene.traverse((o) => {
    if (o instanceof THREE.Mesh) (Array.isArray(o.material) ? o.material : [o.material]).forEach((m) => m.dispose());
  });
  env.dispose();
  renderer.dispose();
}

/** A value that follows its target on a critically damped spring: it sets off and arrives with no jerk and no overshoot. */
export type Spring = { x: number; v: number };
export const s0 = (x = 0): Spring => ({ x, v: 0 });

/** Exact step of a critically damped spring of angular frequency `w` (it settles in about 5 / w seconds). */
export function spring(s: Spring, to: number, dt: number, w: number) {
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
export function track(keys: [number, number][]) {
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
