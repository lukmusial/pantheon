"""Put architecture meshes into /Game/Maps/Pantheon in place (no level rebuild), as build_scene.py's
level step would: one actor per mesh, at the origin (the meshes are in world position), labelled with
the mesh's name, on the exterior or interior lighting channels. An actor with that label already in
the map is replaced. For a mesh new to the manifest, after its import with
    PANTHEON_STEPS=import PANTHEON_ONLY=<names> UnrealEditor ... -script=ue/scripts/build_scene.py

    PLACE=Name1,Name2 UnrealEditor ue/Pantheon/Pantheon.uproject -run=pythonscript \\
        -script=ue/scripts/place_meshes.py -unattended -nosplash -AllowCommandletRendering
"""

import os

import unreal

MAP = "/Game/Maps/Pantheon"
PKG = "/Game/Architecture"
# as build_scene.EXTERIOR_PREFIXES: the sun (channel 0) lights only these
EXTERIOR_PREFIXES = ("Ground", "Forecourt_", "Portico_", "Orn_Portico_", "Bronze_Roof", "Bronze_Inscription", "Drum_Outer",
                     "Dome_Outer", "Capital_Portico_", "Capital_Forecourt_", "Statue_augustus_portico",
                     "Statue_agrippa_portico")


def main():
    names = [n for n in os.environ.get("PLACE", "").split(",") if n]
    if not names:
        raise RuntimeError("PLACE=<mesh names> is empty")
    unreal.EditorLoadingAndSavingUtils.load_map(MAP)
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    for a in actors.get_all_level_actors():
        if a.get_actor_label() in names:
            actors.destroy_actor(a)
    for n in names:
        mesh = unreal.load_asset(PKG + "/" + n)
        if not isinstance(mesh, unreal.StaticMesh):
            raise RuntimeError("no mesh " + PKG + "/" + n)
        a = actors.spawn_actor_from_class(unreal.StaticMeshActor, unreal.Vector(0.0, 0.0, 0.0), unreal.Rotator(0.0, 0.0, 0.0))
        comp = a.get_component_by_class(unreal.StaticMeshComponent)
        comp.set_editor_property("mobility", unreal.ComponentMobility.STATIC)
        comp.set_static_mesh(mesh)
        if not n.startswith(EXTERIOR_PREFIXES):
            comp.set_editor_property("lighting_channels", unreal.LightingChannels(channel0=False, channel1=True, channel2=False))
        if n.startswith("Forecourt_Blockers"):
            # as build_scene.hide_keep_collision: invisible walls in the city's doors and windows
            comp.set_editor_property("visible", False)
            comp.set_editor_property("hidden_in_game", True)
            comp.set_editor_property("cast_shadow", False)
            comp.set_editor_property("affect_distance_field_lighting", False)
        a.set_actor_label(n)
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    if not unreal.EditorLoadingAndSavingUtils.save_map(world, MAP):
        raise RuntimeError("could not save " + MAP)
    unreal.log_warning("[place] %s placed in %s" % (", ".join(names), MAP))


main()
