"""Paint the inner dome as the night sky, in place (no re-import, no level rebuild): builds
/Game/Materials/M_DomeSky (pantheon_materials.build_dome_sky) and sets it on the mesh
/Game/Architecture/Dome_Inner. build_scene.py does the same on a full build. DOME=stucco puts the
plain stucco back.

    UnrealEditor ue/Pantheon/Pantheon.uproject -run=pythonscript -script=ue/scripts/paint_dome.py \\
        -unattended -nosplash -AllowCommandletRendering
"""

import os
import sys

import unreal

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pantheon_materials as pm  # noqa: E402

MESH = "/Game/Architecture/Dome_Inner"
SKY = "/Game/Materials/M_DomeSky"
STUCCO = "/Game/Materials/MI_Stucco"


def main():
    mesh = unreal.load_asset(MESH)
    if mesh is None:
        raise RuntimeError("no mesh " + MESH)
    if os.environ.get("DOME", "sky") == "stucco":
        mat = unreal.load_asset(STUCCO)
    else:
        mat = pm.build_dome_sky(SKY, unreal.load_asset("/Game/Textures/T_Plaster001_Color"),
                                unreal.load_asset("/Game/Textures/T_Plaster001_NormalDX"))
    for i in range(mesh.get_num_sections(0)):
        mesh.set_material(i, mat)
    if not unreal.EditorAssetLibrary.save_loaded_asset(mesh):
        raise RuntimeError("could not save " + MESH)
    unreal.log_warning("[dome] %s now wears %s" % (MESH, mat.get_path_name()))


main()
