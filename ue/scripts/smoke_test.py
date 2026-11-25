"""Smoke test: confirms the editor's Python environment and the APIs the build scripts use."""
import unreal

unreal.log("PANTHEON_SMOKE engine=%s" % unreal.SystemLibrary.get_engine_version())
for name in ("AssetImportTask", "FbxImportUI", "EditorActorSubsystem", "LevelEditorSubsystem",
             "MoviePipelineQueueSubsystem", "LevelSequenceEditorBlueprintLibrary", "CineCameraActor",
             "ExponentialHeightFog", "InterchangeGenericAssetsPipeline", "MaterialEditingLibrary"):
    unreal.log("PANTHEON_SMOKE %s=%s" % (name, hasattr(unreal, name)))
unreal.log("PANTHEON_SMOKE rhi=%s" % unreal.SystemLibrary.get_rendering_detail_mode())
