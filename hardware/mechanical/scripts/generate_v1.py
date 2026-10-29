"""Caseback V1 sensor disc: detailed concept model (Blender 4.x / 5.x).

Run inside Blender (Scripting > Open > Run Script) or headless:
    blender -b --python generate_v1.py -- [--blend FILE]
Without --blend the scene is only built (and the stats and stack budget printed).

Units: 1 Blender unit = 1 mm (scene unit scale 0.001, so STL/OBJ export comes out in mm).
Axes: Z = 0 is the skin face, +Z goes towards the watch caseback.

Everything here is a CONCEPT built from the V1 targets in hardware/mechanical/README.md
(Ø32 mm, 2.7 mm thick, IP67, replaceable microsuction pad, custom PCB). Component sizes are
typical package sizes, not a released design: the PCB does not exist yet (hardware/v1-pcb/).

See stack_budget() for the numbers computed from the constants below.
"""

from __future__ import annotations

import math
import os
import sys
from math import cos, pi, radians, sin

import bmesh
import bpy
from mathutils import Matrix

# ------------------------------------------------------------------ dimensions (mm)
D = 32.0                 # outer diameter
H = 2.7                  # total thickness
R = D / 2
FLOOR = 0.4              # skin-side floor thickness
SEAM_Z = 2.1             # parting line shell / lid
LID_T = H - SEAM_Z       # 0.6; 0.3 remains over the pad recess
WALL_IN = 15.2           # inner radius of the shell rim (wall 0.8)
PAD_R = 11.0             # microsuction recess radius (Ø22)
PAD_T = 0.3
WIN_R = 2.0              # PPG window Ø4.0
PCB_Z0, PCB_T, PCB_R = 0.85, 0.4, 14.5
PCB_Z1 = PCB_Z0 + PCB_T
BATT = (18.0, 9.0, 1.5)  # thin pouch cell that fits the 2.7 mm stack: ~243 mm3, ~16 mAh
BATT_C = (0.0, -7.2)
BATT_Z0 = 0.45
CONTACT_XY = ((-4.0, 13.0), (4.0, 13.0))   # charge pads on the skin face at battery voltage, 8 mm pitch like the V0 puck
NTC_XY = (7.0, 0.0)

COLL_ASM = "Caseback_V1_Assembled"
COLL_EXP = "Caseback_V1_Exploded"
COLL_SEC = "Caseback_V1_Section"


# ------------------------------------------------------------------ geometry helpers
def new_bm() -> bmesh.types.BMesh:
    return bmesh.new()


def add_box(bm, size, center, rot=0.0):
    m = Matrix.Translation(center) @ Matrix.Rotation(radians(rot), 4, "Z") @ Matrix.Diagonal((*size, 1.0))
    bmesh.ops.create_cube(bm, size=1.0, matrix=m)


def add_cyl(bm, r, z0, z1, x=0.0, y=0.0, seg=48):
    bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=seg, radius1=r, radius2=r,
                          depth=z1 - z0, matrix=Matrix.Translation((x, y, (z0 + z1) / 2)))


def prism(poly, z0, z1):
    bm = new_bm()
    f = bm.faces.new([bm.verts.new((x, y, z0)) for x, y in poly])
    res = bmesh.ops.extrude_face_region(bm, geom=[f])
    top = [g for g in res["geom"] if isinstance(g, bmesh.types.BMVert)]
    bmesh.ops.translate(bm, verts=top, vec=(0, 0, z1 - z0))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return bm


def arc(cx, cz, r, a0, a1, n=8):
    return [(cx + r * cos(radians(a0 + (a1 - a0) * i / n)), cz + r * sin(radians(a0 + (a1 - a0) * i / n)))
            for i in range(n + 1)]


def revolve(profile, seg=160):
    """Closed (r, z) profile spun 360 degrees around Z."""
    bm = new_bm()
    vs = [bm.verts.new((r, 0.0, z)) for r, z in profile]
    es = [bm.edges.new((vs[i], vs[(i + 1) % len(vs)])) for i in range(len(vs))]
    bmesh.ops.spin(bm, geom=vs + es, cent=(0, 0, 0), axis=(0, 0, 1), angle=2 * pi, steps=seg,
                   use_merge=True, use_duplicate=False)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-4)
    bmesh.ops.dissolve_degenerate(bm, dist=1e-5, edges=bm.edges)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return bm


def sector(r0, r1, a0, a1, z0, z1, n=10):
    outer = [(r1 * cos(radians(a0 + (a1 - a0) * i / n)), r1 * sin(radians(a0 + (a1 - a0) * i / n))) for i in range(n + 1)]
    inner = [(r0 * cos(radians(a1 - (a1 - a0) * i / n)), r0 * sin(radians(a1 - (a1 - a0) * i / n))) for i in range(n + 1)]
    return prism(outer + inner, z0, z1)


def stadium(half_w, y0, y1, n=14):
    """Rounded tab: rectangle up to y1 - half_w plus a half circle."""
    yc = y1 - half_w
    pts = [(-half_w, y0), (half_w, y0)]
    pts += [(half_w * cos(radians(a)), yc + half_w * sin(radians(a))) for a in range(0, 181, 180 // n)]
    return prism(pts, 0.0, 1.0)


def shift(bm, dz):
    bmesh.ops.translate(bm, verts=bm.verts, vec=(0, 0, dz))


# ------------------------------------------------------------------ scene helpers
def collection(name):
    c = bpy.data.collections.get(name)
    if c is None:
        c = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(c)
    return c


def obj_from_bm(name, bm, mat=None, coll=None, smooth=True):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    if smooth:
        for p in me.polygons:
            p.use_smooth = True
    ob = bpy.data.objects.new(name, me)
    (coll or collection(COLL_ASM)).objects.link(ob)
    if mat:
        ob.data.materials.append(mat)
    return ob


def autosmooth(ob, angle=30.0):
    """Smooth shading with sharp edges above `angle` (replacement for the removed auto-smooth)."""
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    lim = radians(angle)
    for f in bm.faces:
        f.smooth = True
    for e in bm.edges:
        if len(e.link_faces) != 2 or e.calc_face_angle(0.0) > lim:
            e.smooth = False
    bm.to_mesh(ob.data)
    bm.free()


def bool_diff(target, cutter_objs, solver="EXACT"):
    for i, c in enumerate(cutter_objs):
        m = target.modifiers.new(f"cut{i}", "BOOLEAN")
        m.operation, m.object, m.solver = "DIFFERENCE", c, solver
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


def text_cutter(body, size, xy, z, mirror=False):
    cu = bpy.data.curves.new("txt", "FONT")
    cu.body, cu.size, cu.align_x, cu.align_y, cu.extrude = body, size, "CENTER", "CENTER", 0.06
    cu.resolution_u = 16
    tmp = bpy.data.objects.new("txt", cu)
    collection(COLL_ASM).objects.link(tmp)
    bpy.context.view_layer.update()
    me = bpy.data.meshes.new_from_object(tmp.evaluated_get(bpy.context.evaluated_depsgraph_get()))
    bpy.data.objects.remove(tmp, do_unlink=True)
    bpy.data.curves.remove(cu)
    me.transform(Matrix.Translation((xy[0], xy[1], z)) @ Matrix.Diagonal((-1.0 if mirror else 1.0, 1.0, 1.0, 1.0)))
    if mirror:
        me.flip_normals()
    ob = bpy.data.objects.new("txt_cutter", me)
    collection(COLL_ASM).objects.link(ob)
    return ob


# ------------------------------------------------------------------ materials
def make_mat(name, color, metallic=0.0, rough=0.5, transmission=0.0, emission=None, ior=1.45, alpha=1.0):
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    try:
        mat.use_nodes = True
    except Exception:  # noqa: BLE001 - always on in newer Blender
        pass
    nt = mat.node_tree
    bsdf = nt.nodes.get("Principled BSDF") or nt.nodes.new("ShaderNodeBsdfPrincipled")
    if not any(n.type == "OUTPUT_MATERIAL" for n in nt.nodes):
        out = nt.nodes.new("ShaderNodeOutputMaterial")
        nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])

    def put(key, val):
        if key in bsdf.inputs:
            bsdf.inputs[key].default_value = val

    put("Base Color", (*color, 1.0))
    put("Metallic", metallic)
    put("Roughness", rough)
    put("IOR", ior)
    put("Alpha", alpha)
    put("Transmission Weight", transmission)
    if emission:
        put("Emission Color", (*emission, 1.0))
        put("Emission Strength", 1.2)
    mat.diffuse_color = (*color, 1.0)
    return mat


def pad_material():
    mat = make_mat("silicone_pad", (0.72, 0.74, 0.78), rough=0.62)
    nt = mat.node_tree
    bsdf = nt.nodes["Principled BSDF"]
    vor = nt.nodes.new("ShaderNodeTexVoronoi")
    vor.inputs["Scale"].default_value = 55.0
    vor.feature = "DISTANCE_TO_EDGE"
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.6
    bump.inputs["Distance"].default_value = 0.02
    coord = nt.nodes.new("ShaderNodeTexCoord")
    nt.links.new(coord.outputs["Object"], vor.inputs["Vector"])
    nt.links.new(vor.outputs["Distance"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    return mat


def materials():
    return {
        "shell": make_mat("PA12_shell_dark", (0.075, 0.082, 0.095), rough=0.52),
        "lid": make_mat("PA12_lid_dark", (0.09, 0.098, 0.112), rough=0.5),
        "glass": make_mat("window_IR_glass", (0.05, 0.012, 0.012), rough=0.06, transmission=1.0, ior=1.52),
        "pcb": make_mat("pcb_soldermask", (0.018, 0.024, 0.032), rough=0.34),
        "ic": make_mat("ic_black", (0.012, 0.012, 0.014), rough=0.38),
        "chip": make_mat("chip_grey", (0.16, 0.17, 0.19), metallic=0.4, rough=0.35),
        "xtal": make_mat("xtal_metal", (0.72, 0.74, 0.78), metallic=1.0, rough=0.22),
        "ceramic": make_mat("ceramic_tan", (0.55, 0.42, 0.26), rough=0.55),
        "mlcc": make_mat("mlcc_brown", (0.30, 0.17, 0.075), rough=0.5),
        "res": make_mat("resistor_black", (0.02, 0.02, 0.022), rough=0.45),
        "gold": make_mat("gold_ENIG", (1.0, 0.72, 0.30), metallic=1.0, rough=0.24),
        "copper": make_mat("copper_slug", (0.95, 0.48, 0.32), metallic=1.0, rough=0.3),
        "batt": make_mat("battery_foil", (0.70, 0.72, 0.74), metallic=0.9, rough=0.32),
        "foam": make_mat("foam_black", (0.03, 0.03, 0.033), rough=1.0),
        "gasket": make_mat("gasket_silicone", (0.55, 0.60, 0.65), rough=0.42),
        "pad": pad_material(),
        "green": make_mat("led_green", (0.1, 0.9, 0.25), rough=0.3, emission=(0.1, 0.9, 0.25)),
        "red": make_mat("led_red", (0.9, 0.06, 0.04), rough=0.3, emission=(0.9, 0.06, 0.04)),
        "ir": make_mat("led_IR", (0.25, 0.02, 0.05), rough=0.3),
        "pd": make_mat("photodiode", (0.1, 0.14, 0.32), metallic=0.3, rough=0.25),
        "barrier": make_mat("optical_barrier", (0.008, 0.008, 0.008), rough=0.9),
    }


# ------------------------------------------------------------------ parts
def build_shell(M):
    prof = [(WIN_R, 0.0), (15.6, 0.0)] + arc(15.6, 0.4, 0.4, -90, 0, 6)[1:] + \
           [(R, SEAM_Z), (WALL_IN, SEAM_Z), (WALL_IN, FLOOR), (WIN_R, FLOOR)]
    ob = obj_from_bm("Shell_bottom", revolve(prof), M["shell"])
    cutters = []
    for i, (x, y) in enumerate(CONTACT_XY):
        b = new_bm()
        add_box(b, (2.4, 1.2, 1.2), (x, y, FLOOR / 2))
        cutters.append(obj_from_bm(f"cut_contact{i}", b, smooth=False))
    b = new_bm()
    add_cyl(b, 0.9, -0.2, FLOOR + 0.2, NTC_XY[0], NTC_XY[1], 32)
    cutters.append(obj_from_bm("cut_slug", b, smooth=False))
    cutters.append(text_cutter("Caseback V1", 1.5, (0.0, -12.6), 0.0, mirror=True))
    bool_diff(ob, cutters, "EXACT")

    # PCB support ledges (moulded into the shell)
    b = new_bm()
    for a0, a1 in ((30, 60), (120, 150), (165, 185), (-5, 15)):
        sec = sector(14.2, WALL_IN + 0.05, a0, a1, FLOOR - 0.02, PCB_Z0)
        me = bpy.data.meshes.new("sec")
        sec.to_mesh(me)
        sec.free()
        b.from_mesh(me)
        bpy.data.meshes.remove(me)
    obj_from_bm("Shell_pcb_ledges", b, M["shell"], smooth=False)


def build_window_and_skin_parts(M):
    b = new_bm()
    add_cyl(b, WIN_R - 0.01, -0.05, FLOOR, 0, 0, 64)
    obj_from_bm("PPG_window_glass", b, M["glass"])
    b = new_bm()
    add_cyl(b, 0.9, 0.0, 0.5, NTC_XY[0], NTC_XY[1], 32)
    obj_from_bm("NTC_thermal_slug", b, M["copper"])
    b, pins = new_bm(), new_bm()
    for x, y in CONTACT_XY:
        add_box(b, (2.36, 1.16, FLOOR), (x, y, FLOOR / 2))
        add_cyl(pins, 0.4, FLOOR, PCB_Z0, x, y, 20)
    obj_from_bm("Charge_pads", b, M["gold"], smooth=False)
    obj_from_bm("Charge_spring_pins", pins, M["gold"])


def build_optics(M):
    z0, z1 = FLOOR, PCB_Z0
    # light barriers: inner ring around the photodiode, outer ring inside the window
    ring = revolve([(0.78, z0), (0.9, z0), (0.9, z1), (0.78, z1)], 48)
    obj_from_bm("PPG_barrier_inner", ring, M["barrier"])
    ring = revolve([(1.86, z0), (2.0, z0), (2.0, z1), (1.86, z1)], 64)
    obj_from_bm("PPG_barrier_outer", ring, M["barrier"])
    b = new_bm()
    add_box(b, (1.0, 1.0, 0.3), (0, 0, z1 - 0.15))
    obj_from_bm("PPG_photodiode", b, M["pd"], smooth=False)
    for name, ang, key in (("PPG_LED_green_1", 0, "green"), ("PPG_LED_red", 90, "red"),
                           ("PPG_LED_green_2", 180, "green"), ("PPG_LED_IR", 270, "ir")):
        b = new_bm()
        add_box(b, (0.6, 0.5, 0.42), (1.35 * cos(radians(ang)), 1.35 * sin(radians(ang)), z1 - 0.21), ang)
        obj_from_bm(name, b, M[key], smooth=False)
    b = new_bm()
    add_box(b, (1.0, 0.5, 0.35), (NTC_XY[0], NTC_XY[1], PCB_Z0 - 0.175))
    obj_from_bm("NTC_0402", b, M["res"], smooth=False)


def build_pcb(M):
    b = new_bm()
    add_cyl(b, PCB_R, PCB_Z0, PCB_Z1, 0, 0, 160)
    ob = obj_from_bm("PCB", b, M["pcb"])
    c = new_bm()
    add_box(c, (BATT[0] + 0.5, BATT[1] + 0.6, 2.0), (BATT_C[0], BATT_C[1], PCB_Z0 + 0.2))
    bool_diff(ob, [obj_from_bm("cut_batt", c, smooth=False)], "EXACT")

    z = PCB_Z1
    icb = new_bm()          # main ICs
    add_box(icb, (3.55, 3.6, 0.5), (-4.5, 7.2, z + 0.25))          # nRF52840 WLCSP
    add_box(icb, (2.6, 2.0, 0.5), (0.0, 1.2, z + 0.25))            # MAX86140 AFE (above the optics)
    add_box(icb, (2.5, 3.0, 0.83), (6.5, 7.5, z + 0.415))          # BMI270, top at z = 2.08, 0.02 mm below the lid
    add_box(icb, (1.6, 0.9, 0.4), (5.8, 2.6, z + 0.2))             # charger
    obj_from_bm("ICs_nRF52840_MAX86140_BMI270_charger", icb, M["ic"], smooth=False)

    xt = new_bm()
    add_box(xt, (2.0, 1.6, 0.6), (-9.8, 8.6, z + 0.3))             # 32 MHz
    add_box(xt, (1.6, 1.0, 0.5), (-9.8, 6.9, z + 0.25))            # 32.768 kHz
    obj_from_bm("Crystals", xt, M["xtal"], smooth=False)

    ind = new_bm()
    add_box(ind, (2.0, 1.6, 0.8), (-1.0, 9.6, z + 0.4))            # DC/DC inductor
    obj_from_bm("Inductor_DCDC", ind, M["chip"], smooth=False)

    ant = new_bm()
    add_box(ant, (3.2, 1.6, 0.5), (-7.1, 10.6, z + 0.25), rot=34.2)  # 2.4 GHz chip antenna
    obj_from_bm("Antenna_2G4_chip", ant, M["ceramic"], smooth=False)

    # passives: 0402 (1.0x0.5x0.35) and 0201 (0.6x0.3x0.25)
    p402 = [(-4.5, 4.6, 0), (-2.2, 5.9, 90), (-2.2, 7.2, 90), (-2.2, 8.5, 90), (-7.2, 6.2, 90), (7.2, 2.6, 90)]
    p201 = [(-3.6, 4.6, 0), (-5.4, 4.6, 0), (-4.5, 9.9, 0), (-3.6, 9.9, 0), (-2.9, 9.9, 0),
            (5.0, 6.2, 90), (5.0, 8.8, 90), (8.2, 6.2, 90), (8.2, 8.8, 90),
            (-2.2, 1.2, 90), (2.2, 1.6, 90), (0.0, 2.9, 0), (5.8, 1.2, 0), (4.4, 2.6, 90), (5.8, 4.0, 0)]
    mlcc, res = new_bm(), new_bm()
    for i, (x, y, r) in enumerate(p402):
        add_box(mlcc if i % 3 else res, (1.0, 0.5, 0.35), (x, y, z + 0.175), r)
    for i, (x, y, r) in enumerate(p201):
        add_box(mlcc if i % 4 else res, (0.6, 0.3, 0.25), (x, y, z + 0.125), r)
    obj_from_bm("Passives_MLCC", mlcc, M["mlcc"], smooth=False)
    obj_from_bm("Passives_resistors", res, M["res"], smooth=False)

    pads = new_bm()          # SWD / test pads
    for i in range(5):
        add_cyl(pads, 0.35, z, z + 0.04, -11.2, 1.5 + i, 16)
    obj_from_bm("Test_pads_SWD", pads, M["gold"], smooth=False)


def build_battery(M):
    x, y = BATT_C
    b = new_bm()
    add_box(b, BATT, (x, y, BATT_Z0 + BATT[2] / 2))
    bmesh.ops.bevel(b, geom=list(b.edges), offset=0.12, segments=2, affect="EDGES")
    obj_from_bm("Battery_LiPo_thin_cell", b, M["batt"])
    t, s = new_bm(), new_bm()
    zt = BATT_Z0 + BATT[2] / 2
    for tx in (-4.0, 4.0):
        add_box(t, (1.2, 1.4, 0.12), (tx, y + BATT[1] / 2 + 0.7, zt))
        add_cyl(s, 0.45, zt - 0.06, zt + 0.16, tx, y + BATT[1] / 2 + 1.05, 20)
    obj_from_bm("Battery_tabs", t, M["gold"], smooth=False)
    obj_from_bm("Battery_solder", s, M["xtal"])
    f = new_bm()
    add_box(f, (BATT[0] + 0.4, BATT[1] + 0.4, 0.15), (x, y, SEAM_Z - 0.075))
    obj_from_bm("Foam_battery_pad", f, M["foam"], smooth=False)


def build_seal_lid_pad(M):
    g = revolve([(15.025 + 0.175 * cos(radians(a)), 1.9 + 0.175 * sin(radians(a))) for a in range(0, 360, 30)], 160)
    obj_from_bm("Gasket_IP67", g, M["gasket"])

    prof = [(0.0, SEAM_Z), (14.05, SEAM_Z), (14.05, 1.7), (14.85, 1.7), (14.85, SEAM_Z), (R, SEAM_Z)] + \
           arc(R - 0.3, H - LID_T + 0.3, 0.3, 0, 90, 6) + [(PAD_R, H), (PAD_R, H - PAD_T), (0.0, H - PAD_T)]
    lid = obj_from_bm("Lid_top", revolve(prof), M["lid"])
    notch = stadium(2.0, 9.0, 13.4)
    shift(notch, H - PAD_T)
    cut_notch = obj_from_bm("cut_notch", notch, smooth=False)
    cut_txt = text_cutter("Caseback  V1", 1.6, (0.0, -13.35), H)
    bool_diff(lid, [cut_notch, cut_txt], "EXACT")

    b = new_bm()
    add_cyl(b, PAD_R - 0.05, H - PAD_T, H, 0, 0, 160)
    tab = stadium(1.8, 9.0, 13.2)
    bmesh.ops.scale(tab, vec=(1, 1, PAD_T), verts=tab.verts)
    shift(tab, H - PAD_T)
    me = bpy.data.meshes.new("tab")
    tab.to_mesh(me)
    tab.free()
    b.from_mesh(me)
    bpy.data.meshes.remove(me)
    obj_from_bm("Microsuction_pad", b, M["pad"])


# ------------------------------------------------------------------ assembly
def build_model():
    sc = bpy.context.scene
    sc.unit_settings.system = "METRIC"
    sc.unit_settings.scale_length = 0.001
    sc.unit_settings.length_unit = "MILLIMETERS"
    for c in (COLL_ASM, COLL_EXP):
        old = bpy.data.collections.get(c)
        if old:
            for ob in list(old.objects):
                bpy.data.objects.remove(ob, do_unlink=True)
    M = materials()
    build_shell(M)
    build_window_and_skin_parts(M)
    build_optics(M)
    build_pcb(M)
    build_battery(M)
    build_seal_lid_pad(M)
    for ob in collection(COLL_ASM).objects:
        ob["caseback_part"] = ob.name
        autosmooth(ob)


# exploded offsets (mm along +Z) per part-name prefix
EXPLODE = (("PPG_window", -5), ("NTC_thermal", -5), ("Charge_pads", -5), ("Charge_spring", 3.2),
           ("Shell", 0), ("PPG_", 3.2), ("NTC_0402", 3.2), ("PCB", 3.2), ("ICs", 3.2), ("Crystals", 3.2),
           ("Inductor", 3.2), ("Antenna", 3.2), ("Passives", 3.2), ("Test_pads", 3.2),
           ("Battery", 1.2), ("Foam", 6.4), ("Gasket", 8.6), ("Lid", 11.6), ("Microsuction", 16.0))


def build_exploded():
    src, dst = collection(COLL_ASM), collection(COLL_EXP)
    for ob in list(dst.objects):
        bpy.data.objects.remove(ob, do_unlink=True)
    for ob in src.objects:
        dz = next((d for p, d in EXPLODE if ob.name.startswith(p)), 0.0)
        cp = ob.copy()
        cp.location.z += dz
        dst.objects.link(cp)
    dst.hide_render = dst.hide_viewport = True


def build_section():
    """Copy of the assembly cut in half by the plane x = 0 (keeps x <= 0) to show the layer stack."""
    dst = collection(COLL_SEC)
    for ob in list(dst.objects):
        bpy.data.objects.remove(ob, do_unlink=True)
    for ob in collection(COLL_ASM).objects:
        cp = ob.copy()
        cp.data = ob.data.copy()
        dst.objects.link(cp)
        b = new_bm()
        add_box(b, (40.0, 80.0, 20.0), (20.0, 0.0, 1.35))
        me = bpy.data.meshes.new("half")
        b.to_mesh(me)
        b.free()
        cut = bpy.data.objects.new("cut_half", me)
        dst.objects.link(cut)
        bool_diff(cp, [cut], "EXACT")
    dst.hide_render = dst.hide_viewport = True


def stats():
    objs = list(collection(COLL_ASM).objects)
    lo = [min((o.matrix_world @ v.co).z for v in o.data.vertices) for o in objs]
    hi = [max((o.matrix_world @ v.co).z for v in o.data.vertices) for o in objs]
    xs = [abs((o.matrix_world @ v.co).x) for o in objs for v in o.data.vertices]
    ys = [abs((o.matrix_world @ v.co).y) for o in objs for v in o.data.vertices]
    return {"parts": len(objs), "tris": sum(len(o.data.polygons) for o in objs), "z_min": min(lo), "z_max": max(hi),
            "half_x": max(xs), "half_y": max(ys)}


def stack_budget():
    """Layer table from the constants above: (layer, z0, z1, note). Also the clearances that matter."""
    bmi_top = PCB_Z1 + 0.83
    ind_top = PCB_Z1 + 0.8
    batt_top = BATT_Z0 + BATT[2]
    foam_top = SEAM_Z
    lid_over_pad = H - PAD_T - SEAM_Z
    layers = [
        ("Skin floor + charge pads", 0.0, FLOOR, "pads flush in the floor"),
        ("Battery cell", BATT_Z0, batt_top, f"{BATT[0]:g} x {BATT[1]:g} x {BATT[2]:g} mm"),
        ("PCB", PCB_Z0, PCB_Z1, "cut out around the cell"),
        ("Tallest parts on PCB (BMI270 / inductor)", PCB_Z1, bmi_top, f"inductor top {ind_top:.2f}"),
        ("Battery foam", foam_top - 0.15, foam_top, "0.15 mm"),
        ("Lid", SEAM_Z, H, f"{LID_T:.2f} mm, {lid_over_pad:.2f} mm under the pad"),
        ("Microsuction pad", H - PAD_T, H, f"{PAD_T} mm in a recess"),
    ]
    vol = BATT[0] * BATT[1] * BATT[2]
    mah = {wh: vol / 1000.0 * wh / 3.7 for wh in (250, 350)}
    clr = {
        "BMI270 top to lid underside": SEAM_Z - bmi_top,
        "Inductor top to lid underside": SEAM_Z - ind_top,
        "Cell + foam top to lid underside": SEAM_Z - foam_top,
        "Cell bottom to skin floor top": BATT_Z0 - FLOOR,
        "Skin floor": FLOOR,
        "Lid over the pad recess": lid_over_pad,
    }
    return layers, clr, vol, mah


def print_budget():
    layers, clr, vol, mah = stack_budget()
    print(f"{'layer':<44}{'z0':>6}{'z1':>6}  note")
    for n, z0, z1, note in layers:
        print(f"{n:<44}{z0:>6.2f}{z1:>6.2f}  {note}")
    for n, v in clr.items():
        print(f"{n:<44}{v:>6.2f} mm")
    print(f"cell volume {vol:.0f} mm3 -> {mah[250]:.0f} mAh at 250 Wh/L, {mah[350]:.0f} mAh at 350 Wh/L (3.7 V nominal)")


def main():
    build_model()
    build_exploded()
    build_section()
    return stats()


if __name__ == "__main__":
    print(main())
    print_budget()
    if "--" in sys.argv and "--blend" in sys.argv:
        bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(sys.argv[sys.argv.index("--blend") + 1]))
