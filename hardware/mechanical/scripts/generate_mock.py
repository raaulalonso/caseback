"""Printable mock of the Caseback disc (shell, three lids with different snap tightness, a pad placeholder) and of the charging puck.

Headless:
    blender -b --python generate_mock.py -- --out ../print

It reuses the real shell and lid of generate_disc.py (same outline, wall, floor, windows, contact holes, rim pockets, ribs,
pad recess, 3.0 mm + 0.1 mm of pad) and changes only what a 0.4 mm nozzle cannot make:

* the skirt of the lid is 0.46 mm thick instead of 0.36, and it sits 0.06 mm inside the wall. Bambu Studio calls a bead on a wall that is
  no thicker than its line (0.42 mm) a floating region; from 0.44 mm it does not;
* the bead of the snap is 0.09, 0.12 or 0.15 mm high instead of 0.10 (three lids: easy, standard, firm), with 45 degree flanks on
  both sides (the real 60 degree return flank is an overhang that the slicer calls floating), and the groove in the wall is
  cut for the biggest one, 0.15 mm deep (the wall keeps 0.65 mm there);
* the name and the mark are left out: their lines are 0.07 to 0.09 mm wide;
* the face of the lid is dead flat (no pad recess, no rounded edge): face down on the bed, the 17 mm recess was a bridge over nothing. The pad
  stand-in is taped to the flat face and stands 0.4 mm proud instead of 0.1;
* it keeps the edges and the pad of the first 25 mm model (see EDGE_* and R_RECESS below), not those of the final design.

The lids are written upside down (face on the bed) so that they print without support; the shell is printed skin face down.

The puck is the real body of generate_disc.py with the key joined to it and no engraving, and its base plate as a plain disc. It
prints as it is modelled, bottom face on the bed: the pocket for the board is open there, and its roof (a bridge of 26 mm) is
inside. The pins, the USB-C board, the screws and the silicone foot are not printed; the bores and the pocket are there to try
the parts that are bought (a 1.0 to 1.3 mm spring pin, a USB-C breakout board).
Units: millimetres, one file per part, centred on x = y = 0.
"""

from __future__ import annotations

import math
import os
import struct
import sys

import bmesh
import bpy
from mathutils import Matrix

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import generate_disc as gd  # noqa: E402

g, B = gd.g, gd.B

# The printable mock is the first 25 mm model (D53): edge radii 0.5 mm on the skin side and a sharp inside corner, a flat lid face, a 16.9 mm
# pad stand-in. The final design of the disc (D54: edges of 1.2 and 0.6 mm, a 23 mm pad, the name and the mark on the skin face) is not for
# printing, so the values are set here and the mock does not follow generate_disc.py when that changes.
gd.EDGE_SKIN, gd.EDGE_LID, gd.EDGE_IN, gd.R_RECESS = 0.5, 0.3, 0.0, 8.5

OUT = os.path.join(HERE, "..", "print")
argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
if "--out" in argv:
    OUT = argv[argv.index("--out") + 1]

# ------------------------------------------------------------------ what changes for a 0.4 mm nozzle
SK_OUT = 11.64                      # real: 11.66 (0.04 from the wall). 0.06 here, so a printed skirt that comes out a little fat still goes in
SK_THICK = 0.46                     # real: 0.36. Above the 0.42 mm line, or the slicer warns about floating regions at the bead
GROOVE_DEPTH = 0.15                 # the deepest bead; the wall keeps 0.65 mm
SK_TIP = 1.50                       # real: 1.55. Lower, so the 45 degree bead below fits between the tip and the lead-in of the wall
BEAD_FOOT = 1.58                    # height of the foot of the bead, from the skin face
LEADIN = 1.0                        # 45 degrees on the way in: dz = dr
RETURN = 1.0                        # and 45 degrees on the way out: the real 60 degrees from the axis is an overhang a 0.4 mm nozzle prints as floating
LIDS = {"easy": 0.09, "standard": 0.12, "firm": 0.15}      # bead height; the wall is at 11.70, so the nominal interference is bead - 0.06
PAD_D, PAD_T = 2 * (gd.R_RECESS - 0.05), 0.4


def groove_z(depth):
    z0 = 1.52
    z1 = z0 + depth * LEADIN
    z2 = z1 + 0.15
    return (z0, z1, z2, z2 + depth * RETURN)


def bead_z(h):
    z1 = BEAD_FOOT + h * LEADIN
    z2 = z1 + 0.04
    return (BEAD_FOOT, z1, z2, z2 + h * RETURN)


def clean(ob):
    """Merge doubled vertices and drop degenerate faces left by the booleans, and say how many edges are still not shared by two faces."""
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.0008)
    bmesh.ops.dissolve_degenerate(bm, dist=0.0004, edges=bm.edges)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bad = sum(1 for e in bm.edges if len(e.link_faces) != 2)
    bm.to_mesh(ob.data)
    bm.free()
    ob.data.update()
    return bad


def write_stl(ob, path, matrix=None):
    bad = clean(ob)
    if bad:
        print(f"  {ob.name}: {bad} edges are still not shared by exactly two faces")
    me = ob.data
    me.calc_loop_triangles()
    m = ob.matrix_world if matrix is None else matrix @ ob.matrix_world
    n_t = len(me.loop_triangles)
    with open(path, "wb") as f:
        f.write(b"Caseback printable mock, millimetres".ljust(80, b" "))
        f.write(struct.pack("<I", n_t))
        for t in me.loop_triangles:
            a, b, c = (m @ me.vertices[i].co for i in t.vertices)
            n = (b - a).cross(c - a)
            n = n.normalized() if n.length > 0 else n
            f.write(struct.pack("<12fH", n.x, n.y, n.z, *a, *b, *c, 0))
    bm = bmesh.new()
    bm.from_mesh(me)
    vol = bm.calc_volume()
    bm.free()
    return n_t, vol


def clear_scene():
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob, do_unlink=True)


def mock_puck(M):
    """Body of the puck with the hook joined, and the base plate, as STL files ready to print (the latch, its spring and the button
    are not printed)."""
    gd.ENGRAVE = False
    gd.build_puck(M)
    coll = gd.g.collection(gd.COLL_PUCK)
    body, hook = bpy.data.objects["Puck_body"], bpy.data.objects["Puck_hook"]
    # the hook stands out of the dish wall: push its outer face a little into the wall so that the union has no shared face
    for v in hook.data.vertices:
        if v.co.y > gd.DISH_R:
            v.co.y = gd.DISH_R + 0.4
    gd.bool_union(body, [hook])
    report = {}
    report["puck_body"] = write_stl(body, os.path.join(OUT, "caseback_mock_puck_body.stl"))
    report["puck_plate"] = write_stl(bpy.data.objects["Puck_base_plate"], os.path.join(OUT, "caseback_mock_puck_plate.stl"))
    for ob in list(coll.objects):
        bpy.data.objects.remove(ob, do_unlink=True)
    return report


def main():
    os.makedirs(OUT, exist_ok=True)
    clear_scene()
    sc = bpy.context.scene
    sc.unit_settings.system, sc.unit_settings.scale_length, sc.unit_settings.length_unit = "METRIC", 0.001, "MILLIMETERS"
    M = gd.materials()

    gd.ENGRAVE = False
    gd.FLAT_FACE = True
    gd.SK_OUT, gd.SK_IN, gd.SK_Z0 = SK_OUT, SK_OUT - SK_THICK, SK_TIP
    report = {}

    gd.BEAD, gd.GROOVE_Z = GROOVE_DEPTH, groove_z(GROOVE_DEPTH)
    gd.build_shell(M)
    n, v = write_stl(bpy.data.objects["Shell"], os.path.join(OUT, "caseback_mock_shell.stl"))
    report["shell"] = (n, v)
    bpy.data.objects.remove(bpy.data.objects["Shell"], do_unlink=True)

    flip = Matrix.Translation((0.0, 0.0, gd.H)) @ Matrix.Rotation(math.pi, 4, "X")       # face on the bed
    for ticks, (name, h) in enumerate(LIDS.items(), start=1):
        gd.BEAD, gd.BEAD_Z = h, bead_z(h)
        gd.build_lid(M)
        lid = bpy.data.objects["Lid"]
        # one, two or three small vertical notches in the rim, at the top, tell the three lids apart once printed (they look the same)
        notches = [gd.box_cut((0.6, 0.6, 0.5), ((k - (ticks - 1) / 2) * 1.5, gd.R - 0.05, 2.45)) for k in range(ticks)]
        gd.bool_diff(lid, notches, "EXACT")
        n, v = write_stl(lid, os.path.join(OUT, f"caseback_mock_lid_{name}.stl"), flip)
        report[f"lid_{name}"] = (n, v)
        if name == "standard":
            pad = bpy.data.objects["Microsuction_pad"]
            report["pad"] = write_stl(pad, os.path.join(OUT, "caseback_mock_pad.stl"), Matrix.Translation((0.0, 0.0, -(gd.H - gd.PAD_T))))
        for nm in ("Lid", "Microsuction_pad"):
            bpy.data.objects.remove(bpy.data.objects[nm], do_unlink=True)

    report.update(mock_puck(M))
    for k, (n, v) in report.items():
        print(f"mock {k:13s} {n:6d} triangles  {v:7.1f} mm3  {v * 1.27e-3:5.2f} g of PETG if solid")


if __name__ == "__main__":
    main()
