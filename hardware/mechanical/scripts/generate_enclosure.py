"""Caseback V0 mechanical generator (Blender 4.x / 5.x).

Headless:
    blender -b --python generate_enclosure.py -- [--out-dir DIR] [--blend FILE] [--h MM] [--cell NAME] [--tag TXT]

Defaults: STLs go to ../stl, the scene to ./caseback_v0_mechanical.blend. CASEBACK_OUT overrides --out-dir.
Then run `python3 check_geometry.py` (stdlib + numpy) on the exported STLs.

Units: 1 Blender unit = 1 mm (scene unit scale 0.001). STLs are written by this script in plain
millimetres, so no object scaling is needed. Axes: Z = 0 is the skin face, +Z goes to the caseback.
Origin XY is the disc centre; the keying notch and the two charge pads are on the -Y side.

Vertical budget (mm), H = 4.0:
    floor 0.9 | cavity 1.8 | roof 0.9 | pad recess 0.4  ->  0.9 + 1.8 + 0.9 + 0.4 = 4.0
so the thickest cell that fits is H - 2.2 - foam - slack. See CELLS and required_height().
"""

from __future__ import annotations

import json
import os
import struct
import sys
from math import cos, pi, sin

import bmesh
import bpy
from mathutils import Matrix

# ------------------------------------------------------------------ dimensions (mm)
DISC_DIA = 34.0
DISC_H = 4.0                     # documented V0 target
FLOOR = 0.9                      # skin-side floor, also the minimum wall rule
ROOF = 0.9                       # material left under the pad recess
WALL = 2.7                       # rim: web 0.95 + gasket groove 0.8 + web 0.95
SEAM_Z = 2.0                     # parting line bottom shell / lid
SUCTION_DIA = 22.0
SUCTION_DEPTH = 0.4
LIP_H = 0.5                      # inner web of the bottom rim, registers in the lid
LIP_CLR = 0.15
GROOVE_W, GROOVE_D = 0.8, 0.6    # face groove for a 0.8 mm silicone cord (25 % squeeze)
PPG_APERTURE = 3.6
SEAT_DIA = 4.4                   # window seat: 0.4 mm radial ledge for a 0.4 mm glass/PMMA window
SEAT_DEPTH = 0.4
WIN_BOSS_R = 4.0                 # ring boss keeps the ledge >= 0.9 mm thick
WIN_XY = (0.0, 8.0)              # PPG window is off-centre so the cell fits beside it
SCREW_XY = ((-9.5, 8.0), (9.5, 8.0))   # M1 x 3, plastic / brass / titanium, never steel
BOSS_R, PILOT_R = 1.5, 0.4
HOLE_R, CBORE_R, CBORE_DEPTH = 0.6, 1.1, 0.8
POGO_SPACING = 8.0
POGO_Y = -12.6
PAD_SIZE, PAD_RECESS = (2.4, 1.2), 0.3
PAD_BOSS = (3.6, 2.4, 0.35)
NOTCH_W, NOTCH_DEPTH, NOTCH_H = 3.0, 0.9, 1.0    # keying notch in the rim, -Y side
FOAM, SLACK, POCKET_CLR = 0.15, 0.1, 0.3
POCKET_XY = (0.0, -2.4)
RIB_T = 0.6

# battery cells, (thickness, width, length) mm. LiPo naming is normally T x W x L, so 301020 is
# 3.0 x 10 x 20 mm and 401230 is 4.0 x 12 x 30 mm. FROM MEMORY: confirm on the cell datasheet.
CELLS = {
    "THIN_1P5": (1.5, 10.0, 20.0),   # placeholder for a ~1.5 mm cell, no part number chosen
    "301020": (3.0, 10.0, 20.0),
    "401230": (4.0, 12.0, 30.0),
}
CELL = "THIN_1P5"

PUCK_CLR = 0.3                   # per side between disc and dish
PUCK_RIM = 1.7
PUCK_DIA = DISC_DIA + 2 * PUCK_CLR + 2 * PUCK_RIM     # 38.0
PUCK_H = 8.0
DISH_DEPTH = 1.6
KEY_W, KEY_H, KEY_IN = 2.2, 0.8, 0.8
POGO_BORE_R = 0.6

BAND_W, BAND_L, BAND_T = 22.0, 220.0, 2.5
BAND_HOUSING_H = 5.0
BAND_FLOOR = 0.8
BAND_WINDOW_DIA = 26.0

SEG = 180
OUT = {"bottom": "Caseback_disc_bottom", "top": "Caseback_disc_top", "puck": "Caseback_puck", "band": "Caseback_softband"}


def cavity_top(h: float) -> float:
    return h - SUCTION_DEPTH - ROOF


def required_height(cell: str) -> float:
    """Disc height that holds `cell` with the current floor, roof, recess, foam and slack."""
    return FLOOR + CELLS[cell][0] + FOAM + SLACK + ROOF + SUCTION_DEPTH


# ------------------------------------------------------------------ mesh helpers
def lathe(profile, seg: int = SEG, phase: float = 0.0173):
    """Closed (r, z) polygon revolved around Z; points with r = 0 collapse to the axis."""
    bm = bmesh.new()
    rings = []
    for r, z in profile:
        if r < 1e-9:
            rings.append([bm.verts.new((0.0, 0.0, z))] * seg)
        else:
            rings.append([bm.verts.new((r * cos(phase + 2 * pi * k / seg), r * sin(phase + 2 * pi * k / seg), z)) for k in range(seg)])
    n = len(profile)
    for i in range(n):
        a, b = rings[i], rings[(i + 1) % n]
        for k in range(seg):
            quad = [a[k], a[(k + 1) % seg], b[(k + 1) % seg], b[k]]
            uniq = []
            for v in quad:
                if v not in uniq:
                    uniq.append(v)
            if len(uniq) >= 3:
                bm.faces.new(uniq)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return bm


def cyl_bm(r, z0, z1, x=0.0, y=0.0, seg=SEG, phase=0.0173):
    """Cylinder; give coaxial cutters different seg/phase so the exact solver sees no coincident vertices."""
    bm = lathe([(0.0, z0), (r, z0), (r, z1), (0.0, z1)], seg, phase)
    bmesh.ops.translate(bm, verts=bm.verts, vec=(x, y, 0.0))
    return bm


def box_bm(size, center):
    bm = bmesh.new()
    m = Matrix.Translation(center) @ Matrix.Diagonal((*size, 1.0))
    bmesh.ops.create_cube(bm, size=1.0, matrix=m)
    return bm


def new_obj(name: str, bm):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def boolean(target, ops):
    """Apply [(operation, bmesh)] to target in order with the exact solver."""
    tmp = []
    for i, (op, bm) in enumerate(ops):
        cutter = new_obj(f"tmp_{i}", bm)
        tmp.append(cutter)
        m = target.modifiers.new(f"{op}_{i}", "BOOLEAN")
        m.operation, m.object, m.solver = op, cutter, "EXACT"
    bpy.context.view_layer.update()
    ev = target.evaluated_get(bpy.context.evaluated_depsgraph_get())
    new = bpy.data.meshes.new_from_object(ev)
    bm = bmesh.new()
    bm.from_mesh(new)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=2e-4)      # slivers left by the exact solver
    bmesh.ops.dissolve_degenerate(bm, dist=2e-4, edges=bm.edges)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(new)
    bm.free()
    old = target.data
    target.modifiers.clear()
    target.data = new
    bpy.data.meshes.remove(old)
    for c in tmp:
        bpy.data.objects.remove(c, do_unlink=True)


def write_stl(ob, path: str) -> int:
    me = ob.data
    me.calc_loop_triangles()
    tris = me.loop_triangles
    with open(path, "wb") as f:
        f.write(b"Caseback V0 mechanical, millimetres".ljust(80, b" "))
        f.write(struct.pack("<I", len(tris)))
        for t in tris:
            a, b, c = (me.vertices[i].co for i in t.vertices)
            n = (b - a).cross(c - a)
            n = n.normalized() if n.length > 0 else n
            f.write(struct.pack("<12fH", n.x, n.y, n.z, *a, *b, *c, 0))
    return len(tris)


# ------------------------------------------------------------------ parts
def build_bottom(h: float, cell: str):
    """Skin-side shell: floor, rim with lip and gasket groove, window seat, pad recesses, key notch."""
    rin = DISC_DIA / 2 - WALL
    r = DISC_DIA / 2
    g0, g1 = rin + 0.95, rin + 0.95 + GROOVE_W
    prof = [(0, 0), (r, 0), (r, SEAM_Z), (g1, SEAM_Z), (g1, SEAM_Z - GROOVE_D), (g0, SEAM_Z - GROOVE_D),
            (g0, SEAM_Z + LIP_H), (rin, SEAM_Z + LIP_H), (rin, FLOOR), (0, FLOOR)]
    bot = new_obj(OUT["bottom"], lathe(prof))

    t, w, ln = CELLS[cell]
    px, py = POCKET_XY
    ops = []
    # window ring boss, screw bosses, pad bosses, cell locator ribs
    ring = lathe([(SEAT_DIA / 2, FLOOR - 0.4), (WIN_BOSS_R, FLOOR - 0.4), (WIN_BOSS_R, FLOOR + SEAT_DEPTH),
                  (SEAT_DIA / 2, FLOOR + SEAT_DEPTH)], SEG, 0.0311)
    bmesh.ops.translate(ring, verts=ring.verts, vec=(*WIN_XY, 0.0))
    ops.append(("UNION", ring))          # the seat is the air inside the ring, above the floor
    for sx, sy in SCREW_XY:
        ops.append(("UNION", cyl_bm(BOSS_R, FLOOR - 0.4, SEAM_Z, sx, sy, 48)))
    for i in (-1, 1):
        ops.append(("UNION", box_bm((*PAD_BOSS[:2], PAD_BOSS[2] + 0.2),
                                    (i * POGO_SPACING / 2, POGO_Y, FLOOR - 0.2 + (PAD_BOSS[2] + 0.2) / 2))))
    hx, hy = (ln + POCKET_CLR) / 2, (w + POCKET_CLR) / 2
    rz0, rz1 = FLOOR - 0.2, FLOOR + t
    for sx in (-1, 1):
        ops.append(("UNION", box_bm((RIB_T, 4.0, rz1 - rz0), (px + sx * (hx + RIB_T / 2), py, (rz0 + rz1) / 2))))
    for sy in (-1, 1):
        ops.append(("UNION", box_bm((6.0, RIB_T, rz1 - rz0), (px, py + sy * (hy + RIB_T / 2), (rz0 + rz1) / 2))))
    # window aperture, pogo pad recesses, keying notch, screw pilots
    ops.append(("DIFFERENCE", cyl_bm(PPG_APERTURE / 2, -0.2, FLOOR + 0.2, *WIN_XY)))
    for i in (-1, 1):
        ops.append(("DIFFERENCE", box_bm((*PAD_SIZE, PAD_RECESS + 0.2), (i * POGO_SPACING / 2, POGO_Y, PAD_RECESS / 2 - 0.1))))
    ops.append(("DIFFERENCE", box_bm((NOTCH_W, NOTCH_DEPTH + 1.0, NOTCH_H + 0.2),
                                     (0.0, -(r - NOTCH_DEPTH) - (NOTCH_DEPTH + 1.0) / 2, NOTCH_H / 2 - 0.1))))
    for sx, sy in SCREW_XY:
        ops.append(("DIFFERENCE", cyl_bm(PILOT_R, 1.3, SEAM_Z + 0.2, sx, sy, 32)))
    boolean(bot, ops)
    return bot


def build_top(h: float):
    """Caseback-side lid: roof, pad recess, lip recess, screw bosses with counterbore."""
    rin = DISC_DIA / 2 - WALL
    r = DISC_DIA / 2
    zc = cavity_top(h)
    rc = rin + 0.95 + LIP_CLR                 # lip recess outer radius: inner web face + clearance
    prof = [(0, zc), (rc, zc), (rc, SEAM_Z), (r, SEAM_Z), (r, h), (SUCTION_DIA / 2, h),
            (SUCTION_DIA / 2, h - SUCTION_DEPTH), (0, h - SUCTION_DEPTH)]
    top = new_obj(OUT["top"], lathe(prof))
    ops = []
    for sx, sy in SCREW_XY:
        ops.append(("UNION", cyl_bm(BOSS_R, SEAM_Z, zc + 0.3, sx, sy, 48)))
    for sx, sy in SCREW_XY:
        ops.append(("DIFFERENCE", cyl_bm(HOLE_R, SEAM_Z - 0.1, h + 0.1, sx, sy, 32)))
        ops.append(("DIFFERENCE", cyl_bm(CBORE_R, h - CBORE_DEPTH, h + 0.1, sx, sy, 32)))
    boolean(top, ops)
    return top


def build_puck():
    r_dish = DISC_DIA / 2 + PUCK_CLR
    r = PUCK_DIA / 2
    prof = [(0, 0), (r, 0), (r, PUCK_H), (r_dish, PUCK_H), (r_dish, PUCK_H - DISH_DEPTH), (0, PUCK_H - DISH_DEPTH)]
    puck = new_obj(OUT["puck"], lathe(prof))
    floor_z = PUCK_H - DISH_DEPTH
    ops = [("UNION", box_bm((KEY_W, KEY_IN + 0.4, KEY_H + 0.2),
                            (0.0, -(r_dish - KEY_IN / 2 + 0.2), floor_z + KEY_H / 2 - 0.1)))]
    for i in (-1, 1):
        ops.append(("DIFFERENCE", cyl_bm(POGO_BORE_R, floor_z - 3.5, floor_z + 0.1, i * POGO_SPACING / 2, POGO_Y, 32)))
    boolean(puck, ops)
    return puck


def build_softband():
    """Simplified strap blank: 22 mm strap with a moulded housing for the disc. No retention lip."""
    r_pocket = DISC_DIA / 2 + PUCK_CLR
    band = new_obj(OUT["band"], box_bm((BAND_L, BAND_W, BAND_T), (0.0, 0.0, BAND_T / 2)))
    ops = [("UNION", cyl_bm(r_pocket + 3.0, 0.0, BAND_HOUSING_H)),
           ("DIFFERENCE", cyl_bm(r_pocket, BAND_FLOOR, BAND_HOUSING_H + 0.2)),
           ("DIFFERENCE", cyl_bm(BAND_WINDOW_DIA / 2, -0.2, BAND_FLOOR + 0.2)),
           ("UNION", box_bm((KEY_W, KEY_IN + 0.4, KEY_H + 0.2), (0.0, -(r_pocket - KEY_IN / 2 + 0.2), BAND_FLOOR + KEY_H / 2 - 0.1)))]
    boolean(band, ops)
    return band


# ------------------------------------------------------------------ main
def parse_args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    here = os.path.dirname(os.path.abspath(__file__))
    a = {"out_dir": os.environ.get("CASEBACK_OUT") or os.path.join(here, "..", "stl"),
         "blend": os.path.join(here, "caseback_v0_mechanical.blend"), "h": DISC_H, "cell": CELL, "tag": ""}
    it = iter(argv)
    for k in it:
        key = k.lstrip("-").replace("-", "_")
        if key in a:
            a[key] = next(it)
    a["h"] = float(a["h"])
    if a["cell"] not in CELLS:
        raise SystemExit(f"unknown cell {a['cell']}; choose from {sorted(CELLS)}")
    if a["tag"] and "--blend" not in argv:
        a["blend"] = ""
    return a


def main() -> None:
    a = parse_args()
    h, cell, tag = a["h"], a["cell"], a["tag"]
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.unit_settings.system, sc.unit_settings.scale_length, sc.unit_settings.length_unit = "METRIC", 0.001, "MILLIMETERS"

    need = required_height(cell)
    if need > h + 1e-9:
        print(f"WARNING: cell {cell} needs a disc height of {need:.2f} mm, building at {h:.2f} mm: the pocket will not fit")

    parts = {"bottom": build_bottom(h, cell), "top": build_top(h), "puck": build_puck(), "band": build_softband()}
    parts["puck"].location.x = 60.0
    parts["band"].location.y = -60.0
    for key, ob in parts.items():
        ob["part"] = ob.name

    out = os.path.abspath(a["out_dir"])
    os.makedirs(out, exist_ok=True)
    counts = {}
    for key, ob in parts.items():
        counts[key] = write_stl(ob, os.path.join(out, f"caseback_v0_{key}{tag}.stl"))

    t, w, ln = CELLS[cell]
    zc = cavity_top(h)
    params = {
        "disc_dia": DISC_DIA, "disc_h": h, "floor": FLOOR, "roof": ROOF, "wall": WALL, "seam_z": SEAM_Z,
        "cavity_r": DISC_DIA / 2 - WALL, "cavity_z": [FLOOR, zc], "suction_dia": SUCTION_DIA, "suction_depth": SUCTION_DEPTH,
        "groove": {"r0": DISC_DIA / 2 - WALL + 0.95, "w": GROOVE_W, "depth": GROOVE_D, "cord_dia": 0.8},
        "window": {"xy": WIN_XY, "aperture_dia": PPG_APERTURE, "seat_dia": SEAT_DIA, "seat_depth": SEAT_DEPTH},
        "screws": {"xy": SCREW_XY, "hole_r": HOLE_R, "cbore_r": CBORE_R, "cbore_depth": CBORE_DEPTH},
        "pads": {"xy": [(-POGO_SPACING / 2, POGO_Y), (POGO_SPACING / 2, POGO_Y)], "size": PAD_SIZE},
        "notch": {"width": NOTCH_W, "depth": NOTCH_DEPTH, "height": NOTCH_H, "angle_deg": -90},
        "cell": {"name": cell, "t_w_l": [t, w, ln], "required_h": need},
        "cells": CELLS, "foam": FOAM, "slack": SLACK, "pocket_clr": POCKET_CLR,
        "pocket": {"center": POCKET_XY, "size": [ln + POCKET_CLR, w + POCKET_CLR, t + FOAM + SLACK], "z0": FLOOR},
        "puck": {"dia": PUCK_DIA, "h": PUCK_H, "dish_dia": DISC_DIA + 2 * PUCK_CLR, "dish_depth": DISH_DEPTH,
                 "key": {"width": KEY_W, "height": KEY_H, "inner_r": DISC_DIA / 2 + PUCK_CLR - KEY_IN},
                 "pogo_xy": [(-POGO_SPACING / 2, POGO_Y), (POGO_SPACING / 2, POGO_Y)]},
        "stl": {k: f"caseback_v0_{k}{tag}.stl" for k in parts},
    }
    with open(os.path.join(out, f"caseback_v0_params{tag}.json"), "w") as f:
        json.dump(params, f, indent=2)

    print(f"exported {counts} triangles to {out}")
    if a["blend"]:
        bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(a["blend"]))
        print(f"saved {a['blend']}")


if __name__ == "__main__":
    main()
