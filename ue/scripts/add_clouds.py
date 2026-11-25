"""Put the clouds into /Game/Maps/Pantheon in place (no level rebuild), as build_scene.add_clouds does
on a full build: a Volumetric Cloud actor with the engine's own cloud material, and cloud shadows from
the sun. CLOUDS=off removes them.

    UnrealEditor ue/Pantheon/Pantheon.uproject -run=pythonscript -script=ue/scripts/add_clouds.py \\
        -unattended -nosplash -AllowCommandletRendering
"""

import os

import unreal

MAP = "/Game/Maps/Pantheon"
# keep in step with build_scene.CLOUD_MATERIAL and add_clouds
CLOUD_MATERIAL = "/Engine/EngineSky/VolumetricClouds/m_SimpleVolumetricCloud_Inst"


def main():
    unreal.EditorLoadingAndSavingUtils.load_map(MAP)
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    sun = None
    for a in actors.get_all_level_actors():
        if a.get_actor_label() == "Clouds":
            actors.destroy_actor(a)
        elif a.get_actor_label() == "Sun":
            sun = a
    on = os.environ.get("CLOUDS", "on") != "off"
    if on:
        cloud = actors.spawn_actor_from_class(unreal.VolumetricCloud, unreal.Vector(0, 0, 0))
        cloud.set_actor_label("Clouds")
        comp = cloud.get_component_by_class(unreal.VolumetricCloudComponent)
        comp.set_editor_property("material", unreal.load_asset(CLOUD_MATERIAL))
        comp.set_editor_property("layer_bottom_altitude", 2.0)
        comp.set_editor_property("layer_height", 8.0)
    if sun is not None:
        lc = sun.get_component_by_class(unreal.DirectionalLightComponent)
        lc.set_editor_property("cast_cloud_shadows", on)
        lc.set_editor_property("cloud_shadow_strength", 0.6)
        lc.set_editor_property("cast_shadows_on_clouds", on)
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    if not unreal.EditorLoadingAndSavingUtils.save_map(world, MAP):
        raise RuntimeError("could not save " + MAP)
    unreal.log_warning("[clouds] %s, sun %s" % ("on" if on else "off", "found" if sun else "missing"))


main()
