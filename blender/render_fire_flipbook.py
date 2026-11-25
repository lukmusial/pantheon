"""Render a flame flipbook from a CC0 JangaFX EmberGen VDB sequence (Cycles).

Usage:
    blender -b --factory-startup --python blender/render_fire_flipbook.py -- <sim> <first> <count> <step> <size> [test]

    sim    campfire | fire01   (assets/fire/vdb/<sim>/**/*.vdb)
    first  first VDB frame index, count frames to render, step between VDB frames
    size   pixels per flipbook frame (square)
    test   render only the first frame, to renders/previews/fire/<sim>_test.png
    view=<deg>  turn the camera about the simulation's vertical axis (a second view of the same fire
                looks like a different fire); tag=<name> names the output folder <sim>[_smoke]_<name>

Output: assets/fire/flipbooks/<sim>/f_0000.png ... (RGB = flame emission over black, for additive
blending). No alpha: an emission-only volume has zero alpha, and PNG's straight alpha would discard
its colour.

The 'flames' grid drives blackbody emission (dark red edges to yellow-white core); the 'density'
grid, where present, gives thin absorbing smoke. Orthographic camera, simulation up axis vertical.
"""

import glob
import math
import os
import sys

import bpy
from mathutils import Vector

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
# per simulation: up axis of the VDB ("Z" or "-Z"), largest value of the 'flames' grid (measured),
# flame strength, smoke density
SIMS = {
    # crop: (x offset, z offset, size) as fractions of the full-domain framing, around the flames
    "campfire": {"up": "Z", "fmax": 0.8, "strength": 1.4, "smoke": 40.0, "crop": (0.018, -0.197, 0.56)},
    "fire01": {"up": "Z", "fmax": 0.19, "strength": 0.6, "smoke": 0.0},
}


def frame_number(path):
    tail = os.path.basename(path).split(".")[0].split("_")[-1]
    return int("".join(c for c in tail if c.isdigit()))


def bounds_of(obj, lo, hi):
    for c in obj.bound_box:
        v = obj.matrix_world @ Vector(c)
        lo = Vector(map(min, lo, v))
        hi = Vector(map(max, hi, v))
    return lo, hi


def main():
    argv = sys.argv[sys.argv.index("--") + 1:]
    sim, first, count, step, size = argv[0], int(argv[1]), int(argv[2]), int(argv[3]), int(argv[4])
    test = "test" in argv[5:]
    # smoke: render the 'density' grid alone as a white-on-black coverage mask over the whole
    # simulation domain (the smoke rises well above the flames); used as opacity in Unreal
    smoke = "smoke" in argv[5:]
    cfg = SIMS[sim]
    opts = dict(a.split("=", 1) for a in argv[5:] if "=" in a)
    view = math.radians(float(opts.get("view", "0")))
    tag = ("_" + opts["tag"]) if "tag" in opts else ""
    files = sorted(glob.glob(os.path.join(ROOT, "assets", "fire", "vdb", sim, "**", "*.vdb"), recursive=True),
                   key=frame_number)
    scene = bpy.context.scene
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o)

    scene.render.engine = "CYCLES"
    prefs = bpy.context.preferences.addons["cycles"].preferences
    try:
        prefs.compute_device_type = "METAL"
        prefs.get_devices()
        for d in prefs.devices:
            d.use = True
        scene.cycles.device = "GPU"
    except Exception as e:  # noqa: BLE001
        print("GPU not available, using CPU:", e)
    scene.cycles.samples = 48
    scene.cycles.volume_step_rate = 0.5
    scene.cycles.volume_max_steps = 512
    scene.cycles.use_denoising = True
    scene.render.film_transparent = False
    scene.render.resolution_x = scene.render.resolution_y = size
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.render.image_settings.color_depth = "16"
    scene.view_settings.view_transform = "Standard"
    scene.world = bpy.data.worlds.new("W")
    scene.world.use_nodes = True
    scene.world.node_tree.nodes["Background"].inputs[1].default_value = 0.0

    # material: flames -> blackbody emission; density -> thin dark smoke
    mat = bpy.data.materials.new("Fire")
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    flames = nt.nodes.new("ShaderNodeAttribute")
    flames.attribute_name = "flames"
    # temperature 900 K at the faint edge to 2400 K in the core
    temp = nt.nodes.new("ShaderNodeMapRange")
    temp.inputs["From Min"].default_value = 0.0
    temp.inputs["From Max"].default_value = cfg["fmax"]
    temp.inputs["To Min"].default_value = 900.0
    temp.inputs["To Max"].default_value = 2700.0
    nt.links.new(flames.outputs["Fac"], temp.inputs["Value"])
    bb = nt.nodes.new("ShaderNodeBlackbody")
    nt.links.new(temp.outputs["Result"], bb.inputs["Temperature"])
    # emission strength rises steeply with the flame value, so thin wisps stay dim
    power = nt.nodes.new("ShaderNodeMath")
    power.operation = "POWER"
    power.inputs[1].default_value = 1.6
    norm = nt.nodes.new("ShaderNodeMath")
    norm.operation = "DIVIDE"
    norm.inputs[1].default_value = cfg["fmax"]
    nt.links.new(flames.outputs["Fac"], norm.inputs[0])
    nt.links.new(norm.outputs[0], power.inputs[0])
    gain = nt.nodes.new("ShaderNodeMath")
    gain.operation = "MULTIPLY"
    gain.inputs[1].default_value = cfg["strength"]
    nt.links.new(power.outputs[0], gain.inputs[0])
    em = nt.nodes.new("ShaderNodeEmission")
    nt.links.new(bb.outputs["Color"], em.inputs["Color"])
    nt.links.new(gain.outputs[0], em.inputs["Strength"])
    shader = em.outputs[0]
    if cfg["smoke"] > 0.0:
        dens = nt.nodes.new("ShaderNodeAttribute")
        dens.attribute_name = "density"
        dmul = nt.nodes.new("ShaderNodeMath")
        dmul.operation = "MULTIPLY"
        dmul.inputs[1].default_value = cfg["smoke"]
        nt.links.new(dens.outputs["Fac"], dmul.inputs[0])
        absorb = nt.nodes.new("ShaderNodeVolumeAbsorption")
        absorb.inputs["Color"].default_value = (0.02, 0.02, 0.02, 1.0)
        nt.links.new(dmul.outputs[0], absorb.inputs["Density"])
        add = nt.nodes.new("ShaderNodeAddShader")
        nt.links.new(em.outputs[0], add.inputs[0])
        nt.links.new(absorb.outputs[0], add.inputs[1])
        shader = add.outputs[0]
    if smoke:
        dens = nt.nodes.new("ShaderNodeAttribute")
        dens.attribute_name = "density"
        dgain = nt.nodes.new("ShaderNodeMath")
        dgain.operation = "MULTIPLY"
        dgain.inputs[1].default_value = cfg.get("smoke_gain", 12.0)
        nt.links.new(dens.outputs["Fac"], dgain.inputs[0])
        sem = nt.nodes.new("ShaderNodeEmission")
        sem.inputs["Color"].default_value = (1.0, 1.0, 1.0, 1.0)
        nt.links.new(dgain.outputs[0], sem.inputs["Strength"])
        shader = sem.outputs[0]
    nt.links.new(shader, out.inputs["Volume"])

    # fixed framing from the bounds of all rendered frames
    lo, hi = Vector((1e9, 1e9, 1e9)), Vector((-1e9, -1e9, -1e9))
    picks = [files[min(first + i * step, len(files) - 1)] for i in range(1 if test else count)]
    volumes = []
    for path in picks:
        bpy.ops.object.volume_import(filepath=path)
        o = bpy.context.object
        o.data.materials.append(mat)
        lo, hi = bounds_of(o, lo, hi)
        o.hide_render = True
        volumes.append(o)
    if test:  # frame the whole simulation domain, taken from the last frame
        bpy.ops.object.volume_import(filepath=files[-1])
        o = bpy.context.object
        lo, hi = bounds_of(o, lo, hi)
        bpy.data.objects.remove(o)
    centre = 0.5 * (lo + hi)
    extent = max(hi.x - lo.x, hi.z - lo.z) * 1.04
    cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
    scene.collection.objects.link(cam)
    cam.data.type = "ORTHO"
    dx, dz, frac = cfg.get("crop", (0.0, 0.0, 1.0))
    if smoke:
        dx, dz, frac = 0.0, 0.0, 1.0
    if cfg.get("crop"):  # crop fractions refer to the whole simulation domain
        o = bpy.data.objects.new("Dom", None)
        bpy.ops.object.volume_import(filepath=files[-1])
        dom = bpy.context.object
        dlo, dhi = bounds_of(dom, Vector((1e9, 1e9, 1e9)), Vector((-1e9, -1e9, -1e9)))
        bpy.data.objects.remove(dom)
        bpy.data.objects.remove(o)
        centre = 0.5 * (dlo + dhi)
        extent = max(dhi.x - dlo.x, dhi.z - dlo.z) * 1.04
    cam.data.ortho_scale = extent * frac
    cam.data.clip_end = 5000.0
    cam.location = (centre.x + dx * extent, lo.y - 500.0, centre.z + dz * extent)
    # look along +Y; roll 180 degrees when the simulation's up axis is -Z
    cam.rotation_euler = (1.5707963, 3.14159265 if cfg["up"] == "-Z" else 0.0, view)
    if view:  # orbit the camera about the vertical axis through the domain centre
        rel = cam.location - centre
        c, s_ = math.cos(view), math.sin(view)
        cam.location = (centre.x + c * rel.x - s_ * rel.y, centre.y + s_ * rel.x + c * rel.y, cam.location.z)
    scene.camera = cam
    print("FLIPBOOK bounds", [round(c, 1) for c in lo], [round(c, 1) for c in hi], "extent", round(extent, 1))

    out_dir = os.path.join(ROOT, "assets", "fire", "flipbooks", sim + ("_smoke" if smoke else "") + tag)
    os.makedirs(out_dir, exist_ok=True)
    for i, o in enumerate(volumes):
        o.hide_render = False
        scene.render.filepath = (os.path.join(ROOT, "renders", "previews", "fire", sim + ("_smoke" if smoke else "") + "_test.png") if test
                                 else os.path.join(out_dir, "f_%04d.png" % i))
        bpy.ops.render.render(write_still=True)
        o.hide_render = True
    print("FLIPBOOK_DONE", sim, len(volumes))


if __name__ == "__main__":
    main()
