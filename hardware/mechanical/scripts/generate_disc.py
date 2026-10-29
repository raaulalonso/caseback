"""Caseback disc and charging puck, design 1, 25 mm version (Blender 4.x / 5.x).

Headless:
    blender -b --python generate_disc.py -- [--render DIR] [--only name,name] [--stl DIR] [--blend FILE] [--samples N] [--scale F]

Needs KiCad 10 (kicad-cli and its Python) to export the real board; KICAD_CLI and KICAD_PY give their paths.

The stack and the part positions come from hardware/v1-pcb/board_v01.py, so the model, the drawings and the fit checks
use the same numbers. Everything else, the board and cell models, the shell, the lid, the window, the seal, the pad, the
charge contacts and the puck, is drawn here. The design and the reasons are in the design notes.

25 mm across, 3.1 mm thick with the pad, no screws (D53): the lid has a thin skirt with a bead that snaps into a groove
in the wall of the shell, over a silicone ring. The disc charges through its skin face (D52): two flush steel contacts in
the shell floor, a puck that the watch rests on, no magnet and no steel plate. Units: 1 Blender unit = 1 mm. Z = 0 is the
skin face, +Z goes towards the watch caseback. Seen from the watch side (+Z), x is to the right and y up; the key notch is
on -Y, the charge contacts on the left and right.
"""

from __future__ import annotations

import os
import struct
import sys
from math import atan2, cos, degrees, pi, radians, sin

import bmesh
import bpy
from mathutils import Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..", "v1-pcb")))
import board_v01 as B  # noqa: E402
import generate_v1 as g  # noqa: E402  (shared helpers: bmesh primitives, booleans, materials)
import board_parts as BP  # noqa: E402  (the real KiCad board and a model of every part on it)

COLL_ASM, COLL_EXP, COLL_SEC = "Disc", "Disc_Exploded", "Disc_Section"
COLL_PUCK, COLL_DOCK, COLL_DSEC, COLL_BOARD = "Puck", "Disc_Docked", "Disc_DockedSection", "Disc_Board"
g.COLL_ASM = COLL_ASM

# ------------------------------------------------------------------ the disc
H, R = B.H, B.R_DISC                  # 3.0 (lid face; the pad adds 0.1) and 12.5
LID_IN = B.LID_IN                     # 2.20, underside of the lid
WALL_TOP = 2.10                       # top of the shell wall: the gasket is 0.1 mm thick between it and the lid
GASKET = (B.R_CAV + 0.04, B.R_CAV + 0.36)   # flat silicone ring, 0.15 mm free, 0.1 compressed
LIP_R = 12.10                         # the lid has an outer lip from here to the rim that lands on the wall: the hard stop of the snap
# snap fit: a skirt hangs from the lid inside the wall and carries a bead that goes into a groove in the inside of the wall
SK_IN, SK_OUT, SK_Z0 = 11.30, 11.66, 1.55     # skirt: inside radius, outside radius, lowest point. The board is 11.2, the cell 11.0
BEAD = 0.10                           # radial height of the bead and depth of the groove; it goes in against 0.06 mm of interference (the skirt is 0.04 clear of the wall)
BEAD_Z = (1.66, 1.76, 1.83, 1.89)     # bead: foot of the lead-in flank, top of it (45 degrees), foot of the return flank, end of it (60 from the axis)
GROOVE_Z = (1.58, 1.68, 1.85, 1.91)   # groove: where the wall leaves R_CAV, bottom, top of the groove, back to R_CAV
PAD_T, R_RECESS = B.PAD_T, B.R_RECESS
NOTCH_DEPTH, NOTCH_H = 0.4, 1.3       # key notch in the outer wall of the shell, from the skin face up
WIN_GEL = 0.15                        # optical gel between the window resin and the SFH 7072 face
LEDGE_ANGLES = ((-150.0, -130.0), (-100.0, -80.0), (-50.0, -30.0))     # three ribs that carry the board edge, on the side the board keeps
FOOT_R = (10.9, 11.3)                 # the lid has a small foot over each rib that holds the board down (0.03 mm above it)
ENGRAVE = True                        # name and mark on the lid ring, mark on the puck and its plate; the printable mock leaves them out
FLAT_FACE = False                     # the printable mock makes the face of the lid dead flat: no pad recess, no rounded edge, nothing to bridge on the bed

# ------------------------------------------------------------------ the puck
P_R, P_H = 17.0, 7.0
DISH_R, DISH_DEPTH = 12.8, 1.2        # shallow: the disc stands 1.9 mm proud and the watch rests on it
P_FLOOR = P_H - DISH_DEPTH            # 5.8, where the skin face of the disc rests
POGO_FREE = 0.35                      # plunger height above the dish floor when free; the watch presses it flush
POGO_R, POGO_PLUNGER_R = 0.5, 0.37
PUCK_BOARD_R = 12.4                   # the puck board: a disc with a tab for the USB-C socket
POCKET_R = 12.9
PLATE_R = 13.3
USB_Z = 3.03                          # height of the middle of the USB-C receptacle above the bottom of the puck
USB_FLAT_Y = 15.9                     # the rim of the puck is cut flat here, 12 mm wide, so that the face of the receptacle sits square
COLL_STUDIO, COLL_PSEC = "Studio", "Puck_Section"


def cyl_cut(r, z0, z1, x=0.0, y=0.0, seg=48):
    b = g.new_bm()
    g.add_cyl(b, r, z0, z1, x, y, seg)
    return g.obj_from_bm("cut", b, smooth=False)


def box_cut(size, center, rot=0.0):
    b = g.new_bm()
    g.add_box(b, size, center, rot)
    return g.obj_from_bm("cut", b, smooth=False)


def stadium_cut(w, h, y0, y1, xc, zc, seg=24):
    """A tunnel along Y with a stadium cross-section (a rounded slot), w wide and h high, from y0 to y1."""
    r = h / 2
    b = g.new_bm()
    g.add_box(b, (w - 2 * r, y1 - y0, h), (xc, (y0 + y1) / 2, zc))
    for sx in (-1, 1):
        bmesh.ops.create_cone(b, cap_ends=True, cap_tris=False, segments=seg, radius1=r, radius2=r, depth=y1 - y0,
                              matrix=Matrix.Translation((xc + sx * (w / 2 - r), (y0 + y1) / 2, zc)) @ Matrix.Rotation(pi / 2, 4, "X"))
    ob = g.obj_from_bm("cut", b, smooth=False)
    ob["self_x"] = True                                            # box and cones overlap inside one mesh
    return ob


def rounded_rect(w, h, r, seg=8):
    """Corner points of a rounded rectangle w x h, counter-clockwise."""
    pts = []
    for cxs, cys, a0 in ((1, 1, 0), (-1, 1, 90), (-1, -1, 180), (1, -1, 270)):
        for k in range(seg + 1):
            a = radians(a0 + 90.0 * k / seg)
            pts.append((cxs * (w / 2 - r) + r * cos(a), cys * (h / 2 - r) + r * sin(a)))
    return pts


def bool_union(target, objs):
    for i, c in enumerate(objs):
        m = target.modifiers.new(f"add{i}", "BOOLEAN")
        m.operation, m.object, m.solver = "UNION", c, "EXACT"
    bpy.context.view_layer.update()
    ev = target.evaluated_get(bpy.context.evaluated_depsgraph_get())
    new = bpy.data.meshes.new_from_object(ev)
    old = target.data
    mats = list(old.materials)
    target.modifiers.clear()
    target.data = new
    for mt in mats:
        new.materials.append(mt)
    bpy.data.meshes.remove(old)
    for c in objs:
        bpy.data.objects.remove(c, do_unlink=True)


def join_bm(*bms):
    out = g.new_bm()
    for b in bms:
        me = bpy.data.meshes.new("tmp")
        b.to_mesh(me)
        b.free()
        out.from_mesh(me)
        bpy.data.meshes.remove(me)
    return out


def arc_text_cutter(body, radius, centre_deg, size, z, depth=0.07, spacing=0.86):
    """Letters laid along a circle of `radius`, reading left to right as seen from +Z. One mesh, ready for a boolean."""
    n = len(body)
    step = size * spacing / radius                                  # radians per letter
    meshes = []
    for i, ch in enumerate(body):
        if ch == " ":
            continue
        a = radians(centre_deg) + (n - 1) / 2 * step - i * step
        cu = bpy.data.curves.new("ch", "FONT")
        cu.body, cu.size, cu.align_x, cu.align_y, cu.extrude = ch, size, "CENTER", "CENTER", depth
        cu.resolution_u = 12
        tmp = bpy.data.objects.new("ch", cu)
        g.collection(COLL_ASM).objects.link(tmp)
        bpy.context.view_layer.update()
        me = bpy.data.meshes.new_from_object(tmp.evaluated_get(bpy.context.evaluated_depsgraph_get()))
        bpy.data.objects.remove(tmp, do_unlink=True)
        bpy.data.curves.remove(cu)
        me.transform(Matrix.Translation((radius * cos(a), radius * sin(a), z)) @ Matrix.Rotation(a - pi / 2, 4, "Z"))
        meshes.append(me)
    ob = bpy.data.objects.new("txt_cutter", meshes[0])
    g.collection(COLL_ASM).objects.link(ob)
    bm = bmesh.new()
    for me in meshes:
        bm.from_mesh(me)
    bm.to_mesh(ob.data)
    bm.free()
    for me in meshes[1:]:
        bpy.data.meshes.remove(me)
    return ob


GROOVE_EPS = 0.012     # the groove cutters sit this far into the material: a tube centred exactly on a face makes the exact boolean fail
LOGO_SVG = os.path.join(HERE, "..", "..", "..", "web", "public", "logo-line.svg")   # the four-blob mark, outlines only (D34)


def logo_cutters(size, cx, cy, z, mirror=False, stroke=0.09):
    """The Caseback mark as four thin grooves (the outlines of its blobs), `size` mm across, centred at (cx, cy).

    mirror=True for a face that is read from -Z (the skin face and the underside of the puck)."""
    import re
    if not os.path.exists(LOGO_SVG):
        print("logo not found, skipped:", LOGO_SVG)
        return []
    polys = []
    for d in re.findall(r' d="([^"]+)"', open(LOGO_SVG).read()):
        nums = [float(n) for n in re.findall(r"-?\d+\.?\d*", d)]
        polys.append([(nums[i], nums[i + 1]) for i in range(0, len(nums) - 1, 2)])
    xs = [q[0] for pl in polys for q in pl]
    ys = [q[1] for pl in polys for q in pl]
    xc, yc = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
    k = size / max(max(xs) - min(xs), max(ys) - min(ys))
    step = max(2, int(1.3 * stroke / k) + 1)                       # points at least a stroke apart, so the tube never folds on itself
    out = []
    for pl in polys:
        pts = pl[::step]
        cu = bpy.data.curves.new("logo", "CURVE")
        cu.dimensions, cu.bevel_depth, cu.bevel_resolution = "3D", stroke / 2, 2
        sp = cu.splines.new("POLY")
        sp.points.add(len(pts) - 1)
        for i, (x, y) in enumerate(pts):
            X, Y = (x - xc) * k, -(y - yc) * k
            sp.points[i].co = (cx + (-X if mirror else X), cy + Y, z, 1.0)
        sp.use_cyclic_u = True
        tmp = bpy.data.objects.new("logo", cu)
        g.collection(COLL_ASM).objects.link(tmp)
        bpy.context.view_layer.update()
        me = bpy.data.meshes.new_from_object(tmp.evaluated_get(bpy.context.evaluated_depsgraph_get()))
        bpy.data.objects.remove(tmp, do_unlink=True)
        bpy.data.curves.remove(cu)
        out.append(me)
    bm = bmesh.new()                                               # the blobs share their borders: one mesh, tubes overlapping
    for me in out:
        bm.from_mesh(me)
        bpy.data.meshes.remove(me)
    merged = bpy.data.meshes.new("logo_cutter")
    bm.to_mesh(merged)
    bm.free()
    ob = bpy.data.objects.new("logo_cutter", merged)
    ob["self_x"] = True                                            # bool_diff() turns on the exact solver's self-intersection
    g.collection(COLL_ASM).objects.link(ob)
    return [ob]


def bool_diff(target, cutter_objs, solver="EXACT"):
    """g.bool_diff, with the exact solver told to accept cutters that overlap themselves (the logo tubes)."""
    for i, c in enumerate(cutter_objs):
        m = target.modifiers.new(f"cut{i}", "BOOLEAN")
        m.operation, m.object, m.solver = "DIFFERENCE", c, solver
        if c.get("self_x"):
            m.use_self = True
    bpy.context.view_layer.update()
    ev = target.evaluated_get(bpy.context.evaluated_depsgraph_get())
    new = bpy.data.meshes.new_from_object(ev)
    old = target.data
    mats = list(old.materials)
    target.modifiers.clear()
    target.data = new
    for mt in mats:
        new.materials.append(mt)
    bpy.data.meshes.remove(old)
    for c in cutter_objs:
        bpy.data.objects.remove(c, do_unlink=True)


# ------------------------------------------------------------------ materials
def add_grain(mat, scale=70.0, strength=0.22, distance=0.015, rough_var=0.12):
    """Fine bead-blast grain: a noise bump, and a little variation in the roughness."""
    nt = mat.node_tree
    bsdf = nt.nodes["Principled BSDF"]
    coord = nt.nodes.new("ShaderNodeTexCoord")
    noise = nt.nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = scale
    noise.inputs["Detail"].default_value = 8.0
    noise.inputs["Roughness"].default_value = 0.65
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = strength
    bump.inputs["Distance"].default_value = distance
    nt.links.new(coord.outputs["Object"], noise.inputs["Vector"])
    nt.links.new(noise.outputs["Fac"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    base = bsdf.inputs["Roughness"].default_value
    mix = nt.nodes.new("ShaderNodeMapRange")
    mix.inputs["To Min"].default_value = max(base - rough_var, 0.05)
    mix.inputs["To Max"].default_value = min(base + rough_var, 1.0)
    nt.links.new(noise.outputs["Fac"], mix.inputs["Value"])
    nt.links.new(mix.outputs["Result"], bsdf.inputs["Roughness"])


def materials():
    M = g.materials()
    M["pcb"] = g.make_mat("pcb_soldermask_green", (0.012, 0.055, 0.042), rough=0.55)
    M["batt"] = g.make_mat("battery_foil_dull", (0.40, 0.42, 0.46), metallic=0.5, rough=0.55)
    M["module"] = g.make_mat("module_ISP1807", (0.035, 0.07, 0.13), rough=0.42)
    M["sfh"] = g.make_mat("sfh_body", (0.02, 0.02, 0.024), rough=0.5)
    M["steel"] = g.make_mat("steel_parts", (0.55, 0.57, 0.61), metallic=1.0, rough=0.33)
    M["slug"] = g.make_mat("steel_316L_slug", (0.30, 0.31, 0.34), metallic=1.0, rough=0.60)
    add_grain(M["slug"], scale=140.0, strength=0.25, distance=0.01, rough_var=0.08)      # a mirror finish would only show the lamps
    M["spring"] = g.make_mat("spring_contact", (0.95, 0.70, 0.28), metallic=0.8, rough=0.34)
    M["peek"] = g.make_mat("PEEK_black_blasted", (0.040, 0.042, 0.047), rough=0.66)
    M["peek_lid"] = g.make_mat("PEEK_black_lid", (0.046, 0.048, 0.054), rough=0.62)
    add_grain(M["peek"])
    add_grain(M["peek_lid"])
    M["window"] = g.make_mat("window_clear_resin", (0.30, 0.34, 0.31), rough=0.34, transmission=0.88, ior=1.52)
    M["gel"] = g.make_mat("optical_gel", (0.85, 0.9, 0.88), rough=0.05, transmission=0.9, ior=1.4, alpha=0.6)
    M["thermal"] = g.make_mat("thermal_pad", (0.46, 0.48, 0.52), rough=0.8)
    M["gasket"] = g.make_mat("gasket_silicone_grey", (0.30, 0.32, 0.35), rough=0.5)
    M["pad"] = g.pad_material()
    M["pad"].node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.11, 0.115, 0.13, 1.0)
    M["pad"].node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.9
    M["puck"] = g.make_mat("puck_black_ASA", (0.052, 0.055, 0.062), rough=0.55)
    add_grain(M["puck"], scale=18.0, strength=0.5, distance=0.03, rough_var=0.06)      # printed ASA: layer lines are not modelled, the grain is
    M["foot"] = g.make_mat("puck_foot_silicone", (0.02, 0.02, 0.022), rough=0.85)
    add_grain(M["foot"], scale=120.0, strength=0.3, distance=0.02, rough_var=0.05)
    M["usb"] = g.make_mat("usb_c_shell", (0.78, 0.79, 0.82), metallic=1.0, rough=0.26)
    M["usb_tongue"] = g.make_mat("usb_c_tongue", (0.012, 0.012, 0.015), rough=0.45)
    M["pogo"] = g.make_mat("pogo_nickel", (0.80, 0.80, 0.82), metallic=1.0, rough=0.22)
    M["pogo_spring"] = g.make_mat("pogo_spring_steel", (0.86, 0.86, 0.88), metallic=1.0, rough=0.18)
    M["wire"] = g.make_mat("wire_silicone_black", (0.012, 0.012, 0.014), rough=0.7)
    BP.materials(M)
    return M


# ------------------------------------------------------------------ polygon helpers (the cell is not round)
def poly_area2(pts):
    return sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in zip(pts, pts[1:] + pts[:1]))


def inset_poly(pts, d):
    """A convex polygon moved inwards by d, with mitred corners."""
    n = len(pts)
    sgn = 1.0 if poly_area2(pts) > 0 else -1.0
    lines = []
    for i in range(n):
        (x0, y0), (x1, y1) = pts[i], pts[(i + 1) % n]
        dx, dy = x1 - x0, y1 - y0
        ln = (dx * dx + dy * dy) ** 0.5
        lines.append(((x0 - dy / ln * sgn * d, y0 + dx / ln * sgn * d), (dx, dy)))
    out = []
    for i in range(n):
        (px, py), (dx0, dy0) = lines[i - 1]
        (qx, qy), (dx1, dy1) = lines[i]
        det = -dx0 * dy1 + dx1 * dy0
        t = ((qx - px) * -dy1 + dx1 * (qy - py)) / det
        out.append((px + t * dx0, py + t * dy0))
    return out


def clip_poly_y(pts, ymin):
    """The part of a convex polygon with y >= ymin."""
    out = []
    n = len(pts)
    for i in range(n):
        a, b = pts[i], pts[(i + 1) % n]
        ina, inb = a[1] >= ymin, b[1] >= ymin
        if ina:
            out.append(a)
        if ina != inb:
            t = (ymin - a[1]) / (b[1] - a[1])
            out.append((a[0] + t * (b[0] - a[0]), ymin))
    return out


def poly_prism(bm, pts, z0, z1, bevel=0.0, seg=2):
    """A prism on a convex polygon, from z0 to z1, with the outer edges rounded by `bevel`."""
    ccw = poly_area2(pts) > 0
    vb = [bm.verts.new((x, y, z0)) for x, y in pts]
    vt = [bm.verts.new((x, y, z1)) for x, y in pts]
    n = len(pts)
    bm.faces.new(vb[::-1] if ccw else vb)
    bm.faces.new(vt if ccw else vt[::-1])
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((vb[i], vb[j], vt[j], vt[i]) if ccw else (vb[j], vb[i], vt[i], vt[j]))
    if bevel > 0:
        edges = {e for v in vb + vt for e in v.link_edges}
        bmesh.ops.bevel(bm, geom=list(edges), offset=min(bevel, (z1 - z0) * 0.45), segments=seg, affect="EDGES")


# ------------------------------------------------------------------ shell (skin side)
def build_shell(M):
    r0 = B.R_CAV
    prof = [(0.0, 0.0), (R - 0.5, 0.0)] + g.arc(R - 0.5, 0.5, 0.5, -90, 0, 8)[1:] + \
           [(R, WALL_TOP - 0.08), (R - 0.08, WALL_TOP),                  # outer edge of the seam
            (r0 + 0.10, WALL_TOP), (r0, WALL_TOP - 0.10),                # lead-in at the inside of the rim
            (r0, GROOVE_Z[3]), (r0 + BEAD, GROOVE_Z[2]), (r0 + BEAD, GROOVE_Z[1]), (r0, GROOVE_Z[0]),     # the groove for the bead of the lid
            (r0, B.FLOOR), (0.0, B.FLOOR)]
    ob = g.obj_from_bm("Shell", g.revolve(prof, 200), M["peek"])
    sfh = next(p for p in B.ALL_PARTS if p.ref == "U2")
    cut = []
    for (ax, ay, aw, ah) in B.SFH_APERTURES:                      # three windows, the shell's own walls are the light barriers
        cut.append(box_cut((aw, ah, B.FLOOR + 0.4), (sfh.x + ax, sfh.y + ay, B.FLOOR / 2)))
    for x, y in B.CONTACTS:                                       # holes for the two charge slugs
        cut.append(cyl_cut(B.CONTACT_SLUG_D / 2 + 0.05, -0.1, B.FLOOR + 0.1, x, y, 40))
    cut.append(box_cut((B.NOTCH_W, NOTCH_DEPTH + 0.3, NOTCH_H + 0.2),    # key notch in the outer wall, at -Y, for the puck's key
                       (0.0, -(R - NOTCH_DEPTH + (NOTCH_DEPTH + 0.3) / 2), (NOTCH_H - 0.2) / 2)))
    bool_diff(ob, cut, "EXACT")

    b = g.new_bm()                                                # ribs that carry the board edge
    for a0, a1 in LEDGE_ANGLES:
        sec = g.sector(10.85, B.R_CAV + 0.05, a0, a1, B.FLOOR - 0.02, B.PCB_Z0)
        me = bpy.data.meshes.new("sec")
        sec.to_mesh(me)
        sec.free()
        b.from_mesh(me)
        bpy.data.meshes.remove(me)
    led = g.obj_from_bm("Shell_ledges", b, M["peek"], smooth=False)
    bool_union(ob, [led])                                         # one part: the shell with its ribs


def build_window_and_skin(M):
    sfh = next(p for p in B.ALL_PARTS if p.ref == "U2")
    w, gel = g.new_bm(), g.new_bm()
    for (ax, ay, aw, ah) in B.SFH_APERTURES:
        g.add_box(w, (aw - 0.04, ah - 0.04, B.FLOOR), (sfh.x + ax, sfh.y + ay, B.FLOOR / 2))
        g.add_box(gel, (aw - 0.04, ah - 0.04, WIN_GEL), (sfh.x + ax, sfh.y + ay, B.FLOOR + WIN_GEL / 2))
    g.obj_from_bm("Window_resin", w, M["window"], smooth=False)
    g.obj_from_bm("Window_gel", gel, M["gel"], smooth=False)
    t4 = next(p for p in B.ALL_PARTS if p.ref == "U4")             # skin temperature: a gap pad between the part and the floor
    b = g.new_bm()
    g.add_box(b, (t4.w + 0.5, t4.l + 0.5, B.PCB_Z0 - t4.h - B.FLOOR), (t4.x, t4.y, (B.PCB_Z0 - t4.h + B.FLOOR) / 2))
    g.obj_from_bm("Thermal_pad", b, M["thermal"], smooth=False)
    sl = g.new_bm()                                               # charge slugs: rivet-shaped 316L, flush on the skin face
    for x, y in B.CONTACTS:
        g.add_cyl(sl, B.CONTACT_SLUG_D / 2, 0.0, B.FLOOR, x, y, 40)
        g.add_cyl(sl, B.SLUG_HEAD_D / 2, B.FLOOR, B.FLOOR + B.SLUG_HEAD_T, x, y, 40)
    g.obj_from_bm("Slugs_316L", sl, M["slug"])
    ring = g.revolve([(GASKET[0], WALL_TOP), (GASKET[1], WALL_TOP), (GASKET[1], LID_IN), (GASKET[0], LID_IN)], 200)
    g.obj_from_bm("Seam_gasket", ring, M["gasket"], smooth=False)


# ------------------------------------------------------------------ board and cell
def build_cell(M):
    """Custom LiPo pouch cell in the cap of the disc: 1.5 mm thick, its protection board along the flat side that faces the
    board, two nickel tabs to the pads BT1 and BT2."""
    T, z0 = B.CELL_T, B.CELL_Z0
    poly = list(B.CELL_POLY)
    y_flat = min(y for _, y in poly)
    pcm_l = 2.0
    body = clip_poly_y(inset_poly(poly, 0.9), y_flat + pcm_l + 0.1)      # the filled part of the pouch
    bag = BP.Bag()
    poly_prism(bag["pouch"], body, z0, z0 + T, 0.25, 3)
    poly_prism(bag["pouch_seal"], poly, z0 + T / 2 - 0.15, z0 + T / 2 + 0.15, 0.05, 2)      # the seals, folded flat: thin foil
    pcm = g.new_bm()
    pcm_x = 8.9
    g.add_box(pcm, (2 * pcm_x, pcm_l - 0.2, 0.30), (0.0, y_flat + pcm_l / 2, z0 + T - 0.45))
    g.obj_from_bm("Cell_PCM", pcm, M["pcb"], smooth=False)
    for k, (dx, sz) in enumerate(((-5.6, (1.2, 0.7, 0.28)), (-1.4, (0.9, 0.5, 0.25)), (3.0, (1.0, 0.6, 0.26)), (6.2, (0.8, 0.5, 0.24)))):   # parts on it
        BP.rbox(bag["mold"], sz, (dx, y_flat + pcm_l / 2 - 0.1, z0 + T - 0.45 + 0.15 + sz[2] / 2), 0.04, 1)
    pads = [pd for pd in B.PADS if pd[0] in ("BT1", "BT2")]
    for ref, _side, _shape, px, py, _w, _h, _fn in pads:          # nickel tabs, bent up to the pads on the watch side of the board
        ya = y_flat + 0.4
        D = ya - py
        zt = B.PCB_Z1 + 0.06
        BP.sweep(bag["nickel"], [(0.0, z0 + T - 0.35), (0.5, z0 + T - 0.35), (0.9, zt), (D + 0.4, zt)], 1.0, 0.10, px, ya, -90)
        BP.blob(bag["tin"], (px, py, B.PCB_Z1 + 0.07), (0.75, 0.55, 0.05), 12, 6)
    for key, bm in bag.bms.items():
        mat = {"pouch": "pouch", "pouch_seal": "pouch_seal", "mold": "mold", "nickel": "nickel", "tin": "tin"}[key]
        g.obj_from_bm("Cell_" + key, bm, M[mat], smooth=key != "nickel")
    lab = g.new_bm()                                              # printed label on the watch side of the pouch
    poly_prism(lab, inset_poly(body, 0.8), z0 + T, z0 + T + 0.02)
    g.obj_from_bm("Cell_label", lab, g.make_mat("cell_label_white", (0.85, 0.85, 0.82), rough=0.5), smooth=False)
    ymid = sum(y for _, y in body) / len(body)
    txt = bpy.data.objects.new("Cell_label_text", BP.text_mesh(f"LiPo 3.7 V  {B.cell_mah():.0f} mAh", 0.9, 0.0, ymid, z0 + T + 0.032, rot=0.0, extrude=0.008))
    txt.data.materials.append(g.make_mat("label_ink", (0.02, 0.02, 0.02), rough=0.5))
    g.collection(COLL_ASM).objects.link(txt)
    f = g.new_bm()
    poly_prism(f, inset_poly(body, 0.4), z0 + T + 0.03, z0 + T + 0.03 + B.FOAM_T, 0.06, 2)
    g.obj_from_bm("Foam_cell", f, M["foam"])


# ------------------------------------------------------------------ lid (watch side)
def build_lid(M):
    prof = [(0.0, LID_IN), (SK_IN, LID_IN), (SK_IN, SK_Z0), (SK_OUT - 0.10, SK_Z0), (SK_OUT, SK_Z0 + 0.08),      # underside, inside of the skirt, its tip
            (SK_OUT, BEAD_Z[0]), (SK_OUT + BEAD, BEAD_Z[1]), (SK_OUT + BEAD, BEAD_Z[2]), (SK_OUT, BEAD_Z[3]),    # the bead: 45 degrees to go in, 60 from the axis to come out
            (SK_OUT, LID_IN), (LIP_R, LID_IN), (LIP_R, WALL_TOP), (R - 0.08, WALL_TOP), (R, WALL_TOP + 0.08),   # outside of the skirt, the lip that lands on the wall
            (R, H - 0.3)] + g.arc(R - 0.3, H - 0.3, 0.3, 0, 90, 8)[1:] + [(R_RECESS, H), (R_RECESS, H - PAD_T), (0.0, H - PAD_T)]
    if FLAT_FACE:
        prof = prof[:prof.index((R, H - 0.3))] + [(R, H), (0.0, H)]
    lid = g.obj_from_bm("Lid", g.revolve(prof, 200), M["peek_lid"])
    if ENGRAVE:                                                    # generate_mock.py turns it off: 0.07 mm lines cannot be printed with a 0.4 mm nozzle
        cut = [arc_text_cutter("CASEBACK", 10.35, 90.0, 1.2, H)]
        cut += logo_cutters(3.2, 10.35 * cos(radians(-90.0)), 10.35 * sin(radians(-90.0)), H - GROOVE_EPS, mirror=False, stroke=0.07)
        bool_diff(lid, cut, "EXACT")
    b = g.new_bm()                                                 # a small foot over each rib: the board cannot lift off its ribs
    for a0, a1 in LEDGE_ANGLES:
        sec = g.sector(FOOT_R[0], FOOT_R[1], a0, a1, B.PCB_Z1 + 0.03, LID_IN + 0.05)
        me = bpy.data.meshes.new("sec")
        sec.to_mesh(me)
        sec.free()
        b.from_mesh(me)
        bpy.data.meshes.remove(me)
    bool_union(lid, [g.obj_from_bm("Lid_feet", b, M["peek_lid"], smooth=False)])

    top = H + B.PAD_PROUD                                          # microsuction pad, 0.4 mm in a 0.3 mm recess: 0.1 mm proud
    b = g.new_bm()
    g.add_cyl(b, R_RECESS - 0.05, H - PAD_T, top, 0, 0, 160)
    g.obj_from_bm("Microsuction_pad", b, M["pad"])


def build_all():
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob, do_unlink=True)
    sc = bpy.context.scene
    sc.unit_settings.system, sc.unit_settings.scale_length, sc.unit_settings.length_unit = "METRIC", 0.001, "MILLIMETERS"
    M = materials()
    build_shell(M)
    build_window_and_skin(M)
    BP.import_board(M)
    BP.build_parts(M)
    build_cell(M)
    build_lid(M)
    for ob in g.collection(COLL_ASM).objects:
        g.autosmooth(ob, 12.0 if ob.name in ("Shell", "Lid") else 30.0)       # a low angle keeps the flat faces flat around the grooves
    return M


# ------------------------------------------------------------------ puck
def pogo_pins(M, coll, tip_z, name="Puck_pogo_pins"):
    """Two spring pins on the puck board. tip_z is the height of the plunger tip: P_FLOOR + POGO_FREE free, P_FLOOR pressed.

    Each pin is a hollow barrel with a flange, a coil spring and a plunger with a rounded tip, so a section shows how it works."""
    z_bar0, z_bar1 = 1.4, P_FLOOR - 0.75
    stroke = max(0.0, (P_FLOOR + POGO_FREE) - tip_z)                  # how far the plunger is pushed in
    barrel = g.new_bm()
    plunger = g.new_bm()
    spring = g.new_bm()
    for x, y in B.CONTACTS:
        r_i, r_lip = POGO_R - 0.07, POGO_PLUNGER_R + 0.03
        prof = [(r_i, z_bar0), (POGO_R, z_bar0), (POGO_R, z_bar1), (r_lip, z_bar1 + 0.10), (r_lip, z_bar1 - 0.05), (r_i, z_bar1 - 0.05)]
        ring = g.revolve([(r, z) for r, z in prof], 28)
        me = bpy.data.meshes.new("tmp")
        ring.to_mesh(me)
        ring.free()
        me.transform(Matrix.Translation((x, y, 0)))
        barrel.from_mesh(me)
        bpy.data.meshes.remove(me)
        g.add_cyl(barrel, POGO_R + 0.06, z_bar0, z_bar0 + 0.14, x, y, 28)             # flange where it sits on the board
        ztip = tip_z - 0.10
        g.add_cyl(plunger, POGO_PLUNGER_R, z_bar1 - 1.0 + 0.25 * stroke, ztip, x, y, 24)
        g.add_cyl(plunger, POGO_PLUNGER_R + 0.07, z_bar1 - 0.55 + stroke, z_bar1 - 0.3 + stroke, x, y, 24)
        bmesh.ops.create_uvsphere(plunger, u_segments=24, v_segments=8, radius=POGO_PLUNGER_R,
                                  matrix=Matrix.Translation((x, y, ztip)) @ Matrix.Diagonal((1, 1, 0.38, 1)))
        turns, n = 6, 6 * 18
        zs0, zs1 = z_bar0 + 0.2, z_bar1 - 0.55 + stroke
        pts = [(x + 0.30 * cos(2 * pi * turns * i / n), y + 0.30 * sin(2 * pi * turns * i / n), zs0 + (zs1 - zs0) * i / n) for i in range(n + 1)]
        BP.tube(spring, pts, 0.045, 6)
    g.obj_from_bm(name + "_barrels", barrel, M["pogo"], coll)
    g.obj_from_bm(name + "_springs", spring, M["pogo_spring"], coll)
    return g.obj_from_bm(name, plunger, M["gold"], coll)


def build_puck(M):
    coll = g.collection(COLL_PUCK)
    prof = [(0.0, 0.0), (P_R - 0.8, 0.0)] + g.arc(P_R - 0.8, 0.8, 0.8, -90, 0, 8)[1:] + [(P_R, P_H - 0.5)] + \
           g.arc(P_R - 0.5, P_H - 0.5, 0.5, 0, 90, 6)[1:] + [(DISH_R + 0.4, P_H), (DISH_R, P_H - 0.4), (DISH_R, P_FLOOR),
                                                           (0.0, P_FLOOR)]
    body = g.obj_from_bm("Puck_body", g.revolve(prof, 200), M["puck"], coll)
    cut = logo_cutters(2.4, (P_R - 2.1) * cos(radians(225)), (P_R - 2.1) * sin(radians(225)), P_H - GROOVE_EPS, mirror=False, stroke=0.07) if ENGRAVE else []
    cut += [cyl_cut(POCKET_R, -0.1, 1.55, 0, 0, 96),                # pocket for the board, open at the bottom
            box_cut((9.6, 7.9, 4.25), (0.0, 12.25, 2.655)),         # cavity for the receptacle and the tab of the board under it
            box_cut((12.0, 2.0, 4.6), (0.0, USB_FLAT_Y + 1.0, USB_Z))]      # a flat on the rim: the cylinder meets y = 15.9 at x = +-6
    for x, y in B.CONTACTS:
        cut.append(cyl_cut(0.62, 1.4, P_FLOOR + 0.1, x, y, 24))
    bool_diff(body, cut, "EXACT")

    base = g.new_bm()
    g.add_cyl(base, PLATE_R, 0.0, 0.6, 0, 0, 96)
    plate = g.obj_from_bm("Puck_base_plate", base, M["puck"], coll)
    if ENGRAVE:
        bool_diff(plate, logo_cutters(10.0, 0.0, 0.0, GROOVE_EPS, mirror=True, stroke=0.12), "EXACT")
    foot = g.revolve([(PLATE_R + 0.6, -0.5), (P_R - 0.8, -0.5), (P_R - 0.8, 0.0), (PLATE_R + 0.6, 0.0)], 200)
    g.obj_from_bm("Puck_foot", foot, M["foot"], coll)

    key = g.new_bm()                                               # key tab: enters the notch in the outer wall of the disc
    g.add_box(key, (2.6, 0.7, 1.1), (0.0, -(R - NOTCH_DEPTH + 0.15 + 0.35), P_FLOOR + 0.55))
    g.obj_from_bm("Puck_key", key, M["puck"], coll, smooth=False)
    pc = g.new_bm()                                                # puck board: round, with a tab for the USB-C socket
    g.add_cyl(pc, PUCK_BOARD_R, 0.6, 1.4, 0, 0, 96)
    pcb = g.obj_from_bm("Puck_pcb", pc, M["pcb"], coll)
    tab = g.new_bm()
    g.add_box(tab, (9.3, 3.6, 0.8), (0.0, 13.7, 1.0))
    bool_union(pcb, [g.obj_from_bm("tab", tab, smooth=False)])      # one solid, so the section cut sees a closed mesh
    zc_u = USB_Z
    y_front = USB_FLAT_Y - 0.1                                     # the face of the receptacle, 0.1 mm behind the flat
    usb = g.new_bm()                                               # USB-C receptacle: rounded shell 8.94 x 3.26, tongue, 12 contacts a side
    poly_prism(usb, rounded_rect(8.94, 3.26, 1.0), 0.0, 7.3)
    usb.transform(Matrix.Translation((0.0, y_front, zc_u)) @ Matrix.Rotation(pi / 2, 4, "X"))      # local z runs back from the face, local y is up
    shell = g.obj_from_bm("Puck_usb_c", usb, M["usb"], coll, smooth=False)
    bool_diff(shell, [stadium_cut(8.34, 2.56, y_front - 7.3 + 0.05, y_front + 0.1, 0.0, zc_u)], "EXACT")
    tg = g.new_bm()
    g.add_box(tg, (6.7, 5.6, 0.70), (0.0, y_front - 3.0 - 0.7, zc_u))
    g.obj_from_bm("Puck_usb_tongue", tg, M["usb_tongue"], coll, smooth=False)
    pins = g.new_bm()
    for k in range(12):
        xk = -2.75 + 0.5 * k
        for sz in (-1, 1):
            g.add_box(pins, (0.20, 4.2, 0.03), (xk, y_front - 3.0 - 0.55 - 0.0 - 0.1, zc_u + sz * 0.355))
    g.obj_from_bm("Puck_usb_contacts", pins, M["gold"], coll, smooth=False)
    for k in range(4):                                             # four small screws hold the base plate
        a = radians(45 + 90 * k)
        sx, sy = 12.0 * cos(a), 12.0 * sin(a)
        scr = g.new_bm()
        g.add_cyl(scr, 1.35, -0.42, 0.05, sx, sy, 32)
        sc = g.obj_from_bm(f"Puck_plate_screw_{k}", scr, M["steel"], coll)
        bool_diff(sc, [box_cut((2.2, 0.35, 0.3), (sx, sy, -0.40), 45 + 90 * k)], "EXACT")
    pogo_pins(M, coll, P_FLOOR + POGO_FREE)
    for ob in coll.objects:
        g.autosmooth(ob)


DOCK_CUT_X = B.CONTACTS[1][0] + 0.011                                # the section through the right charge contact, 0.011 mm off its axis: on the axis the boolean drops the barrel and the plunger
DOCK_T = Matrix.Translation((0, 0, P_FLOOR))                       # skin face down on the dish floor, nothing turned over


def copy_collection(src, dst, matrix=None):
    for ob in list(dst.objects):
        bpy.data.objects.remove(ob, do_unlink=True)
    for ob in src.objects:
        cp = ob.copy()
        cp.data = ob.data.copy()
        if matrix is not None:
            cp.matrix_world = matrix @ ob.matrix_world
        dst.objects.link(cp)


def cut_half(coll, x_cut):
    for ob in list(coll.objects):
        crosses = ob.type == "MESH" and any((ob.matrix_world @ v.co).x < x_cut - 0.05 for v in ob.data.vertices)
        cutter = box_cut((60.0, 120.0, 40.0), (x_cut + 30.0, 0.0, 5.0))
        cutter["self_x"] = True                                     # the pins are built from overlapping solids: without this the exact solver drops the half it cuts
        bool_diff(ob, [cutter], "EXACT")
        if crosses and not ob.data.vertices:
            print(f"WARNING: {ob.name} vanished in the section cut (open or self-overlapping mesh)")


EXPLODE = (("Window", -4.0), ("Slugs", -4.0), ("Shell", 0.0), ("Thermal", 1.6), ("Seam", 9.0), ("PCB", 3.4),
           ("Skin_", 3.4), ("Pads_", 3.4), ("Cell", 3.4), ("Foam", 6.0), ("Lid", 12.0), ("Microsuction", 15.5))




def build_variants(M):
    asm = g.collection(COLL_ASM)
    dst = g.collection(COLL_EXP)
    for ob in list(dst.objects):
        bpy.data.objects.remove(ob, do_unlink=True)
    for ob in asm.objects:
        cp = ob.copy()
        cp.location.z += next((d for p, d in EXPLODE if ob.name.startswith(p)), 0.0)
        dst.objects.link(cp)
    board = g.collection(COLL_BOARD)
    for ob in list(board.objects):
        bpy.data.objects.remove(ob, do_unlink=True)
    for ob in asm.objects:
        if ob.name.startswith(("PCB", "Skin_", "Pads_", "Cell", "Foam", "Thermal")):
            board.objects.link(ob.copy())
    copy_collection(asm, g.collection(COLL_SEC))
    cut_half(g.collection(COLL_SEC), 3.2)
    build_puck(M)
    copy_collection(g.collection(COLL_PUCK), g.collection(COLL_PSEC))
    for ob in list(g.collection(COLL_PSEC).objects):                # the cut at x = 0 does not touch the pins (x = +-9): leave them out
        if ob.name.startswith("Puck_pogo_pins"):
            bpy.data.objects.remove(ob, do_unlink=True)
    cut_half(g.collection(COLL_PSEC), 0.0)                          # through the middle of the USB-C receptacle
    copy_collection(asm, g.collection(COLL_DOCK), DOCK_T)
    dock = g.collection(COLL_DOCK)
    for ob in g.collection(COLL_PUCK).objects:
        if not ob.name.startswith("Puck_pogo_pins"):
            dock.objects.link(ob.copy())
    pogo_pins(M, dock, P_FLOOR, "Puck_pogo_pins_pressed")           # pressed flush by the weight of the watch
    copy_collection(g.collection(COLL_DOCK), g.collection(COLL_DSEC))
    cut_half(g.collection(COLL_DSEC), DOCK_CUT_X)


# ------------------------------------------------------------------ files
def write_stl(ob, path: str) -> int:
    me = ob.data
    me.calc_loop_triangles()
    tris = me.loop_triangles
    with open(path, "wb") as f:
        f.write(b"Caseback disc, millimetres".ljust(80, b" "))
        f.write(struct.pack("<I", len(tris)))
        for t in tris:
            a, b, c = (ob.matrix_world @ me.vertices[i].co for i in t.vertices)
            n = (b - a).cross(c - a)
            n = n.normalized() if n.length > 0 else n
            f.write(struct.pack("<12fH", n.x, n.y, n.z, *a, *b, *c, 0))
    return len(tris)


def build_dummy(M):
    """Solid disc of the same outline, with the pad recess and the key notch, for the microsuction tests.
    No cavity: it is a weight on the pad. Print it in PETG at full infill and add a washer to reach the weight to test."""
    prof = [(0.0, 0.0), (R - 0.5, 0.0)] + g.arc(R - 0.5, 0.5, 0.5, -90, 0, 8)[1:] + [(R, H - 0.3)] + \
           g.arc(R - 0.3, H - 0.3, 0.3, 0, 90, 8)[1:] + [(R_RECESS, H), (R_RECESS, H - PAD_T), (0.0, H - PAD_T)]
    ob = g.obj_from_bm("Fit_dummy", g.revolve(prof, 200), M["peek"], g.collection("Dummy"))
    cut = [box_cut((B.NOTCH_W, NOTCH_DEPTH + 0.3, NOTCH_H + 0.2), (0.0, -(R - NOTCH_DEPTH + (NOTCH_DEPTH + 0.3) / 2), (NOTCH_H - 0.2) / 2))]
    bool_diff(ob, cut, "EXACT")
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    vol = bm.calc_volume()
    bm.free()
    print(f"fit dummy volume {vol:.0f} mm3, {vol * 1.27e-3:.2f} g in PETG at full infill")
    return ob


STL_PARTS = {"disc_shell": "Shell", "disc_lid": "Lid", "puck_body": "Puck_body", "puck_base_plate": "Puck_base_plate",
             "puck_key": "Puck_key"}


def export_stl(out, M):
    os.makedirs(out, exist_ok=True)
    info = {}
    for fname, oname in STL_PARTS.items():
        ob = bpy.data.objects.get(oname)
        if ob:
            info[fname] = write_stl(ob, os.path.join(out, fname + ".stl"))
    d = build_dummy(M)
    info["disc_fit_dummy"] = write_stl(d, os.path.join(out, "disc_fit_dummy.stl"))
    bpy.data.objects.remove(d, do_unlink=True)
    print("stl:", info)


# ------------------------------------------------------------------ render
def setup_render(w=1800, h=1350, samples=96):
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.render.image_settings.file_format = "JPEG"          # PNG of a denoised render is 3 MB; JPEG at 92 is a fifth of it
    sc.render.image_settings.quality = 92
    sc.cycles.samples = samples
    sc.cycles.use_denoising = True
    sc.cycles.device = "CPU"
    sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = w, h, 100
    sc.view_settings.view_transform = "Standard"
    wd = bpy.data.worlds.new("wdisc")
    wd.use_nodes = True
    bg = wd.node_tree.nodes["Background"]
    bg.inputs[0].default_value = (0.045, 0.047, 0.052, 1.0)       # dark studio, the project's own black
    bg.inputs[1].default_value = 1.0
    sc.world = wd


def make_camera():
    """Camera with a key light, a fill and a rim light that follow it, so the edge profile and the seam read."""
    cam_d = bpy.data.cameras.new("cam")
    cam = bpy.data.objects.new("cam", cam_d)
    bpy.context.scene.collection.objects.link(cam)
    bpy.context.scene.camera = cam
    tgt = bpy.data.objects.new("tgt", None)
    bpy.context.scene.collection.objects.link(tgt)
    con = cam.constraints.new("TRACK_TO")
    con.target, con.track_axis, con.up_axis = tgt, "TRACK_NEGATIVE_Z", "UP_Y"
    for name, power, ang, rot in (("key", 4.5, 8, (radians(42), radians(-34), 0)), ("fill", 1.3, 30, (radians(-20), radians(46), 0)),
                                  ("rim", 6.0, 4, (radians(-58), radians(150), 0)), ("top", 1.6, 20, (radians(70), radians(6), 0))):
        ld = bpy.data.lights.new(name, "SUN")
        ld.energy, ld.angle = power, radians(ang)
        lo = bpy.data.objects.new(name, ld)
        bpy.context.scene.collection.objects.link(lo)
        lo.parent = cam
        lo.rotation_euler = rot
    return cam, tgt


def build_studio(cam, cam_target):
    """For the puck shots: a dark floor with a soft pool of light on it, and three soft boxes round the camera, so that the
    steel and the gold of the receptacle and the pins have something to reflect whichever way the shot looks."""
    coll = g.collection(COLL_STUDIO)
    for ob in list(coll.objects):
        bpy.data.objects.remove(ob, do_unlink=True)
    fl = g.new_bm()
    g.add_cyl(fl, 400.0, -2.0, -0.5, 0, 0, 96)
    mat = g.make_mat("studio_floor", (0.05, 0.052, 0.058), rough=0.62)
    nt = mat.node_tree
    coord, mp = nt.nodes.new("ShaderNodeTexCoord"), nt.nodes.new("ShaderNodeMapping")
    grad, ramp = nt.nodes.new("ShaderNodeTexGradient"), nt.nodes.new("ShaderNodeValToRGB")
    mp.inputs["Scale"].default_value = (1 / 210.0,) * 3
    grad.gradient_type = "SPHERICAL"
    ramp.color_ramp.elements[0].color = (0.016, 0.017, 0.020, 1.0)
    ramp.color_ramp.elements[1].color = (0.070, 0.073, 0.082, 1.0)
    nt.links.new(coord.outputs["Object"], mp.inputs["Vector"])
    nt.links.new(mp.outputs["Vector"], grad.inputs["Vector"])
    nt.links.new(grad.outputs["Fac"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], nt.nodes["Principled BSDF"].inputs["Base Color"])
    g.obj_from_bm("Studio_floor", fl, mat, coll)
    # position in the camera's frame (x right, y up, z behind it), size, power: a radiance of about 3, bright in a reflection and
    # little light on the object itself
    for name, loc, size, power in (("soft_key", (-55.0, 45.0, 30.0), (70.0, 50.0), 3.3e4),
                                   ("soft_strip", (60.0, 5.0, 30.0), (20.0, 70.0), 1.3e4),
                                   ("soft_top", (0.0, 70.0, 20.0), (100.0, 30.0), 2.8e4)):
        ld = bpy.data.lights.new(name, "AREA")
        ld.shape, ld.size, ld.size_y, ld.energy = "RECTANGLE", size[0], size[1], power
        lo = bpy.data.objects.new(name, ld)
        coll.objects.link(lo)
        lo.parent = cam
        lo.location = loc
        lo.visible_camera = False
        con = lo.constraints.new("TRACK_TO")
        con.target, con.track_axis, con.up_axis = cam_target, "TRACK_NEGATIVE_Z", "UP_Y"


SHOTS = {
    # name: (collections, target, distance, azimuth, elevation, (width, height))
    "disc_skin_side": ([COLL_ASM], (0, 0, 1.5), 78, 180, -52, (1800, 1350)),
    "disc_watch_side": ([COLL_ASM], (0, 0, 1.5), 78, 0, 52, (1800, 1350)),
    "disc_edge": ([COLL_ASM], (0, -12.5, 1.5), 40, 12, 14, (1800, 1000)),
    "disc_exploded": ([COLL_EXP], (0, 0, 7.5), 105, 0, 30, (1800, 1350)),
    "disc_section": ([COLL_SEC], (0.0, 0, 1.3), 70, 90, 17, (1800, 900)),
    "disc_puck": ([COLL_PUCK], (0, 2, 3.0), 108, 200, 34, (1800, 1350)),
    "disc_puck_usb": ([COLL_PUCK], (0, 16.0, USB_Z), 40, 180, 9, (1800, 1200)),
    "disc_puck_section": ([COLL_PSEC], (0.0, 0.0, 3.4), 100, 90, 12, (1800, 1000)),
    "disc_docked": ([COLL_DOCK], (0, 0, 4.5), 85, 22, 30, (1800, 1350)),
    "disc_docked_section": ([COLL_DSEC], (DOCK_CUT_X, -1.0, 4.5), 62, 90, 12, (1800, 900)),
    "disc_contact_section": ([COLL_DSEC], (DOCK_CUT_X, -1.0, 4.6), 34, 90, 5, (1800, 1000)),
    "disc_skin_contacts": ([COLL_ASM], (0, -1.0, 0.2), 52, 180, -50, (1800, 1100)),
    "board_skin": ([COLL_BOARD], (0, -0.5, 1.2), 52, 180, -84, (1800, 1800)),
    "board_watch": ([COLL_BOARD], (0, -0.5, 1.9), 52, 0, 84, (1800, 1800)),
    "board_oblique": ([COLL_BOARD], (0, -0.5, 1.4), 48, 160, -38, (1800, 1350)),
    "board_detail": ([COLL_BOARD], (2.0, -1.0, 1.0), 22, 205, -48, (1800, 1200)),
}


def aim(cam, tgt, collections, target, dist, azim, elev, lens=85):
    """Show only `collections` and put the camera on a shot, without rendering."""
    studio = any(c in collections for c in (COLL_PUCK, COLL_DOCK, COLL_DSEC, COLL_PSEC))
    for c in (COLL_ASM, COLL_EXP, COLL_SEC, COLL_BOARD, COLL_PUCK, COLL_DOCK, COLL_DSEC, COLL_PSEC, COLL_STUDIO):
        coll = bpy.data.collections.get(c)
        if coll:
            coll.hide_render = coll.hide_viewport = not (studio if c == COLL_STUDIO else c in collections)
    cam.data.lens = lens
    cam.data.clip_start, cam.data.clip_end = 1.0, 2000.0
    az, el = radians(azim), radians(elev)
    cam.location = (target[0] + dist * cos(el) * sin(az), target[1] - dist * cos(el) * cos(az), target[2] + dist * sin(el))
    tgt.location = target
    bpy.context.view_layer.update()


def shot(cam, tgt, path, collections, target, dist, azim, elev, lens=85):
    aim(cam, tgt, collections, target, dist, azim, elev, lens)
    bpy.context.scene.render.filepath = path
    bpy.ops.render.render(write_still=True)
    print("rendered", path)


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    out = argv[argv.index("--render") + 1] if "--render" in argv else None
    only = argv[argv.index("--only") + 1].split(",") if "--only" in argv else None
    stl = argv[argv.index("--stl") + 1] if "--stl" in argv else None
    blend = argv[argv.index("--blend") + 1] if "--blend" in argv else None
    samples = int(argv[argv.index("--samples") + 1]) if "--samples" in argv else 96
    scale = float(argv[argv.index("--scale") + 1]) if "--scale" in argv else 1.0           # 0.5 for quick test renders
    M = build_all()
    zs = [(o.matrix_world @ vv.co).z for o in g.collection(COLL_ASM).objects for vv in o.data.vertices]
    print(f"disc z range {min(zs):.3f} .. {max(zs):.3f} (thickness {B.H})")
    build_variants(M)
    if stl:
        export_stl(stl, M)
    if out or blend:
        setup_render(samples=samples)
        cam, tgt = make_camera()
        build_studio(cam, tgt)
    if out:
        os.makedirs(out, exist_ok=True)
        for name, (colls, target, dist, az, el, size) in SHOTS.items():
            if only and name not in only:
                continue
            bpy.context.scene.render.resolution_x, bpy.context.scene.render.resolution_y = int(size[0] * scale), int(size[1] * scale)
            shot(cam, tgt, os.path.join(out, name + ".jpg"), colls, target, dist, az, el)
    if blend:
        # opens on the assembled disc seen from the watch side; the other views (exploded, sections, board alone, puck,
        # docked) are collections that are hidden: switch them on in the outliner (viewport and render eye icons)
        colls, target, dist, az, el, size = SHOTS["disc_watch_side"]
        aim(cam, tgt, colls, target, dist, az, el)
        bpy.context.scene.render.resolution_x, bpy.context.scene.render.resolution_y = size
        bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(blend))


if __name__ == "__main__":
    main()
