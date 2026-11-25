"""Normalise one statue scan for Unreal: up axis, facing, height, origin, triangle budget.

Usage:
    blender -b --factory-startup --python blender/process_statues.py -- <key> [<key> ...]
    blender -b --factory-startup --python blender/process_statues.py -- --list

Writes assets/statues/processed/<key>.fbx, <key>.json and renders/previews/statues/<key>.png
(front view, camera on -Y looking at +Y, i.e. what the rotunda centre sees after placement).

After processing, a statue stands on z = 0 with its base centred on the origin, faces -Y
and is `height` metres tall. Placement in the building is done by build_pantheon.py slots
and the UE level script.
"""

import json
import math
import os
import sys

import bpy
from mathutils import Matrix, Vector

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
RAW = os.path.join(ROOT, "assets", "statues", "raw")
OUT = os.path.join(ROOT, "assets", "statues", "processed")
PREVIEW = os.path.join(ROOT, "renders", "previews", "statues")

# key: source file (relative to RAW), target height in metres including the scan's own plinth,
# yaw in degrees applied after import so the face looks towards -Y, optional up axis override
# ("Y" for files whose vertical axis is Y), triangle budget.
STATUES = {
    "jupiter_smyrna": dict(src="jupiter_smyrna_stw/67a2fdd4cc10992323531181bc987556_normalized.glb",
                           height=7.0, yaw=180.0, max_tris=2_000_000),
    "venus_capitoline": dict(src="venus_capitoline/KAS493_capitoline_venus.stl", height=2.9, yaw=0.0),
    "ares_ludovisi": dict(src="ares_ludovisi/KAS250_ares_ludovisi.stl", height=2.3, yaw=0.0),
    "apollo_belvedere": dict(src="apollo_belvedere/KAS353_apollo_belvedere_smk.stl", height=3.1, yaw=0.0),
    "diana_gabii": dict(src="diana_gabii/diana_von_gabii_vimune.glb", height=2.9, yaw=0.0),
    "athena_giustiniani": dict(src="athena_giustiniani/KAS255_athena_giustiniani.stl", height=3.1, yaw=0.0),
    "neptune_nimes": dict(src="neptune_nimes/Neptune_Iustinian_Funie.obj", height=3.1, yaw=180.0, flip=True),
    "apollo_lykeios": dict(src="apollo_lykeios/KAS1026_apollo_lykeios.stl", height=2.6, yaw=0.0),
    "herakles_lansdowne": dict(src="herakles_lansdowne/KAS224_herakles_lansdowne.stl", height=2.6, yaw=0.0),
    "dionysus": dict(src="dionysus_hadrians_villa/KAS196_dionysos.stl", height=2.6, yaw=0.0),
    "hermes_logios": dict(src="hermes_logios_germanicus/KAS644_germanicus.stl", height=2.6, yaw=0.0),
    "augustus_prima_porta": dict(src="augustus_prima_porta/KAS65_augustus_prima_porta.stl", height=2.6, yaw=0.0),
    "demeter_knidos": dict(src="demeter_knidos/KAS128_demeter_knidos.stl", height=2.2, yaw=0.0),
    "hermes_belvedere": dict(src="hermes_belvedere/KAS1161_hermes_belvedere.stl", height=2.6, yaw=0.0),
    "caesar": dict(src="caesar_fori_imperiali/caesar_fori_imperiali_riccioni.glb", height=4.4, yaw=0.0),
    # complete replacements (Scan the World via Zenodo, CC BY-NC-SA 4.0) for damaged or soft scans
    "ceres_louvre": dict(src="julia_ceres_louvre_stw/3895e1fc275de79751756e1436bc80b1_normalized.glb",
                         height=2.6, yaw=0.0),
    "hermes_farnese": dict(src="hermes_farnese_bm_stw/2c3a829b582d040ac66722b92958779c_normalized.glb",
                           height=2.6, yaw=180.0),
    "caesar_borghese": dict(src="caesar_borghese_stw/df1c917fe9a4351257c056a0bfb841e6_normalized.glb",
                            height=2.6, yaw=0.0),
    # attic blind niches (reconstruction after Palladio and Ligorio; reference/attic_niches.md), 2 m scale
    "attic_juno": dict(src="juno_versailles_stw/31bd6d6806b04eb3f3fa221ecd5fe7a0_normalized.glb", height=2.0, yaw=90.0),
    "attic_aesculapius": dict(src="asklepios_giustini_stw/5cbf4da0b186e0db28895b97b3e45c3f_normalized.glb",
                              height=2.0, yaw=0.0),
    "attic_mercury": dict(src="hermes_pioclementino_versailles_stw/87d7f1303ccbfbae61921890ce70fd07_normalized.glb",
                          height=2.0, yaw=0.0),
    "attic_augustus_jupiter": dict(src="emperor_seated_augustus_stw/2bda4307fcadc8dc90b9c76642090540_normalized.glb",
                                   height=1.7, yaw=0.0),
    "attic_nerva_jupiter": dict(src="nerva_jupiter_stw/881649f3726d9aa68c2130fcfa59c0ee_normalized.glb",
                                height=1.7, yaw=0.0),
    "attic_mars": dict(src="mars_bacon_lincoln/Mars.stl", height=2.0, yaw=0.0, flip=True),
    "attic_ceres": dict(src="demeter_seated_stw/6233f987ee29f122ae48f26cb280f44e_normalized.glb", height=1.7, yaw=0.0),
    "attic_vulcan": dict(src="vulcan_thorvaldsen/a9f8a85b4d6842cf9e10b7b5d4070dc2.glb", height=2.0, yaw=0.0),
    # portico niche (Cassius Dio 53.27): Augustus at heroic scale; the aedicula beside the apse
    # takes the complete Hermitage Augustus as Jupiter instead
    "augustus_portico": dict(src="augustus_prima_porta/KAS65_augustus_prima_porta.stl", height=3.4, yaw=0.0),
    "augustus_jupiter_hermitage": dict(src="augustus_jupiter_hermitage_stw/f42cfb85fed7b26149043ec86e59d39f_normalized.glb",
                                       height=2.3, yaw=0.0),
    # Agrippa: generated with TRELLIS.2 (microsoft/TRELLIS.2 Space) from the public-domain photo of the
    # colossal Venice Agrippa (Commons "Agrip2.jpg"); see assets/statues/raw/agrippa_gen3d/notes.md
    "agrippa_portico": dict(src="agrippa_gen3d/agrippa_trellis2.glb", height=3.3, yaw=0.0),
}
DEFAULT_MAX_TRIS = 1_500_000


def import_mesh(path):
    before = set(bpy.data.objects)
    ext = os.path.splitext(path)[1].lower()
    if ext in (".glb", ".gltf"):
        bpy.ops.import_scene.gltf(filepath=path)
    elif ext == ".stl":
        bpy.ops.wm.stl_import(filepath=path)
    elif ext == ".obj":
        bpy.ops.wm.obj_import(filepath=path)
    elif ext == ".ply":
        bpy.ops.wm.ply_import(filepath=path)
    else:
        raise ValueError("unsupported format: " + ext)
    meshes = [o for o in bpy.data.objects if o not in before and o.type == "MESH"]
    if not meshes:
        raise RuntimeError("no mesh imported from " + path)
    # bake parent transforms (glTF imports come with a Y-up correction on a parent)
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


def bbox(obj):
    import numpy as np
    co = np.empty(len(obj.data.vertices) * 3)
    obj.data.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)
    return co.min(axis=0), co.max(axis=0)


def normalise(obj, cfg):
    lo, hi = bbox(obj)
    up = cfg.get("up")
    if up is None:
        up = "XYZ"[int((hi - lo).argmax())]
    if up == "Y":
        obj.data.transform(Matrix.Rotation(math.radians(90.0), 4, "X"))
    elif up == "X":
        obj.data.transform(Matrix.Rotation(math.radians(-90.0), 4, "Y"))
    if cfg.get("flip"):
        obj.data.transform(Matrix.Rotation(math.radians(180.0), 4, "X"))
    obj.data.transform(Matrix.Rotation(math.radians(cfg.get("yaw", 0.0)), 4, "Z"))
    lo, hi = bbox(obj)
    scale = cfg["height"] / float(hi[2] - lo[2])
    # Centre on the footprint (the bottom 3 % of the figure: plinth or feet), not on the
    # whole bounding box, which raised arms and attributes pull to one side.
    import numpy as np
    co = np.empty(len(obj.data.vertices) * 3)
    obj.data.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)
    foot = co[co[:, 2] < lo[2] + 0.03 * (hi[2] - lo[2])]
    flo, fhi = foot.min(axis=0), foot.max(axis=0)
    centre = Vector((0.5 * (flo[0] + fhi[0]), 0.5 * (flo[1] + fhi[1]), lo[2]))
    obj.data.transform(Matrix.Scale(scale, 4) @ Matrix.Translation(-centre))
    return up, scale


def decimate(obj, max_tris):
    tris = sum(len(p.vertices) - 2 for p in obj.data.polygons)
    if tris <= max_tris:
        return tris
    mod = obj.modifiers.new("Decimate", "DECIMATE")
    mod.decimate_type = "COLLAPSE"
    mod.ratio = max_tris / float(tris)
    mod.use_collapse_triangulate = True
    bpy.ops.object.modifier_apply(modifier=mod.name)
    return sum(len(p.vertices) - 2 for p in obj.data.polygons)


def render_front(obj, path, height):
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.display.shading.light = "STUDIO"
    scene.display.shading.color_type = "SINGLE"
    scene.render.resolution_x, scene.render.resolution_y = 600, 900
    cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
    scene.collection.objects.link(cam)
    cam.data.type = "ORTHO"
    cam.data.ortho_scale = height * 1.15
    cam.location = (0.0, -10.0 * height, 0.5 * height)
    cam.rotation_euler = (math.radians(90.0), 0.0, 0.0)
    cam.data.clip_end = 30.0 * height
    scene.camera = cam
    scene.render.filepath = path
    bpy.ops.render.render(write_still=True)


def process(key):
    cfg = STATUES[key]
    bpy.ops.wm.read_factory_settings(use_empty=True)
    obj = import_mesh(os.path.join(RAW, cfg["src"]))
    tris_in = sum(len(p.vertices) - 2 for p in obj.data.polygons)
    up, scale = normalise(obj, cfg)
    tris = decimate(obj, cfg.get("max_tris", DEFAULT_MAX_TRIS))
    obj.name = obj.data.name = "Statue_" + key
    bpy.ops.object.shade_smooth()

    os.makedirs(OUT, exist_ok=True)
    os.makedirs(PREVIEW, exist_ok=True)
    lo, hi = bbox(obj)
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.ops.export_scene.fbx(filepath=os.path.join(OUT, key + ".fbx"), use_selection=True,
                             apply_scale_options="FBX_SCALE_UNITS", mesh_smooth_type="FACE",
                             add_leaf_bones=False, bake_anim=False)
    info = {"key": key, "source": cfg["src"], "up_axis": up, "scale": scale, "yaw": cfg.get("yaw", 0.0),
            "triangles_in": tris_in, "triangles": tris,
            "size_m": [round(float(hi[i] - lo[i]), 3) for i in range(3)]}
    with open(os.path.join(OUT, key + ".json"), "w") as fh:
        json.dump(info, fh, indent=1)
    render_front(obj, os.path.join(PREVIEW, key + ".png"), cfg["height"])
    print("STATUE_DONE", json.dumps(info))


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    if not argv or argv[0] == "--list":
        print(" ".join(STATUES))
        return
    for key in argv:
        process(key)


if __name__ == "__main__":
    main()
