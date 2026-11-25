"""Prepare the scanned Corinthian capital (Tarraco theatre, CC BY-NC) for instancing.

Usage:
    blender -b --factory-startup --python blender/process_capital.py -- candidates [cut_fraction]
        renders one mirrored candidate per quarter into renders/previews/capital/q<k>.png
    blender -b --factory-startup --python blender/process_capital.py -- build <quarter> <cut_fraction>
        writes assets/architecture/capital/capital.fbx and capital.json (quarter -1: no mirroring)
    blender -b --factory-startup --python blender/process_capital.py -- faces [cut_fraction]
        renders the four abacus faces of the unmirrored scan (renders/previews/capital/face_*.png)

Steps: import, square the abacus to the X/Y axes, cut off the shaft stub below the bell at
cut_fraction of the height, keep one quarter (x and y signs from <quarter> 0..3) and mirror it
across both vertical planes. The scan's modern fixing block and its chipped abacus corner sit in
other quarters, so the mirrored result is clean and four-fold symmetric like the original design.
Output: bell base at z = 0, the base ring's centre at the origin, height 1 m (scaled per use in
build_scene.py, the ring fitted to each shaft), faces of the abacus along +-X and +-Y.
capital.json records ring_diameter (in capital heights).
"""

import json
import math
import os
import sys

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC = os.path.join(ROOT, "assets", "architecture", "scans", "capital_tarraco_theatre",
                   "03f18fa9b86b4383aba5df9cd6af4324_normalized.glb")
OUT = os.path.join(ROOT, "assets", "architecture", "capital")
PREV = os.path.join(ROOT, "renders", "previews", "capital")
QUARTERS = [(1, 1), (-1, 1), (-1, -1), (1, -1)]
RING = {}   # base ring fitted in make(): radius (in capital heights), offset removed, points used


def load():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=SRC)
    meshes = [o for o in bpy.data.objects if o.type == "MESH"]
    for o in meshes:
        o.data.transform(o.matrix_world)
    for o in meshes:
        o.parent = None
        o.matrix_world = Matrix.Identity(4)
    for o in list(bpy.data.objects):
        if o.type != "MESH":
            bpy.data.objects.remove(o)
    bpy.ops.object.select_all(action="DESELECT")
    for o in meshes:
        o.select_set(True)
    bpy.context.view_layer.objects.active = meshes[0]
    if len(meshes) > 1:
        bpy.ops.object.join()
    obj = bpy.context.view_layer.objects.active
    obj.data.materials.clear()
    return obj


def coords(obj):
    co = np.empty(len(obj.data.vertices) * 3)
    obj.data.vertices.foreach_get("co", co)
    return co.reshape(-1, 3)


def square_abacus(obj):
    co = coords(obj)
    lo, hi = co.min(axis=0), co.max(axis=0)
    top = co[co[:, 2] > hi[2] - 0.06 * (hi[2] - lo[2])][:, :2]
    best = (1e9, 0.0)
    for k in range(180):
        a = math.radians(k * 0.5)
        c, s = math.cos(a), math.sin(a)
        p = top @ np.array([[c, -s], [s, c]])
        area = np.ptp(p[:, 0]) * np.ptp(p[:, 1])
        if area < best[0]:
            best = (area, a)
    obj.data.transform(Matrix.Rotation(-best[1], 4, "Z"))
    co = coords(obj)
    lo, hi = co.min(axis=0), co.max(axis=0)
    top = co[co[:, 2] > hi[2] - 0.06 * (hi[2] - lo[2])]
    cx, cy = 0.5 * (top[:, 0].min() + top[:, 0].max()), 0.5 * (top[:, 1].min() + top[:, 1].max())
    obj.data.transform(Matrix.Translation((-cx, -cy, -lo[2])))
    return math.degrees(best[1])


def bisect(obj, co, no):
    """Cut along a plane and delete the side the normal points to."""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    geom = bm.verts[:] + bm.edges[:] + bm.faces[:]
    bmesh.ops.bisect_plane(bm, geom=geom, plane_co=co, plane_no=no, clear_outer=True)
    bm.to_mesh(obj.data)
    bm.free()


def make(quarter, cut_fraction):
    obj = load()
    angle = square_abacus(obj)
    h = coords(obj)[:, 2].max()
    bisect(obj, (0, 0, cut_fraction * h), (0, 0, -1))   # drop the shaft stub
    mirror = quarter >= 0
    if mirror:
        sx, sy = QUARTERS[quarter]
        bisect(obj, (0, 0, 0), (-sx, 0, 0))              # keep the sx side
        bisect(obj, (0, 0, 0), (0, -sy, 0))              # keep the sy side
    for scale in (((-1, 1, 1), (1, -1, 1)) if mirror else ()):
        dup = obj.copy()
        dup.data = obj.data.copy()
        bpy.context.scene.collection.objects.link(dup)
        dup.data.transform(Matrix.Diagonal((*scale, 1.0)))
        dup.data.flip_normals()
        bpy.ops.object.select_all(action="DESELECT")
        obj.select_set(True)
        dup.select_set(True)
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.join()
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=0.0005)
    bm.to_mesh(obj.data)
    bm.free()
    co = coords(obj)
    obj.data.transform(Matrix.Scale(1.0 / (co[:, 2].max() - co[:, 2].min()), 4) @
                       Matrix.Translation((0, 0, -co[:, 2].min())))
    # Centre on the base ring, not the abacus. The abacus of the unmirrored scan is chipped, so its
    # bounding box put the ring off the column axis, and the shaft stood off-centre under the bell
    # (user, 2026-11-23). A circle fitted to the cut edge at the bottom gives the axis and the ring
    # diameter, which the level script uses to fit the ring to each shaft.
    co = coords(obj)
    ring = co[co[:, 2] < 0.004]
    x, y = ring[:, 0], ring[:, 1]
    a = np.column_stack([x, y, np.ones_like(x)])
    sol = np.linalg.lstsq(a, x * x + y * y, rcond=None)[0]
    cx, cy = 0.5 * sol[0], 0.5 * sol[1]
    RING["radius"] = float(math.sqrt(sol[2] + cx * cx + cy * cy))
    RING["offset"] = [float(cx), float(cy)]
    RING["points"] = int(len(ring))
    obj.data.transform(Matrix.Translation((-cx, -cy, 0.0)))
    obj.name = obj.data.name = "Capital"
    for p in obj.data.polygons:
        p.use_smooth = True
    return obj, angle


def render(obj, path):
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.display.shading.light = "STUDIO"
    scene.render.resolution_x, scene.render.resolution_y = 900, 700
    cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
    scene.collection.objects.link(cam)
    cam.data.type = "ORTHO"
    cam.data.ortho_scale = 2.2
    cam.location = (1.6, -2.2, 1.1)
    d = Vector((0, 0, 0.5)) - cam.location
    cam.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    scene.camera = cam
    scene.render.filepath = path
    bpy.ops.render.render(write_still=True)
    bpy.data.objects.remove(cam)


def render_faces(obj, prefix):
    """Orthographic views of the four abacus faces, for finding the damaged one."""
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.display.shading.light = "STUDIO"
    scene.render.resolution_x, scene.render.resolution_y = 600, 500
    for label, pos in (("+X", (3, 0, 0.5)), ("-X", (-3, 0, 0.5)), ("+Y", (0, 3, 0.5)), ("-Y", (0, -3, 0.5))):
        cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
        scene.collection.objects.link(cam)
        cam.data.type = "ORTHO"
        cam.data.ortho_scale = 1.4
        cam.location = pos
        cam.rotation_euler = (Vector((0, 0, 0.5)) - Vector(pos)).to_track_quat("-Z", "Y").to_euler()
        scene.camera = cam
        scene.render.filepath = prefix + label.replace("+", "p").replace("-", "m") + ".png"
        bpy.ops.render.render(write_still=True)
        bpy.data.objects.remove(cam)


def main():
    argv = sys.argv[sys.argv.index("--") + 1:]
    os.makedirs(PREV, exist_ok=True)
    if argv[0] == "faces":
        obj, _ = make(-1, float(argv[1]) if len(argv) > 1 else 0.30)
        render_faces(obj, os.path.join(PREV, "face_"))
    elif argv[0] == "candidates":
        cut = float(argv[1]) if len(argv) > 1 else 0.30
        for q in range(4):
            obj, _ = make(q, cut)
            render(obj, os.path.join(PREV, "q%d.png" % q))
    elif argv[0] == "build":
        q, cut = int(argv[1]), float(argv[2])
        obj, angle = make(q, cut)
        os.makedirs(OUT, exist_ok=True)
        render(obj, os.path.join(PREV, "final.png"))
        bpy.ops.object.select_all(action="DESELECT")
        obj.select_set(True)
        bpy.ops.export_scene.fbx(filepath=os.path.join(OUT, "capital.fbx"), use_selection=True,
                                 apply_scale_options="FBX_SCALE_UNITS", mesh_smooth_type="FACE",
                                 add_leaf_bones=False, bake_anim=False)
        co = coords(obj)
        info = {"quarter": q, "cut_fraction": cut, "abacus_rotation_deg": angle,
                "triangles": sum(len(p.vertices) - 2 for p in obj.data.polygons),
                "size": [float(x) for x in (co.max(axis=0) - co.min(axis=0))],
                "ring_diameter": 2.0 * RING["radius"], "ring_offset_removed": RING["offset"],
                "ring_points": RING["points"]}
        json.dump(info, open(os.path.join(OUT, "capital.json"), "w"), indent=1)
        print("CAPITAL_DONE", json.dumps(info))


if __name__ == "__main__":
    main()
