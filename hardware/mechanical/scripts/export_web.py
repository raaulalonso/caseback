"""The assembled disc of design 1 as a glTF for the website (web/public/models/disc.glb).

Headless, from this folder:
    blender -b caseback_disc_design1.blend --python export_web.py -- [--out FILE] [--raw] [--samples N]

It reads the `Disc` collection of the open scene (made by `generate_disc.py --blend`), draws the cell again with
`generate_disc.build_cell` (so the page has the current cell even when the blend is older than the script; it needs no
KiCad), joins the objects into the parts the home page moves one by one, gives every part weighted normals and bakes
ambient occlusion into its vertex colours with Cycles, adds an empty where the "app" callout starts (the antenna, which is
inside the board part) and writes a binary glTF. Unless `--raw` is given it
then runs gltfpack (npx, meshopt compression, positions quantised to 14 bits), which takes the file from about 9 MB to
1.5 MB (0.5 MB gzipped, as a server sends it).

The occlusion is baked for each part on its own, with the other parts hidden: the page takes the disc apart and shows the
board through the shell, so shadows cast by one part on another would be wrong in most of what it shows. The page uses the
red channel as the occlusion of the light from the studio around the disc, which costs nothing when it draws.

Units stay in millimetres. The glTF exporter turns Blender's +Z (towards the watch) into +Y; x stays to the right of the
watch-side view. Every part keeps its assembled position, so the page only has to move parts along +Y and back.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from math import radians

import bpy
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import generate_disc as GD  # noqa: E402  (the cell, the materials and the weighted normals)

ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
OUT = os.path.join(ROOT, "web", "public", "models", "disc.glb")
GLTFPACK = "gltfpack@1.3.0"
AO_DISTANCE = 1.6  # mm: about half the thickness of the disc, so the cavity of the shell darkens towards its floor
LONG_EDGE = 1.2  # mm, see flatten_long

# part name -> prefixes of the objects in the Disc collection, in the order the home page puts them in
PARTS = (
    ("shell", ("Shell",)),
    ("window", ("Window_",)),
    ("contacts", ("Slugs_",)),
    ("board", ("PCB", "Skin_", "Pads_", "Thermal_")),
    ("cell", ("Cell_", "Foam_")),
    ("gasket", ("Seam_",)),
    ("lid", ("Lid",)),
    ("pad", ("Microsuction",)),
)


def args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    out, raw, blend, samples = OUT, False, None, 64
    i = 0
    while i < len(argv):
        if argv[i] == "--out":
            out, i = os.path.abspath(argv[i + 1]), i + 1
        elif argv[i] == "--raw":
            raw = True
        elif argv[i] == "--blend":
            blend, i = os.path.abspath(argv[i + 1]), i + 1
        elif argv[i] == "--samples":
            samples, i = int(argv[i + 1]), i + 1
        i += 1
    return out, raw, blend, samples


def bottom_centre(ob):
    pts = [ob.matrix_world @ Vector(c) for c in ob.bound_box]
    return Vector((sum(p.x for p in pts) / 8, sum(p.y for p in pts) / 8, min(p.z for p in pts)))


def bake_ao(parts, samples):
    """Ambient occlusion of each part on its own, into a colour attribute named AO."""
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = samples
    scene.world = scene.world or bpy.data.worlds.new("World")
    scene.world.light_settings.distance = AO_DISTANCE
    for ob in parts:
        for other in parts:
            other.hide_render = other is not ob
        # Per face corner, so that a corner is baked along its own normal and not the average at a sharp edge. The board
        # is per vertex: its parts are small, and corners would split its 170 000 vertices and double the file.
        ob.data.color_attributes.new("AO", "BYTE_COLOR", "POINT" if ob.name == "board" else "CORNER")
        ob.data.color_attributes.active_color = ob.data.color_attributes["AO"]
        bpy.ops.object.select_all(action="DESELECT")
        ob.select_set(True)
        bpy.context.view_layer.objects.active = ob
        bpy.ops.object.bake(type="AO", target="VERTEX_COLORS")
        flatten_long(ob)
        print(f"baked {ob.name}")
    for ob in parts:
        ob.hide_render = False


def flatten_long(ob):
    """Occlusion is drawn by interpolating between vertices. The flat faces of the shell and the lid are large polygons
    that the export cuts into long thin triangles from the windows and the engraving to the rim, so a dark corner at a
    window would streak across the whole face. A corner of a polygon wider than LONG_EDGE is set back to unoccluded,
    fully at twice that width; the same vertex keeps its occlusion on the small faces of a wall or a groove."""
    me = ob.data
    span = []
    for poly in me.polygons:
        pts = [me.vertices[i].co for i in poly.vertices]
        lo = Vector([min(c) for c in zip(*pts)])
        hi = Vector([max(c) for c in zip(*pts)])
        span.append((hi - lo).length)
    attr = me.color_attributes["AO"]
    if attr.domain == "CORNER":
        width = [0.0] * len(me.loops)
        for poly in me.polygons:
            for li in poly.loop_indices:
                width[li] = span[poly.index]
    else:
        width = [0.0] * len(me.vertices)
        for poly in me.polygons:
            for vi in poly.vertices:
                width[vi] = max(width[vi], span[poly.index])
    for w, c in zip(width, attr.data):
        u = min(1.0, max(0.0, (w - LONG_EDGE) / LONG_EDGE))
        v = c.color[0] + (1.0 - c.color[0]) * u
        c.color = (v, v, v, 1.0)


def main():
    out, raw, blend, samples = args()
    if blend:
        bpy.ops.wm.open_mainfile(filepath=blend)
    src = bpy.data.collections.get("Disc")
    if src is None:
        raise SystemExit("no Disc collection: open caseback_disc_design1.blend or pass --blend")

    for o in [o for o in src.objects if o.name.startswith(("Cell_", "Foam_"))]:
        bpy.data.objects.remove(o, do_unlink=True)
    GD.build_cell(GD.materials())

    scene = bpy.context.scene
    web = bpy.data.collections.new("Web")
    scene.collection.children.link(web)
    taken = set()
    antenna = bottom_centre(src.objects["Skin_antenna"])
    roots = {}
    for part, prefixes in PARTS:
        obs = [o for o in src.objects if o.type == "MESH" and o.name.startswith(prefixes) and o.name not in taken]
        if not obs:
            raise SystemExit(f"no objects for {part}")
        taken.update(o.name for o in obs)
        copies = []
        for o in obs:
            c = o.copy()
            c.data = o.data.copy()
            c.modifiers.clear()
            web.objects.link(c)
            copies.append(c)
        bpy.ops.object.select_all(action="DESELECT")
        for c in copies:
            c.select_set(True)
        bpy.context.view_layer.objects.active = copies[0]
        if len(copies) > 1:
            bpy.ops.object.join()
        ob = bpy.context.view_layer.objects.active
        bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
        # Without sharp edges and weighted normals the flat faces would share normals with the walls of the windows, the
        # engraving and the fillets, and the shading (and the occlusion baked along those normals) would streak across them.
        bpy.ops.object.shade_smooth_by_angle(angle=radians(30), keep_sharp_edges=True)
        GD.weighted_normals(ob)
        ob = bpy.context.view_layer.objects.active
        ob.name = ob.data.name = part
        roots[part] = ob
        print(f"{part:9s} {len(obs):3d} objects  {len(ob.data.vertices):7d} vertices")
    left = sorted(o.name for o in src.objects if o.type == "MESH" and o.name not in taken)
    if left:
        print("not exported:", ", ".join(left))

    # only the Web collection takes part in the bake and the export
    for c in scene.collection.children:
        c.hide_viewport = c.hide_render = c is not web
        bpy.context.view_layer.layer_collection.children[c.name].exclude = c is not web
    for o in scene.collection.objects:
        o.hide_render = True
    bake_ao(list(roots.values()), samples)

    e = bpy.data.objects.new("anchor_antenna", None)
    web.objects.link(e)
    e.parent = roots["board"]
    e.location = antenna
    bpy.ops.object.select_all(action="DESELECT")
    for o in web.objects:
        o.select_set(True)

    os.makedirs(os.path.dirname(out), exist_ok=True)
    tmp = out if raw else out + ".raw.glb"
    bpy.ops.export_scene.gltf(
        filepath=tmp, export_format="GLB", use_selection=True, export_apply=True, export_yup=True,
        export_normals=True, export_texcoords=False, export_materials="EXPORT", export_cameras=False, export_lights=False,
        export_vertex_color="NAME", export_vertex_color_name="AO", export_all_vertex_colors=False,
        export_extras=False, export_animations=False,
    )
    print(f"wrote {os.path.basename(tmp)} ({os.path.getsize(tmp) / 1e6:.1f} MB)")
    if raw:
        return
    npx = shutil.which("npx")
    if not npx:
        raise SystemExit("npx not found: install Node, or pass --raw and run gltfpack yourself")
    # -cc meshopt compression, -kn keep the named nodes (parts and anchor), -km keep the materials apart, -vp 14 position bits
    subprocess.run([npx, "--yes", GLTFPACK, "-i", tmp, "-o", out, "-cc", "-kn", "-km", "-vp", "14"], check=True)
    os.remove(tmp)
    print(f"wrote {os.path.basename(out)} ({os.path.getsize(out) / 1e6:.2f} MB)")


main()
