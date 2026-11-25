"""F3 "ghosts in the fog": the assets the walk-through app needs, in /Game/F3Runtime (cooked, see
DefaultGame.ini). AF3GhostDriver loads them at run time:

- M_GhostFog / MI_GhostFog: the thin floor fog (pantheon_materials.build_ghost_fog);
- M_GhostMist / MI_GhostMist: the ghosts and their trails, volumes of mist marched in the pixel shader
  (pantheon_materials.build_ghost_mist);
- /Game/Materials/M_Statue: the statues' master material, rebuilt with the eyes that follow the visitor
  in ghost mode (F3_STATUE=0 skips it);
- MM_Idle: a copy of the mannequin's idle, the standing base pose (only this animation is cooked, not
  the whole Unarmed folder).

Run headless:
    UnrealEditor ue/Pantheon/Pantheon.uproject -run=pythonscript -script=ue/scripts/f3_runtime.py \\
        -unattended -nosplash -AllowCommandletRendering
"""

import os
import sys

import unreal

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pantheon_materials as pm  # noqa: E402

RUNTIME = "/Game/F3Runtime"
IDLE_SRC = "/Game/Characters/Mannequins/Anims/Unarmed/MM_Idle"

# floor fog: parameters of MI_GhostFog (see pantheon_materials.build_ghost_fog). A third of the first
# density: at 0.06 the 18 m across the rotunda hid everything below waist height. The ghosts are no
# longer drawn in the fog grid (too coarse for a figure), so GhostDensity is unused.
FOG_PARAMS = {"Density": 0.02, "Haze": 0.0, "FogTop": 140.0, "WaveAmp": 70.0, "WispReach": 60.0,
              "FogFade": 60.0, "PatchLow": 0.3, "PatchHigh": 1.5, "Soft": 14.0, "GhostDensity": 0.0,
              "CarveAmount": 0.0}
# the ghosts: parameters of MI_GhostMist (see pantheon_materials.build_ghost_mist). Density is per cm
# of mist along the view ray. HaloReach + BodyNoise (cm) must stay within the pad the driver gives each
# body capsule (BodyPad in F3GhostDriver.cpp).
MIST_PARAMS = {"Density": 0.016, "Soft": 5.0, "Blend": 4.0, "BodyNoise": 3.5, "NoiseScale": 0.085,
               "TrailDensity": 0.3, "FeetLow": 0.45, "ShellT": 5.0, "Hollow": 0.3, "Pleat": 0.4,
               "PleatCount": 1.5, "PleatRise": 0.11, "Halo": 0.12, "HaloReach": 20.0}
MIST_COLOURS = {"GhostColor": (0.30, 0.33, 0.38), "GhostGlow": (0.006, 0.007, 0.009)}
# replaced by the mist volumes (2026-11-23): the mannequin drawn with a see-through material
OBSOLETE = ("MI_GhostFigure", "M_GhostFigure")

assets = unreal.EditorAssetLibrary
tools = unreal.AssetToolsHelpers.get_asset_tools()
mel = unreal.MaterialEditingLibrary


def log(msg):
    unreal.log_warning("[f3runtime] " + msg)


def instance(name, parent, scalars, colours=None):
    path = RUNTIME + "/" + name
    if assets.does_asset_exist(path):
        assets.delete_asset(path)
    mi = tools.create_asset(name, RUNTIME, unreal.MaterialInstanceConstant, unreal.MaterialInstanceConstantFactoryNew())
    mel.set_material_instance_parent(mi, parent)
    for k, v in scalars.items():
        mel.set_material_instance_scalar_parameter_value(mi, k, v)
    for k, (r, g, b) in (colours or {}).items():
        mel.set_material_instance_vector_parameter_value(mi, k, unreal.LinearColor(r, g, b, 1.0))
    assets.save_loaded_asset(mi)
    return mi


def build_fog():
    white = unreal.load_asset("/Engine/EngineResources/WhiteSquareTexture")
    return instance("MI_GhostFog", pm.build_ghost_fog(RUNTIME + "/M_GhostFog", white), FOG_PARAMS)


def build_mist():
    white = unreal.load_asset("/Engine/EngineResources/WhiteSquareTexture")
    return instance("MI_GhostMist", pm.build_ghost_mist(RUNTIME + "/M_GhostMist", white), MIST_PARAMS, MIST_COLOURS)


def copy_idle():
    dst = RUNTIME + "/MM_Idle"
    if not assets.does_asset_exist(dst):
        if not assets.duplicate_asset(IDLE_SRC, dst):
            raise RuntimeError("could not copy " + IDLE_SRC)
    if not assets.save_asset(dst, only_if_is_dirty=False):
        raise RuntimeError("could not save " + dst)
    log("idle at " + dst)


def build_statue():
    """The statue master again, as build_scene.py builds it: it carries the eyes that follow the
    visitor in ghost mode (pantheon_materials.statue_eyes), off unless the app turns them on."""
    return pm.build_statue_master("/Game/Materials/M_Statue", unreal.load_asset("/Game/Textures/T_Marble021_Color"))


def main():
    if os.environ.get("F3_STATUE", "1") != "0":
        build_statue()
    for name in OBSOLETE:
        if assets.does_asset_exist(RUNTIME + "/" + name):
            assets.delete_asset(RUNTIME + "/" + name)
            log("removed " + name)
    build_fog()
    build_mist()
    copy_idle()
    log("built MI_GhostFog, MI_GhostMist, MM_Idle in " + RUNTIME)


if __name__ == "__main__":
    main()
