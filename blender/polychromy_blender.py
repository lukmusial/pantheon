"""Blender side of the polychromy pipeline (driven by blender/paint_statues.py; not run by hand).

Commands (all run headless):
    blender -b --factory-startup --python blender/polychromy_blender.py -- mesh  <fbx> <workdir>
    blender -b --factory-startup --python blender/polychromy_blender.py -- views <fbx> <workdir> <views.json>
    blender -b --factory-startup --python blender/polychromy_blender.py -- paint <workdir> <out.fbx>
    blender -b --factory-startup --python blender/polychromy_blender.py -- preview <painted.fbx> <workdir> <out.png> <preview.json>

mesh     welds exact duplicate vertices (the scans are often triangle soup), subdivides locally
         where <workdir>/subdivide.json asks for detail (eyes: spheres with a maximum edge length),
         saves <workdir>/work.blend and <workdir>/mesh.npz: co (V,3) float32, tris (T,3) int32,
         vnormal (V,3) float32.
views    renders each camera in views.json (Workbench, grey studio shading with cavity) to
         <workdir>/views/<name>.png (RGBA) and <name>.exr (depth), and writes the camera
         projection matrices to <workdir>/views/<name>.json.
paint    opens work.blend (same vertex order as mesh.npz), loads <workdir>/paint.npz (rgba per
         vertex: sRGB colour, linear coverage), writes the colour attribute "Col" (point domain)
         and exports FBX with sRGB vertex colours. It then re-imports the FBX and checks that the
         colours survived (prints PAINT_VERIFY).
preview  renders front, three-quarter and face close-up views with the paint shown over a
         marble-white base, and joins them into one PNG.
"""

import json
import math
import os
import sys

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector

WELD_DIST = 1e-6  # metres; only exact duplicates (triangle-soup scans) are merged


# --------------------------------------------------------------------------- mesh io

def import_statue(path):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=path)
    meshes = [o for o in bpy.data.objects if o.type == "MESH"]
    if not meshes:
        raise RuntimeError("no mesh in " + path)
    for o in meshes:
        o.data.transform(o.matrix_world)
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
    me = obj.data
    for name in [a.name for a in me.color_attributes]:
        me.color_attributes.remove(me.color_attributes[name])
    bm = bmesh.new()
    bm.from_mesh(me)
    n0 = len(bm.verts)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=WELD_DIST)
    bm.to_mesh(me)
    bm.free()
    me.update()
    # Triangle-soup scans come with flat per-face normals. After welding, drop the custom normals
    # and shade smooth, keeping sharp edges only above 50 degrees (plinth corners).
    if "custom_normal" in me.attributes:
        me.attributes.remove(me.attributes["custom_normal"])
    for a in ("sharp_face", "sharp_edge"):
        if a in me.attributes:
            me.attributes.remove(me.attributes[a])
    me.shade_smooth()
    me.set_sharp_from_angle(angle=math.radians(50.0))
    print("WELD %d -> %d vertices" % (n0, len(me.vertices)))
    return obj


def mesh_arrays(obj):
    me = obj.data
    nv = len(me.vertices)
    co = np.empty(nv * 3, dtype=np.float32)
    me.vertices.foreach_get("co", co)
    me.calc_loop_triangles()
    tris = np.empty(len(me.loop_triangles) * 3, dtype=np.int32)
    me.loop_triangles.foreach_get("vertices", tris)
    vn = np.empty(nv * 3, dtype=np.float32)
    me.vertex_normals.foreach_get("vector", vn)
    return co.reshape(-1, 3), tris.reshape(-1, 3), vn.reshape(-1, 3)


def cmd_mesh(fbx, workdir):
    obj = import_statue(fbx)
    sub = os.path.join(workdir, "subdivide.json")
    if os.path.exists(sub):
        with open(sub) as fh:
            regions = json.load(fh)
        if regions:
            subdivide_regions(obj, regions)
    co, tris, vn = mesh_arrays(obj)
    os.makedirs(workdir, exist_ok=True)
    np.savez(os.path.join(workdir, "mesh.npz"), co=co, tris=tris, vnormal=vn)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(workdir, "work.blend"), compress=False)
    print("MESH_DONE verts=%d tris=%d" % (len(co), len(tris)))


# --------------------------------------------------------------------------- rendering

def setup_workbench(scene, colour_mode="SINGLE"):
    scene.render.engine = "BLENDER_WORKBENCH"
    sh = scene.display.shading
    sh.light = "STUDIO"
    sh.color_type = colour_mode
    sh.single_color = (0.80, 0.78, 0.74)
    sh.show_cavity = True
    sh.cavity_type = "BOTH"
    sh.cavity_ridge_factor = 1.0
    sh.cavity_valley_factor = 1.0
    sh.show_specular_highlight = True
    scene.render.film_transparent = True
    scene.view_settings.view_transform = "Standard"


def make_camera(scene, name="Cam"):
    cam = bpy.data.objects.new(name, bpy.data.cameras.new(name))
    scene.collection.objects.link(cam)
    scene.camera = cam
    return cam


def place_camera(cam, v):
    """v: dict with target [x,y,z], az, el (degrees; az 0 = camera on -Y looking at +Y,
    az 90 = camera on +X), ortho_scale (or lens for perspective), dist, res [w,h]."""
    az, el = math.radians(v["az"]), math.radians(v["el"])
    d = Vector((math.sin(az) * math.cos(el), -math.cos(az) * math.cos(el), math.sin(el)))
    tgt = Vector(v["target"])
    dist = v.get("dist", 50.0)
    cam.location = tgt + d * dist
    rot = (-d).to_track_quat("-Z", "Y")
    cam.rotation_euler = rot.to_euler()
    cam.data.clip_start = max(0.01, dist - v.get("depth_range", 20.0))
    cam.data.clip_end = dist + v.get("depth_range", 20.0)
    if v.get("type", "ORTHO") == "ORTHO":
        cam.data.type = "ORTHO"
        cam.data.ortho_scale = v["ortho_scale"]
    else:
        cam.data.type = "PERSP"
        cam.data.lens = v.get("lens", 50.0)
    cam.data.sensor_fit = "AUTO"


def camera_json(scene, cam, w, h):
    dg = bpy.context.evaluated_depsgraph_get()
    P = cam.calc_matrix_camera(dg, x=w, y=h, scale_x=1.0, scale_y=1.0)
    V = cam.matrix_world.inverted()
    return {"P": [list(r) for r in P], "V": [list(r) for r in V], "w": w, "h": h,
            "type": cam.data.type, "location": list(cam.location),
            "forward": list(cam.matrix_world.to_3x3() @ Vector((0, 0, -1)))}


def cmd_views(fbx, workdir, views_json):
    with open(views_json) as fh:
        views = json.load(fh)
    obj = import_statue(fbx)
    bpy.ops.object.shade_smooth()
    scene = bpy.context.scene
    setup_workbench(scene)
    scene.view_layers[0].use_pass_z = True
    cam = make_camera(scene)
    out = os.path.join(workdir, "views")
    os.makedirs(out, exist_ok=True)
    for v in views:
        w, h = v["res"]
        scene.render.resolution_x, scene.render.resolution_y = w, h
        scene.render.resolution_percentage = 100
        place_camera(cam, v)
        bpy.context.view_layer.update()
        base = os.path.join(out, v["name"])
        scene.render.image_settings.media_type = "MULTI_LAYER_IMAGE"
        scene.render.image_settings.file_format = "OPEN_EXR_MULTILAYER"
        scene.render.image_settings.color_depth = "32"
        scene.render.filepath = base + ".exr"
        bpy.ops.render.render(write_still=True)
        # PNG of the same frame for the segmentation models
        scene.render.image_settings.media_type = "IMAGE"
        scene.render.image_settings.file_format = "PNG"
        scene.render.image_settings.color_mode = "RGBA"
        scene.render.image_settings.color_depth = "8"
        scene.render.filepath = base + ".png"
        bpy.ops.render.render(write_still=True)
        cj = camera_json(scene, cam, w, h)
        cj.update({"view": v})
        with open(base + ".json", "w") as fh:
            json.dump(cj, fh)
    print("VIEWS_DONE %d" % len(views))


# --------------------------------------------------------------------------- painting

def srgb_to_linear(c):
    c = np.asarray(c, dtype=np.float64)
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def subdivide_regions(obj, regions):
    """Subdivide faces inside spheres until edges are shorter than the requested length.
    regions: list of {centre:[x,y,z], radius: r, max_edge: m}, processed coarsest first; each
    region is cut once with as many cuts as its current mean edge length needs."""
    me = obj.data
    for r in sorted(regions, key=lambda r: -r["max_edge"]):
        npoly = len(me.polygons)
        cen = np.empty(npoly * 3)
        me.polygons.foreach_get("center", cen)
        area = np.empty(npoly)
        me.polygons.foreach_get("area", area)
        sel = np.where(np.linalg.norm(cen.reshape(-1, 3) - np.array(r["centre"]), axis=1) < r["radius"])[0]
        if len(sel) == 0:
            continue
        edge = float(np.sqrt(4.0 * np.median(area[sel]) / math.sqrt(3.0)))
        cuts = int(min(8, math.ceil(edge / r["max_edge"]) - 1))
        if cuts <= 0:
            print("SUBDIV region r=%.3f: edges %.4f already fine" % (r["radius"], edge))
            continue
        bm = bmesh.new()
        bm.from_mesh(me)
        bm.faces.ensure_lookup_table()
        edges = list({e for i in sel for e in bm.faces[int(i)].edges})
        bmesh.ops.subdivide_edges(bm, edges=edges, cuts=cuts, use_grid_fill=True,
                                  quad_corner_type="INNER_VERT")
        bmesh.ops.triangulate(bm, faces=[f for f in bm.faces if len(f.verts) > 3])
        bm.to_mesh(me)
        bm.free()
        me.update()
        print("SUBDIV region r=%.3f: %d faces, edge %.4f -> %d cuts, now %d vertices" % (
            r["radius"], len(sel), edge, cuts, len(me.vertices)))


def cmd_paint(workdir, out_fbx):
    bpy.ops.wm.open_mainfile(filepath=os.path.join(workdir, "work.blend"))
    obj = [o for o in bpy.data.objects if o.type == "MESH"][0]
    bpy.context.view_layer.objects.active = obj
    me = obj.data
    paint = np.load(os.path.join(workdir, "paint.npz"))
    rgba = paint["rgba"].astype(np.float64)  # sRGB colour + linear alpha per vertex of mesh.npz
    if len(rgba) != len(me.vertices):
        raise RuntimeError("paint.npz has %d vertices, mesh has %d" % (len(rgba), len(me.vertices)))
    for name in [a.name for a in me.color_attributes]:
        me.color_attributes.remove(me.color_attributes[name])
    attr = me.color_attributes.new("Col", "FLOAT_COLOR", "POINT")
    lin = rgba.copy()
    lin[:, :3] = srgb_to_linear(rgba[:, :3])
    attr.data.foreach_set("color", lin.astype(np.float32).ravel())
    me.color_attributes.active_color = attr
    me.color_attributes.render_color_index = 0
    key = os.path.splitext(os.path.basename(out_fbx))[0]
    obj.name = me.name = "Statue_" + key
    os.makedirs(os.path.dirname(out_fbx), exist_ok=True)
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.ops.export_scene.fbx(filepath=out_fbx, use_selection=True, apply_scale_options="FBX_SCALE_UNITS",
                             mesh_smooth_type="FACE", add_leaf_bones=False, bake_anim=False,
                             colors_type="SRGB", prioritize_active_color=True)
    verify(out_fbx, lin.astype(np.float32))


def verify(out_fbx, ref_lin):
    """Re-import the FBX and compare its colours with the linear reference (per vertex)."""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=out_fbx, colors_type="SRGB")
    obj = [o for o in bpy.data.objects if o.type == "MESH"][0]
    me = obj.data
    if not me.color_attributes:
        print("PAINT_VERIFY FAIL no colour attribute after re-import")
        raise SystemExit(2)
    ca = me.color_attributes[0]
    n = len(ca.data)
    c = np.empty(n * 4, dtype=np.float32)
    ca.data.foreach_get("color", c)
    c = c.reshape(-1, 4)
    used = np.ones(len(me.vertices), bool)
    if ca.domain == "CORNER":
        cv = np.empty(len(me.loops), dtype=np.int64)
        me.loops.foreach_get("vertex_index", cv)
        pv = np.zeros((len(me.vertices), 4))
        pv[cv] = c
        c = pv
        # loose vertices (no faces) carry no corner colour; they are not rendered either
        used[:] = False
        used[cv] = True
    if ca.data_type == "BYTE_COLOR":
        pass  # Blender already returns linear floats for byte colours
    nv = min(len(c), len(ref_lin))
    err = np.abs(c[:nv] - ref_lin[:nv])[used[:nv]].max(axis=0)
    ok = len(c) == len(ref_lin) and float(err.max()) < 0.02
    print("PAINT_VERIFY %s verts=%d/%d max_abs_err_rgba=%s painted(A>0.01)=%d attr=%s/%s" % (
        "OK" if ok else "FAIL", len(c), len(ref_lin), np.round(err, 4).tolist(),
        int((c[:, 3] > 0.01).sum()), ca.data_type, ca.domain))
    if not ok:
        raise SystemExit(2)


# --------------------------------------------------------------------------- preview

def cmd_preview(fbx, workdir, out_png, preview_json):
    """Cycles-free quick look: EEVEE with a material mixing vertex colour over marble white."""
    with open(preview_json) as fh:
        pv = json.load(fh)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=fbx, colors_type="SRGB")
    obj = [o for o in bpy.data.objects if o.type == "MESH"][0]
    for o in list(bpy.data.objects):
        if o.type != "MESH":
            bpy.data.objects.remove(o)
    obj.matrix_world = Matrix.Identity(4)
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    bpy.ops.object.shade_smooth()
    scene = bpy.context.scene
    mat = bpy.data.materials.new("PaintedMarble")
    mat.use_nodes = True
    nt = mat.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    attr = nt.nodes.new("ShaderNodeVertexColor")
    attr.layer_name = obj.data.color_attributes[0].name if obj.data.color_attributes else ""
    mix = nt.nodes.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    mix.inputs["A"].default_value = (0.80, 0.78, 0.74, 1.0)  # marble
    nt.links.new(attr.outputs["Color"], mix.inputs["B"])
    nt.links.new(attr.outputs["Alpha"], mix.inputs["Factor"])
    nt.links.new(mix.outputs["Result"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.45
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    obj.data.materials.clear()
    obj.data.materials.append(mat)

    scene.render.engine = "BLENDER_EEVEE"
    world = bpy.data.worlds.new("W")
    scene.world = world
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs[0].default_value = (0.35, 0.35, 0.37, 1)
    world.node_tree.nodes["Background"].inputs[1].default_value = 0.6
    # key light follows each camera (from above-left of the lens), plus a weak fixed top light
    sun = bpy.data.objects.new("Sun", bpy.data.lights.new("Sun", "SUN"))
    sun.data.energy = 3.0
    sun.data.angle = math.radians(10)
    scene.collection.objects.link(sun)
    top = bpy.data.objects.new("Top", bpy.data.lights.new("Top", "SUN"))
    top.data.energy = 1.0
    top.rotation_euler = (math.radians(20), 0, math.radians(30))
    scene.collection.objects.link(top)
    scene.view_settings.view_transform = "Standard"
    scene.view_settings.look = "None"
    scene.view_settings.exposure = -0.3
    scene.render.film_transparent = False
    cam = make_camera(scene)
    tiles = []
    tmp = os.path.join(workdir, "_preview_tile.png")
    scene.render.image_settings.media_type = "IMAGE"
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    for v in pv["views"]:
        w, h = v["res"]
        scene.render.resolution_x, scene.render.resolution_y = w, h
        scene.render.resolution_percentage = 100
        place_camera(cam, v)
        bpy.context.view_layer.update()
        sun.matrix_world = (cam.matrix_world.to_3x3().to_4x4() @ Matrix.Rotation(math.radians(28), 4, "X")
                            @ Matrix.Rotation(math.radians(-22), 4, "Y"))
        scene.render.filepath = tmp
        bpy.ops.render.render(write_still=True)
        img = bpy.data.images.load(tmp)
        px = np.empty(w * h * 4, dtype=np.float32)
        img.pixels.foreach_get(px)
        tiles.append(px.reshape(h, w, 4))
        bpy.data.images.remove(img)
    os.remove(tmp)
    H = max(t.shape[0] for t in tiles)
    tiles = [np.concatenate([np.ones((H - t.shape[0], t.shape[1], 4), np.float32), t], 0) for t in tiles]
    sheet = np.concatenate(tiles, axis=1)
    hh, ww = sheet.shape[:2]
    res = bpy.data.images.new("sheet", width=ww, height=hh, alpha=False)
    res.pixels.foreach_set(sheet.ravel())
    res.filepath_raw = out_png
    res.file_format = "PNG"
    os.makedirs(os.path.dirname(out_png), exist_ok=True)
    res.save()
    print("PREVIEW_DONE " + out_png)


def main():
    argv = sys.argv[sys.argv.index("--") + 1:]
    cmd = argv[0]
    if cmd == "mesh":
        cmd_mesh(argv[1], argv[2])
    elif cmd == "views":
        cmd_views(argv[1], argv[2], argv[3])
    elif cmd == "paint":
        cmd_paint(argv[1], argv[2])
    elif cmd == "preview":
        cmd_preview(argv[1], argv[2], argv[3], argv[4])
    else:
        raise SystemExit("unknown command " + cmd)


if __name__ == "__main__":
    main()
