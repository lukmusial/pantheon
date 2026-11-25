"""F3 step G1: does Niagara Fluids 3D gas render on this Mac, and does a walking figure carve it?

Builds a test level with a floor, sun and sky, the engine's Grid3D_Gas_Smoke template and (except in
variant A) the UE5 mannequin walking through the plume. The walker is hidden from the camera but stays
in the scene so its collision bodies can push the gas. A fixed camera, a 6 s sequence and a render
preset (four frames, 960x540) go with each level.

F3_VARIANT (environment) chooses how the walker is offered to the gas, one level per variant, so the
renders can be diffed against A to see whether the walker carves the plume:
    A  no walker (reference)
    B  walker bound through the template's user parameter User.Collide_PhysicsAsset
    C  walker found by the rigid-mesh collision query (actor tag and source actors)
    D  a plain 1.2 m static-mesh sphere through the plume, offered to the rigid-mesh query: does
       that collision path work at all?

Run headless:
    F3_VARIANT=B UnrealEditor-Cmd ue/Pantheon/Pantheon.uproject -run=pythonscript \\
        -script=ue/scripts/f3_smoketest.py -unattended -nosplash -AllowCommandletRendering
Render: PANTHEON_MAP=/Game/F3/F3_Smoke_B PANTHEON_SEQ_DIR=/Game/F3 PANTHEON_SEQ=SEQ_Smoke_B \\
        ue/render.sh MRQ_SmokeTest_B          (frames in renders/f3_smoketest/B)
"""

import os

import unreal

F3 = "/Game/F3"
VARIANT = os.environ.get("F3_VARIANT", "B")
MAP = F3 + "/F3_Smoke_" + VARIANT
FPS = 24
SECONDS = 6
GAS = "/NiagaraFluids/Templates/Gas/3D/Systems/Grid3D_Gas_Smoke.Grid3D_Gas_Smoke"
MANNY = "/Game/Characters/Mannequins/Meshes/SKM_Manny_Simple"
WALK = "/Game/Characters/Mannequins/Anims/Unarmed/Walk/MF_Unarmed_Walk_Fwd"
WALKER_TAG = "F3Walker"

assets = unreal.EditorAssetLibrary
tools = unreal.AssetToolsHelpers.get_asset_tools()


def log(msg):
    unreal.log_warning("[f3] " + msg)


def recreate(name, cls, factory):
    path = F3 + "/" + name
    if assets.does_asset_exist(path):
        assets.delete_asset(path)
    return tools.create_asset(name, F3, cls, factory)


def build_set(actors):
    floor = actors.spawn_actor_from_class(unreal.StaticMeshActor, unreal.Vector(0, 0, 0))
    floor.static_mesh_component.set_static_mesh(unreal.load_asset("/Engine/BasicShapes/Plane"))
    floor.set_actor_scale3d(unreal.Vector(40, 40, 1))
    sun = actors.spawn_actor_from_class(unreal.DirectionalLight, unreal.Vector(0, 0, 1000), unreal.Rotator(0, -40, 30))
    sun.get_component_by_class(unreal.DirectionalLightComponent).set_editor_property("intensity", 4.0)
    sky = actors.spawn_actor_from_class(unreal.SkyLight, unreal.Vector(0, 0, 500))
    sky.get_component_by_class(unreal.SkyLightComponent).set_editor_property("real_time_capture", True)
    actors.spawn_actor_from_class(unreal.SkyAtmosphere, unreal.Vector(0, 0, 0))


def build_walker(actors):
    manny = actors.spawn_actor_from_class(unreal.SkeletalMeshActor, unreal.Vector(-400, 0, 0), unreal.Rotator(0, 0, 0))
    manny.set_actor_label("Walker")
    manny.tags = [WALKER_TAG]
    sk = manny.skeletal_mesh_component
    sk.set_skeletal_mesh_asset(unreal.load_asset(MANNY))
    sk.set_editor_property("animation_mode", unreal.AnimationMode.ANIMATION_SINGLE_NODE)
    anim = unreal.SingleAnimationPlayData()
    anim.set_editor_property("anim_to_play", unreal.load_asset(WALK))
    anim.set_editor_property("saved_looping", True)
    anim.set_editor_property("saved_playing", True)
    sk.set_editor_property("animation_data", anim)
    sk.set_collision_enabled(unreal.CollisionEnabled.QUERY_AND_PHYSICS)
    # hidden from the camera, but kept in the scene for the gas collision
    sk.set_editor_property("visible_in_ray_tracing", False)
    sk.set_editor_property("cast_shadow", False)
    sk.set_editor_property("render_in_main_pass", False)
    sk.set_editor_property("render_in_depth_pass", False)
    return manny, sk


def bind_walker(nc, manny, sk):
    if VARIANT == "B":
        for call, args in (("set_variable_object", ("User.Collide_PhysicsAsset", sk)),
                           ("set_variable_actor", ("User.Collide_PhysicsAsset", manny))):
            try:
                getattr(nc, call)(*args)
                log("B: %s ok" % call)
            except Exception as exc:
                log("B: %s failed: %s" % (call, exc))
        try:
            unreal.NiagaraFunctionLibrary.override_system_user_variable_skeletal_mesh_component(
                nc, "Collide_PhysicsAsset", sk)
            log("B: skeletal mesh component override ok")
        except Exception as exc:
            log("B: skeletal mesh component override failed: %s" % exc)
    elif VARIANT == "C":
        lib = unreal.NiagaraDIRigidMeshCollisionFunctionLibrary
        log("C: library functions %s" % [n for n in dir(lib) if not n.startswith("_")])
        for override in ("User.Collide_StaticMesh", "Collide_StaticMesh", "User.Collide_PhysicsAsset"):
            try:
                lib.set_source_actors(nc, override, [manny])
                log("C: set_source_actors(%s) ok" % override)
            except Exception as exc:
                log("C: set_source_actors(%s) failed: %s" % (override, exc))


def build_sequence(cam, manny):
    seq = recreate("SEQ_Smoke_" + VARIANT, unreal.LevelSequence, unreal.LevelSequenceFactoryNew())
    seq.set_display_rate(unreal.FrameRate(FPS, 1))
    seq.set_tick_resolution(unreal.FrameRate(24000, 1))
    end = FPS * SECONDS
    seq.set_playback_start(0)
    seq.set_playback_end(end)
    cam_binding = seq.add_possessable(cam)
    if manny is not None:
        walker = seq.add_possessable(manny)
        sec = walker.add_track(unreal.MovieScene3DTransformTrack).add_section()
        sec.set_range(0, end)
        ch = sec.get_all_channels()
        for f, x in ((0, -400.0), (end, 400.0)):   # about 1.3 m/s, a slow walk
            ch[0].add_key(unreal.FrameNumber(f), x, interpolation=unreal.MovieSceneKeyInterpolation.LINEAR)
    cut = seq.add_track(unreal.MovieSceneCameraCutTrack).add_section()
    cut.set_range(0, end)
    cut.set_camera_binding_id(seq.get_portable_binding_id(seq, cam_binding) if hasattr(seq, "get_portable_binding_id")
                              else seq.get_binding_id(cam_binding))
    assets.save_loaded_asset(seq)


def build_preset():
    config_cls = getattr(unreal, "MoviePipelinePrimaryConfig", None) or unreal.MoviePipelineMasterConfig
    factory_cls = getattr(unreal, "MoviePipelinePrimaryConfigFactory", None) or unreal.MoviePipelineMasterConfigFactory
    cfg = recreate("MRQ_SmokeTest_" + VARIANT, config_cls, factory_cls())
    out = cfg.find_or_add_setting_by_class(unreal.MoviePipelineOutputSetting)
    out.set_editor_property("output_resolution", unreal.IntPoint(960, 540))
    out.set_editor_property("output_directory", unreal.DirectoryPath("{project_dir}/../../renders/f3_smoketest/" + VARIANT))
    out.set_editor_property("file_name_format", "smoke.{frame_number}")
    out.set_editor_property("output_frame_step", 12)
    cfg.find_or_add_setting_by_class(unreal.MoviePipelineDeferredPassBase)
    cfg.find_or_add_setting_by_class(unreal.MoviePipelineImageSequenceOutput_PNG)
    aa = cfg.find_or_add_setting_by_class(unreal.MoviePipelineAntiAliasingSetting)
    aa.set_editor_property("temporal_sample_count", 4)
    aa.set_editor_property("engine_warm_up_count", 32)
    cfg.find_or_add_setting_by_class(unreal.MoviePipelineGameOverrideSetting)
    assets.save_loaded_asset(cfg)


def main():
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    world = unreal.EditorLoadingAndSavingUtils.new_blank_map(False)
    build_set(actors)
    gas = actors.spawn_actor_from_class(unreal.NiagaraActor, unreal.Vector(0, 0, 0))
    gas.set_actor_label("Gas")
    nc = gas.get_component_by_class(unreal.NiagaraComponent)
    nc.set_asset(unreal.load_asset(GAS))
    manny = None
    if VARIANT in ("B", "C"):
        manny, sk = build_walker(actors)
        bind_walker(nc, manny, sk)
    elif VARIANT == "D":
        manny = actors.spawn_actor_from_class(unreal.StaticMeshActor, unreal.Vector(-400, 0, 100))
        manny.set_actor_label("Ball")
        manny.tags = [WALKER_TAG]
        mc = manny.static_mesh_component
        mc.set_static_mesh(unreal.load_asset("/Engine/BasicShapes/Sphere"))
        mc.set_mobility(unreal.ComponentMobility.MOVABLE)
        mc.set_collision_enabled(unreal.CollisionEnabled.QUERY_AND_PHYSICS)
        mc.set_editor_property("render_in_main_pass", False)
        mc.set_editor_property("cast_shadow", False)
        manny.set_actor_scale3d(unreal.Vector(1.2, 1.2, 1.2))
        lib = unreal.NiagaraDIRigidMeshCollisionFunctionLibrary
        for override in ("User.Collide_StaticMesh", "User.Collide_PhysicsAsset", "User.Collide_GeometryCollection"):
            try:
                lib.set_source_actors(nc, override, [manny])
                log("D: set_source_actors(%s) ok" % override)
            except Exception as exc:
                log("D: set_source_actors(%s) failed: %s" % (override, exc))
    cam = actors.spawn_actor_from_class(unreal.CineCameraActor, unreal.Vector(0, -900, 170), unreal.Rotator(0, -2, 90))
    cam.set_actor_label("SmokeCam")
    build_sequence(cam, manny)
    build_preset()
    if not unreal.EditorLoadingAndSavingUtils.save_map(world, MAP):
        raise RuntimeError("could not save " + MAP)
    log("variant %s: saved %s, sequence and preset" % (VARIANT, MAP))


main()
