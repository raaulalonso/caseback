"""Renders a group of generic phones, each showing a real screenshot of the Caseback app, with Blender (Cycles).

Run by tools/app_renders/render_all.py; by hand:

    /Applications/Blender.app/Contents/MacOS/Blender --background --python tools/app_renders/render_phones.py -- \
        --scene today --tex <dir with the screenshots, island already drawn> --out out.png [--width 1760] [--samples 96]

The phone is generic on purpose: a flat metal frame, a black glass front and a pill cut-out, no marks of any maker. One unit
is one centimetre. Object space: width along X, height along Y, the screen looks towards +Z. The scene writes a sidecar
`<out>.json` with where each phone and its screen land in the picture (0 to 1, from the top left), which the website uses to
line up its captions.
"""
import json
import math
import sys

import bmesh
import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Matrix, Vector

# ------------------------------------------------------------------ the phone (cm)
W, H, T = 7.19, 15.21, 0.86  # body: 71.9 x 152.1 x 8.6 mm
R_BODY = 1.02  # outer corner radius
GLASS_INSET = 0.07
BEZEL = 0.17  # black border between the edge of the body and the lit screen
SCREEN_W = W - 2 * BEZEL
SCREEN_H = H - 2 * BEZEL
R_SCREEN = R_BODY - BEZEL + 0.02

# ------------------------------------------------------------------ the groups: which screenshot, where, how it is turned
# loc in cm, rot in degrees about X (pitch), Y (yaw), Z (roll). Yaw > 0 turns the screen towards +X.
SCENES = {
    # Three phones, the one in front is the screen to read; the other two lean in behind it.
    "today": {
        "camera": (0.0, 3.0, 62.0), "target": (0.0, 0.2, 0.0),
        "phones": [
            {"shot": "today_night", "loc": (-6.9, -0.6, -5.5), "rot": (-5, 25, 1.5)},
            {"shot": "today_sheet", "loc": (6.9, -0.6, -5.5), "rot": (-5, -25, -1.5)},
            {"shot": "today_now", "loc": (0.0, 0.4, 0.0), "rot": (-5, 0, 0)},
        ],
    },
    # Two phones, one in front and lower, one behind and higher, both turned the same way.
    "trends": {
        # a square picture: the pair is as tall as it is wide, and in 4:3 the lower phone lost its foot
        "camera": (0.0, 3.0, 56.0), "target": (0.0, 0.0, 0.0), "aspect": 1.0,
        "phones": [
            {"shot": "trends_readiness", "loc": (-4.4, 1.5, -4.0), "rot": (-6, 20, 3)},
            {"shot": "trends_scrub", "loc": (4.6, -1.0, 1.5), "rot": (-6, 20, 3)},
        ],
    },
    # Three phones in a straight row, all turned the same way: one Home Screen at three moments (just synced, the next day, four
    # days later), so they stand level, like the frames of a strip. They turn to the right: turned to the left the big soft key
    # lands on the glass and veils the screens, which reads as the dimming the widgets show for old data.
    "widgets": {
        "camera": (0.0, 3.0, 70.0), "target": (0.0, 0.0, 0.0),
        "phones": [
            {"shot": "widgets_home_fresh", "loc": (-8.4, 0.0, 0.0), "rot": (-6, 16, 1)},
            {"shot": "widgets_home_day", "loc": (0.0, 0.0, 0.0), "rot": (-6, 16, 1)},
            {"shot": "widgets_home_days", "loc": (8.4, 0.0, 0.0), "rot": (-6, 16, 1)},
        ],
    },
    # Three phones in a descending line, each turned the same way.
    "device": {
        "camera": (0.0, 3.0, 70.0), "target": (0.4, -0.5, 0.0),
        "phones": [
            {"shot": "device_health", "loc": (-8.2, 1.6, -4.0), "rot": (-6, 22, 2)},
            {"shot": "device", "loc": (0.0, 0.0, 0.0), "rot": (-6, 22, 2)},
            {"shot": "device_data", "loc": (8.2, -1.6, 4.0), "rot": (-6, 22, 2)},
        ],
    },
}


def rounded_rect(w, h, r, n=28):
    """Outline points, counter-clockwise, of a rounded rectangle centred on the origin."""
    pts = []
    for cx, cy, a0 in ((w / 2 - r, h / 2 - r, 0), (-w / 2 + r, h / 2 - r, 90), (-w / 2 + r, -h / 2 + r, 180), (w / 2 - r, -h / 2 + r, 270)):
        for i in range(n + 1):
            a = math.radians(a0 + 90 * i / n)
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


def slab(name, w, h, r, z0, z1, bevel=0.0, uv_box=None):
    """A rounded rectangle extruded from z0 to z1. With z0 == z1 it is a single face."""
    mesh = bpy.data.meshes.new(name)
    bm = bmesh.new()
    verts = [bm.verts.new((x, y, z0)) for x, y in rounded_rect(w, h, r)]
    face = bm.faces.new(verts)
    if z1 != z0:
        ext = bmesh.ops.extrude_face_region(bm, geom=[face])
        moved = [v for v in ext["geom"] if isinstance(v, bmesh.types.BMVert)]
        bmesh.ops.translate(bm, vec=(0, 0, z1 - z0), verts=moved)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    if uv_box:  # planar UV over the box (width, height): the screenshot fills it
        layer = bm.loops.layers.uv.new("UVMap")
        bw, bh = uv_box
        for f in bm.faces:
            for loop in f.loops:
                x, y, _ = loop.vert.co
                loop[layer].uv = (x / bw + 0.5, y / bh + 0.5)
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    for p in mesh.polygons:
        p.use_smooth = True
    if bevel:
        m = obj.modifiers.new("bevel", "BEVEL")
        m.width = bevel
        m.segments = 4
        m.limit_method = "ANGLE"
        m.angle_limit = math.radians(35)
        m.harden_normals = True
    return obj


def box(name, size, loc, parent, bevel=0.03):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
    o = bpy.context.active_object
    o.name = name
    o.scale = size
    bpy.ops.object.transform_apply(scale=True)
    m = o.modifiers.new("bevel", "BEVEL")
    m.width = bevel
    m.segments = 3
    o.parent = parent
    for p in o.data.polygons:
        p.use_smooth = True
    return o


def principled(name, **kw):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    for k, v in kw.items():
        bsdf.inputs[k.replace("_", " ")].default_value = v
    return mat, bsdf


def metal_material():
    # natural titanium: a warm light grey that a black ground can still show as a silhouette
    mat, b = principled("frame", Base_Color=(0.62, 0.60, 0.57, 1), Metallic=1.0, Roughness=0.27)
    return mat


def glass_material():
    mat, b = principled("glass", Base_Color=(0.0, 0.0, 0.0, 1), Metallic=0.0, Roughness=0.035)
    b.inputs["Specular IOR Level"].default_value = 0.8
    return mat


def screen_material(path):
    # the screen is the app: a faint, soft reflection of the lights stays on it (the user likes the glass look) but not enough to
    # change how the interface reads, and the colours are the screenshot's own (emission 1.0 with the Standard view transform
    # gives back the pixels). The strong version of this (specular 0.6, roughness 0.09, emission 1.3) washed the screens out.
    mat, b = principled("screen", Base_Color=(0, 0, 0, 1), Metallic=0.0, Roughness=0.14)
    b.inputs["Specular IOR Level"].default_value = 0.3
    nt = mat.node_tree
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = bpy.data.images.load(path)
    tex.image.colorspace_settings.name = "sRGB"
    tex.interpolation = "Cubic"
    tex.extension = "EXTEND"
    nt.links.new(tex.outputs["Color"], b.inputs["Emission Color"])
    b.inputs["Emission Strength"].default_value = 1.0
    return mat


def build_phone(shot, tex_dir, loc, rot):
    root = bpy.data.objects.new(f"phone_{shot}", None)
    bpy.context.scene.collection.objects.link(root)

    body = slab("body", W, H, R_BODY, -T / 2, T / 2, bevel=0.055)
    body.data.materials.append(metal_material())
    body.parent = root

    front = slab("glass", W - 2 * GLASS_INSET, H - 2 * GLASS_INSET, R_BODY - GLASS_INSET, T / 2 - 0.015, T / 2 + 0.02, bevel=0.012)
    front.data.materials.append(glass_material())
    front.parent = root

    screen = slab("screen", SCREEN_W, SCREEN_H, R_SCREEN, T / 2 + 0.0215, T / 2 + 0.0215, uv_box=(SCREEN_W, SCREEN_H))
    screen.data.materials.append(screen_material(f"{tex_dir}/{shot}.png"))
    screen.parent = root

    back = slab("back", W - 2 * GLASS_INSET, H - 2 * GLASS_INSET, R_BODY - GLASS_INSET, -T / 2 - 0.02, -T / 2 + 0.015, bevel=0.012)
    back.data.materials.append(glass_material())
    back.parent = root

    # side buttons: power on the right, action and volume on the left
    for name, x, y, length in (("power", W / 2 + 0.012, 2.6, 2.1), ("action", -W / 2 - 0.012, 4.6, 0.9),
                               ("vol_up", -W / 2 - 0.012, 2.9, 1.5), ("vol_down", -W / 2 - 0.012, 1.0, 1.5)):
        b = box(name, (0.1, length, 0.42), (x, y, 0), root)
        b.data.materials.append(metal_material())

    root.location = loc
    root.rotation_euler = [math.radians(a) for a in rot]
    return root, screen


def aim(obj, at):
    """Turn obj so that its -Z axis looks at the point `at` with its +Y axis towards the scene's Y (up in these pictures).
    Blender's own track helpers take world +Z as up, which is degenerate for a camera that looks along Z."""
    back = (obj.location - Vector(at)).normalized()
    right = Vector((0, 1, 0)).cross(back).normalized()
    up = back.cross(right)
    obj.rotation_euler = Matrix((right, up, back)).transposed().to_euler()


def softbox(name, kind, size, loc, target, power):
    d = bpy.data.lights.new(name, "AREA")
    d.shape = "RECTANGLE" if kind == "rect" else "SQUARE"
    d.size = size[0]
    if kind == "rect":
        d.size_y = size[1]
    d.energy = power
    d.color = (1.0, 1.0, 1.0)
    o = bpy.data.objects.new(name, d)
    bpy.context.scene.collection.objects.link(o)
    o.location = loc
    aim(o, target)
    return o


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    opt = {"--width": "1760", "--samples": "96"}
    for i in range(0, len(argv), 2):
        opt[argv[i]] = argv[i + 1]
    spec = SCENES[opt["--scene"]]
    width = int(opt["--width"])
    height = int(round(width / float(opt.get("--aspect", spec.get("aspect", 1.333)))))

    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.samples = int(opt["--samples"])
    scene.cycles.use_denoising = True
    scene.cycles.denoiser = "OPENIMAGEDENOISE"
    scene.cycles.max_bounces = 6
    scene.cycles.glossy_bounces = 4
    prefs = bpy.context.preferences.addons["cycles"].preferences
    try:
        prefs.compute_device_type = "METAL"
        prefs.get_devices()
        for d in prefs.devices:
            d.use = True
        scene.cycles.device = "GPU"
    except Exception as e:  # a machine with no GPU renders on the CPU, only slower
        print("GPU not available:", e)
    scene.render.resolution_x, scene.render.resolution_y = width, height
    scene.render.resolution_percentage = 100
    scene.render.film_transparent = True
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.view_settings.view_transform = "Standard"  # the app's colours must stay the app's colours
    scene.view_settings.look = "None"

    world = bpy.data.worlds.new("black")
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs["Color"].default_value = (0, 0, 0, 1)
    scene.world = world

    # camera: a long lens keeps the phones from stretching at the edges
    cam_data = bpy.data.cameras.new("cam")
    cam_data.lens = 85
    cam = bpy.data.objects.new("cam", cam_data)
    scene.collection.objects.link(cam)
    cam.location = spec["camera"]
    target = spec["target"]
    aim(cam, target)
    scene.camera = cam

    # light: a big soft key from the upper left (it only shows on the black glass round the screen), two thin strips behind the phones that run along the
    # edges of the frame, and a top strip for the upper edge
    softbox("key", "sq", (26,), (-24, 26, 52), target, 8000)
    softbox("rim_left", "rect", (3, 40), (-34, 4, -16), target, 18000)
    softbox("rim_right", "rect", (3, 40), (34, 2, -14), target, 22000)
    softbox("top", "rect", (30, 3), (0, 34, 4), target, 11000)
    softbox("bottom", "rect", (30, 3), (0, -30, 8), target, 8000)
    softbox("fill", "sq", (30,), (26, -10, 50), target, 1800)

    phones = []
    for p in spec["phones"]:
        phones.append(build_phone(p["shot"], opt["--tex"], p["loc"], p["rot"]) + (p["shot"],))

    bpy.context.view_layer.update()
    # where things land in the picture, from the top left, 0 to 1
    info = []
    for root, screen, shot in phones:
        def at(local):
            v = world_to_camera_view(scene, cam, root.matrix_world @ Vector(local))
            return [round(v.x, 4), round(1 - v.y, 4)]
        corners = [at((sx * W / 2, sy * H / 2, sz * T / 2)) for sx in (-1, 1) for sy in (-1, 1) for sz in (-1, 1)]
        xs, ys = [c[0] for c in corners], [c[1] for c in corners]
        info.append({"shot": shot, "centre": at((0, 0, T / 2)), "top": at((0, SCREEN_H / 2, T / 2)),
                     "bottom": at((0, -SCREEN_H / 2, T / 2)), "box": [min(xs), min(ys), max(xs), max(ys)]})

    scene.render.filepath = opt["--out"]
    bpy.ops.render.render(write_still=True)
    with open(opt["--out"] + ".json", "w") as f:
        json.dump({"width": width, "height": height, "phones": info}, f, indent=1)


main()
