"""Move the water streaks under the dome's springing (decals Leak_attic_00..11) to
build_scene.ATTIC_LEAK_AZ, in place (no level rebuild): halfway between the attic's openings, so none
projects into a niche or window reveal.

    UnrealEditor ue/Pantheon/Pantheon.uproject -run=pythonscript -script=ue/scripts/move_attic_leaks.py \\
        -unattended -nosplash -AllowCommandletRendering
"""

import math

import unreal

MAP = "/Game/Maps/Pantheon"
RADIUS = 21.72
# as build_scene.ATTIC_LEAK_AZ (that module builds the whole level when imported, so it is not imported)
ATTIC_LEAK_AZ = (11.25, 33.75, 56.25, 123.75, 146.25, 168.75, 191.25, 213.75, 236.25, 303.75, 326.25, 348.75)


def main():
    unreal.EditorLoadingAndSavingUtils.load_map(MAP)
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    moved = 0
    for a in actors.get_all_level_actors():
        label = a.get_actor_label()
        if not label.startswith("Leak_attic_"):
            continue
        az = ATTIC_LEAK_AZ[int(label.split("_")[-1])]
        x, y = RADIUS * math.cos(math.radians(az)), RADIUS * math.sin(math.radians(az))
        # as build_scene.add_decal: Blender (x, y, z) m to Unreal cm, projected radially outwards
        a.set_actor_location_and_rotation(unreal.Vector(x * 100.0, -y * 100.0, 1860.0),
                                          unreal.Rotator(90.0, 0.0, -az), False, False)
        moved += 1
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    if not unreal.EditorLoadingAndSavingUtils.save_map(world, MAP):
        raise RuntimeError("could not save " + MAP)
    unreal.log_warning("[leaks] %d attic streaks moved, %s saved" % (moved, MAP))


main()
