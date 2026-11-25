"""F3 "ghosts in the fog": the scene, a test camera and a render preset.

Copies /Game/Maps/Pantheon to /Game/F3/F3_Pantheon and adds:
- GhostFog: a box over the rotunda floor carrying the Volume-domain fog (pantheon_materials.build_ghost_fog),
  tagged F3Fog;
- invisible walkers (UE5 mannequin, walk cycle, hidden from the camera and from ray tracing), tagged
  F3Walker, moved along paths by the sequence;
- AF3GhostDriver, which writes the walkers' capsules for the fog to carve out every frame;
- a camera and the sequence /Game/F3/SEQ_GhostTest with the preset MRQ_GhostTest.

Run headless:
    UnrealEditor-Cmd ue/Pantheon/Pantheon.uproject -run=pythonscript -script=ue/scripts/f3_scene.py \\
        -unattended -nosplash -AllowCommandletRendering
Render: PANTHEON_MAP=/Game/F3/F3_Pantheon PANTHEON_SEQ_DIR=/Game/F3 PANTHEON_SEQ=SEQ_GhostTest \\
        ue/render.sh MRQ_GhostTest
"""

import math
import os
import sys

import unreal

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pantheon_materials as pm  # noqa: E402

F3 = "/Game/F3"
RUNTIME = "/Game/F3Runtime"   # cooked into the walk-through app (DefaultGame.ini)
SRC_MAP = "/Game/Maps/Pantheon"
MAP = F3 + "/F3_Pantheon"
FPS = 24
SECONDS = 14
MANNY = "/Game/Characters/Mannequins/Meshes/SKM_Manny_Simple"
QUINN = "/Game/Characters/Mannequins/Meshes/SKM_Quinn_Simple"
WALK = "/Game/Characters/Mannequins/Anims/Unarmed/Walk/MF_Unarmed_Walk_Fwd"

# where the oculus beam lands in F3 (Blender metres): on the floor in the rotunda, so the walkers
# cross it; in the films it falls on Jupiter in the apse
BEAM_TARGET = (2.0, -6.0, 0.0)
OCULUS = (0.0, 0.0, 43.0)

# walkers: mesh, start and end (Blender metres, +Y towards the door), start and end time (s)
WALKERS = [
    (MANNY, (-9.0, -1.0), (11.0, -10.0), 0.0, 14.0),
    (QUINN, (7.0, 7.0), (-1.0, -17.0), 1.5, 14.0),
    (MANNY, (-5.0, -15.0), (8.0, 3.0), 3.0, 14.0),
]
# fog look: parameters of MI_GhostFog, shared with the app's runtime assets
from f3_runtime import FOG_PARAMS  # noqa: E402
CAM_EV = 3.6

# test camera (Blender metres): low, looking at the beam with the walkers between
CAM_POS, CAM_LOOK, CAM_FOCAL = (-1.0, 0.5, 7.0), (1.0, -5.5, 0.0), 22.0

assets = unreal.EditorAssetLibrary
tools = unreal.AssetToolsHelpers.get_asset_tools()


def log(msg):
    unreal.log_warning("[f3scene] " + msg)


def ue(p):
    return unreal.Vector(p[0] * 100.0, -p[1] * 100.0, p[2] * 100.0 if len(p) > 2 else 0.0)


def recreate(name, cls, factory):
    path = F3 + "/" + name
    if assets.does_asset_exist(path):
        assets.delete_asset(path)
    return tools.create_asset(name, F3, cls, factory)


def fog_material():
    white = unreal.load_asset("/Engine/EngineResources/WhiteSquareTexture")
    return pm.build_ghost_fog(RUNTIME + "/M_GhostFog", white)


def main():
    # a fresh copy of the Pantheon level: load it and save it under the F3 name (duplicate_asset
    # refuses once the copy exists, and a map cannot always be deleted from a commandlet)
    world = unreal.EditorLoadingAndSavingUtils.load_map(SRC_MAP)
    if not unreal.EditorLoadingAndSavingUtils.save_map(world, MAP):
        raise RuntimeError("could not save the copy as " + MAP)
    world = unreal.EditorLoadingAndSavingUtils.load_map(MAP)
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)

    mat = fog_material()
    fog = actors.spawn_actor_from_class(unreal.StaticMeshActor, unreal.Vector(0, 0, 1000))
    fog.set_actor_label("GhostFog")
    fog.tags = ["F3Fog"]
    fc = fog.static_mesh_component
    fc.set_static_mesh(unreal.load_asset("/Engine/BasicShapes/Cube"))
    mel = unreal.MaterialEditingLibrary
    lpath = RUNTIME + "/MI_GhostFog"
    if assets.does_asset_exist(lpath):
        assets.delete_asset(lpath)
    look = tools.create_asset("MI_GhostFog", RUNTIME, unreal.MaterialInstanceConstant, unreal.MaterialInstanceConstantFactoryNew())
    mel.set_material_instance_parent(look, mat)
    for k, v in FOG_PARAMS.items():
        mel.set_material_instance_scalar_parameter_value(look, k, v)
    assets.save_loaded_asset(look)
    mat = look
    if os.environ.get("F3_DEBUG"):
        mi = recreate("MI_GhostFog_Debug", unreal.MaterialInstanceConstant, unreal.MaterialInstanceConstantFactoryNew())
        unreal.MaterialEditingLibrary.set_material_instance_parent(mi, mat)
        unreal.MaterialEditingLibrary.set_material_instance_scalar_parameter_value(mi, "CarveDebug", 1.0)
        unreal.MaterialEditingLibrary.set_material_instance_scalar_parameter_value(mi, "FogTop", 300.0)

        assets.save_loaded_asset(mi)
        mat = mi
    fc.set_material(0, mat)
    fc.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
    fc.set_editor_property("cast_shadow", False)
    fc.set_editor_property("visible_in_ray_tracing", False)
    fog.set_actor_scale3d(unreal.Vector(44.0, 44.0, 20.0))   # the rotunda, 0-20 m: floor fog and thin haze

    # the level's own height fog only as a trace: the fog volume carries the look, and the ghosts
    # can carve only what it makes
    for a in actors.get_all_level_actors():
        label = a.get_actor_label()
        if label == "HeightFog":
            a.get_component_by_class(unreal.ExponentialHeightFogComponent).set_editor_property("fog_density", 0.004)
        elif label == "OculusShaft":
            # aimed from the oculus to BEAM_TARGET, placed 140 m back along that line; the cone stays
            # inside the oculus (4.45 m radius about 96 m from the light)
            tx, ty, tz = BEAM_TARGET
            ox, oy, oz = OCULUS
            d = (ox - tx, oy - ty, oz - tz)
            n = math.sqrt(sum(c * c for c in d))
            pos = ue(tuple(tc + dc / n * 140.0 for tc, dc in zip(BEAM_TARGET, d)))
            aim = ue(BEAM_TARGET) - pos
            a.set_actor_location(pos, False, False)
            a.set_actor_rotation(unreal.Rotator(0.0, math.degrees(math.atan2(aim.z, math.hypot(aim.x, aim.y))),
                                                math.degrees(math.atan2(aim.y, aim.x))), False)
            sc = a.get_component_by_class(unreal.SpotLightComponent)
            sc.set_editor_property("outer_cone_angle", 2.4)
            sc.set_editor_property("inner_cone_angle", 2.0)
            # the beam lights the fog, not the floor: glowing fog over dark marble, so the walkers'
            # gaps show as dark shapes (over a sunlit white floor, lit fog had no contrast)
            sc.set_editor_property("diffuse_scale", 0.0)
            sc.set_editor_property("specular_scale", 0.0)
            sc.set_editor_property("volumetric_scattering_intensity", 20.0)

    walkers = []
    for k, (mesh, a, b, t0, t1) in enumerate(WALKERS):
        w = actors.spawn_actor_from_class(unreal.SkeletalMeshActor, ue(a))
        w.set_actor_label("Ghost_%d" % k)
        w.tags = ["F3Walker"]
        sk = w.skeletal_mesh_component
        sk.set_skeletal_mesh_asset(unreal.load_asset(mesh))
        sk.set_editor_property("animation_mode", unreal.AnimationMode.ANIMATION_SINGLE_NODE)
        anim = unreal.SingleAnimationPlayData()
        anim.set_editor_property("anim_to_play", unreal.load_asset(WALK))
        anim.set_editor_property("saved_looping", True)
        anim.set_editor_property("saved_playing", True)
        anim.set_editor_property("saved_play_rate", 0.85)
        anim.set_editor_property("saved_position", 0.37 * k)
        sk.set_editor_property("animation_data", anim)
        sk.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
        for prop, val in (("render_in_main_pass", False), ("render_in_depth_pass", False), ("cast_shadow", False),
                          ("visible_in_ray_tracing", False), ("visible_in_reflection_captures", False)):
            sk.set_editor_property(prop, val)
        walkers.append((w, a, b, t0, t1))

    driver_cls = unreal.load_class(None, "/Script/Pantheon.F3GhostDriver")
    drv = actors.spawn_actor_from_class(driver_cls, unreal.Vector(0, 0, 0))
    drv.set_actor_label("GhostDriver")

    cam = actors.spawn_actor_from_class(unreal.CineCameraActor, ue(CAM_POS))
    cam.set_actor_label("GhostTestCamera")
    d = ue(CAM_LOOK) - ue(CAM_POS)
    cam.set_actor_rotation(unreal.Rotator(0.0, math.degrees(math.atan2(d.z, math.hypot(d.x, d.y))),
                                          math.degrees(math.atan2(d.y, d.x))), False)
    cc = cam.get_cine_camera_component()
    cc.set_editor_property("current_focal_length", CAM_FOCAL)
    pp = cc.get_editor_property("post_process_settings")
    pp.set_editor_property("override_auto_exposure_bias", True)
    pp.set_editor_property("auto_exposure_bias", CAM_EV)
    cc.set_editor_property("post_process_settings", pp)
    focus = cc.get_editor_property("focus_settings")
    focus.set_editor_property("focus_method", unreal.CameraFocusMethod.DISABLE)
    cc.set_editor_property("focus_settings", focus)

    seq = recreate("SEQ_GhostTest", unreal.LevelSequence, unreal.LevelSequenceFactoryNew())
    seq.set_display_rate(unreal.FrameRate(FPS, 1))
    seq.set_tick_resolution(unreal.FrameRate(24000, 1))
    end = FPS * SECONDS
    seq.set_playback_start(0)
    seq.set_playback_end(end)
    cam_binding = seq.add_possessable(cam)
    lin = unreal.MovieSceneKeyInterpolation.LINEAR
    for w, a, b, t0, t1 in walkers:
        bind = seq.add_possessable(w)
        sec = bind.add_track(unreal.MovieScene3DTransformTrack).add_section()
        sec.set_range(0, end)
        ch = sec.get_all_channels()   # loc x y z, rot roll pitch yaw
        pa, pb = ue(a), ue(b)
        yaw = math.degrees(math.atan2(pb.y - pa.y, pb.x - pa.x)) - 90.0   # the mannequin faces +Y
        for t, p in ((0.0, pa), (t0, pa), (t1, pb), (SECONDS, pb)):
            f = unreal.FrameNumber(int(round(t * FPS)))
            ch[0].add_key(f, p.x, interpolation=lin)
            ch[1].add_key(f, p.y, interpolation=lin)
            ch[2].add_key(f, 0.0, interpolation=lin)
            ch[5].add_key(f, yaw, interpolation=lin)
    cut = seq.add_track(unreal.MovieSceneCameraCutTrack).add_section()
    cut.set_range(0, end)
    cut.set_camera_binding_id(seq.get_portable_binding_id(seq, cam_binding) if hasattr(seq, "get_portable_binding_id")
                              else seq.get_binding_id(cam_binding))
    assets.save_loaded_asset(seq)

    config_cls = getattr(unreal, "MoviePipelinePrimaryConfig", None) or unreal.MoviePipelineMasterConfig
    factory_cls = getattr(unreal, "MoviePipelinePrimaryConfigFactory", None) or unreal.MoviePipelineMasterConfigFactory
    cfg = recreate("MRQ_GhostTest", config_cls, factory_cls())
    out = cfg.find_or_add_setting_by_class(unreal.MoviePipelineOutputSetting)
    out.set_editor_property("output_resolution", unreal.IntPoint(1280, 720))
    out.set_editor_property("output_directory", unreal.DirectoryPath("{project_dir}/../../renders/f3_ghosttest"))
    out.set_editor_property("file_name_format", "ghost.{frame_number}")
    out.set_editor_property("output_frame_step", 24)
    cfg.find_or_add_setting_by_class(unreal.MoviePipelineDeferredPassBase)
    cfg.find_or_add_setting_by_class(unreal.MoviePipelineImageSequenceOutput_PNG)
    aa = cfg.find_or_add_setting_by_class(unreal.MoviePipelineAntiAliasingSetting)
    aa.set_editor_property("temporal_sample_count", 8)
    aa.set_editor_property("override_anti_aliasing", True)
    aa.set_editor_property("anti_aliasing_method", unreal.AntiAliasingMethod.AAM_NONE)
    aa.set_editor_property("engine_warm_up_count", 48)
    game = cfg.find_or_add_setting_by_class(unreal.MoviePipelineGameOverrideSetting)
    game.set_editor_property("cinematic_quality_settings", True)
    cv = cfg.find_or_add_setting_by_class(unreal.MoviePipelineConsoleVariableSetting)
    for k, v in (("r.VolumetricFog.GridPixelSize", 4), ("r.VolumetricFog.GridSizeZ", 128),
                 ("r.VolumetricFog.HistoryMissSupersampleCount", 16),
                 ("r.Lumen.ScreenProbeGather.ScreenTraces", 0), ("r.Lumen.Reflections.ScreenTraces", 0)):
        cv.add_or_update_console_variable(k, v)
    assets.save_loaded_asset(cfg)

    unreal.EditorLoadingAndSavingUtils.save_current_level()
    log("saved %s: fog volume, %d walkers, driver, camera, SEQ_GhostTest, MRQ_GhostTest" % (MAP, len(walkers)))


main()
