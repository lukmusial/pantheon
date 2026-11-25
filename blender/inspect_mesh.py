"""Report triangle/vertex counts and bounding-box size of mesh files.

Usage (run from any directory that is NOT a download folder):
    blender -b --factory-startup --python blender/inspect_mesh.py -- file1.stl file2.glb ...

Prints one TSV line per file:
    MESH <path> <format> <triangles> <vertices> <dx> <dy> <dz>
Binary STL is parsed directly with numpy (fast, no import into the scene).
Other formats (GLB/GLTF/OBJ/PLY/FBX) are imported with bpy. Files are only read, never executed.
"""
import os
import sys

import numpy as np


def inspect_stl(path):
    size = os.path.getsize(path)
    with open(path, "rb") as fh:
        head = fh.read(84)
        ntri = int(np.frombuffer(head[80:84], dtype="<u4")[0])
        if 84 + 50 * ntri != size:
            return None  # ASCII or damaged; fall back to bpy
        lo = np.full(3, np.inf)
        hi = np.full(3, -np.inf)
        dt = np.dtype([("n", "<f4", 3), ("v", "<f4", (3, 3)), ("a", "<u2")])
        chunk = 2_000_000
        left = ntri
        while left > 0:
            n = min(chunk, left)
            arr = np.frombuffer(fh.read(50 * n), dtype=dt)
            v = arr["v"].reshape(-1, 3)
            lo = np.minimum(lo, v.min(axis=0))
            hi = np.maximum(hi, v.max(axis=0))
            left -= n
    d = hi - lo
    # STL stores no shared vertices; a closed manifold has about tris/2
    return "stl", ntri, "~%d" % (ntri // 2), d


def inspect_bpy(path):
    import bpy
    from mathutils import Vector

    bpy.ops.wm.read_factory_settings(use_empty=True)
    ext = os.path.splitext(path)[1].lower()
    if ext in (".glb", ".gltf"):
        bpy.ops.import_scene.gltf(filepath=path)
    elif ext == ".obj":
        bpy.ops.wm.obj_import(filepath=path)
    elif ext == ".ply":
        bpy.ops.wm.ply_import(filepath=path)
    elif ext == ".stl":
        bpy.ops.wm.stl_import(filepath=path)
    elif ext == ".fbx":
        bpy.ops.import_scene.fbx(filepath=path)
    else:
        raise ValueError("unsupported format " + ext)
    tris = 0
    verts = 0
    lo = Vector((float("inf"),) * 3)
    hi = Vector((float("-inf"),) * 3)
    for ob in bpy.context.scene.objects:
        if ob.type != "MESH":
            continue
        me = ob.data
        verts += len(me.vertices)
        tris += sum(len(p.vertices) - 2 for p in me.polygons)
        for corner in ob.bound_box:
            w = ob.matrix_world @ Vector(corner)
            lo = Vector(map(min, lo, w))
            hi = Vector(map(max, hi, w))
    return ext.lstrip("."), tris, str(verts), hi - lo


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    for path in argv:
        try:
            res = None
            if path.lower().endswith(".stl"):
                res = inspect_stl(path)
            if res is None:
                res = inspect_bpy(path)
            fmt, tris, verts, d = res
            print("MESH\t%s\t%s\t%d\t%s\t%.3f\t%.3f\t%.3f" % (path, fmt, tris, verts, d[0], d[1], d[2]), flush=True)
        except Exception as exc:  # keep going over the remaining files
            print("MESHFAIL\t%s\t%r" % (path, exc), flush=True)


main()
