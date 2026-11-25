"""Render a 4-view contact sheet (front/right/back/left) of a mesh for a quick completeness check.

Usage:
    blender -b --factory-startup --python blender/render_preview.py -- out.png mesh [up_axis]

up_axis is optional: Z (default) or Y, for STL/OBJ files whose vertical axis is Y.
The mesh file is only imported and rendered with the Workbench engine; nothing from it is executed.
"""
import math
import os
import sys

import bpy
import numpy as np
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:]
out_png, path = argv[0], argv[1]
up = argv[2].upper() if len(argv) > 2 else "Z"

bpy.ops.wm.read_factory_settings(use_empty=True)
ext = os.path.splitext(path)[1].lower()
if ext in (".glb", ".gltf"):
    bpy.ops.import_scene.gltf(filepath=path)
elif ext == ".obj":
    bpy.ops.wm.obj_import(filepath=path, forward_axis="Y", up_axis="Z")
elif ext == ".ply":
    bpy.ops.wm.ply_import(filepath=path)
elif ext == ".stl":
    bpy.ops.wm.stl_import(filepath=path)
else:
    raise SystemExit("unsupported format " + ext)

scene = bpy.context.scene
meshes = [o for o in scene.objects if o.type == "MESH"]
if up == "Y":
    root = bpy.data.objects.new("root", None)
    scene.collection.objects.link(root)
    for o in scene.objects:
        if o.parent is None and o is not root:
            o.parent = root
    root.rotation_euler = (math.radians(90), 0, 0)
    bpy.context.view_layer.update()

lo = Vector((float("inf"),) * 3)
hi = Vector((float("-inf"),) * 3)
for ob in meshes:
    for corner in ob.bound_box:
        w = ob.matrix_world @ Vector(corner)
        lo = Vector(map(min, lo, w))
        hi = Vector(map(max, hi, w))
center = (lo + hi) / 2
size = hi - lo
radius = max(size) * 0.5

cam_data = bpy.data.cameras.new("cam")
cam_data.type = "ORTHO"
cam_data.ortho_scale = max(size.z, max(size.x, size.y) * 1.5) * 1.05
cam_data.clip_start = radius * 0.01
cam_data.clip_end = radius * 20
cam = bpy.data.objects.new("cam", cam_data)
scene.collection.objects.link(cam)
scene.camera = cam

scene.render.engine = "BLENDER_WORKBENCH"
scene.display.shading.light = "STUDIO"
scene.display.shading.color_type = "SINGLE"
scene.display.shading.single_color = (0.85, 0.83, 0.8)
scene.display.shading.show_cavity = True
scene.display.shading.cavity_type = "BOTH"
scene.render.resolution_x = 420
scene.render.resolution_y = 630
scene.render.film_transparent = False
scene.render.image_settings.file_format = "PNG"

tiles = []
base = os.path.splitext(out_png)[0]
for i, ang in enumerate((0, 90, 180, 270)):
    a = math.radians(ang)
    direction = Vector((math.sin(a), -math.cos(a), 0.0))
    cam.location = center + direction * radius * 6
    cam.rotation_euler = (math.radians(90), 0, a)
    tile = "%s_v%d.png" % (base, i)
    scene.render.filepath = tile
    bpy.ops.render.render(write_still=True)
    img = bpy.data.images.load(tile)
    w, h = img.size
    px = np.empty(w * h * 4, dtype=np.float32)
    img.pixels.foreach_get(px)
    tiles.append(px.reshape(h, w, 4))
    bpy.data.images.remove(img)
    os.remove(tile)

sheet = np.concatenate(tiles, axis=1)
h, w = sheet.shape[:2]
res = bpy.data.images.new("sheet", width=w, height=h, alpha=False)
res.pixels.foreach_set(sheet.ravel())
res.filepath_raw = out_png
res.file_format = "PNG"
res.save()
print("PREVIEW\t%s\t%s\tsize=%.2f,%.2f,%.2f" % (path, out_png, size.x, size.y, size.z))
