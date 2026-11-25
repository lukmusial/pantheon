"""The easter egg, in place (no level rebuild): four small tile mosaics of pixel creatures, in the
manner of the street mosaics set on city walls (user, 2026-11-24). blender/build_pantheon.py makes
them (build_invaders) and leaves out the coffer rosette one of them replaces:

    blender -b --python blender/build_pantheon.py -- --export assets/architecture/fbx \\
        --only Gilded_Rosettes,Invader_Dome,Invader_Altar,Invader_Exedra,Invader_Jupiter

This script builds /Game/Materials/M_InvaderTile, imports those five meshes and puts the four
mosaics into /Game/Maps/Pantheon (again, if they are there already). build_scene.py does the same on a
full build. INVADERS=off takes the mosaics out of the map (the rosette comes back with a Blender
export without INVADER_COFFER). INVADER_GLOW=<x> sets the tiles' own light (default 0).

    UnrealEditor ue/Pantheon/Pantheon.uproject -run=pythonscript -script=ue/scripts/place_invaders.py \\
        -unattended -nosplash -AllowCommandletRendering
"""

import os
import sys

import unreal

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pantheon_materials as pm  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
FBX_DIR = os.path.join(ROOT, "assets", "architecture", "fbx")
PKG = "/Game/Architecture"
MAP = "/Game/Maps/Pantheon"
TILE = "/Game/Materials/M_InvaderTile"
GILDED = "/Game/Materials/MI_Gilded_Satin"
MOSAICS = ("Invader_Dome", "Invader_Altar", "Invader_Exedra", "Invader_Jupiter")

assets = unreal.EditorAssetLibrary


def log(msg):
    unreal.log_warning("[invaders] " + msg)


def import_meshes(names):
    """As build_scene.import_fbx: through Interchange, which keeps the vertex colours."""
    tasks = []
    for n in names:
        t = unreal.AssetImportTask()
        t.set_editor_property("filename", os.path.join(FBX_DIR, n + ".fbx"))
        t.set_editor_property("destination_path", PKG)
        t.set_editor_property("automated", True)
        t.set_editor_property("replace_existing", True)
        t.set_editor_property("save", True)
        tasks.append(t)
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks(tasks)
    out = {}
    for n in names:
        mesh = unreal.load_asset(PKG + "/" + n)
        if not isinstance(mesh, unreal.StaticMesh):
            raise RuntimeError("import of %s failed" % n)
        out[n] = mesh
    return out


def dress(mesh, material, collide):
    settings = mesh.get_editor_property("nanite_settings")
    settings.set_editor_property("enabled", False)
    mesh.set_editor_property("nanite_settings", settings)
    for i in range(mesh.get_num_sections(0)):
        mesh.set_material(i, material)
    if collide:
        body = mesh.get_editor_property("body_setup")
        body.set_editor_property("collision_trace_flag", unreal.CollisionTraceFlag.CTF_USE_COMPLEX_AS_SIMPLE)
        body.set_editor_property("double_sided_geometry", True)   # as build_scene.set_collision
        mesh.set_editor_property("body_setup", body)
    assets.save_loaded_asset(mesh)


def main():
    on = os.environ.get("INVADERS", "on") != "off"
    meshes = {}
    if on:
        tile = pm.build_invader_tile(TILE, glow=float(os.environ.get("INVADER_GLOW", "0")))
        meshes = import_meshes(("Gilded_Rosettes",) + MOSAICS)
        dress(meshes["Gilded_Rosettes"], unreal.load_asset(GILDED), True)
        for n in MOSAICS:
            dress(meshes[n], tile, False)
    unreal.EditorLoadingAndSavingUtils.load_map(MAP)
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    removed = 0
    for a in actors.get_all_level_actors():
        if a.get_actor_label() in MOSAICS:
            actors.destroy_actor(a)
            removed += 1
    for n in MOSAICS if on else ():
        # the meshes are in world position, like the rest of the architecture
        a = actors.spawn_actor_from_class(unreal.StaticMeshActor, unreal.Vector(0.0, 0.0, 0.0), unreal.Rotator(0.0, 0.0, 0.0))
        if a is None:
            raise RuntimeError("could not spawn " + n)
        comp = a.get_component_by_class(unreal.StaticMeshComponent)
        comp.set_editor_property("mobility", unreal.ComponentMobility.STATIC)
        comp.set_static_mesh(meshes[n])
        # interior surfaces are lit on channel 1 only (build_scene.INTERIOR_CHANNELS)
        comp.set_editor_property("lighting_channels", unreal.LightingChannels(channel0=False, channel1=True, channel2=False))
        comp.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
        a.set_actor_label(n)
        b = meshes[n].get_bounding_box()
        log("%s at %s .. %s" % (n, b.min, b.max))
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    if not unreal.EditorLoadingAndSavingUtils.save_map(world, MAP):
        raise RuntimeError("could not save " + MAP)
    log("%s: %d mosaics removed, %d placed, map saved" % (MAP, removed, len(MOSAICS) if on else 0))


main()
