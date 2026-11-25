"""Copy a render preset with a custom frame range, to resume an interrupted render.

    PANTHEON_RESUME_PRESET=MRQ_Final4K PANTHEON_RESUME_FRAME=1510 \
    UnrealEditor-Cmd ue/Pantheon/Pantheon.uproject -run=pythonscript \
        -script=ue/scripts/resume_preset.py -unattended -nosplash -nop4

Writes /Game/Cinematics/<preset>_Resume rendering from PANTHEON_RESUME_FRAME to the end of
SEQ_Flythrough. Frame numbers in file names stay absolute, so the new frames land beside the
old ones; the warm-up frames run before the start frame, so motion blur and temporal history
are settled at the join.

PANTHEON_RESUME_END=<frame> stops there instead (end exclusive) and PANTHEON_RESUME_SUFFIX names
the copy (default _Resume): to re-render only the opening of a film, e.g. its outside shots,
PANTHEON_RESUME_FRAME=0 PANTHEON_RESUME_END=300 PANTHEON_RESUME_SUFFIX=_Head.
PANTHEON_SEQ=SEQ_Vertical reads the portrait film's length.
"""

import os

import unreal

CINE = "/Game/Cinematics"
assets = unreal.EditorAssetLibrary

src_name = os.environ.get("PANTHEON_RESUME_PRESET", "MRQ_Final4K")
start = int(os.environ["PANTHEON_RESUME_FRAME"])
src = "%s/%s" % (CINE, src_name)
dst = src + os.environ.get("PANTHEON_RESUME_SUFFIX", "_Resume")

seq = unreal.load_asset(CINE + "/" + os.environ.get("PANTHEON_SEQ", "SEQ_Flythrough"))
end = int(os.environ.get("PANTHEON_RESUME_END", seq.get_playback_end()))
unreal.log_warning("[resume] sequence playback %d..%d" % (seq.get_playback_start(), end))

if assets.does_asset_exist(dst):
    assets.delete_asset(dst)
cfg = assets.duplicate_asset(src, dst)
out = cfg.find_setting_by_class(unreal.MoviePipelineOutputSetting)
out.set_editor_property("use_custom_playback_range", True)
out.set_editor_property("custom_start_frame", start)
out.set_editor_property("custom_end_frame", end)
assets.save_loaded_asset(cfg)
unreal.log_warning("[resume] %s frames %d..%d (end exclusive)" % (dst, start, end))
