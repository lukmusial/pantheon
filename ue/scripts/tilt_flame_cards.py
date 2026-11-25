"""Tilt the flame and smoke cards already in the level, in place (no level rebuild), so that their
bounds are a box and not a flat slab: see CARD_TILT in build_scene.py. Run once on a level built
before 2026-11-23; build_scene.py now places the cards tilted.

    UnrealEditor ue/Pantheon/Pantheon.uproject -run=pythonscript -script=ue/scripts/tilt_flame_cards.py \\
        -unattended -nosplash
"""

import unreal

MAPS = ("/Game/Maps/Pantheon",)
TILT = unreal.Rotator(45.0, 45.0, 0.0)   # roll, pitch, yaw: as CARD_TILT in build_scene.py


def main():
    for path in MAPS:
        unreal.EditorLoadingAndSavingUtils.load_map(path)
        actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
        n = 0
        for a in actors.get_all_level_actors():
            label = a.get_actor_label()
            if label.startswith("Flame_") or label.startswith("Smoke_"):
                a.modify()
                a.set_actor_rotation(TILT, True)
                r = a.get_actor_rotation()
                if abs(r.roll - TILT.roll) > 0.1 or abs(r.pitch - TILT.pitch) > 0.1:
                    raise RuntimeError("could not tilt %s: rotation is %s" % (label, r))
                n += 1
        world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
        if not unreal.EditorLoadingAndSavingUtils.save_map(world, path):
            raise RuntimeError("could not save " + path)
        unreal.log_warning("[tilt] %s: %d cards tilted and saved" % (path, n))


main()
