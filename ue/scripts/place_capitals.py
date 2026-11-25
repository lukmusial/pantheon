"""Put scanned capitals into /Game/Maps/Pantheon in place (no level rebuild), as build_scene.py's level
step does: one actor per capital slot of the manifest whose column name starts with one of the
prefixes given, labelled Capital_<column>. Actors with those labels already in the map are replaced.

    PLACE_CAPITALS=Forecourt_ UnrealEditor ue/Pantheon/Pantheon.uproject -run=pythonscript \\
        -script=ue/scripts/place_capitals.py -unattended -nosplash -AllowCommandletRendering
"""

import json
import os

import unreal

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
MANIFEST = os.path.join(ROOT, "assets", "architecture", "fbx", "manifest.json")
CAPITAL_INFO = os.path.join(ROOT, "assets", "architecture", "capital", "capital.json")
MAP = "/Game/Maps/Pantheon"
CAPITAL = "/Game/Architecture/Capital/capital"
# as build_scene.EXTERIOR_PREFIXES: these capitals stay on the sun's channel; the rest are interior
EXTERIOR = ("Capital_Portico_", "Capital_Forecourt_")


def main():
    prefixes = tuple(p for p in os.environ.get("PLACE_CAPITALS", "").split(",") if p)
    if not prefixes:
        raise RuntimeError("PLACE_CAPITALS=<column name prefixes> is empty")
    slots = [s for s in json.load(open(MANIFEST)).get("capital_slots", []) if s["column"].startswith(prefixes)]
    ring = json.load(open(CAPITAL_INFO)).get("ring_diameter") if os.path.exists(CAPITAL_INFO) else None
    mesh = unreal.load_asset(CAPITAL)
    if mesh is None:
        raise RuntimeError("no capital mesh at " + CAPITAL)
    unreal.EditorLoadingAndSavingUtils.load_map(MAP)
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    labels = {"Capital_" + s["column"] for s in slots}
    for a in actors.get_all_level_actors():
        if a.get_actor_label() in labels:
            actors.destroy_actor(a)
    for s in slots:
        x, y, z = s["position"]
        # Blender metres to UE centimetres (Blender +Y is UE -Y), yaw as build_scene's level step
        a = actors.spawn_actor_from_class(unreal.StaticMeshActor, unreal.Vector(x * 100.0, -y * 100.0, z * 100.0),
                                          unreal.Rotator(0.0, 0.0, -s["yaw"]))
        comp = a.get_component_by_class(unreal.StaticMeshComponent)
        comp.set_editor_property("mobility", unreal.ComponentMobility.STATIC)
        comp.set_static_mesh(mesh)
        label = "Capital_" + s["column"]
        if not label.startswith(EXTERIOR):
            comp.set_editor_property("lighting_channels", unreal.LightingChannels(channel0=False, channel1=True, channel2=False))
        a.set_actor_label(label)
        k = s["height"]
        kxy = s["diameter"] / ring if ring else k
        a.set_actor_scale3d(unreal.Vector(kxy, kxy, k))
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    if not unreal.EditorLoadingAndSavingUtils.save_map(world, MAP):
        raise RuntimeError("could not save " + MAP)
    unreal.log_warning("[capitals] %d placed in %s" % (len(slots), MAP))


main()
