"""Blender model of the Caseback band: a woven strap that starts in one end of a silicone holder round the disc, goes once round the
wrist, passes through a steel buckle moulded into the other end of the holder and carries on over the holder and over its own start,
where it holds by hook-and-loop. The strap does not fold back; its free end covers the back of the holder. The skin face of the disc
stands out of the holder, so the disc goes on its charger without leaving the band.

Headless:
    blender -b --python generate_band.py -- --render DIR [--stl DIR] [--blend FILE] [--only a,b] [--samples N] [--scale S] [--simple]

The dimensions come from band_v01.py, the same numbers its checks use. The disc and the puck are the models of generate_disc.py
(--simple swaps the disc for a solid one of the same outline).
Units: millimetres. Band frame: the loop lies in the x-z plane with the strap width along y; the disc is on the inner side of the top.
For the shots the band is turned to stand on its side with the disc on the right; on the puck it stands on its holder.
"""

from __future__ import annotations

import os
import sys
from math import cos, hypot, pi, radians, sin

import bmesh
import bpy
from mathutils import Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..", "v1-pcb")))
import band_v01 as V  # noqa: E402
import board_parts as BP  # noqa: E402
import generate_disc as gd  # noqa: E402
import generate_v1 as g  # noqa: E402

WRIST_LOOP = dict(a=31.5, b=26.5, n=2.0, flat_top=19.5, flat_bottom=9.0)   # inner line of the strap: half width, half height, exponent, flat half-lengths
LOOP = dict(WRIST_LOOP)
assert abs(2 * WRIST_LOOP["a"] - V.LOOP_INNER[0]) < 1e-9 and abs(2 * WRIST_LOOP["b"] - V.LOOP_INNER[1]) < 1e-9
STRAP_W, STRAP_T, HOOK_T = V.STRAP_W, V.STRAP_T, V.HOOK_T
O1 = STRAP_T / 2                              # centre of the strap where it lies on the wrist
O2 = STRAP_T + HOOK_T + STRAP_T / 2           # centre of the free end, over the strap and over the holder
ROOF = STRAP_T + HOOK_T                       # the back of the holder is flush with the outside of the strap under the free end
BUCKLE = dict(V.BUCKLE, oc=O2 - 0.3)          # oc: the middle of the buckle over the inner line of the strap
EXTRA = V.EXTRA                               # length of the free end past the start of the strap
COLL_CLOSED, COLL_OPEN, COLL_CHARGE, COLL_PARTS, COLL_STUDIO = "Band", "Band_Open", "Band_Charging", "Band_Parts", "Band_Studio"


# ------------------------------------------------------------------ helpers
def rrect_pts(length, width, r, n=10):
    """Counter-clockwise rounded rectangle with corners of radius r, the same number of points whatever r is."""
    r = max(r, 0.05)
    pts = []
    for sx, sy, a0 in ((1, 1, 0), (-1, 1, 90), (-1, -1, 180), (1, -1, 270)):
        for k in range(n + 1):
            a = radians(a0 + 90.0 * k / n)
            pts.append((sx * (length / 2 - r) + r * cos(a), sy * (width / 2 - r) + r * sin(a)))
    return pts


def rings_rounded(z0, z1, rb, rt, steps=5):
    """(inset, z) rings from z0 to z1 with the bottom edge rounded by rb and the top edge by rt."""
    out = []
    if rb > 0:
        out += [(rb * (1 - sin(pi / 2 * k / steps)), z0 + rb * (1 - cos(pi / 2 * k / steps))) for k in range(steps + 1)]
    else:
        out.append((0.0, z0))
    if rt > 0:
        out += [(rt * (1 - cos(pi / 2 * k / steps)), z1 - rt * (1 - sin(pi / 2 * k / steps))) for k in range(steps + 1)]
    else:
        out.append((0.0, z1))
    return out


def rbox_obj(name, rings, length, width, corner, mat=None, coll=None):
    """A solid on rounded-rectangle outlines inset by d at height z, bottom to top, with flat caps."""
    bm = g.new_bm()
    vs = [[bm.verts.new((x, y, z)) for x, y in rrect_pts(length - 2 * d, width - 2 * d, corner - d)] for d, z in rings]
    m = len(vs[0])
    for a, b in zip(vs, vs[1:]):
        for i in range(m):
            j = (i + 1) % m
            bm.faces.new((a[i], a[j], b[j], b[i]))
    bm.faces.new(vs[0][::-1])
    bm.faces.new(vs[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return g.obj_from_bm(name, bm, mat, coll)


class _Nodes:
    """Small helper to build shader node graphs with maths on floats."""

    def __init__(self, nt):
        self.nt, self.n = nt, nt.nodes

    def math(self, op, a=None, b=None, c=None, clamp=False):
        nd = self.n.new("ShaderNodeMath")
        nd.operation, nd.use_clamp = op, clamp
        for i, v in enumerate((a, b, c)):
            if v is None:
                continue
            if isinstance(v, (int, float)):
                nd.inputs[i].default_value = v
            else:
                self.nt.links.new(v, nd.inputs[i])
        return nd.outputs[0]

    def mix(self, fac, a, b):
        nd = self.n.new("ShaderNodeMix")
        nd.data_type = "RGBA"
        for key, v in (("Factor", fac), ("A", a), ("B", b)):
            if isinstance(v, (int, float)):
                nd.inputs[key].default_value = v
            elif isinstance(v, tuple):
                nd.inputs[key].default_value = (*v, 1.0)
            else:
                self.nt.links.new(v, nd.inputs[key])
        return nd.outputs["Result"]

    def map_range(self, val, a0, a1, b0, b1, clamp=True):
        nd = self.n.new("ShaderNodeMapRange")
        nd.clamp = clamp
        for key, v in (("From Min", a0), ("From Max", a1), ("To Min", b0), ("To Max", b1)):
            nd.inputs[key].default_value = v
        self.nt.links.new(val, nd.inputs["Value"])
        return nd.outputs["Result"]


def hook_material():
    """Hook tape: grey, with a field of small hooks as a dot bump."""
    mat = g.make_mat("hook_tape_grey", (0.30, 0.31, 0.33), rough=0.8)
    nt = mat.node_tree
    vor = nt.nodes.new("ShaderNodeTexVoronoi")
    vor.inputs["Scale"].default_value = 11.0
    coord = nt.nodes.new("ShaderNodeTexCoord")
    nt.links.new(coord.outputs["Object"], vor.inputs["Vector"])
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.8
    bump.inputs["Distance"].default_value = 0.05
    nt.links.new(vor.outputs["Distance"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], nt.nodes["Principled BSDF"].inputs["Normal"])
    return mat


def smoothstep(s):
    s = min(max(s, 0.0), 1.0)
    return s * s * (3 - 2 * s)


def cum_len(pts):
    out = [0.0]
    for a, b in zip(pts, pts[1:]):
        out.append(out[-1] + hypot(b[0] - a[0], b[1] - a[1]))
    return out


def left_normals(pts):
    """Unit normal on the left of the direction of travel at each point of an (x, z) polyline."""
    out = []
    for i in range(len(pts)):
        a, b = pts[max(i - 1, 0)], pts[min(i + 1, len(pts) - 1)]
        dx, dz = b[0] - a[0], b[1] - a[1]
        ln = hypot(dx, dz)
        out.append((-dz / ln, dx / ln))
    return out


def sweep(name, pts, width, thick, mat, coll, uv=False, tip=0.0, y=0.0):
    """A strip `width` wide and `thick` thick along a polyline (x, z); its outer face is on the left of the direction of travel. With `uv` it
    gets a UV map: u millimetres along the strip, v millimetres across it from its right edge. With `tip` the last `tip` mm narrow to a rounded end."""
    path = [pts[0]]
    for q in pts[1:]:
        if hypot(q[0] - path[-1][0], q[1] - path[-1][1]) > 1e-3:
            path.append(q)
    nrm = left_normals(path)
    sl = cum_len(path)
    rc = max(min(0.3, thick / 2 - 0.02), 0.02)
    bm = g.new_bm()
    layer = bm.loops.layers.uv.new("UV") if uv else None
    uv_of = {}
    rings = []
    for (px, pz), (nx, nz), s in zip(path, nrm, sl):
        k = (s - (sl[-1] - tip)) / tip if tip else 0.0
        w = max(width * (1.0 - k * k) ** 0.5, 1.2) if k > 0 else width
        ring = []
        for u, v in gd.rounded_rect(w, thick, min(rc, w / 2 - 0.05), 3):
            vert = bm.verts.new((px + nx * v, y + u, pz + nz * v))
            uv_of[vert] = (s, u + width / 2)
            ring.append(vert)
        rings.append(ring)
    m = len(rings[0])
    for ra, rb in zip(rings, rings[1:]):
        for j in range(m):
            k2 = (j + 1) % m
            bm.faces.new((ra[j], ra[k2], rb[k2], rb[j]))
    bm.faces.new(rings[0][::-1])
    bm.faces.new(rings[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    if layer:
        for f in bm.faces:
            for lp in f.loops:
                lp[layer].uv = uv_of[lp.vert]
    ob = g.obj_from_bm(name, bm, mat, coll)
    g.autosmooth(ob, 40.0)
    return ob


def clear_scene():
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob, do_unlink=True)
    sc = bpy.context.scene
    sc.unit_settings.system, sc.unit_settings.scale_length, sc.unit_settings.length_unit = "METRIC", 0.001, "MILLIMETERS"


# ------------------------------------------------------------------ the loop, by arc length
def _loop_polyline():
    a, b, n = LOOP["a"], LOOP["b"], LOOP["n"]
    ct, cb = LOOP["flat_top"], LOOP["flat_bottom"]

    def quad(c, sx, sz):
        return [(sx * (c + (a - c) * cos(th) ** (2 / n)), sz * b * sin(th) ** (2 / n)) for th in [pi / 2 * k / 120 for k in range(121)]]

    # clockwise from the right end of the flat top: right side down, bottom right to left, left side up, top left to right
    pts = quad(ct, 1, 1)[::-1][:-1]
    pts += quad(cb, 1, -1)[:-1]
    pts += [(x, -b) for x in [cb - 2 * cb * k / 40 for k in range(40)]]
    pts += quad(cb, -1, -1)[::-1][:-1]
    pts += quad(ct, -1, 1)[:-1]
    pts += [(x, b) for x in [-ct + 2 * ct * k / 60 for k in range(61)]]
    return pts


def set_loop(loop):
    """Use another inner line for the strap."""
    global _RAW, _S, L_LOOP, S_TOP_MID
    LOOP.clear()
    LOOP.update(loop)
    _RAW = _loop_polyline()
    _S = cum_len(_RAW)
    L_LOOP = _S[-1]
    S_TOP_MID = L_LOOP - LOOP["flat_top"]                      # middle of the top


set_loop(WRIST_LOOP)


def at(s):
    """Point of the inner line at arc length s (clockwise from the right end of the flat top), the outward normal and the clockwise tangent."""
    s = s % L_LOOP
    lo, hi = 0, len(_S) - 1
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if _S[mid] <= s:
            lo = mid
        else:
            hi = mid
    f = (s - _S[lo]) / max(_S[hi] - _S[lo], 1e-9)
    x = _RAW[lo][0] + f * (_RAW[hi][0] - _RAW[lo][0])
    z = _RAW[lo][1] + f * (_RAW[hi][1] - _RAW[lo][1])
    a0, a1 = _RAW[max(lo - 2, 0)], _RAW[min(hi + 2, len(_RAW) - 1)]
    dx, dz = a1[0] - a0[0], a1[1] - a0[1]
    ln = hypot(dx, dz)
    dx, dz = dx / ln, dz / ln
    return (x, z), (-dz, dx), (dx, dz)


def off_pt(s, o):
    (x, z), (nx, nz), _ = at(s)
    return x + nx * o, z + nz * o


def s_at_top(x):
    """Arc length of the point of the flat top at x."""
    return (S_TOP_MID + x) % L_LOOP


# ------------------------------------------------------------------ the strap
def strap_path(peel=0.0):
    """Centre lines of the strap and of the hook tape. The strap is V.STRAP_LEN long from the end moulded into the holder; past the buckle
    it lies over the holder and over its own start."""
    hx = V.HOLDER["L"] / 2
    s_start = s_at_top(hx - V.HOLDER["strap_in"])                  # the end of the strap, moulded into the right end of the holder
    s_out = s_at_top(hx)
    s_buckle = s_at_top(-(hx + BUCKLE["depth"] / 2 - BUCKLE["wall"])) + L_LOOP
    s_cover0 = s_buckle + 2.0
    s_end = s_start + V.STRAP_LEN
    pts, hook, step = [], [], 0.35
    s = s_start
    while s <= s_end:
        if s < s_out:
            o = O1 - V.HOLDER["strap_sink"]
        elif s < s_buckle - 4.0:
            o = O1 - V.HOLDER["strap_sink"] * (1.0 - smoothstep((s - s_out) / 3.0))
        else:
            o = O1 + (O2 - O1) * smoothstep((s - (s_buckle - 4.0)) / 4.3)
        if peel and s > s_cover0:
            o += peel * smoothstep((s - s_cover0) / 30.0)
        pts.append(off_pt(s, o))
        if s_end - (EXTRA - 6.0) <= s <= s_end - 4.0:
            hook.append(off_pt(s, o - STRAP_T / 2 - HOOK_T / 2))
        s += step
    return pts, hook, s_buckle


# ------------------------------------------------------------------ materials
def twill_material(name, dark, light):
    """A bold diagonal twill like a woven sport loop: rows of slanted grains, black and grey yarns in turn. Reads the UV map: u along the
    strap, v across it, in millimetres."""
    mat = g.make_mat(name, dark, rough=0.82)
    nt = mat.node_tree
    bsdf = nt.nodes["Principled BSDF"]
    for key, val in (("Sheen Weight", 0.45), ("Sheen Roughness", 0.35), ("Sheen Tint", (0.6, 0.6, 0.62, 1.0)), ("Specular IOR Level", 0.35)):
        if key in bsdf.inputs:
            bsdf.inputs[key].default_value = val
    N = _Nodes(nt)
    uvn = nt.nodes.new("ShaderNodeUVMap")
    uvn.uv_map = "UV"
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(uvn.outputs["UV"], sep.inputs[0])
    u, v = sep.outputs["X"], sep.outputs["Y"]
    ang = radians(52.0)
    d1 = N.math("ADD", N.math("MULTIPLY", u, cos(ang)), N.math("MULTIPLY", v, sin(ang)))       # along a row of grains
    d2 = N.math("SUBTRACT", N.math("MULTIPLY", v, cos(ang)), N.math("MULTIPLY", u, sin(ang)))  # across the rows
    p_row, p_grain = 0.62, 0.95
    r = N.math("DIVIDE", d2, p_row)
    ri = N.math("FLOOR", r)
    fr = N.math("SUBTRACT", N.math("FRACT", r), 0.5)
    q = N.math("ADD", N.math("DIVIDE", d1, p_grain), N.math("MULTIPLY", ri, 0.5))
    qi = N.math("FLOOR", q)
    fq = N.math("SUBTRACT", N.math("FRACT", q), 0.5)
    across = N.math("SUBTRACT", 1.0, N.math("MULTIPLY", N.math("MULTIPLY", fr, fr), 4.0))
    along = N.math("SUBTRACT", 1.0, N.math("MULTIPLY", N.math("MULTIPLY", fq, fq), 4.0))
    grain = N.math("POWER", N.math("MULTIPLY", N.math("MAXIMUM", across, 0.0), N.math("MAXIMUM", along, 0.0)), 0.6)
    parity = N.math("MODULO", N.math("ABSOLUTE", N.math("ADD", ri, qi)), 2.0)                   # grey and black grains in turn along each row
    hsh = nt.nodes.new("ShaderNodeTexWhiteNoise")
    hsh.noise_dimensions = "2D"
    cmb = nt.nodes.new("ShaderNodeCombineXYZ")
    nt.links.new(ri, cmb.inputs[0])
    nt.links.new(qi, cmb.inputs[1])
    nt.links.new(cmb.outputs[0], hsh.inputs["Vector"])
    rnd = hsh.outputs["Value"]
    grey = N.mix(rnd, light, tuple(c * 0.75 for c in light))
    black = N.mix(rnd, dark, tuple(c * 1.6 for c in dark))
    col = N.mix(parity, black, grey)
    col = N.mix(N.map_range(grain, 0.0, 1.0, 0.45, 0.0), col, (0.0, 0.0, 0.0))                # the gaps between grains go dark
    edge = N.math("MINIMUM", v, N.math("SUBTRACT", STRAP_W, v))
    bind = N.map_range(edge, 0.7, 0.95, 1.0, 0.0)
    rib_b = N.map_range(N.math("SINE", N.math("MULTIPLY", u, 2 * pi / 0.45)), -1.0, 1.0, 0.0, 1.0)
    col = N.mix(bind, col, tuple(c * 0.8 for c in dark))
    nt.links.new(col, bsdf.inputs["Base Color"])
    h = N.math("ADD", N.math("MULTIPLY", grain, N.math("SUBTRACT", 1.0, bind)), N.math("MULTIPLY", rib_b, N.math("MULTIPLY", bind, 0.5)))
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 1.0
    bump.inputs["Distance"].default_value = 0.16
    nt.links.new(h, bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    nt.links.new(N.map_range(grain, 0.0, 1.0, 0.95, 0.75), bsdf.inputs["Roughness"])
    return mat


def metal_material(name, colour, rough):
    mat = g.make_mat(name, colour, metallic=1.0, rough=rough)
    gd.add_grain(mat, scale=220.0, strength=0.08, distance=0.006, rough_var=0.05)
    return mat


# ------------------------------------------------------------------ geometry
def sweep_strap(name, pts, mat, coll, tip=9.0):
    path = [pts[0]]
    for q in pts[1:]:
        if hypot(q[0] - path[-1][0], q[1] - path[-1][1]) > 1e-3:
            path.append(q)
    nrm = left_normals(path)
    sl = cum_len(path)
    bm = g.new_bm()
    layer = bm.loops.layers.uv.new("UV")
    uv_of, rings = {}, []
    prof = gd.rounded_rect(STRAP_W, STRAP_T, 0.62, 5)
    for (px, pz), (nx, nz), s in zip(path, nrm, sl):
        k = (s - (sl[-1] - tip)) / tip
        sc = max((1.0 - k * k) ** 0.5, 0.06) if k > 0 else 1.0
        ring = []
        for u, v in prof:
            vert = bm.verts.new((px + nx * v, u * sc, pz + nz * v))
            uv_of[vert] = (s, u * sc + STRAP_W / 2)
            ring.append(vert)
        rings.append(ring)
    m = len(prof)
    for ra, rb in zip(rings, rings[1:]):
        for j in range(m):
            k2 = (j + 1) % m
            bm.faces.new((ra[j], ra[k2], rb[k2], rb[j]))
    bm.faces.new(rings[0][::-1])
    bm.faces.new(rings[-1])
    for f in bm.faces:
        for lp in f.loops:
            lp[layer].uv = uv_of[lp.vert]
    ob = g.obj_from_bm(name, bm, mat, coll)
    g.autosmooth(ob, 40.0)
    return ob


def silicone_material(name, colour):
    mat = g.make_mat(name, colour, rough=0.55)
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    for key, val in (("Coat Weight", 0.25), ("Coat Roughness", 0.35), ("Specular IOR Level", 0.4)):
        if key in bsdf.inputs:
            bsdf.inputs[key].default_value = val
    gd.add_grain(mat, scale=160.0, strength=0.05, distance=0.004, rough_var=0.04)
    return mat


def build_holder_and_buckle(M, coll, s_buckle):
    """The silicone holder: a rounded block the width of the strap with a round bore for the disc, a back over it with a push-out hole,
    and the buckle moulded into its left end."""
    h = V.HOLDER
    z_top = LOOP["b"] + ROOF
    z_skin = z_top - h["roof"] - V.DISC_TOP                      # skin face of the disc
    z0 = z_skin + h["proud"]
    ob = rbox_obj("Holder", rings_rounded(z0, z_top, h["edge_skin"], h["edge_back"], 6), h["L"], STRAP_W, h["corner"], M["silicone"], coll)
    gd.bool_diff(ob, [gd.cyl_cut(h["bore_r"], z0 - 1.0, z_top - h["roof"], 0.0, 0.0, 160),
                      gd.cyl_cut(h["push_r"], z_top - h["roof"] - 0.5, z_top + 1.0, 0.0, 0.0, 64)], "EXACT")
    g.autosmooth(ob, 35.0)
    k = BUCKLE
    (px, pz), (nx, nz), (dx, dz) = at(s_buckle)
    w_in = STRAP_W + 0.6
    outer = g.new_bm()
    BP.rbox(outer, (k["depth"], w_in + 2 * k["wall"], k["slot"] + 2 * k["wall"]), (0.0, 0.0, 0.0), 0.8, 5)
    bk = g.obj_from_bm("Buckle", outer, M["metal_black"], coll)
    inner = g.new_bm()
    BP.rbox(inner, (k["depth"] + 2.0, w_in, k["slot"]), (0.0, 0.0, 0.0), 0.35, 3)
    gd.bool_diff(bk, [g.obj_from_bm("cut", inner, None, None, smooth=False)], "EXACT")
    bk.data.transform(Matrix(((dx, 0.0, nx, px + nx * k["oc"]), (0.0, 1.0, 0.0, 0.0), (dz, 0.0, nz, pz + nz * k["oc"]), (0.0, 0.0, 0.0, 1.0))))
    g.autosmooth(bk, 30.0)
    return z_skin


def band_materials(M):
    M["twill"] = twill_material("twill_sport_loop", (0.030, 0.031, 0.034), (0.068, 0.070, 0.075))
    M["metal_black"] = metal_material("metal_black_anodised", (0.028, 0.029, 0.032), 0.38)
    M["silicone"] = silicone_material("silicone_graphite", (0.040, 0.041, 0.045))
    M["hook"] = hook_material()
    M["hook"].node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.035, 0.036, 0.040, 1.0)
    return M


def build_band(M, disc_src, coll_name, peel=0.0, pose="stand"):
    """The band in a collection of its own. pose: "stand" on its side with the disc on the right wall, "charge" the same with the charger
    inside the loop, clicked onto the disc, "parts" in the holder frame (skin face of the disc at z = 0) with no disc."""
    coll = g.collection(coll_name)
    for ob in list(coll.objects):
        bpy.data.objects.remove(ob, do_unlink=True)
    pts, hook, s_buckle = strap_path(peel)
    sweep_strap("Strap", pts, M["twill"], coll)
    sweep("Hook", hook, V.HOOK_W, HOOK_T * 0.9, M["hook"], coll)
    z_skin = build_holder_and_buckle(M, coll, s_buckle)
    if pose != "parts":
        for ob in disc_src.objects:                                   # the disc, skin face down towards the wrist
            cp = ob.copy()
            cp.data = ob.data.copy()
            coll.objects.link(cp)
            cp.matrix_world = Matrix.Translation((0, 0, z_skin)) @ ob.matrix_world
    if pose == "charge":                                              # the charger upside down inside the loop, its dish floor on the skin face
        puck = g.collection(gd.COLL_PUCK)
        for ob in list(puck.objects):
            if ob.name.startswith("Puck_pogo_pins"):
                bpy.data.objects.remove(ob, do_unlink=True)
        gd.pogo_pins(M, puck, gd.P_FLOOR, "Puck_pogo_pins_pressed")   # the hook and the latch hold the disc down on them
        Tp = Matrix.Translation((0.0, 0.0, z_skin + gd.P_FLOOR)) @ Matrix.Rotation(pi, 4, "Y")    # turned over about y: hook at +y, latch at -y
        for ob in list(puck.objects):
            ob.matrix_world = Tp @ ob.matrix_world
            coll.objects.link(ob)
            puck.objects.unlink(ob)
    if pose in ("stand", "charge"):
        T = Matrix.Rotation(radians(90.0), 4, "Y")                    # the disc on the right wall, the buckle at the upper right
    else:
        T = Matrix.Translation((0.0, 0.0, -z_skin))
    for ob in coll.objects:
        ob.matrix_world = T @ ob.matrix_world
    if pose in ("stand", "charge"):
        zmin = min((ob.matrix_world @ Vector(c)).z for ob in coll.objects if ob.type == "MESH" for c in ob.bound_box)
        for ob in coll.objects:
            ob.matrix_world = Matrix.Translation((0.0, 0.0, -zmin)) @ ob.matrix_world
    return coll


def simple_disc(M):
    d = gd.build_dummy(M)
    d.name = "Disc_simple"
    for c in list(d.users_collection):
        c.objects.unlink(d)
    coll = g.collection(gd.COLL_ASM)
    coll.objects.link(d)
    b = g.new_bm()
    g.add_cyl(b, gd.R_RECESS - 0.05, gd.H - gd.PAD_T, V.DISC_TOP, 0, 0, 96)
    g.obj_from_bm("Microsuction_pad", b, M["pad"], coll)
    sb = g.new_bm()
    for x, y in V.CONTACTS:
        g.add_cyl(sb, V.CONTACT_D / 2, -0.01, 0.02, x, y, 32)
    g.obj_from_bm("Skin_contacts", sb, M["steel"], coll)


def check_puck():
    """The numbers band_v01.py repeats from generate_disc.py."""
    have = dict(r=gd.P_R, h=gd.P_H, dish_r=gd.DISH_R, dish_depth=gd.DISH_DEPTH, pogo_free=gd.POGO_FREE, hook_reach=gd.HOOK["reach"],
                hook_w=gd.HOOK["w"], latch_w=gd.LATCH["w"], latch_travel=gd.LATCH["travel"])
    bad = {k: (v, V.PUCK.get(k)) for k, v in have.items() if V.PUCK.get(k) is None or abs(v - V.PUCK[k]) > 1e-9}
    print("puck numbers in band_v01:", "match" if not bad else f"DIFFER {bad}")
    return not bad


def export_stl(out, M):
    os.makedirs(out, exist_ok=True)
    build_band(M, None, COLL_PARTS, pose="parts")
    parts = g.collection(COLL_PARTS)
    parts.hide_render = parts.hide_viewport = True
    info = {name: gd.write_stl(next(o for o in parts.objects if o.name.split(".")[0] == obj), os.path.join(out, name + ".stl")) for name, obj in (("band_holder", "Holder"), ("band_buckle", "Buckle"))}
    print("stl:", info)


# ------------------------------------------------------------------ studio
def studio():
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.use_denoising = True
    sc.render.image_settings.file_format = "JPEG"
    sc.render.image_settings.quality = 94
    sc.render.use_stamp_filename = sc.render.use_stamp_hostname = False   # the blend is saved first: its path would go into each JPEG
    sc.view_settings.view_transform = "AgX"
    sc.view_settings.look = "AgX - Medium High Contrast"
    wd = bpy.data.worlds.new("w_concept")
    wd.use_nodes = True
    wd.node_tree.nodes["Background"].inputs[0].default_value = (0.85, 0.85, 0.86, 1.0)
    wd.node_tree.nodes["Background"].inputs[1].default_value = 0.6
    sc.world = wd
    coll = g.collection(COLL_STUDIO)
    prof = [(-500.0, 0.0)] + [(160.0 + 140.0 * sin(radians(a)), 140.0 - 140.0 * cos(radians(a))) for a in range(0, 91, 3)] + [(300.0, 700.0)]
    bm = g.new_bm()
    rows = [[bm.verts.new((y, x, z)) for x, z in prof] for y in (-900.0, 900.0)]
    for i in range(len(prof) - 1):
        bm.faces.new((rows[0][i], rows[0][i + 1], rows[1][i + 1], rows[1][i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    g.obj_from_bm("Sweep", bm, g.make_mat("sweep_white", (0.80, 0.80, 0.80), rough=0.9), coll)
    tgt = bpy.data.objects.new("light_tgt", None)
    sc.collection.objects.link(tgt)
    tgt.location = (0, 0, 28)
    for name, loc, size, power in (("key", (-120.0, -160.0, 260.0), 320.0, 1.3e6), ("fill", (230.0, -140.0, 70.0), 360.0, 3.0e5),
                                   ("rim", (40.0, 240.0, 170.0), 160.0, 4.5e5), ("top", (0.0, 0.0, 420.0), 500.0, 6.0e5)):
        ld = bpy.data.lights.new(name + "_c", "AREA")
        ld.shape, ld.size, ld.energy = "DISK", size, power
        lo = bpy.data.objects.new(name + "_c", ld)
        coll.objects.link(lo)
        lo.location = loc
        con = lo.constraints.new("TRACK_TO")
        con.target, con.track_axis, con.up_axis = tgt, "TRACK_NEGATIVE_Z", "UP_Y"
    cam_d = bpy.data.cameras.new("cam_c")
    cam = bpy.data.objects.new("cam_c", cam_d)
    sc.collection.objects.link(cam)
    sc.camera = cam
    ct = bpy.data.objects.new("cam_tgt", None)
    sc.collection.objects.link(ct)
    con = cam.constraints.new("TRACK_TO")
    con.target, con.track_axis, con.up_axis = ct, "TRACK_NEGATIVE_Z", "UP_Y"
    cam_d.dof.use_dof = True
    cam_d.dof.focus_object = ct
    return cam, ct


def aim(cam, ct, show, target, dist, azim, elev, lens, fstop):
    for c in bpy.data.collections:
        if c.name.startswith("Band") and c.name != COLL_STUDIO or c.name in (gd.COLL_ASM, gd.COLL_PUCK):
            c.hide_render = c.hide_viewport = c.name not in show
    az, el = radians(azim), radians(elev)
    cam.location = (target[0] + dist * cos(el) * sin(az), target[1] - dist * cos(el) * cos(az), target[2] + dist * sin(el))
    ct.location = target
    cam.data.lens = lens
    cam.data.dof.aperture_fstop = fstop
    cam.data.clip_start, cam.data.clip_end = 1.0, 5000.0
    bpy.context.view_layer.update()


# name: (collection, target, distance, azimuth, elevation, lens, f-stop, (w, h))
SHOTS = {
    "band_hero": ((COLL_CLOSED,), (2, 0, 31), 255, 40, 22, 85, 7.1, (2000, 2000)),
    "band_inside": ((COLL_CLOSED,), (2, 0, 31), 265, -35, 14, 85, 7.1, (2000, 1700)),
    "band_holder": ((COLL_CLOSED,), (22, 0, 34), 120, -62, 8, 85, 5.6, (2000, 1500)),
    "band_buckle": ((COLL_CLOSED,), (26, 0, 48), 110, 35, 28, 85, 4.5, (2000, 1500)),
    "band_open": ((COLL_OPEN,), (10, 0, 32), 300, 45, 24, 85, 7.1, (2000, 1800)),
    "band_charging": ((COLL_CHARGE,), (14, 0, 31), 230, 35, 16, 85, 7.1, (2000, 1800)),
}


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    out = argv[argv.index("--render") + 1] if "--render" in argv else None
    only = argv[argv.index("--only") + 1].split(",") if "--only" in argv else None
    samples = int(argv[argv.index("--samples") + 1]) if "--samples" in argv else 160
    scale = float(argv[argv.index("--scale") + 1]) if "--scale" in argv else 1.0
    if "--simple" in argv:
        clear_scene()
        M = gd.materials()
        simple_disc(M)
    else:
        M = gd.build_all()
    gd.build_puck(M)
    check_puck()
    band_materials(M)
    disc = g.collection(gd.COLL_ASM)
    for c in list(bpy.data.collections):
        if c.name not in (gd.COLL_ASM, gd.COLL_PUCK):
            c.hide_render = c.hide_viewport = True
    build_band(M, disc, COLL_CLOSED)
    build_band(M, disc, COLL_OPEN, peel=16.0)
    build_band(M, disc, COLL_CHARGE, pose="charge")
    if "--stl" in argv:
        export_stl(argv[argv.index("--stl") + 1], M)
    cam, ct = studio()
    sc = bpy.context.scene
    sc.cycles.samples = samples
    if "--blend" in argv:
        bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(argv[argv.index("--blend") + 1]))
    if not out:
        return
    os.makedirs(out, exist_ok=True)
    for name, (colls, target, dist, az, el, lens, fs, size) in SHOTS.items():
        if only and name not in only:
            continue
        sc.render.resolution_x, sc.render.resolution_y = int(size[0] * scale), int(size[1] * scale)
        aim(cam, ct, {*colls, COLL_STUDIO}, target, dist, az, el, lens, fs)
        sc.render.filepath = os.path.join(out, name + ".jpg")
        bpy.ops.render.render(write_still=True)
        print("rendered", name)


if __name__ == "__main__":
    main()
