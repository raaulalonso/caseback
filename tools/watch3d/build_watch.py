"""Builds the Caseback watch model in Blender and exports it as glTF (tools/watch3d/out/) and for the iOS app (USDZ).

Run inside Blender (the MCP `execute_blender_code` tool, or Scripting > Run Script):

    CASEBACK_ROOT=/path/to/caseback blender --background --python tools/watch3d/build_watch.py

or, from the Blender Python console, set the variable first and then
`exec(open(os.environ['CASEBACK_ROOT'] + '/tools/watch3d/build_watch.py').read())`.

Units: the case radius is 1. Object space (before the export rotation): dial towards +Z, 12 o'clock towards +Y, crown towards +X.
The export parents everything to an empty turned 90 degrees about X so that, in the exported file (Y up), the dial looks
towards +Z and 12 o'clock towards +Y. Parts that the apps move are separate nodes with their origin on the dial axis:
`hand_hour`, `hand_minute`, `hand_second`.

The disc the blobs make goes on the caseback plate at z = -0.20 (the plate is flat there on purpose).
"""
import math
import os

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector

# Repository root: CASEBACK_ROOT if set, else two levels above this file (unknown when the script is exec'd).
ROOT = os.environ.get('CASEBACK_ROOT') or os.path.abspath(os.path.join(os.path.dirname(globals().get('__file__', '.')), '..', '..'))
OUT_DIR = ROOT + '/tools/watch3d'
FONT = ROOT + '/apps/ios/Caseback/Resources/Fonts/IBMPlexMono-Medium.ttf'
COLL = 'Watch'

# ---------------------------------------------------------------- scene plumbing

coll = bpy.data.collections.get(COLL)
if coll:
    for o in list(coll.objects):
        bpy.data.objects.remove(o, do_unlink=True)
else:
    coll = bpy.data.collections.new(COLL)
    bpy.context.scene.collection.children.link(coll)
for m in list(bpy.data.materials):
    if m.name.startswith('w_'):
        bpy.data.materials.remove(m)

rig = bpy.data.objects.new('CasebackWatch', None)
rig.empty_display_type = 'PLAIN_AXES'
rig.rotation_euler = (math.pi / 2, 0, 0)
coll.objects.link(rig)


def material(name, color, metallic=0.0, rough=0.5, alpha=1.0, coat=0.0, normal_map=None, normal_strength=1.0):
    m = bpy.data.materials.new('w_' + name)
    m.use_nodes = True
    nt = m.node_tree
    bsdf = nt.nodes['Principled BSDF']
    bsdf.inputs['Base Color'].default_value = (*color, 1.0)
    bsdf.inputs['Metallic'].default_value = metallic
    bsdf.inputs['Roughness'].default_value = rough
    bsdf.inputs['Alpha'].default_value = alpha
    if 'Coat Weight' in bsdf.inputs:
        bsdf.inputs['Coat Weight'].default_value = coat
    if alpha < 1.0:
        m.surface_render_method = 'BLENDED'
    if normal_map is not None:
        tex = nt.nodes.new('ShaderNodeTexImage')
        tex.image = bpy.data.images.load(normal_map, check_existing=True)
        tex.image.colorspace_settings.name = 'Non-Color'
        nm = nt.nodes.new('ShaderNodeNormalMap')
        nm.inputs['Strength'].default_value = normal_strength
        nt.links.new(tex.outputs['Color'], nm.inputs['Color'])
        nt.links.new(nm.outputs['Normal'], bsdf.inputs['Normal'])
    return m


def smooth_by_angle(bm, degrees=32):
    lim = math.radians(degrees)
    for e in bm.edges:
        e.smooth = not (len(e.link_faces) == 2 and e.calc_face_angle(0) > lim)
    for f in bm.faces:
        f.smooth = True


def make(name, bm, mat, parent=None, smooth=32, location=(0, 0, 0)):
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    if smooth:
        smooth_by_angle(bm, smooth)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    ob.data.materials.append(mat)
    ob.location = location
    coll.objects.link(ob)
    ob.parent = parent or rig
    return ob


def revolve(profile, steps=96, close=True):
    """Spins a polyline of (r, z) points about the Z axis. With close=True the profile is a closed polygon (a solid)."""
    bm = bmesh.new()
    vs = [bm.verts.new((r, 0.0, z)) for r, z in profile]
    es = [bm.edges.new((vs[i], vs[i + 1])) for i in range(len(vs) - 1)]
    if close:
        es.append(bm.edges.new((vs[-1], vs[0])))
    bmesh.ops.spin(bm, geom=vs + es, cent=(0, 0, 0), axis=(0, 0, 1), angle=2 * math.pi, steps=steps)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
    bmesh.ops.dissolve_degenerate(bm, edges=bm.edges, dist=1e-6)
    return bm


def box(bm, center, size, rot_z=0.0, rot_x=0.0, bevel=0.0):
    m = Matrix.Translation(center) @ Matrix.Rotation(rot_z, 4, 'Z') @ Matrix.Rotation(rot_x, 4, 'X')
    res = bmesh.ops.create_cube(bm, size=1.0, matrix=m @ Matrix.Diagonal((size[0], size[1], size[2], 1.0)))
    if bevel > 0:
        edges = {e for v in res['verts'] for e in v.link_edges}
        bmesh.ops.bevel(bm, geom=list(edges), offset=bevel, segments=2, affect='EDGES')
    return res


def prism(bm, outline, z0, z1):
    """Extrudes a polygon (list of (x, y)) between two heights."""
    vs = [bm.verts.new((x, y, z0)) for x, y in outline]
    f = bm.faces.new(vs)
    ex = bmesh.ops.extrude_face_region(bm, geom=[f])
    top = [v for v in ex['geom'] if isinstance(v, bmesh.types.BMVert)]
    bmesh.ops.translate(bm, verts=top, vec=(0, 0, z1 - z0))


# ---------------------------------------------------------------- materials

steel = material('steel_brushed', (0.62, 0.62, 0.65), metallic=1.0, rough=0.34)
polished = material('steel_polished', (0.86, 0.86, 0.88), metallic=1.0, rough=0.07)
dial_m = material('dial', (0.012, 0.013, 0.016), metallic=0.0, rough=0.38, coat=0.4)
index_m = material('index', (0.92, 0.92, 0.92), metallic=1.0, rough=0.3)
print_m = material('print', (0.78, 0.78, 0.76), metallic=0.0, rough=0.6)
hand_m = material('hand', (0.9, 0.9, 0.92), metallic=1.0, rough=0.28)
thread_m = material('thread', (0.42, 0.38, 0.31), metallic=0.0, rough=0.8)


def grain_normal_map(path, size=512, seed=3):
    """A fine tileable leather grain: small pebbles and pores, blurred noise turned into a tangent-space normal map."""
    rng = np.random.default_rng(seed)
    h = np.zeros((size, size))
    for octave, amp in ((64, 1.0), (128, 0.7), (256, 0.35)):
        n = rng.random((octave, octave))
        big = np.kron(n, np.ones((size // octave, size // octave)))
        for _ in range(2):
            big = (big + np.roll(big, 1, 0) + np.roll(big, -1, 0) + np.roll(big, 1, 1) + np.roll(big, -1, 1)) / 5
        h += amp * big
    h = (h - h.min()) / (h.max() - h.min())
    dx = (np.roll(h, -1, 1) - np.roll(h, 1, 1)) * 5.0
    dy = (np.roll(h, -1, 0) - np.roll(h, 1, 0)) * 5.0
    nz = np.ones_like(h)
    ln = np.sqrt(dx * dx + dy * dy + nz * nz)
    rgb = np.stack([(-dx / ln) * 0.5 + 0.5, (-dy / ln) * 0.5 + 0.5, nz / ln * 0.5 + 0.5, np.ones_like(h)], -1)
    img = bpy.data.images.new('w_grain', size, size, alpha=True)
    img.pixels = rgb.flatten().tolist()
    img.filepath_raw = path
    img.file_format = 'PNG'
    img.save()
    bpy.data.images.remove(img)
    return path


grain = grain_normal_map(OUT_DIR + '/leather_grain_normal.png')
leather = material('leather', (0.03, 0.028, 0.027), metallic=0.0, rough=0.5, normal_map=grain, normal_strength=0.5)
leather_edge = material('leather_edge', (0.012, 0.011, 0.011), metallic=0.0, rough=0.28)   # burnished edge: darker and glossier
steel_buckle = material('buckle', (0.8, 0.8, 0.82), metallic=1.0, rough=0.16)


def studio_environment(path, w=1024, h=512):
    """An equirectangular studio for the reflections: a big soft box above and to the left, a strip on the right, a dim floor."""
    u = (np.arange(w) + 0.5) / w
    v = (np.arange(h) + 0.5) / h
    phi = (u[None, :] - 0.5) * 2 * math.pi         # three.js equirect: u = atan2(z, x) / 2pi + 0.5
    el = (0.5 - v[:, None]) * math.pi              # +pi/2 up
    dx = np.cos(el) * np.cos(phi)
    dy = np.sin(el) * np.ones_like(phi)
    dz = np.cos(el) * np.sin(phi)
    img = np.zeros((h, w, 3))
    sky = 0.04 + 0.5 * np.clip(dy * 0.5 + 0.5, 0, 1) ** 1.6
    img += sky[..., None]

    def box(direction, size_u, size_v, power):
        d = np.array(direction, dtype=float)
        d /= np.linalg.norm(d)
        up = np.array([0, 1, 0.0]) if abs(d[1]) < 0.9 else np.array([1, 0, 0.0])
        r = np.cross(up, d); r /= np.linalg.norm(r)
        t = np.cross(d, r)
        fd = dx * d[0] + dy * d[1] + dz * d[2]
        fu = dx * r[0] + dy * r[1] + dz * r[2]
        fv = dx * t[0] + dy * t[1] + dz * t[2]
        m = (fd > 0.2)
        eu = np.abs(fu / np.maximum(fd, 1e-3)) / size_u
        ev = np.abs(fv / np.maximum(fd, 1e-3)) / size_v
        e = np.maximum(eu, ev)
        return power * m * (1 - np.clip((e - 0.85) / 0.25, 0, 1))

    img += box((-0.55, 0.7, 0.55), 0.55, 0.4, 9.0)[..., None]    # key
    img += box((0.95, 0.15, 0.4), 0.14, 0.6, 5.0)[..., None]     # strip on the right
    img += box((0.0, 1.0, 0.1), 0.6, 0.6, 3.0)[..., None]        # ceiling
    img += box((0.1, -0.35, 1.0), 0.8, 0.25, 0.7)[..., None]     # low front fill
    img[dy < -0.05] *= 0.35                                      # dark floor
    rgba = np.concatenate([img, np.ones((h, w, 1))], -1)[::-1]   # image rows go bottom to top
    im = bpy.data.images.new('w_studio', w, h, alpha=False, float_buffer=True)
    im.pixels = rgba.astype(np.float32).flatten().tolist()
    im.filepath_raw = path
    im.file_format = 'HDR'
    im.save()
    bpy.data.images.remove(im)


# ---------------------------------------------------------------- case, bezel, crystal, dial

case_profile = [
    (0.0, -0.20), (0.80, -0.20), (0.85, -0.17), (0.95, -0.17), (0.995, -0.13), (1.0, -0.10), (1.0, 0.11),
    (0.985, 0.15), (0.93, 0.17), (0.90, 0.16), (0.885, 0.14), (0.885, 0.085), (0.0, 0.085),
]
make('case', revolve(case_profile), steel)

bezel_profile = [(0.88, 0.15), (0.99, 0.15), (0.995, 0.19), (0.965, 0.222), (0.915, 0.232), (0.885, 0.215), (0.875, 0.18)]
make('bezel', revolve(bezel_profile), polished, smooth=40)

# No crystal in the model: a thin alpha shell reads as a grey film in most engines. The apps add the reflection themselves.

make('dial', revolve([(0.0, 0.08), (0.885, 0.08), (0.885, 0.095), (0.0, 0.095)]), dial_m, smooth=40)

# Indices: twelve applied bars, the quarters longer and wider.
bm = bmesh.new()
for k in range(12):
    a = k * math.pi / 6
    quarter = k % 3 == 0
    length = 0.2 if quarter else 0.14
    width = 0.058 if quarter else 0.04
    r = 0.80 - length / 2
    box(bm, (math.sin(a) * r, math.cos(a) * r, 0.108), (width, length, 0.026), rot_z=-a, bevel=0.004)
make('indices', bm, index_m, smooth=40)

# Minute track and the name, printed.
bm = bmesh.new()
for k in range(60):
    a = k * math.pi / 30
    r = 0.845
    box(bm, (math.sin(a) * r, math.cos(a) * r, 0.0965), (0.007, 0.04, 0.003), rot_z=-a)
make('minute_track', bm, print_m, smooth=0)

bpy.ops.object.text_add(location=(0, 0.34, 0.0965))
txt = bpy.context.active_object
txt.name = 'wordmark_src'
txt.data.body = 'Caseback'
txt.data.size = 0.085
txt.data.extrude = 0.0015
txt.data.align_x = 'CENTER'
txt.data.align_y = 'CENTER'
txt.data.font = bpy.data.fonts.load(FONT)
dg = bpy.context.evaluated_depsgraph_get()
me = bpy.data.meshes.new_from_object(txt.evaluated_get(dg))
bpy.data.objects.remove(txt, do_unlink=True)
wm = bpy.data.objects.new('wordmark', me)
wm.data.materials.append(print_m)
wm.location = (0, 0.34, 0.0965)
coll.objects.link(wm)
wm.parent = rig

# ---------------------------------------------------------------- hands (origin on the dial axis)


def hand(name, outline, z0, z1, angle_deg):
    bm = bmesh.new()
    prism(bm, outline, 0.0, z1 - z0)
    ob = make(name, bm, hand_m, smooth=45, location=(0, 0, z0))
    ob.rotation_euler = (0, 0, -math.radians(angle_deg))
    return ob


hand('hand_hour', [(0, -0.12), (0.05, 0.0), (0.045, 0.1), (0, 0.48), (-0.045, 0.1), (-0.05, 0.0)], 0.12, 0.134, 305)
hand('hand_minute', [(0, -0.15), (0.04, 0.0), (0.032, 0.1), (0, 0.74), (-0.032, 0.1), (-0.04, 0.0)], 0.136, 0.15, 60)
sec = [(-0.007, -0.04), (-0.007, 0.8), (0.007, 0.8), (0.007, -0.04)]
bm = bmesh.new()
prism(bm, sec, 0.0, 0.008)
# the counterweight of the second hand
cw = [(0.026 * math.cos(t), -0.17 + 0.026 * math.sin(t)) for t in np.linspace(0, 2 * math.pi, 16, endpoint=False)]
prism(bm, cw, 0.0, 0.008)
prism(bm, [(-0.007, -0.17), (-0.007, -0.04), (0.007, -0.04), (0.007, -0.17)], 0.0, 0.008)
sh = make('hand_second', bm, hand_m, smooth=45, location=(0, 0, 0.152))
sh.rotation_euler = (0, 0, -math.radians(168))

bm = revolve([(0.0, 0.118), (0.055, 0.118), (0.055, 0.16), (0.03, 0.172), (0.0, 0.172)], steps=32)
make('hand_cap', bm, hand_m, smooth=45)

# ---------------------------------------------------------------- lugs, crown, back

bm = bmesh.new()
for sx in (-1, 1):
    for sy in (-1, 1):
        # the lugs curve down towards the strap
        box(bm, (sx * 0.62, sy * 0.96, -0.03), (0.17, 0.44, 0.19), rot_x=-sy * 0.2, bevel=0.07)
make('lugs', bm, steel, smooth=40)

# Crown: a knurled cylinder along +X on a short stem.
bm = bmesh.new()
n = 48
rings = [(0.94, 0.085), (1.0, 0.085), (1.0, 0.15), (1.04, 0.15), (1.17, 0.15), (1.2, 0.125), (1.205, 0.0)]
rows = []
for x, r in rings:
    row = []
    for k in range(n):
        rr = r * (0.935 if (k % 2 and r > 0.14 and x >= 1.04 and x <= 1.17) else 1.0)
        a = 2 * math.pi * k / n
        row.append(bm.verts.new((x, rr * math.cos(a), rr * math.sin(a))))
    rows.append(row)
for i in range(len(rows) - 1):
    for k in range(n):
        a, b = rows[i][k], rows[i][(k + 1) % n]
        c, d = rows[i + 1][(k + 1) % n], rows[i + 1][k]
        if i == len(rows) - 2:
            bm.faces.new((a, b, d))
        else:
            bm.faces.new((a, b, c, d))
bm.faces.new(rows[0][::-1])
make('crown', bm, steel, smooth=34)

# Caseback: a ring round the place of the disc and six screws.
make('back_ring', revolve([(0.80, -0.20), (0.84, -0.20), (0.835, -0.212), (0.805, -0.212)]), polished, smooth=40)
bm = bmesh.new()
for k in range(6):
    a = (k + 0.5) * math.pi / 3
    box(bm, (0.93 * math.cos(a), 0.93 * math.sin(a), -0.183), (0.07, 0.07, 0.034), bevel=0.012)
make('screws', bm, polished, smooth=40)

# ---------------------------------------------------------------- straps
# Each strap is a swept rounded cross-section (no bevel or solidify artefacts): flat top, rounded burnished edges, a slight
# arch. The upper strap ends folded round a buckle, the lower one in a rounded tip with holes, like a watch lying unbuckled.

BEND = 0.2


def strap_halfwidth(y):
    return 0.58 + (0.50 - 0.58) * min(max((y - 0.7) / 1.3, 0.0), 1.0)


def strap_zc(y):
    over = max(y - 0.95, 0.0)
    return -0.03 - BEND * over * over


def section(hw, ht, n=44, power=7.0):
    pts = []
    for k in range(n):
        t = 2 * math.pi * k / n
        c, sn = math.cos(t), math.sin(t)
        pts.append((hw * math.copysign(abs(c) ** (2 / power), c), ht * math.copysign(abs(sn) ** (2 / power), sn)))
    return pts


def build_strap(name, sign, y0, y1, tip_radius, holes):
    N, n = 150, 44
    bm = bmesh.new()
    uv = bm.loops.layers.uv.new('UVMap')
    rows = []
    for i in range(N + 1):
        y = y0 + (y1 - y0) * i / N
        k = 1.0
        if tip_radius > 0:
            e = y1 - tip_radius
            if y > e:
                k = math.sqrt(max(1.0 - ((y - e) / tip_radius) ** 2, 0.0))
        hw = strap_halfwidth(y) * k
        ht = 0.047 * (0.25 + 0.75 * k)
        dz = (strap_zc(y + 0.005) - strap_zc(y - 0.005)) / 0.01
        L = math.sqrt(1 + dz * dz)
        row = []
        for x, zl in section(max(hw, 1e-4), max(ht, 1e-4), n):
            zl_arch = zl + 0.03 * (1 - (x / max(strap_halfwidth(y), 1e-4)) ** 2) * (1 if zl >= 0 else 1) * k
            yp = y - dz * zl_arch / L
            zp = strap_zc(y) + zl_arch / L
            row.append(bm.verts.new((x, sign * yp, zp)))
        rows.append(row)
    for i in range(N):
        for j in range(n):
            j2 = (j + 1) % n
            f = bm.faces.new((rows[i][j], rows[i][j2], rows[i + 1][j2], rows[i + 1][j]))
            for loop in f.loops:
                loop[uv].uv = (loop.vert.co.x * 2.4, abs(loop.vert.co.y) * 2.4)
    # close the open end (the tip collapses to a point; the flat end is capped)
    if tip_radius == 0:
        bm.faces.new(rows[-1][::-1])
    bm.faces.new(rows[0])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    for f in bm.faces:
        f.smooth = True
        nz = abs(f.normal.z)
        f.material_index = 0 if nz > 0.55 else 1       # top and bottom: leather; the rim: burnished edge paint
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    ob.data.materials.append(leather)
    ob.data.materials.append(leather_edge)
    coll.objects.link(ob)
    ob.parent = rig
    if holes:
        dg0 = bpy.context.evaluated_depsgraph_get()
        for k in range(5):
            y = 1.62 + 0.17 * k
            cyl = bpy.data.objects.new('hole', bpy.data.meshes.new('hole'))
            b2 = bmesh.new()
            bmesh.ops.create_cone(b2, cap_ends=True, segments=28, radius1=0.04, radius2=0.04, depth=0.5)
            b2.to_mesh(cyl.data)
            b2.free()
            cyl.location = (0, sign * y, strap_zc(y))
            coll.objects.link(cyl)
            bo = ob.modifiers.new('hole%d' % k, 'BOOLEAN')
            bo.operation = 'DIFFERENCE'
            bo.object = cyl
            bo.solver = 'EXACT'
        dg = bpy.context.evaluated_depsgraph_get()
        me2 = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
        for m in list(ob.modifiers):
            ob.modifiers.remove(m)
        ob.data = me2
        for o in [o for o in coll.objects if o.name.startswith('hole')]:
            bpy.data.objects.remove(o, do_unlink=True)
        ob.data.materials.clear()
        ob.data.materials.append(leather)
        ob.data.materials.append(leather_edge)
        for p in ob.data.polygons:
            p.use_smooth = True
            p.material_index = 0 if abs(p.normal.z) > 0.55 else 1
    # stitching: slanted ellipsoid stitches along both edges of the top face
    bs = bmesh.new()
    top = y1 - (tip_radius + 0.12 if tip_radius else 0.1)
    for side in (-1, 1):
        y = y0 + 0.16
        while y < top:
            hw = strap_halfwidth(y)
            x = side * (hw - 0.085)
            dz = (strap_zc(y + 0.005) - strap_zc(y - 0.005)) / 0.01
            z = strap_zc(y) + 0.047 + 0.03 * (1 - ((hw - 0.085) / hw) ** 2) + 0.002
            m = (Matrix.Translation((x, sign * y, z)) @ Matrix.Rotation(math.atan(dz) * sign, 4, 'X') @ Matrix.Rotation(math.radians(-14), 4, 'Z')
                 @ Matrix.Diagonal((0.0075, 0.034, 0.0055, 1.0)))
            bmesh.ops.create_uvsphere(bs, u_segments=10, v_segments=6, radius=1.0, matrix=m)
            y += 0.082
    make(name + '_stitching', bs, thread_m, smooth=60)
    return ob


build_strap('strap_top', 1, 0.80, 1.94, 0.0, False)
build_strap('strap_bottom', -1, 0.80, 2.62, 0.34, True)

# The fold of the upper strap round the buckle bar, the buckle itself and the keeper.
y_bar = 1.99
hw_bar = strap_halfwidth(y_bar)
bm = bmesh.new()
for k in range(1):
    pass
roll = bmesh.ops.create_cone(bm, cap_ends=True, segments=32, radius1=0.062, radius2=0.062, depth=hw_bar * 2 * 0.99,
                             matrix=Matrix.Translation((0, y_bar - 0.01, strap_zc(y_bar))) @ Matrix.Rotation(math.pi / 2, 4, 'Y'))
for f in bm.faces:
    f.smooth = True
ob = make('strap_fold', bm, leather, smooth=0)
ob.data.materials.append(leather_edge)


def tube(bm, path, radius, segs=10, closed=True):
    """A tube of circular section along a polyline of 3D points."""
    ring_prev = None
    rings = []
    n = len(path)
    for i, p in enumerate(path):
        a = Vector(path[(i + 1) % n]) - Vector(path[i - 1]) if closed else Vector(path[min(i + 1, n - 1)]) - Vector(path[max(i - 1, 0)])
        t = a.normalized()
        ref = Vector((0, 0, 1)) if abs(t.z) < 0.9 else Vector((1, 0, 0))
        nx = t.cross(ref).normalized()
        ny = t.cross(nx).normalized()
        ring = []
        for k in range(segs):
            ang = 2 * math.pi * k / segs
            ring.append(bm.verts.new(Vector(p) + nx * math.cos(ang) * radius + ny * math.sin(ang) * radius))
        rings.append(ring)
    cnt = n if closed else n - 1
    for i in range(cnt):
        r0, r1 = rings[i], rings[(i + 1) % n]
        for k in range(segs):
            bm.faces.new((r0[k], r0[(k + 1) % segs], r1[(k + 1) % segs], r1[k]))


def rounded_rect(cx, cy, w, d, rc, z, pts=10):
    out = []
    corners = [(cx + w / 2 - rc, cy + d / 2 - rc, 0), (cx - w / 2 + rc, cy + d / 2 - rc, 90), (cx - w / 2 + rc, cy - d / 2 + rc, 180), (cx + w / 2 - rc, cy - d / 2 + rc, 270)]
    for ccx, ccy, a0 in corners:
        for k in range(pts + 1):
            a = math.radians(a0 + 90 * k / pts)
            out.append((ccx + rc * math.cos(a), ccy + rc * math.sin(a), z))
    return out


bm = bmesh.new()
bz = strap_zc(2.2) + 0.0
frame = rounded_rect(0.0, 2.2, hw_bar * 2 + 0.16, 0.5, 0.12, bz)
tube(bm, frame, 0.034, 12, closed=True)
for f in bm.faces:
    f.smooth = True
make('buckle', bm, steel_buckle, smooth=0)
bm = bmesh.new()
tube(bm, [(0.0, y_bar, bz + 0.02), (0.0, 2.2 + 0.25, bz + 0.012)], 0.02, 10, closed=False)
make('buckle_prong', bm, steel_buckle, smooth=40)

# Keeper: a leather loop round the strap.
bm = bmesh.new()
yk = 1.66
hwk = strap_halfwidth(yk)
outer = bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation((0, yk, strap_zc(yk))) @ Matrix.Diagonal((hwk * 2 + 0.1, 0.11, 0.17, 1.0)))
kp = make('keeper', bm, leather, smooth=0)
inner = bpy.data.objects.new('kcut', bpy.data.meshes.new('kcut'))
b3 = bmesh.new()
bmesh.ops.create_cube(b3, size=1.0, matrix=Matrix.Diagonal((hwk * 2 + 0.0, 0.5, 0.108, 1.0)))
b3.to_mesh(inner.data)
b3.free()
inner.location = (0, yk, strap_zc(yk))
coll.objects.link(inner)
bo = kp.modifiers.new('cut', 'BOOLEAN')
bo.operation = 'DIFFERENCE'
bo.object = inner
bo.solver = 'EXACT'
bev = kp.modifiers.new('bev', 'BEVEL')
bev.width = 0.018
bev.segments = 3
dg = bpy.context.evaluated_depsgraph_get()
kme = bpy.data.meshes.new_from_object(kp.evaluated_get(dg))
for m in list(kp.modifiers):
    kp.modifiers.remove(m)
kp.data = kme
bpy.data.objects.remove(inner, do_unlink=True)
kp.data.materials.clear()
kp.data.materials.append(leather_edge)
for p in kp.data.polygons:
    p.use_smooth = True

# ---------------------------------------------------------------- export

studio_environment(ROOT + '/apps/ios/Caseback/Resources/CasebackStudio.hdr')
bpy.context.view_layer.update()
sel = [rig] + [o for o in coll.objects if o is not rig]
bpy.ops.object.select_all(action='DESELECT')
for o in sel:
    o.select_set(True)
bpy.context.view_layer.objects.active = rig
import os
os.makedirs(ROOT + '/tools/watch3d/out', exist_ok=True)
GLB = ROOT + '/tools/watch3d/out/caseback-watch.glb'
USDZ = ROOT + '/apps/ios/Caseback/Resources/CasebackWatch.usdz'
bpy.ops.export_scene.gltf(filepath=GLB, export_format='GLB', use_selection=True, export_apply=True, export_yup=True,
                          export_materials='EXPORT', export_cameras=False, export_lights=False, export_image_format='JPEG', export_image_quality=90)
bpy.ops.wm.usd_export(filepath=USDZ, selected_objects_only=True, export_materials=True, generate_preview_surface=True,
                      export_textures_mode='NEW', convert_orientation=True, export_global_up_selection='Y',
                      export_global_forward_selection='NEGATIVE_Z', export_animation=False, export_normals=True, export_uvmaps=True)
bpy.ops.wm.save_as_mainfile(filepath=OUT_DIR + '/CasebackWatch.blend', copy=True)
result = {'objects': [o.name for o in sel], 'tris': sum(len(o.data.polygons) for o in sel if o.type == 'MESH'), 'glb': os.path.getsize(GLB), 'usdz': os.path.getsize(USDZ)}
