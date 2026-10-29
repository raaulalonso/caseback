"""The real V0.1 board in Blender: the KiCad board itself plus a model of every part on it (Blender 4.x / 5.x).

The copper, the vias, the pads, the solder mask, the silkscreen and the board body come from KiCad's own export of
`hardware/v1-pcb/kicad/caseback_v01.kicad_pcb` (`kicad-cli pcb export glb`), so every track and every via on the model is
the one in the file. The parts are built here from the pads of the placed footprints (`kicad/placement_v01.json`, written
by `kicad/tools/dump_footprints.py`): the pads fix the position, the turn and the pin 1 corner of each part, the body sizes
come from the footprint names and the datasheets. They are models of the packages, not CAD files from the makers.

Units: millimetres. Z = 0 is the skin face of the disc, the board's skin-side face is at B.PCB_Z0.
"""

from __future__ import annotations

import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
from math import atan2, cos, degrees, pi, radians, sin

import bmesh
import bpy
from mathutils import Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..", "v1-pcb")))
import board_v01 as B  # noqa: E402
import generate_v1 as g  # noqa: E402

KICAD_DIR = os.path.abspath(os.path.join(HERE, "..", "..", "v1-pcb", "kicad"))
BOARD_FILE = os.path.join(KICAD_DIR, "caseback_v01.kicad_pcb")
PLACEMENT = os.path.join(KICAD_DIR, "placement_v01.json")
GLB_SHIFT = 1.50              # the exported board has its skin-side solder mask at z = -0.05; the disc has it at B.PCB_Z0 = 1.45
Z_SEAT = B.PCB_Z0 + 0.01      # height of the face of a skin-side pad: the parts hang from here


def kicad_cli() -> str:
    for c in (os.environ.get("KICAD_CLI"), os.path.expanduser("~/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli"),
              "/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli", shutil.which("kicad-cli")):
        if c and os.path.exists(c):
            return c
    raise RuntimeError("kicad-cli not found: install KiCad 10 or set KICAD_CLI")


def kicad_python() -> str:
    for c in (os.environ.get("KICAD_PY"), os.path.expanduser("~/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3"),
              "/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3"):
        if c and os.path.exists(c):
            return c
    raise RuntimeError("KiCad's Python not found: set KICAD_PY")


def export_glb(path: str) -> None:
    """The board as KiCad sees it, without parts: copper, vias (filled and capped), pads, mask, silkscreen, body.

    The export is made from a copy whose outline arc is cut into short lines (tools/densify_outline.py), because KiCad
    draws an arc in segments of about 1.5 mm and a 28 mm board then looks like a polygon."""
    work = tempfile.mkdtemp(prefix="caseback_glb_")
    dense = os.path.join(work, "caseback_v01.kicad_pcb")
    subprocess.run([kicad_python(), "-I", os.path.join(KICAD_DIR, "tools", "densify_outline.py"), BOARD_FILE, dense],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run([kicad_cli(), "pcb", "export", "glb", "--include-tracks", "--include-pads", "--include-zones",
                    "--include-inner-copper", "--include-silkscreen", "--include-soldermask", "--no-components",
                    "--fill-all-vias", "--user-origin", "0x0mm", "-f", "-o", path, dense],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    shutil.rmtree(work, ignore_errors=True)


# ------------------------------------------------------------------ materials
def materials(M: dict) -> None:
    mk = g.make_mat
    M["mask"] = mk("solder_mask_green", (0.005, 0.075, 0.028), rough=0.34, alpha=0.62)
    M["fr4"] = mk("fr4_edge", (0.10, 0.12, 0.055), rough=0.75)
    M["copper_t"] = mk("copper_under_mask", (0.96, 0.56, 0.34), metallic=1.0, rough=0.34)
    M["enig"] = mk("ENIG_gold", (1.0, 0.76, 0.34), metallic=1.0, rough=0.26)
    M["silk"] = mk("silkscreen_white", (0.86, 0.86, 0.83), rough=0.55)
    M["tin"] = mk("solder_SAC305", (0.66, 0.67, 0.69), metallic=1.0, rough=0.40)
    M["tin_dull"] = mk("tin_plating", (0.58, 0.59, 0.61), metallic=1.0, rough=0.42)
    M["mold"] = mk("mold_compound_black", (0.011, 0.011, 0.013), rough=0.46)
    M["mold_ink"] = mk("package_mark_grey", (0.30, 0.30, 0.31), rough=0.6)
    M["die"] = mk("silicon_die_backside", (0.018, 0.019, 0.024), metallic=0.3, rough=0.22)
    M["alumina"] = mk("resistor_alumina", (0.74, 0.72, 0.66), rough=0.55)
    M["mlcc_body"] = mk("mlcc_ceramic", (0.34, 0.20, 0.09), rough=0.42)
    M["res_top"] = mk("resistor_overglaze", (0.016, 0.016, 0.018), rough=0.38)
    M["shield"] = mk("shield_can_stainless", (0.62, 0.63, 0.66), metallic=1.0, rough=0.34)
    M["module_mold"] = mk("module_overmold", (0.010, 0.010, 0.012), rough=0.5)
    M["module_sub"] = mk("module_substrate", (0.020, 0.032, 0.040), rough=0.5)
    M["antenna"] = mk("ceramic_antenna", (0.62, 0.50, 0.32), rough=0.45)
    M["clear"] = mk("optical_silicone_clear", (0.88, 0.92, 0.90), rough=0.06, transmission=0.94, ior=1.41)
    M["wire"] = mk("bond_wire_gold", (1.0, 0.78, 0.36), metallic=1.0, rough=0.2)
    M["pouch"] = mk("pouch_film_silver", (0.60, 0.62, 0.65), metallic=0.85, rough=0.38)
    M["pouch_seal"] = mk("pouch_seal_matt", (0.42, 0.44, 0.47), metallic=0.6, rough=0.55)
    M["kapton"] = mk("polyimide_tape", (0.62, 0.34, 0.06), rough=0.3, alpha=0.9)
    M["nickel"] = mk("nickel_tab", (0.55, 0.56, 0.58), metallic=1.0, rough=0.3)
    M["spring_plate"] = mk("spring_contact_gold", (0.98, 0.74, 0.30), metallic=1.0, rough=0.27)


# ------------------------------------------------------------------ small mesh helpers
def rbox(bm, size, center, bevel=0.0, seg=2, rot=0.0):
    """Box with rounded edges. size and center in the world frame, rot about Z in degrees."""
    m = Matrix.Translation(center) @ Matrix.Rotation(radians(rot), 4, "Z") @ Matrix.Diagonal((*size, 1.0))
    r = bmesh.ops.create_cube(bm, size=1.0, matrix=m)
    if bevel > 0:
        edges = {e for v in r["verts"] for e in v.link_edges}
        bmesh.ops.bevel(bm, geom=list(edges), offset=min(bevel, min(size) * 0.45), segments=seg, affect="EDGES")


def blob(bm, center, radii, seg=10, ring=6):
    """A squashed sphere, used for solder fillets and balls."""
    m = Matrix.Translation(center) @ Matrix.Diagonal((*radii, 1.0))
    bmesh.ops.create_uvsphere(bm, u_segments=seg, v_segments=ring, radius=1.0, matrix=m)


def sphere(bm, center, r, seg=14):
    bmesh.ops.create_uvsphere(bm, u_segments=seg, v_segments=max(6, seg // 2), radius=r, matrix=Matrix.Translation(center))


def tube(bm, pts, r, seg=6):
    """A thin round wire along a polyline."""
    for a, b in zip(pts, pts[1:]):
        d = Vector(b) - Vector(a)
        if d.length < 1e-6:
            continue
        mid = (Vector(a) + Vector(b)) / 2
        rot = d.to_track_quat("Z", "Y").to_matrix().to_4x4()
        bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=seg, radius1=r, radius2=r, depth=d.length,
                              matrix=Matrix.Translation(mid) @ rot)


def sweep(bm, profile, width, thick, x0=0.0, y0=0.0, ang=0.0):
    """A strip of sheet metal: `profile` is a polyline of (u, z) points, `width` runs along v, `thick` is the sheet."""
    ca, sa = cos(radians(ang)), sin(radians(ang))

    def w(u, v, z):
        return (x0 + u * ca - v * sa, y0 + u * sa + v * ca, z)

    rings = []
    n = len(profile)
    for i, (u, z) in enumerate(profile):
        a = profile[max(i - 1, 0)]
        b = profile[min(i + 1, n - 1)]
        du, dz = b[0] - a[0], b[1] - a[1]
        L = math.hypot(du, dz) or 1.0
        nu, nz = -dz / L, du / L                      # normal in the (u, z) plane
        t = thick / 2
        ring = [bm.verts.new(w(u + nu * t, -width / 2, z + nz * t)), bm.verts.new(w(u + nu * t, width / 2, z + nz * t)),
                bm.verts.new(w(u - nu * t, width / 2, z - nz * t)), bm.verts.new(w(u - nu * t, -width / 2, z - nz * t))]
        rings.append(ring)
    for r0, r1 in zip(rings, rings[1:]):
        for k in range(4):
            bm.faces.new((r0[k], r0[(k + 1) % 4], r1[(k + 1) % 4], r1[k]))
    bm.faces.new(rings[0])
    bm.faces.new(list(reversed(rings[-1])))


def text_mesh(body, size, x, y, z, rot=0.0, extrude=0.01, mirror=False):
    """Letters as a mesh, centred on (x, y), lying flat. mirror=True for a face that is read from -Z (the skin side)."""
    cu = bpy.data.curves.new("txt", "FONT")
    cu.body, cu.size, cu.align_x, cu.align_y, cu.extrude = body, size, "CENTER", "CENTER", extrude
    cu.resolution_u = 8
    tmp = bpy.data.objects.new("txt", cu)
    g.collection(g.COLL_ASM).objects.link(tmp)
    bpy.context.view_layer.update()
    me = bpy.data.meshes.new_from_object(tmp.evaluated_get(bpy.context.evaluated_depsgraph_get()))
    bpy.data.objects.remove(tmp, do_unlink=True)
    bpy.data.curves.remove(cu)
    flip = Matrix.Diagonal((-1.0, 1.0, 1.0, 1.0)) if mirror else Matrix.Identity(4)
    me.transform(Matrix.Translation((x, y, z)) @ Matrix.Rotation(radians(rot), 4, "Z") @ flip)
    if mirror:
        me.flip_normals()
    return me


# ------------------------------------------------------------------ parts
class Bag:
    """Meshes collected by material key, turned into one object per key at the end."""

    def __init__(self):
        self.bms: dict[str, bmesh.types.BMesh] = {}

    def __getitem__(self, key):
        if key not in self.bms:
            self.bms[key] = g.new_bm()
        return self.bms[key]

    def __setitem__(self, key, value):
        self.bms[key] = value


def pad_axis(pads):
    (x1, y1), (x2, y2) = (pads[0]["x"], pads[0]["y"]), (pads[1]["x"], pads[1]["y"])
    return (x1 + x2) / 2, (y1 + y2) / 2, degrees(atan2(y2 - y1, x2 - x1))


def fillet(bag, pad, h=0.16, grow=1.0, key="tin"):
    """Solder over a pad: a flattened lump on the pad, rising towards the part."""
    h = h * 0.55
    blob(bag[key], (pad["x"], pad["y"], Z_SEAT - h * 0.30), (max(pad["w"], 0.1) * 0.5 * grow, max(pad["h"], 0.1) * 0.5 * grow, h), 14, 7)


def passive(bag, f, ref):
    pads = sorted((p for p in f["pads"]), key=lambda p: p["n"])
    cx, cy, ang = pad_axis(pads)
    is_c = ref.startswith("C")
    H = 0.50 if is_c else 0.36
    zc = Z_SEAT - 0.04 - H / 2
    ca, sa = cos(radians(ang)), sin(radians(ang))

    def at(u):
        return (cx + u * ca, cy + u * sa, zc)

    rbox(bag["mlcc_body" if is_c else "res_top"], (0.60, 0.46 if is_c else 0.40, H * (1.0 if is_c else 0.9)), at(0), 0.04, 2, ang)
    if not is_c:                                                   # alumina edges and the white back of a chip resistor
        rbox(bag["alumina"], (0.62, 0.44, 0.05), (cx, cy, Z_SEAT - 0.04 - 0.025), 0.01, 1, ang)
    for s in (-1, 1):
        rbox(bag["tin_dull"], (0.20, 0.50 if is_c else 0.46, H), at(s * 0.40), 0.05, 2, ang)
    for p in pads:
        fillet(bag, p, 0.17, 1.05)


def sot523(bag, f):
    pads = f["pads"]
    xs = [p["x"] for p in pads]
    ys = [p["y"] for p in pads]
    cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
    long_x = (max(xs) - min(xs)) >= (max(ys) - min(ys)) * 0.9   # leads on the long sides
    # SOT-523: body 1.6 x 0.8 x 0.7; three gull-wing leads, two on one long side and one on the other
    bw, bl, bh = (1.6, 0.8, 0.62) if abs(max(xs) - min(xs)) > 0.8 else (0.8, 1.6, 0.62)
    zc = Z_SEAT - 0.10 - bh / 2
    rbox(bag["mold"], (bw, bl, bh), (cx, cy, zc), 0.05, 2)
    for p in pads:
        side = (p["x"] - cx, p["y"] - cy)
        horiz = abs(max(xs) - min(xs)) > 0.8                        # pads spread along x: leads run along y
        if horiz:
            ysg = 1 if side[1] > 0 else -1
            rbox(bag["tin_dull"], (0.20, 0.45, 0.07), (p["x"], p["y"] - ysg * 0.0, Z_SEAT - 0.06), 0.01, 1)
            rbox(bag["tin_dull"], (0.20, 0.07, 0.30), (p["x"], cy + ysg * (bl / 2 + 0.03), Z_SEAT - 0.20), 0.01, 1)
        else:
            xsg = 1 if side[0] > 0 else -1
            rbox(bag["tin_dull"], (0.45, 0.20, 0.07), (p["x"], p["y"], Z_SEAT - 0.06), 0.01, 1)
            rbox(bag["tin_dull"], (0.07, 0.20, 0.30), (cx + xsg * (bw / 2 + 0.03), p["y"], Z_SEAT - 0.20), 0.01, 1)
        fillet(bag, p, 0.12, 0.9)
    rbox(bag["mold_ink"], (0.14, 0.14, 0.006), (cx - bw / 2 + 0.2, cy - bl / 2 + 0.18, zc - bh / 2 - 0.002))


def son(bag, f, ref, h, size):
    """Leadless two-sided or four-sided plastic package: black body, pin 1 dot, solder at the pad ends."""
    xs = [p["x"] for p in f["pads"]]
    ys = [p["y"] for p in f["pads"]]
    cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
    bw, bl = size
    zc = Z_SEAT - 0.03 - h / 2
    rbox(bag["mold"], (bw, bl, h), (cx, cy, zc), 0.045, 2)
    p1 = next((p for p in f["pads"] if p["n"] in ("1", "A1")), f["pads"][0])
    sx = -1 if p1["x"] < cx else 1
    sy = -1 if p1["y"] < cy else 1
    mark = min(bw, bl) * 0.12
    k = bag["mold_ink"]
    bmesh.ops.create_cone(k, cap_ends=True, cap_tris=False, segments=14, radius1=mark, radius2=mark, depth=0.008,
                          matrix=Matrix.Translation((cx + sx * (bw / 2 - mark * 2.1), cy + sy * (bl / 2 - mark * 2.1), zc - h / 2 - 0.002)))
    for p in f["pads"]:
        if p["w"] < 0.05:
            continue
        fillet(bag, p, 0.10, 1.0)


def bga(bag, f, ref, h, size, ball=0.22):
    """Wafer-level package: a die with a laminate back and a grid of balls."""
    xs = [p["x"] for p in f["pads"]]
    ys = [p["y"] for p in f["pads"]]
    cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
    bw, bl = size
    top = Z_SEAT - ball * 0.82
    rbox(bag["die"], (bw, bl, h - ball * 0.82), (cx, cy, top - (h - ball * 0.82) / 2), 0.03, 2)
    for p in f["pads"]:
        sphere(bag["tin"], (p["x"], p["y"], Z_SEAT - ball * 0.45), ball / 2, 14)
    p1 = next((p for p in f["pads"] if p["n"] in ("A1",)), f["pads"][0])
    sx = -1 if p1["x"] < cx else 1
    sy = -1 if p1["y"] < cy else 1
    bmesh.ops.create_cone(bag["mold_ink"], cap_ends=True, cap_tris=False, segments=12, radius1=0.05, radius2=0.05, depth=0.006,
                          matrix=Matrix.Translation((cx + sx * (bw / 2 - 0.14), cy + sy * (bl / 2 - 0.14), top - (h - ball * 0.82) - 0.002)))


def lga(bag, f, ref, h, size):
    xs = [p["x"] for p in f["pads"]]
    ys = [p["y"] for p in f["pads"]]
    cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
    bw, bl = size
    zc = Z_SEAT - 0.03 - h / 2
    rbox(bag["mold"], (bw, bl, h), (cx, cy, zc), 0.04, 2)
    p1 = f["pads"][0]
    sx = -1 if p1["x"] < cx else 1
    sy = -1 if p1["y"] < cy else 1
    bmesh.ops.create_cone(bag["mold_ink"], cap_ends=True, cap_tris=False, segments=14, radius1=0.09, radius2=0.09, depth=0.008,
                          matrix=Matrix.Translation((cx + sx * (bw / 2 - 0.25), cy + sy * (bl / 2 - 0.25), zc - h / 2 - 0.002)))
    for p in f["pads"]:
        fillet(bag, p, 0.08, 0.95)


def sfh7072(bag, f):
    """OSRAM SFH 7072: black body, three optical windows on the skin face with clear gel and the dice behind them."""
    xs = [p["x"] for p in f["pads"]]
    ys = [p["y"] for p in f["pads"]]
    cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
    h = 0.90
    zc = Z_SEAT - 0.03 - h / 2
    zf = zc - h / 2                                              # optical face
    body = g.new_bm()
    rbox(body, (7.5, 3.9, h), (cx, cy, zc), 0.07, 2)
    me = bpy.data.meshes.new("sfh_body")
    body.to_mesh(me)
    body.free()
    ob = bpy.data.objects.new("Skin_SFH7072_body", me)
    g.collection(g.COLL_ASM).objects.link(ob)
    cut = []
    for (ax, ay, aw, ah) in B.SFH_APERTURES:                      # cavities, 0.5 mm deep, with the clear gel flush in them
        cb = g.new_bm()
        g.add_box(cb, (aw, ah, 0.55), (cx + ax, cy + ay, zf + 0.20))
        cut.append(g.obj_from_bm("cut", cb, smooth=False))
        rbox(bag["clear"], (aw - 0.02, ah - 0.02, 0.375), (cx + ax, cy + ay, zf + 0.1875), 0.04, 2)
    g.bool_diff(ob, cut, "EXACT")
    ob.data.materials.clear()
    ob.data.materials.append(bpy.data.materials["mold_compound_black"])
    kinds = {"green": "led_green", "red": "led_red", "ir": "led_IR", "pd": "photodiode"}
    for kind, dx, dy, size in B.SFH_DICE:
        key = "pd" if kind.startswith("pd") else kind
        sy = size * (2.69 / 1.29) if kind == "pd2" else size
        rbox(bag["die_" + key], (size, sy, 0.10), (cx + dx, cy + dy, zf + 0.425), 0.012, 1)
        x0 = cx + dx - size / 2
        tube(bag["wire"], [(x0 + 0.05, cy + dy, zf + 0.372), (x0 - 0.10, cy + dy + 0.08, zf + 0.30), (x0 - 0.25, cy + dy + 0.15, zf + 0.44)], 0.011, 4)
    for p in f["pads"]:
        fillet(bag, p, 0.10, 1.0)
    return {"die_green": "green", "die_red": "red", "die_ir": "ir", "die_pd": "pd"}


def isp1807(bag, f, ref):
    """ISP1807 BLE module, 8 x 8 mm: dark substrate with castellated pads, black overmold, ceramic antenna on the side of
    the antenna pads (65 to 78 of the footprint), which the board puts towards the rim of the disc."""
    xs = [p["x"] for p in f["pads"]]
    ys = [p["y"] for p in f["pads"]]
    cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
    ant = [p for p in f["pads"] if p["n"].isdigit() and 65 <= int(p["n"]) <= 78]
    ux, uy = sum(p["x"] for p in ant) / len(ant) - cx, sum(p["y"] for p in ant) / len(ant) - cy
    turn = degrees(atan2(uy, ux)) - 180.0                              # the model is drawn with the antenna on -x, then turned

    def W(dx, dy):
        a = radians(turn)
        return (cx + dx * cos(a) - dy * sin(a), cy + dx * sin(a) + dy * cos(a))

    W_ = 8.0
    sub_t, tall = 0.46, 0.94
    zs = Z_SEAT - 0.02
    rbox(bag["module_sub"], (W_, W_, sub_t), (cx, cy, zs - sub_t / 2), 0.05, 2, rot=turn)
    # castellated pads: gold half-barrels on the four edges
    for p in f["pads"]:
        dx, dy = p["x"] - cx, p["y"] - cy
        if max(abs(dx), abs(dy)) < W_ / 2 - 0.9:
            continue
        horizontal = abs(dx) > abs(dy)
        sx = 1 if dx > 0 else -1
        sy = 1 if dy > 0 else -1
        if horizontal:
            rbox(bag["enig"], (0.05, max(p["h"], 0.3) * 0.9, sub_t * 0.9), (cx + sx * (W_ / 2 + 0.005), p["y"], zs - sub_t / 2), 0.0)
        else:
            rbox(bag["enig"], (max(p["w"], 0.3) * 0.9, 0.05, sub_t * 0.9), (p["x"], cy + sy * (W_ / 2 + 0.005), zs - sub_t / 2), 0.0)
        fillet(bag, p, 0.08, 0.8)
    ant_w = 1.5
    ax, ay = W(-W_ / 2 + ant_w / 2 + 0.2, 0.0)
    rbox(bag["antenna"], (ant_w, W_ - 1.2, tall - sub_t - 0.1), (ax, ay, zs - sub_t - (tall - sub_t - 0.1) / 2), 0.08, 2, rot=turn)
    fx, fy = W(-W_ / 2 + ant_w / 2 + 0.2, (W_ - 1.2) / 2 - 0.15)
    rbox(bag["enig"], (ant_w - 0.1, 0.3, 0.03), (fx, fy, zs - sub_t - (tall - sub_t - 0.1) + 0.0), 0.0, rot=turn)
    mold_x0 = -W_ / 2 + ant_w + 0.6
    mold_x1 = W_ / 2 - 0.25
    mx, my = W((mold_x0 + mold_x1) / 2, 0.0)
    rbox(bag["module_mold"], (mold_x1 - mold_x0, W_ - 0.5, tall - sub_t), (mx, my, zs - sub_t - (tall - sub_t) / 2), 0.07, 2, rot=turn)
    # white mark on the mold, readable from the skin side
    bag["_text_ISP1807"] = text_mesh("ISP1807", 0.62, mx, my, zs - tall - 0.002, rot=90 + turn, extrude=0.012, mirror=True)


def spring_contact(bag, pad, ang=0.0):
    """Generic SMD spring finger for the charge pad: foot soldered on the land, a bent leaf up to the steel rivet."""
    x, y = pad["x"], pad["y"]
    zt = Z_SEAT - 0.02
    top = B.FLOOR + B.SLUG_HEAD_T                                    # where the rivet head is, the leaf is pressed on it
    zf = zt - 0.04
    sweep(bag["spring_plate"], [(-1.0, zf), (-0.55, zf), (-0.38, zf - 0.20), (-0.20, zf - 0.55), (-0.05, top + 0.08),
                                (0.08, top + 0.02), (0.22, top + 0.06), (0.38, top + 0.20)], 1.7, 0.09, x, y, ang)
    fillet(bag, pad, 0.12, 0.9)


def build_parts(M: dict) -> dict:
    """All the skin-side parts and the pads' solder, from the KiCad placement. Returns a note on what was built."""
    fps = {f["ref"]: f for f in json.load(open(PLACEMENT))}
    bag = Bag()
    for ref, f in sorted(fps.items()):
        if f["side"] != "skin" and not f["pads"][0].get("skin"):
            continue
        n = f["name"]
        if ref in ("CP1", "CP2"):
            spring_contact(bag, f["pads"][0])
        elif n.startswith(("C_0402", "R_0402")):
            passive(bag, f, ref)
        elif ref == "U2":
            sfh7072(bag, f)
        elif ref == "U5":
            isp1807(bag, f, ref)
        elif ref == "U1":
            bga(bag, f, ref, 0.50, (2.0, 1.8))
        elif ref == "U6":
            bga(bag, f, ref, 0.50, (1.6, 0.9), 0.20)
        elif ref == "U3":
            lga(bag, f, ref, 0.83, (3.0, 2.5))
        elif ref == "U4":
            son(bag, f, ref, 0.80, (2.0, 2.0))
        elif ref == "U7":
            son(bag, f, ref, 0.40, (1.0, 1.0))
        elif ref == "D1":
            son(bag, f, ref, 0.40, (1.0, 0.6))
        elif ref == "Q1":
            sot523(bag, f)
    mats = {"tin": "tin", "tin_dull": "tin_dull", "mold": "mold", "mold_ink": "mold_ink", "die": "die", "alumina": "alumina",
            "mlcc_body": "mlcc_body", "res_top": "res_top", "module_mold": "module_mold", "module_sub": "module_sub",
            "antenna": "antenna", "enig": "enig", "clear": "clear", "wire": "wire", "spring_plate": "spring_plate",
            "die_green": "green", "die_red": "red", "die_ir": "ir", "die_pd": "pd"}
    out = {}
    for key, bm in bag.bms.items():
        if key.startswith("_text_"):
            continue
        ob = g.obj_from_bm("Skin_" + key, bm, M[mats[key]], smooth=key not in ("mlcc_body",))
        out[key] = ob
    for key, me in [(k, v) for k, v in bag.bms.items() if k.startswith("_text_")]:
        ob = bpy.data.objects.new("Skin_mark_" + key[6:], me)
        ob.data.materials.append(M["silk"])
        g.collection(g.COLL_ASM).objects.link(ob)
    return out


def import_board(M: dict) -> None:
    """The KiCad board: copper, pads, vias, mask, silkscreen and body, placed in the disc frame."""
    glb = os.path.join(tempfile.gettempdir(), "caseback_board_v01.glb")
    export_glb(glb)
    before = set(bpy.data.objects)
    units = bpy.context.scene.unit_settings
    keep_scale = units.scale_length
    units.scale_length = 1.0                                           # the importer would scale metres to the scene's unit; the mesh is scaled below
    bpy.ops.import_scene.gltf(filepath=glb)
    units.scale_length = keep_scale
    new = [o for o in bpy.data.objects if o not in before]
    coll = g.collection(g.COLL_ASM)
    keep = {"caseback_v01_copper": "copper_t", "caseback_v01_pad": "enig", "caseback_v01_via": "copper_t",
            "caseback_v01_silkscreen": "silk", "caseback_v01_soldermask": "mask", "caseback_v01_PCB": "fr4"}
    names = {"caseback_v01_copper": "PCB_copper", "caseback_v01_pad": "PCB_pads", "caseback_v01_via": "PCB_vias",
             "caseback_v01_silkscreen": "PCB_silkscreen", "caseback_v01_soldermask": "PCB_mask", "caseback_v01_PCB": "PCB"}
    for ob in new:
        if ob.type != "MESH":
            continue
        base = ob.data.name.split(".")[0]
        mat = keep.get(base)
        if not mat:
            bpy.data.objects.remove(ob, do_unlink=True)
            continue
        me = ob.data
        me.transform(ob.matrix_world)                                  # bake the node transform
        ob.parent = None
        ob.matrix_world = Matrix.Identity(4)
        me.transform(Matrix.Translation((0, 0, GLB_SHIFT)) @ Matrix.Diagonal((1000.0, 1000.0, 1000.0, 1.0)))
        me.materials.clear()
        me.materials.append(M[mat])
        for u in list(ob.users_collection):
            u.objects.unlink(ob)
        coll.objects.link(ob)
        zmean = sum(v.co.z for v in me.vertices) / max(len(me.vertices), 1)
        side = "_watch" if zmean > B.PCB_Z0 + 0.3 else "_skin"
        ob.name = names[base] + (side if base in ("caseback_v01_silkscreen", "caseback_v01_soldermask") else "")
        for p in me.polygons:
            p.use_smooth = False
    for ob in list(bpy.data.objects):                                  # the importer leaves empties behind
        if ob.type == "EMPTY":
            bpy.data.objects.remove(ob, do_unlink=True)
