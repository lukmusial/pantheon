"""Build the Pantheon level in Unreal Engine 5.9 from the Blender exports.

Run headless:
    UnrealEditor-Cmd ue/Pantheon/Pantheon.uproject -run=pythonscript \
        -script=ue/scripts/build_scene.py -unattended -nosplash -nop4

Steps: master material and one instance per stone, import architecture and statue FBX
files (Nanite on), create /Game/Maps/Pantheon, place everything, add lighting, fog and
post-processing, save. Re-running replaces the assets and rebuilds the level.

Coordinates: Blender metres, Z up, +Y towards the entrance. Unreal centimetres, Z up,
left-handed, so Blender (x, y, z) becomes (100x, -100y, 100z) and a Blender yaw becomes
its negative.
"""

import json
import math
import os

import sys

import unreal

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import pantheon_materials as pm  # noqa: E402
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
ARCH_DIR = os.path.join(ROOT, "assets", "architecture", "fbx")
STATUE_DIR = os.path.join(ROOT, "assets", "statues", "processed")
PAINTED_DIR = os.path.join(ROOT, "assets", "statues", "painted")
CAPITAL_FBX = os.path.join(ROOT, "assets", "architecture", "capital", "capital.fbx")
CAPITAL_PKG = "/Game/Architecture/Capital"
PAINT_TEX_DIR = os.path.join(ROOT, "assets", "paintings", "textures")
PAINT_PKG = "/Game/Paintings"
_painted = {}


def painted_material(obj_name):
    """Material instance with the composed painting for a Painted_* object (tools/compose_paintings.py):
    textures/<name>.png, else the name with trailing _parts removed (e.g. Painted_AedFrieze_0225)."""
    base = obj_name
    while base and not os.path.exists(os.path.join(PAINT_TEX_DIR, base + ".png")):
        base = base.rsplit("_", 1)[0] if "_" in base else ""
    if not base:
        return None
    if base in _painted:
        return _painted[base]
    t = unreal.AssetImportTask()
    t.set_editor_property("filename", os.path.join(PAINT_TEX_DIR, base + ".png"))
    t.set_editor_property("destination_path", PAINT_PKG)
    t.set_editor_property("destination_name", "T_" + base)
    t.set_editor_property("automated", True)
    t.set_editor_property("replace_existing", True)
    t.set_editor_property("save", True)
    tools.import_asset_tasks([t])
    tex = unreal.load_asset("%s/T_%s" % (PAINT_PKG, base))
    path = "%s/MI_%s" % (PAINT_PKG, base)
    mi = unreal.load_asset(path) if assets.does_asset_exist(path) else tools.create_asset(
        "MI_" + base, PAINT_PKG, unreal.MaterialInstanceConstant, unreal.MaterialInstanceConstantFactoryNew())
    mel.set_material_instance_parent(mi, unreal.load_asset(MAT_DIR + "/M_PaintedMaster"))
    mel.set_material_instance_texture_parameter_value(mi, "Painting", tex)
    mel.set_material_instance_texture_parameter_value(
        mi, "PlasterNormal", unreal.load_asset("%s/T_Plaster002_NormalDX" % TEX_PKG))
    mel.set_material_instance_vector_parameter_value(mi, "Tint", unreal.LinearColor(1.0, 1.0, 1.0, 1.0))
    assets.save_loaded_asset(mi)
    _painted[base] = mi
    return mi
MANIFEST = json.load(open(os.path.join(ARCH_DIR, "manifest.json")))

MAT_DIR = "/Game/Materials"
ARCH_PKG = "/Game/Architecture"
# StatuesV2: a fresh folder, because reimporting over the assets that a classic-FBX import had made
# kept its unit settings and shrank the statues to 1/100
STATUE_PKG = "/Game/StatuesV2"
MAP = "/Game/Maps/Pantheon"

assets = unreal.EditorAssetLibrary
mel = unreal.MaterialEditingLibrary
tools = unreal.AssetToolsHelpers.get_asset_tools()


def log(msg):
    unreal.log("PANTHEON " + msg)


def ue_loc(p):
    return unreal.Vector(p[0] * 100.0, -p[1] * 100.0, p[2] * 100.0)


# --------------------------------------------------------------------------
# Materials
# --------------------------------------------------------------------------

TEX_DIR = os.path.join(ROOT, "assets", "textures")
TEX_PKG = "/Game/Textures"
WAT = "/Engine/Functions/Engine_MaterialFunctions01/Texturing/WorldAlignedTexture.WorldAlignedTexture"

# Per stone: CC0 texture set (ambientCG, assets/textures/<id>), tint, brightness, tile size in cm.
# The textures stand in for the real stones; tint and brightness pull them towards the colours
# in reference/dimensions.md. None means untextured (flat colour from the Blender manifest).
TEX_RES = "4K"
# Per stone: CC0 texture set (ambientCG, assets/textures/<id>_4K), tint, brightness, tile size in cm.
# The vein recolouring below then gives each stone its real ground and vein colours.
STONES = {
    "M_WhiteMarble": ("Marble021", (1.0, 1.0, 1.0), 1.0, 300.0),
    "M_Pavonazzetto": ("Marble012", (1.0, 0.96, 1.0), 1.6, 350.0),
    "M_GialloAntico": ("Marble014", (1.0, 0.78, 0.45), 1.05, 200.0),
    "M_Porphyry": ("Granite002A", (1.0, 0.32, 0.36), 0.55, 50.0),
    "M_GreyGranite": ("Granite002A", (0.85, 0.85, 0.88), 0.8, 80.0),
    "M_PinkGranite": ("Granite004A", (1.0, 0.74, 0.66), 1.1, 80.0),
    "M_Stucco": ("Plaster001", (1.0, 0.98, 0.94), 1.0, 400.0),
    "M_Concrete": ("Plaster001", (0.78, 0.74, 0.68), 0.9, 400.0),
    "M_Travertine": ("Travertine009", (1.0, 1.0, 1.0), 0.95, 300.0),
    "M_Bronze": ("Metal008", (1.0, 0.72, 0.42), 1.0, 120.0),
    "M_Gilded": ("Metal048C", (1.0, 0.86, 0.55), 1.0, 60.0),
    "M_DarkMarble": ("Marble006", (1.0, 1.0, 1.0), 1.0, 250.0),
    "M_Terracotta": ("Plaster001", (0.66, 0.36, 0.24), 1.0, 150.0),
}
# Ground and vein colours (sRGB hex), threshold, contrast and invert (1 = specks lighter than the
# ground), from the measured luminance of each texture (p10 for dark veins, p90 for light specks).
VEINS = {
    "M_WhiteMarble": ("#D6D0C6", "#948D86", 0.935, 12.0, 0.0, 0.957),
    "M_Pavonazzetto": ("#CFC6C0", "#653856", 0.64, 7.0, 0.0, 0.694),
    "M_GialloAntico": ("#DDB46A", "#8C4A28", 0.74, 8.0, 0.0, 0.788),
    "M_Porphyry": ("#5C1E24", "#D8C6BE", 0.80, 10.0, 1.0, 0.710),
    "M_GreyGranite": ("#77746F", "#2E2C2A", 0.56, 6.0, 0.0, 0.710),
    "M_DarkMarble": ("#1D1A19", "#CEC6BB", 0.16, 10.0, 1.0, 0.078),
}


def srgb_hex(h):
    v = [int(h[i:i + 2], 16) / 255.0 for i in (1, 3, 5)]
    return [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in v]


# Base roughness per stone: honed rather than mirror-polished, so reflections stay soft.
ROUGHNESS = {
    # walls honed (above Lumen's 0.4 trace limit, so grazing views do not mirror the sunlit doorway,
    # which blew them out to white); floors use the polished "_Floor" variants (x0.45)
    "M_WhiteMarble": 0.45, "M_Pavonazzetto": 0.55, "M_GialloAntico": 0.5, "M_Porphyry": 0.45,
    "M_GreyGranite": 0.45, "M_PinkGranite": 0.45, "M_Stucco": 0.8, "M_Concrete": 0.9,
    "M_Travertine": 0.6, "M_Bronze": 0.35, "M_DarkMarble": 0.45,
}


def import_textures():
    ids = sorted({v[0] for v in STONES.values() if v[0]} | {"Plaster002"})
    tasks = []
    for tid in ids:
        for kind in ("Color", "Roughness", "NormalDX"):
            f = os.path.join(TEX_DIR, "%s_%s" % (tid, TEX_RES), "%s_%s-JPG_%s.jpg" % (tid, TEX_RES, kind))
            t = unreal.AssetImportTask()
            t.set_editor_property("filename", f)
            t.set_editor_property("destination_path", TEX_PKG)
            t.set_editor_property("destination_name", "T_%s_%s" % (tid, kind))
            t.set_editor_property("automated", True)
            t.set_editor_property("replace_existing", True)
            t.set_editor_property("save", True)
            tasks.append(t)
    tools.import_asset_tasks(tasks)
    for tid in ids:
        nrm = unreal.load_asset("%s/T_%s_NormalDX" % (TEX_PKG, tid))
        if nrm is not None:
            nrm.set_editor_property("srgb", False)
            nrm.set_editor_property("compression_settings", unreal.TextureCompressionSettings.TC_NORMALMAP)
            assets.save_loaded_asset(nrm)
        rough = unreal.load_asset("%s/T_%s_Roughness" % (TEX_PKG, tid))
        if rough is not None:
            rough.set_editor_property("srgb", False)
            rough.set_editor_property("compression_settings", unreal.TextureCompressionSettings.TC_GRAYSCALE)
            assets.save_loaded_asset(rough)
    log("textures %d sets" % len(ids))


# Megascans surfaces used instead of the ambientCG set: texture path prefix, tile size (cm), normal
# strength. Tested on the dome's stucco (Damaged_Wall_Plaster_ubhkefscw, 300 cm, 0.8) and not adopted:
# the ribs turned grey against yellow coffers and dark blotches appeared near the rim
# (renders/dometest_cool, renders/dometest). Entry kept as an example:
#   "M_Stucco": (_MS + "Damaged_Wall_Plaster_ubhkefscw/High/ubhkefscw_tier_1/Textures/T_ubhkefscw_4K", 300.0, 0.8)
_MS = "/Game/Fab/Megascans/Surfaces/"
MEGASCANS = {}
EXT_NORMALS = {"stone": _MS + "Chiseled_Roman_Marble_tkwgfatew/High/tkwgfatew_tier_1/Textures/T_tkwgfatew_4K_N",
               "plaster": _MS + "Old_Plaster_rmthh1p0/High/rmthh1p0_tier_1/Textures/T_rmthh1p0_4K_N"}
# Outside surfaces (texture prefix, tile cm, tint): scanned plasters. The drum, the dome's steps and
# the forecourt's walls in white lime stucco (user, 2026-11-25: "white stucco"; it was a warm, patchy
# yellow plaster, tkxmedsaw); the city's blocks in painted stuccoes and brick-coloured render.
_WHITE = _MS + "Damaged_Wall_Plaster_ubhkefscw/High/ubhkefscw_tier_1/Textures/T_ubhkefscw_4K"
EXT_SURFACE = {
    "M_Concrete": (_WHITE, 350.0, (1.0, 1.0, 1.0)),
    "M_Stucco": (_WHITE, 300.0, (1.0, 1.0, 1.0)),
    "M_StuccoOchre": (_MS + "Stucco_Wall_ugxodcls/High/ugxodcls_tier_1/Textures/T_ugxodcls_4K", 300.0, (1.15, 1.05, 0.95)),
    "M_StuccoRed": (_MS + "Stucco_Wall_th5keedew/High/th5keedew_tier_1/Textures/T_th5keedew_4K", 300.0, (1.1, 0.85, 0.75)),
    "M_StuccoCream": (_MS + "Stucco_Wall_pgbiw1s0/High/pgbiw1s0_tier_1/Textures/T_pgbiw1s0_4K", 300.0, (0.95, 0.92, 0.86)),
    "M_Brick": (_MS + "Stucco_Wall_tewhehno/High/tewhehno_tier_1/Textures/T_tewhehno_4K", 300.0, (1.0, 0.82, 0.72)),
}
EXT_WEATHER = {"Roughness": 0.8, "NormalStrength": 1.0, "GrimeAmount": 0.35, "GrimeHeight": 220.0,
               "StreakAmount": 0.3, "StreakWidth": 260.0, "StreakLength": 1600.0, "StreakCover": 0.55}
# scored joints on the outer walls: the drum's stucco ruled like ashlar, the block's marble facing
# (JointRadius: the wall's distance from the axis, so that JointWidth is measured along it, cm)
EXT_JOINTS = {"M_Concrete": {"JointRadius": 2792.0, "JointWidth": 120.0, "JointHeight": 60.0, "JointLine": 1.0},
              "M_WhiteMarble": {"JointRadius": 3342.0, "JointWidth": 180.0, "JointHeight": 90.0, "JointLine": 0.8}}
# the outer walls that get the joints (the rest of the outside gets "_Ext")
EXT_WALLS = ("Drum_Outer", "Drum_Outer_Upper", "Portico_Block", "Portico_Tympanum")


def build_master_material():
    return pm.build_stone_master(MAT_DIR + "/M_Stone")


# Normal map strength per stone: polished stones nearly flat, stucco and concrete rougher.
NORMAL_STRENGTH = {
    "M_WhiteMarble": 0.25, "M_Pavonazzetto": 0.25, "M_GialloAntico": 0.25, "M_Porphyry": 0.3,
    "M_GreyGranite": 0.4, "M_PinkGranite": 0.4, "M_Stucco": 0.7, "M_Concrete": 0.9, "M_Travertine": 0.7,
    "M_DarkMarble": 0.25,
}
SPECIAL = ("M_Painted", "M_Flame", "M_InvaderTile")


def build_instances(master):
    out = {}
    for name, spec in MANIFEST["materials"].items():
        if name in SPECIAL:
            continue
        mi_name = "MI_" + name[2:]
        path = MAT_DIR + "/" + mi_name
        if assets.does_asset_exist(path):
            mi = unreal.load_asset(path)
        else:
            mi = tools.create_asset(mi_name, MAT_DIR, unreal.MaterialInstanceConstant,
                                    unreal.MaterialInstanceConstantFactoryNew())
        mel.set_material_instance_parent(mi, master)
        c = spec["base_color"]
        mel.set_material_instance_vector_parameter_value(mi, "BaseColor", unreal.LinearColor(c[0], c[1], c[2], 1.0))
        mel.set_material_instance_scalar_parameter_value(mi, "Roughness", spec["roughness"])
        mel.set_material_instance_scalar_parameter_value(mi, "Metallic", spec["metallic"])
        tid, tint, bright, tile_cm = STONES.get(name, (None, (1.0, 1.0, 1.0), 1.0, 200.0))
        if tid:
            mel.set_material_instance_texture_parameter_value(
                mi, "Albedo", unreal.load_asset("%s/T_%s_Color" % (TEX_PKG, tid)))
            mel.set_material_instance_texture_parameter_value(
                mi, "RoughnessMap", unreal.load_asset("%s/T_%s_Roughness" % (TEX_PKG, tid)))
            mel.set_material_instance_vector_parameter_value(mi, "BaseColor", unreal.LinearColor(*tint, 1.0))
            mel.set_material_instance_scalar_parameter_value(mi, "Roughness", ROUGHNESS.get(name, spec["roughness"]))
            mel.set_material_instance_texture_parameter_value(
                mi, "NormalMap", unreal.load_asset("%s/T_%s_NormalDX" % (TEX_PKG, tid)))
            mel.set_material_instance_scalar_parameter_value(mi, "NormalStrength", NORMAL_STRENGTH.get(name, 0.4))
        if name in MEGASCANS and assets.does_asset_exist(MEGASCANS[name][0] + "_B"):
            # scanned colour and relief from Quixel Megascans (added through Fab by the user)
            prefix, ms_tile, ms_normal = MEGASCANS[name]
            mel.set_material_instance_texture_parameter_value(mi, "Albedo", unreal.load_asset(prefix + "_B"))
            mel.set_material_instance_texture_parameter_value(mi, "NormalMap", unreal.load_asset(prefix + "_N"))
            mel.set_material_instance_scalar_parameter_value(mi, "NormalStrength", ms_normal)
            tile_cm = ms_tile
        if name in VEINS:
            ground, vein, level, contrast, inv, median = VEINS[name]
            mel.set_material_instance_vector_parameter_value(mi, "GroundColor", unreal.LinearColor(*srgb_hex(ground), 1.0))
            mel.set_material_instance_vector_parameter_value(mi, "VeinColor", unreal.LinearColor(*srgb_hex(vein), 1.0))
            for k, v in (("VeinLevel", level), ("VeinContrast", contrast), ("VeinInvert", inv),
                         ("TexMedian", median), ("DetailAmount", 0.5), ("VeinMix", 1.0)):
                mel.set_material_instance_scalar_parameter_value(mi, k, v)
        mel.set_material_instance_scalar_parameter_value(mi, "Brightness", bright)
        mel.set_material_instance_scalar_parameter_value(mi, "TileSize", tile_cm)
        assets.save_loaded_asset(mi)
        out[name] = mi
    # polished floor paving: same stones, glossier, so the oculus light and the fires reflect
    for name in list(out):
        mi_name = "MI_" + name[2:] + "_Floor"
        path = MAT_DIR + "/" + mi_name
        fl = unreal.load_asset(path) if assets.does_asset_exist(path) else tools.create_asset(
            mi_name, MAT_DIR, unreal.MaterialInstanceConstant, unreal.MaterialInstanceConstantFactoryNew())
        mel.set_material_instance_parent(fl, out[name])
        rough = ROUGHNESS.get(name, MANIFEST["materials"][name]["roughness"])
        # honed and worn rather than mirror-polished (was x0.45), with the stone's relief stronger
        mel.set_material_instance_scalar_parameter_value(fl, "Roughness", rough * 0.85)
        mel.set_material_instance_scalar_parameter_value(fl, "NormalStrength", 2.0 * NORMAL_STRENGTH.get(name, 0.4))
        assets.save_loaded_asset(fl)
        out[name + "_Floor"] = fl
    # drum walls with slab joints; polished column shafts
    for name in list(out):
        if name.endswith("_Floor"):
            continue
        for suffix, params in (("_Wall", {"JointMix": 1.0}),
                               ("_Polished", {"Roughness": ROUGHNESS.get(name, MANIFEST["materials"][name]["roughness"]) * 0.5}),
                               # attic zone: matte. At honed roughness the roughness map dips under Lumen's
                               # 0.4 trace limit and the upper half of the wall mirrored the lit dome as a
                               # hard white band
                               ("_Matte", {"Roughness": 0.85}),
                               ("_WallMatte", {"JointMix": 1.0, "Roughness": 0.85}),
                               # outside: weathered, grimy at the foot, streaked by rain (user, 2026-11-24:
                               # the exterior "doesn't look realistic"); "_ExtWall" adds scored joints
                               ("_Ext", dict(EXT_WEATHER)),
                               ("_ExtWall", dict(EXT_WEATHER, JointMix=1.0, **EXT_JOINTS.get(name, {}))),
                               # weathered, unpolished metal for the door leaves
                               # darker too: rough bright bronze picks up the firelight and reads as rust
                               ("_Aged", {"Roughness": min(0.9, ROUGHNESS.get(name, MANIFEST["materials"][name]["roughness"]) * 1.7),
                                          "Brightness": 0.65, "NormalStrength": 0.9})):
            mi_name = "MI_" + name[2:] + suffix
            path = MAT_DIR + "/" + mi_name
            v = unreal.load_asset(path) if assets.does_asset_exist(path) else tools.create_asset(
                mi_name, MAT_DIR, unreal.MaterialInstanceConstant, unreal.MaterialInstanceConstantFactoryNew())
            mel.set_material_instance_parent(v, out[name])
            for k, val in params.items():
                mel.set_material_instance_scalar_parameter_value(v, k, val)
            if suffix in ("_Ext", "_ExtWall"):
                # tooled, weathered relief from a Megascans scan (chiselled marble; old plaster on
                # the concrete and stucco shells)
                nrm = EXT_NORMALS["plaster" if name in ("M_Concrete", "M_Stucco") else "stone"]
                if assets.does_asset_exist(nrm):
                    mel.set_material_instance_texture_parameter_value(v, "NormalMap", unreal.load_asset(nrm))
                if name in EXT_SURFACE and assets.does_asset_exist(EXT_SURFACE[name][0] + "_B"):
                    # the drum and dome: aged lime stucco over the brick-faced concrete, scanned
                    prefix, ext_tile, tint = EXT_SURFACE[name]
                    mel.set_material_instance_texture_parameter_value(v, "Albedo", unreal.load_asset(prefix + "_B"))
                    mel.set_material_instance_texture_parameter_value(v, "NormalMap", unreal.load_asset(prefix + "_N"))
                    mel.set_material_instance_vector_parameter_value(v, "BaseColor", unreal.LinearColor(*tint, 1.0))
                    for k, val in (("TileSize", ext_tile), ("Brightness", 1.0), ("VeinMix", 0.0)):
                        mel.set_material_instance_scalar_parameter_value(v, k, val)
            assets.save_loaded_asset(v)
            out[name + suffix] = v
    # Coffer rosettes: satin gilded stucco. At the leaf's 0.28 the small star shapes mirrored the dark
    # dome and floor (they read black) and sparkled from frame to frame as the view moved, unlike
    # real gilding, which glows softly in diffuse light (user, 2026-11-23)
    if "M_Gilded" in out:
        path = MAT_DIR + "/MI_Gilded_Satin"
        v = unreal.load_asset(path) if assets.does_asset_exist(path) else tools.create_asset(
            "MI_Gilded_Satin", MAT_DIR, unreal.MaterialInstanceConstant, unreal.MaterialInstanceConstantFactoryNew())
        mel.set_material_instance_parent(v, out["M_Gilded"])
        mel.set_material_instance_scalar_parameter_value(v, "Roughness", 0.5)
        mel.set_material_instance_scalar_parameter_value(v, "NormalStrength", 0.2)
        # gilded stucco (Piranesi), not solid metal: fully metallic, deep in the coffers they saw only
        # dark reflections and stayed black even at satin roughness; part diffuse takes the room's light
        mel.set_material_instance_scalar_parameter_value(v, "Metallic", 0.4)
        assets.save_loaded_asset(v)
        out["M_Gilded_Satin"] = v
    # The dome's gilded bronze tiles outside (user, 2026-11-25: "dome in gilded bronze"): fully
    # metallic, a little rough, weathered like the rest of the outside (grime low down is out of reach
    # up there; rain streaks run down the cap), with only a faint hammered relief
    if "M_Gilded" in out:
        path = MAT_DIR + "/MI_Gilded_Roof"
        v = unreal.load_asset(path) if assets.does_asset_exist(path) else tools.create_asset(
            "MI_Gilded_Roof", MAT_DIR, unreal.MaterialInstanceConstant, unreal.MaterialInstanceConstantFactoryNew())
        mel.set_material_instance_parent(v, out["M_Gilded"])
        for k, val in dict(EXT_WEATHER, Roughness=0.42, NormalStrength=0.3, GrimeAmount=0.0,
                           StreakAmount=0.25).items():
            mel.set_material_instance_scalar_parameter_value(v, k, val)
        assets.save_loaded_asset(v)
        out["M_Gilded_Roof"] = v
    # The forecourt's paving: darker and weathered, not the portico's clean travertine (user,
    # 2026-11-25: "we need a darker, more weathered material used for the plaza stones, it's too
    # ideal"): a duller, greyer stone, rough, grimy all over, with each slab's own colour (vertex
    # colour from the export) varying it
    if "M_Travertine" in out:
        path = MAT_DIR + "/MI_Travertine_Paving"
        v = unreal.load_asset(path) if assets.does_asset_exist(path) else tools.create_asset(
            "MI_Travertine_Paving", MAT_DIR, unreal.MaterialInstanceConstant, unreal.MaterialInstanceConstantFactoryNew())
        mel.set_material_instance_parent(v, out["M_Travertine"])
        mel.set_material_instance_vector_parameter_value(v, "BaseColor", unreal.LinearColor(0.80, 0.76, 0.70, 1.0))
        for k, val in dict(EXT_WEATHER, Brightness=0.62, Roughness=0.9, NormalStrength=1.6, GrimeAmount=0.55,
                           GrimeHeight=400.0, StreakAmount=0.0).items():
            mel.set_material_instance_scalar_parameter_value(v, k, val)
        if assets.does_asset_exist(EXT_NORMALS["stone"]):
            mel.set_material_instance_texture_parameter_value(v, "NormalMap", unreal.load_asset(EXT_NORMALS["stone"]))
        assets.save_loaded_asset(v)
        out["M_Travertine_Paving"] = v
    # The porphyry frieze of the main entablature: honed and lighter. At the wall roughness it read as
    # a black mirror strip wedged between the white fasciae and the cornice (user, 2026-11-23)
    if "M_Porphyry" in out:
        path = MAT_DIR + "/MI_Porphyry_Frieze"
        v = unreal.load_asset(path) if assets.does_asset_exist(path) else tools.create_asset(
            "MI_Porphyry_Frieze", MAT_DIR, unreal.MaterialInstanceConstant, unreal.MaterialInstanceConstantFactoryNew())
        mel.set_material_instance_parent(v, out["M_Porphyry"])
        mel.set_material_instance_scalar_parameter_value(v, "Roughness", 0.75)
        mel.set_material_instance_scalar_parameter_value(v, "Brightness", 1.0)
        mel.set_material_instance_scalar_parameter_value(v, "NormalStrength", 0.6)
        # a lighter red ground: in the shade of the cornice the stone's own #5C1E24 read as a black void
        mel.set_material_instance_vector_parameter_value(v, "GroundColor", unreal.LinearColor(*srgb_hex("#8E3A3C"), 1.0))
        assets.save_loaded_asset(v)
        out["M_Porphyry_Frieze"] = v
    out.update(build_special_materials())
    log("materials %d" % len(out))
    return out


# two views of the simulation, 128 looping frames each, in a 16x16 sheet (tools/assemble_flipbook.py)
FIRE_SHEET = os.path.join(ROOT, "assets", "fire", "flipbooks", "campfire_2x128_16x16.png")
SMOKE_SHEET = os.path.join(ROOT, "assets", "fire", "flipbooks", "campfire_smoke_2x128_16x16.png")
# width and height in cm; base = how far below the light slot the flame starts (m)
FLAMES = {
    "stand": dict(Width=20.0, Height=30.0, USpan=0.62, EmissiveStrength=22.0, FramesPerSecond=30.0, base=0.10,
                  smoke=0.10),
    "brazier": dict(Width=62.0, Height=62.0, USpan=1.0, EmissiveStrength=26.0, FramesPerSecond=24.0, base=0.38,
                    smoke=0.20),
    "altar": dict(Width=105.0, Height=100.0, USpan=1.0, EmissiveStrength=30.0, FramesPerSecond=20.0, base=0.52,
                  smoke=0.24),
}


def import_fire_sheet(filename=FIRE_SHEET, name="T_FireSheet", srgb=True):
    t = unreal.AssetImportTask()
    t.set_editor_property("filename", filename)
    t.set_editor_property("destination_path", TEX_PKG)
    t.set_editor_property("destination_name", name)
    t.set_editor_property("automated", True)
    t.set_editor_property("replace_existing", True)
    t.set_editor_property("save", True)
    tools.import_asset_tasks([t])
    tex = unreal.load_asset(TEX_PKG + "/" + name)
    tex.set_editor_property("srgb", srgb)
    tex.set_editor_property("address_x", unreal.TextureAddress.TA_CLAMP)
    tex.set_editor_property("address_y", unreal.TextureAddress.TA_CLAMP)
    assets.save_loaded_asset(tex)
    return tex


# The cards are turned and sized in the material, which uses only the pivot and the UVs, so the mesh's
# own orientation does not show. Lying flat, the plane's bounds were a slab without height at the top
# of the torch; seen edge-on from across the rotunda the occlusion test took it for hidden in some
# frames and the small fires went out and came back (user, 2026-11-23). Tilted, the bounds are a box.
CARD_TILT = unreal.Rotator(45.0, 45.0, 0.0)   # roll, pitch, yaw


def add_flames(actors):
    """One camera-facing flame card per fire, at the base of the flame."""
    plane = unreal.load_asset("/Engine/BasicShapes/Plane")
    for slot in MANIFEST.get("light_slots", []):
        spec = FLAMES[slot["kind"]]
        x, y, z = slot["position"]
        a = actors.spawn_actor_from_class(unreal.StaticMeshActor, ue_loc((x, y, z - spec["base"])), CARD_TILT)
        a.set_actor_label("Flame_" + slot["name"])
        c = a.static_mesh_component
        c.set_static_mesh(plane)
        c.set_material(0, unreal.load_asset(MAT_DIR + "/MI_Flame_" + slot["kind"]))
        c.set_editor_property("cast_shadow", False)
        c.set_editor_property("bounds_scale", 6.0)   # the card is moved and sized in the material
        c.set_editor_property("affect_dynamic_indirect_lighting", False)
        c.set_editor_property("visible_in_ray_tracing", False)
        k = max(spec["Width"], spec["Height"]) / 100.0
        a.set_actor_scale3d(unreal.Vector(k, k, k))
        smoke_mi = MAT_DIR + "/MI_Smoke_" + slot["kind"]
        if assets.does_asset_exist(smoke_mi):
            # same pivot as the flame, so both play the same frame of the simulation
            b = actors.spawn_actor_from_class(unreal.StaticMeshActor, ue_loc((x, y, z - spec["base"])), CARD_TILT)
            b.set_actor_label("Smoke_" + slot["name"])
            sc = b.static_mesh_component
            sc.set_static_mesh(plane)
            sc.set_material(0, unreal.load_asset(smoke_mi))
            sc.set_editor_property("cast_shadow", False)
            sc.set_editor_property("bounds_scale", 10.0)
            sc.set_editor_property("affect_dynamic_indirect_lighting", False)
            sc.set_editor_property("visible_in_ray_tracing", False)
            b.set_actor_scale3d(unreal.Vector(k, k, k))
    log("flames %d" % len(MANIFEST.get("light_slots", [])))


def build_special_materials():
    """Flame, painted surfaces, statues and the fire flicker light function."""
    out = {"M_Flame": pm.build_flame(MAT_DIR + "/M_Flame", import_fire_sheet())}
    # flame size per kind of fire (cm); stands use the middle of the sheet for a narrower flame
    for kind, spec in FLAMES.items():
        path = MAT_DIR + "/MI_Flame_" + kind
        mi = unreal.load_asset(path) if assets.does_asset_exist(path) else tools.create_asset(
            "MI_Flame_" + kind, MAT_DIR, unreal.MaterialInstanceConstant, unreal.MaterialInstanceConstantFactoryNew())
        mel.set_material_instance_parent(mi, out["M_Flame"])
        for k in ("Width", "Height", "USpan", "EmissiveStrength", "FramesPerSecond"):
            mel.set_material_instance_scalar_parameter_value(mi, k, spec[k])
        assets.save_loaded_asset(mi)
    # Smoke plumes from the same simulation. The smoke sheet frames the whole simulation domain, the
    # flame sheet a 0.56 crop of it, so a smoke card 1/0.56 the flame's size lines up with the flame.
    if os.path.exists(SMOKE_SHEET):
        smoke = pm.build_flame(MAT_DIR + "/M_Smoke", import_fire_sheet(SMOKE_SHEET, "T_SmokeSheet", False), smoke=True)
        for kind, spec in FLAMES.items():
            path = MAT_DIR + "/MI_Smoke_" + kind
            mi = unreal.load_asset(path) if assets.does_asset_exist(path) else tools.create_asset(
                "MI_Smoke_" + kind, MAT_DIR, unreal.MaterialInstanceConstant, unreal.MaterialInstanceConstantFactoryNew())
            mel.set_material_instance_parent(mi, smoke)
            mel.set_material_instance_scalar_parameter_value(mi, "Width", spec["Width"] / 0.56)
            mel.set_material_instance_scalar_parameter_value(mi, "Height", spec["Height"] / 0.56)
            mel.set_material_instance_scalar_parameter_value(mi, "USpan", spec["USpan"])
            mel.set_material_instance_scalar_parameter_value(mi, "FramesPerSecond", spec["FramesPerSecond"])
            mel.set_material_instance_scalar_parameter_value(mi, "Opacity", spec["smoke"])
            assets.save_loaded_asset(mi)
    painted_master = pm.build_painted_master(MAT_DIR + "/M_PaintedMaster")
    path = MAT_DIR + "/MI_Painted"
    mi = unreal.load_asset(path) if assets.does_asset_exist(path) else tools.create_asset(
        "MI_Painted", MAT_DIR, unreal.MaterialInstanceConstant, unreal.MaterialInstanceConstantFactoryNew())
    mel.set_material_instance_parent(mi, painted_master)
    # placeholder until the painted textures are made: Pompeian red ground
    mel.set_material_instance_vector_parameter_value(mi, "Tint", unreal.LinearColor(0.45, 0.07, 0.04, 1.0))
    assets.save_loaded_asset(mi)
    out["M_Painted"] = mi
    out["M_Statue"] = pm.build_statue_master(MAT_DIR + "/M_Statue",
                                             unreal.load_asset(TEX_PKG + "/T_Marble021_Color"))  # 4K set since revision 2
    # bowl fires 85-107 % (was 68-112 %): on the stone around the door the swing read as a flicker
    # stone would not show (user, 2026-11-23); the flames themselves carry the liveliness
    out["M_FireFlicker"] = pm.build_flicker(MAT_DIR + "/M_FireFlicker", 0.85, 1.07)
    out["M_LampFlicker"] = pm.build_flicker(MAT_DIR + "/M_LampFlicker", 0.88, 1.06)
    out["M_Soot"] = pm.build_soot(MAT_DIR + "/M_Soot")
    out["M_DomeSky"] = build_dome_sky()
    out["M_InvaderTile"] = pm.build_invader_tile(MAT_DIR + "/M_InvaderTile")
    return out


def build_dome_sky():
    """The inner dome's paint: a blue night sky behind the gilded stars (user, 2026-11-24)."""
    return pm.build_dome_sky(MAT_DIR + "/M_DomeSky", unreal.load_asset(TEX_PKG + "/T_Plaster001_Color"),
                             unreal.load_asset(TEX_PKG + "/T_Plaster001_NormalDX"))


def load_materials():
    out = {n: unreal.load_asset(MAT_DIR + "/MI_" + n[2:]) for n in MANIFEST["materials"] if n not in SPECIAL}
    for n in list(out):
        for suffix in ("_Floor", "_Wall", "_Polished", "_Aged", "_Matte", "_WallMatte", "_Ext", "_ExtWall", "_Satin",
                       "_Frieze", "_Roof", "_Paving"):
            if assets.does_asset_exist(MAT_DIR + "/MI_" + n[2:] + suffix):
                out[n + suffix] = unreal.load_asset(MAT_DIR + "/MI_" + n[2:] + suffix)
    out["M_Flame"] = unreal.load_asset(MAT_DIR + "/M_Flame")
    out["M_Painted"] = unreal.load_asset(MAT_DIR + "/MI_Painted")
    out["M_Statue"] = unreal.load_asset(MAT_DIR + "/M_Statue")
    out["M_FireFlicker"] = unreal.load_asset(MAT_DIR + "/M_FireFlicker")
    for n in ("M_DomeSky", "M_InvaderTile"):
        if assets.does_asset_exist(MAT_DIR + "/" + n):
            out[n] = unreal.load_asset(MAT_DIR + "/" + n)
    return out


# --------------------------------------------------------------------------
# Import
# --------------------------------------------------------------------------

def import_fbx(files, dest, legacy=False):
    """legacy=True imports through the classic FBX importer instead of Interchange: Interchange
    ignores FbxImportUI, including the vertex colour option the painted statues need."""
    if legacy:
        unreal.SystemLibrary.execute_console_command(None, "Interchange.FeatureFlags.Import.FBX 0")
    tasks = []
    for f in files:
        opts = unreal.FbxImportUI()
        opts.set_editor_property("import_mesh", True)
        opts.set_editor_property("import_materials", False)
        opts.set_editor_property("import_textures", False)
        opts.set_editor_property("import_as_skeletal", False)
        opts.set_editor_property("mesh_type_to_import", unreal.FBXImportType.FBXIT_STATIC_MESH)
        sm = opts.get_editor_property("static_mesh_import_data")
        sm.set_editor_property("combine_meshes", True)
        sm.set_editor_property("auto_generate_collision", False)
        sm.set_editor_property("generate_lightmap_u_vs", False)
        sm.set_editor_property("build_nanite", True)
        sm.set_editor_property("convert_scene", True)
        sm.set_editor_property("convert_scene_unit", True)
        sm.set_editor_property("vertex_color_import_option", unreal.VertexColorImportOption.REPLACE)
        t = unreal.AssetImportTask()
        t.set_editor_property("filename", f)
        t.set_editor_property("destination_path", dest)
        t.set_editor_property("automated", True)
        t.set_editor_property("replace_existing", True)
        t.set_editor_property("save", True)
        t.set_editor_property("options", opts)
        tasks.append(t)
    tools.import_asset_tasks(tasks)
    meshes = {}
    for t in tasks:
        for p in t.get_editor_property("imported_object_paths") or []:
            obj = unreal.load_asset(p)
            if isinstance(obj, unreal.StaticMesh):
                meshes[os.path.splitext(os.path.basename(t.get_editor_property("filename")))[0]] = obj
    if legacy:
        unreal.SystemLibrary.execute_console_command(None, "Interchange.FeatureFlags.Import.FBX 1")
    log("imported %d of %d into %s" % (len(meshes), len(files), dest))
    return meshes


def enable_nanite(mesh, material=None, nanite=True):
    settings = mesh.get_editor_property("nanite_settings")
    settings.set_editor_property("enabled", nanite)
    mesh.set_editor_property("nanite_settings", settings)
    if material is not None:
        for i in range(mesh.get_num_sections(0)):
            mesh.set_material(i, material)
    assets.save_loaded_asset(mesh)


# --------------------------------------------------------------------------
# Level
# --------------------------------------------------------------------------

# Lighting channels: the sun (channel 0) lights only the exterior; interior surfaces are on channel 1,
# lit by the oculus spot light and the fires. The sun leaked through the building shells onto
# interior walls (they went white in close-ups); with channels it cannot reach them at all.
EXTERIOR_PREFIXES = ("Ground", "Forecourt_", "Portico_", "Orn_Portico_", "Bronze_Roof", "Bronze_Inscription", "Drum_Outer",
                     "Dome_Outer", "Capital_Portico_", "Capital_Forecourt_", "Statue_augustus_portico",
                     "Statue_agrippa_portico")
INTERIOR_CHANNELS = unreal.LightingChannels(channel0=False, channel1=True, channel2=False)
ALL_CHANNELS = unreal.LightingChannels(channel0=True, channel1=True, channel2=False)


def spawn_mesh(actors, mesh, label, location=None, yaw=0.0):
    # spawn_actor_from_object returns None in commandlet mode, so spawn a plain actor and set the mesh
    loc = location or unreal.Vector(0.0, 0.0, 0.0)
    actor = actors.spawn_actor_from_class(unreal.StaticMeshActor, loc, unreal.Rotator(0.0, 0.0, yaw))
    if actor is None:
        raise RuntimeError("could not spawn actor for " + label)
    comp = actor.get_component_by_class(unreal.StaticMeshComponent)
    comp.set_editor_property("mobility", unreal.ComponentMobility.STATIC)
    comp.set_static_mesh(mesh)
    if not label.startswith(EXTERIOR_PREFIXES):
        comp.set_editor_property("lighting_channels", INTERIOR_CHANNELS)
    if label.startswith(BLOCKERS):
        hide_keep_collision(comp)
    actor.set_actor_label(label)
    return actor


# Invisible walls in the city's doors and windows: one can look into the dark rooms behind but not
# walk or fly in (user, 2026-11-25). Hidden, casting no shadow, still colliding.
BLOCKERS = ("Forecourt_Blockers",)


def hide_keep_collision(comp):
    comp.set_editor_property("visible", False)
    comp.set_editor_property("hidden_in_game", True)
    comp.set_editor_property("cast_shadow", False)
    comp.set_editor_property("affect_distance_field_lighting", False)


def load_meshes(pkg, names):
    out = {}
    for n in names:
        path = "%s/%s" % (pkg, n)
        if assets.does_asset_exist(path):
            out[n] = unreal.load_asset(path)
    return out


# The walk-through app (F2) needs something to walk on: the architecture was imported without collision
# (the films never needed it). Every mesh collides per triangle, except the flame cards.
NO_COLLISION = ("Flames", "Invader_")


def set_collision(meshes):
    n = 0
    for name, mesh in meshes.items():
        if name.startswith(NO_COLLISION):
            continue
        body = mesh.get_editor_property("body_setup")
        if body is None:
            log("no body setup on %s; collision skipped" % name)
            continue
        body.set_editor_property("collision_trace_flag", unreal.CollisionTraceFlag.CTF_USE_COMPLEX_AS_SIMPLE)
        # Both sides of every face collide. The walls are shells with hollows between their faces, and
        # one-sided faces stopped the visitor only from the front: pushed a little past a face at a
        # seam (behind a statue, in a corner), one was inside the hollow and could walk through every
        # wall from behind (user, 2026-11-24: "possible to slide between the walls"; found by
        # -PantheonLeakTest, which floods those hollows with the visitor's capsule)
        body.set_editor_property("double_sided_geometry", True)
        mesh.set_editor_property("body_setup", body)
        assets.save_loaded_asset(mesh)
        n += 1
    log("collision (complex as simple) on %d meshes" % n)


# Clouds: the engine's own volumetric cloud material (user, 2026-11-25: "sky needs clouds - don't
# generate them, use assets"), lit by the sun and the sky atmosphere, seen through the oculus too
CLOUD_MATERIAL = "/Engine/EngineSky/VolumetricClouds/m_SimpleVolumetricCloud_Inst"


def add_clouds(actors, sun=None):
    cloud = actors.spawn_actor_from_class(unreal.VolumetricCloud, unreal.Vector(0, 0, 0))
    cloud.set_actor_label("Clouds")
    comp = cloud.get_component_by_class(unreal.VolumetricCloudComponent)
    mat = unreal.load_asset(CLOUD_MATERIAL)
    if mat is not None:
        comp.set_editor_property("material", mat)
    else:
        log("cloud material %s not found" % CLOUD_MATERIAL)
    for prop, value in (("layer_bottom_altitude", 2.0), ("layer_height", 8.0)):
        try:
            comp.set_editor_property(prop, value)
        except Exception as exc:  # noqa: BLE001
            log("cloud property %s skipped: %s" % (prop, exc))
    if sun is not None:
        lc = sun.get_component_by_class(unreal.DirectionalLightComponent)
        # soft moving patches of cloud shadow on the city and the forecourt
        for prop, value in (("cast_cloud_shadows", True), ("cloud_shadow_strength", 0.6),
                            ("cast_shadows_on_clouds", True)):
            try:
                lc.set_editor_property(prop, value)
            except Exception as exc:  # noqa: BLE001
                log("sun property %s skipped: %s" % (prop, exc))
    return cloud


def add_lighting(actors):
    # Sun aimed so the shaft through the oculus falls on Jupiter in the apse. Artistic licence:
    # the apse faces south, so in Rome real sunlight through the oculus never reaches it.
    # Oculus centre (0, 0, 43.0) to Jupiter's chest (0, -22.5, 6.5) in Blender coordinates is
    # 58.4 degrees down; travelling towards Blender -Y is UE +Y, i.e. yaw +90.
    sun = actors.spawn_actor_from_class(unreal.DirectionalLight, unreal.Vector(0, 0, 8000),
                                        unreal.Rotator(0.0, -58.4, 90.0))
    sun.set_actor_label("Sun")
    lc = sun.get_component_by_class(unreal.DirectionalLightComponent)
    # lux scaled down; exposure is manual. 10 blew out the sunlit portico paving and column bases
    # (user, after draft 10); the sun only lights the exterior channel, so the interior and the
    # oculus shaft (its own spot light) are unchanged
    # 3.0 (user, 2026-11-23: "light outside still too harsh"): the walk-through app's outside exposure
    # rises from 1.5 to 2.0 EV to match, so sunlit stone stays about as bright while the shade, lit
    # by the sky, opens up by half a stop
    lc.set_editor_property("intensity", 3.0)   # 6 still left the sunlit paving near white
    # a slightly hazy summer sun: softer shadow edges than the true 0.53 degree disc
    lc.set_editor_property("light_source_angle", 2.0)
    lc.set_editor_property("atmosphere_sun_light", True)
    # the sun lights surfaces only; its fog scattering leaked through the thin dome shells as hard
    # camera-dependent edges, so the visible shaft comes from the spot light below
    lc.set_editor_property("volumetric_scattering_intensity", 0.0)
    lc.set_editor_property("cast_volumetric_shadow", True)
    lc.set_editor_property("mobility", unreal.ComponentMobility.MOVABLE)

    # Oculus shaft: a narrow spot light 100 m up the sun's line (cone 1.7 degrees, about 4.2 m wide at
    # Jupiter, so it stays off the apse columns). It
    # lights the fog and, since the sun is restricted to the exterior channel, also the surfaces it
    # falls on inside (Jupiter, the floor), at about the sun's 10 lux (200000 cd at ~143 m). Blender: oculus centre (0, 0, 43.0), sun
    # travelling along (0, -0.524, -0.852) -> spot at (0, 52.4, 128.2); UE flips Y.
    shaft = actors.spawn_actor_from_class(unreal.SpotLight, unreal.Vector(0.0, -5240.0, 12820.0),
                                          unreal.Rotator(0.0, -58.4, 90.0))
    shaft.set_actor_label("OculusShaft")
    sc_ = shaft.get_component_by_class(unreal.SpotLightComponent)
    for prop, value in (("mobility", unreal.ComponentMobility.MOVABLE),
                        ("intensity_units", unreal.LightUnits.CANDELAS), ("intensity", 200000.0),
                        ("attenuation_radius", 25000.0), ("outer_cone_angle", 1.7), ("inner_cone_angle", 1.4),
                        ("source_radius", 0.0), ("cast_shadows", True), ("cast_volumetric_shadow", True),
                        ("volumetric_scattering_intensity", 14.0), ("diffuse_scale", 1.0), ("specular_scale", 1.0),
                        ("indirect_lighting_intensity", 1.0), ("use_temperature", True), ("temperature", 5600.0),
                        ("lighting_channels", ALL_CHANNELS)):
        try:
            sc_.set_editor_property(prop, value)
        except Exception as exc:
            log("oculus shaft property %s skipped: %s" % (prop, exc))

    actors.spawn_actor_from_class(unreal.SkyAtmosphere, unreal.Vector(0, 0, 0)).set_actor_label("SkyAtmosphere")
    add_clouds(actors, sun)

    sky = actors.spawn_actor_from_class(unreal.SkyLight, unreal.Vector(0, 0, 6000))
    sky.set_actor_label("SkyLight")
    sc = sky.get_component_by_class(unreal.SkyLightComponent)
    sc.set_editor_property("real_time_capture", True)
    sc.set_editor_property("mobility", unreal.ComponentMobility.MOVABLE)
    sc.set_editor_property("intensity", 0.6)  # less sky through the oculus on the facing walls

    fog = actors.spawn_actor_from_class(unreal.ExponentialHeightFog, unreal.Vector(0, 0, 0))
    fog.set_actor_label("HeightFog")
    fc = fog.get_component_by_class(unreal.ExponentialHeightFogComponent)
    fc.set_editor_property("fog_density", 0.016)
    fc.set_editor_property("fog_height_falloff", 0.02)
    fc.set_editor_property("enable_volumetric_fog", True)
    fc.set_editor_property("volumetric_fog_scattering_distribution", 0.8)
    fc.set_editor_property("volumetric_fog_extinction_scale", 1.0)
    fc.set_editor_property("volumetric_fog_albedo", unreal.Color(r=240, g=235, b=225, a=255))

    ppv = actors.spawn_actor_from_class(unreal.PostProcessVolume, unreal.Vector(0, 0, 0))
    ppv.set_actor_label("PostProcess")
    ppv.set_editor_property("unbound", True)
    s = ppv.get_editor_property("settings")
    for prop, value in (
        ("override_auto_exposure_method", True), ("auto_exposure_method", unreal.AutoExposureMethod.AEM_MANUAL),
        ("override_auto_exposure_apply_physical_camera_exposure", True),
        ("auto_exposure_apply_physical_camera_exposure", False),
        ("override_auto_exposure_bias", True), ("auto_exposure_bias", 0.0),
        ("override_bloom_intensity", True), ("bloom_intensity", 0.2),
        ("override_dynamic_global_illumination_method", True),
        ("dynamic_global_illumination_method", unreal.DynamicGlobalIlluminationMethod.LUMEN),
        ("override_reflection_method", True), ("reflection_method", unreal.ReflectionMethod.LUMEN),
        ("override_lumen_final_gather_quality", True), ("lumen_final_gather_quality", 4.0),
        ("override_lumen_scene_lighting_quality", True), ("lumen_scene_lighting_quality", 2.0),
        ("override_lumen_reflection_quality", True), ("lumen_reflection_quality", 2.0),
        # Bounce boost back to 1.0: at 2.0 pale walls (albedo ~0.87) returned more light than they
        # received and recesses ran away to white; the patches it once hid came from screen traces
        ("override_lumen_diffuse_color_boost", True), ("lumen_diffuse_color_boost", 1.0),
        ("override_lumen_skylight_leaking", True), ("lumen_skylight_leaking", 0.0),
        # Local exposure: the oculus-facing exedra walls were far brighter than the columns, altars and
        # paintings beside them; compress highlights and lift shadows locally, as the eye does
        ("override_local_exposure_highlight_contrast_scale", True), ("local_exposure_highlight_contrast_scale", 0.55),
        ("override_local_exposure_shadow_contrast_scale", True), ("local_exposure_shadow_contrast_scale", 0.7),
        # warmer white balance: the sky-lit marble otherwise reads lilac
        ("override_white_temp", True), ("white_temp", 7000.0),
    ):
        try:
            s.set_editor_property(prop, value)
        except Exception as exc:  # property names drift between engine versions
            log("post-process property %s skipped: %s" % (prop, exc))
    ppv.set_editor_property("settings", s)


# candela per light kind; the sun is scaled down to 10 lux and exposure is manual, so these
# are tuned by eye against the stills rather than physical lamp output
FIRE = {
    "stand": dict(intensity=0.05, radius=1400.0, source=8.0),
    "brazier": dict(intensity=1.5, radius=2000.0, source=20.0),
    "altar": dict(intensity=3.0, radius=2600.0, source=25.0),
}


# --------------------------------------------------------------------------
# Ageing (the user allowed some: soot, streaks, broken marble)
# --------------------------------------------------------------------------
_DECALS = "/Game/Fab/Megascans/Decals/"
LEAK_IDS = ("tculfbnc", "skitfhqc", "tdcafitc", "skivejqc", "tcumebvc", "skphbg3c", "tculfhnc")
LEAK_TEX = [_DECALS + "Leakage_%s/High/%s_tier_1/Textures/T_%s_4K_B-O" % (k, k, k) for k in LEAK_IDS]


def leak_materials():
    """One instance of M_Leak (pantheon_materials.build_leak) per Megascans streak texture."""
    textures = [unreal.load_asset(p) for p in LEAK_TEX if assets.does_asset_exist(p)]
    if not textures:
        return []
    master = pm.build_leak(MAT_DIR + "/M_Leak", textures[0])
    out = []
    for tex in textures:
        name = "MI_Leak_" + tex.get_name().split("_")[1]
        path = MAT_DIR + "/" + name
        mi = unreal.load_asset(path) if assets.does_asset_exist(path) else tools.create_asset(
            name, MAT_DIR, unreal.MaterialInstanceConstant, unreal.MaterialInstanceConstantFactoryNew())
        mel.set_material_instance_parent(mi, master)
        mel.set_material_instance_texture_parameter_value(mi, "Streaks", tex)
        assets.save_loaded_asset(mi)
        out.append(mi)
    return out
_SCANS = "/Game/Fab/Megascans/3D/"
# scanned Roman marble pieces as old votive altars: mesh, azimuth (degrees), radius (m), scale
PROPS = [
    (_SCANS + "Roman_Marble_Plinth_tg0pfjxda/High/tg0pfjxda_tier_1/StaticMeshes/tg0pfjxda_tier_1", 78.75, 19.4, 1.3),
    (_SCANS + "Roman_Marble_Plinth_tg0pfjxda/High/tg0pfjxda_tier_1/StaticMeshes/tg0pfjxda_tier_1", 101.25, 19.4, 1.3),
    (_SCANS + "Roman_Marble_Ornate_Plinth_tfuwdeafa/High/tfuwdeafa_tier_1/StaticMeshes/tfuwdeafa_tier_1", 258.75, 19.4, 1.3),
    (_SCANS + "Roman_Marble_Ornate_Plinth_tfxpcbcfa/Medium/tfxpcbcfa_tier_2/StaticMeshes/tfxpcbcfa_tier_2", 281.25, 19.4, 1.3),
]


# Water streaks under the dome's springing: halfway between the attic's openings (windows and niches
# every 22.5 degrees), never over the entrance or apse arch. At 11.25 + 30k most of them straddled an
# opening, and a decal projected into a niche's reveal ran sideways across it (user, 2026-11-24:
# "horizontal water stains, where we said they should only be vertical").
ATTIC_LEAK_AZ = (11.25, 33.75, 56.25, 123.75, 146.25, 168.75, 191.25, 213.75, 236.25, 303.75, 326.25, 348.75)


def add_decal(actors, label, material, position, az_deg, size_cm):
    """Decal projected radially outward onto the drum wall. size_cm: (depth, half width, half height).
    The decal's texture runs along its local Y, so it is rolled 90 degrees to hang down the wall."""
    a = actors.spawn_actor_from_class(unreal.DecalActor, ue_loc(position), unreal.Rotator(90.0, 0.0, -az_deg))
    size_cm = (size_cm[0], size_cm[2], size_cm[1])
    if a is None:
        return None
    a.set_actor_label(label)
    c = a.get_component_by_class(unreal.DecalComponent)
    c.set_decal_material(material)
    c.set_editor_property("decal_size", unreal.Vector(*size_cm))
    return a


def add_ageing(actors):
    radius = 21.72
    leaks = leak_materials()
    n = 0
    if leaks:
        # water streaks under the dome springing (attic zone) and under the first cornice
        for k, az in enumerate(ATTIC_LEAK_AZ):
            pos = (radius * math.cos(math.radians(az)), radius * math.sin(math.radians(az)), 18.6)
            n += add_decal(actors, "Leak_attic_%02d" % k, leaks[k % len(leaks)], pos, az, (120.0, 110.0, 220.0)) is not None
        for k in range(16):
            az = 11.25 + 22.5 * k
            pos = (radius * math.cos(math.radians(az)), radius * math.sin(math.radians(az)), 10.6)
            n += add_decal(actors, "Leak_drum_%02d" % k, leaks[(k + 3) % len(leaks)], pos, az, (120.0, 60.0, 130.0)) is not None
    soot = unreal.load_asset(MAT_DIR + "/M_Soot")
    m = 0
    if soot is not None:
        for slot in MANIFEST.get("light_slots", []):
            if slot["kind"] != "stand" or slot["name"].startswith("apse"):
                continue
            x, y, z = slot["position"]
            az = math.degrees(math.atan2(y, x))
            r = math.hypot(x, y) + 1.2
            pos = (r * math.cos(math.radians(az)), r * math.sin(math.radians(az)), z + 1.5)
            m += add_decal(actors, "Soot_" + slot["name"], soot, pos, az, (260.0, 95.0, 170.0)) is not None
    p = 0
    for path, az, r, scale in PROPS:
        if not assets.does_asset_exist(path):
            continue
        pos = (r * math.cos(math.radians(az)), r * math.sin(math.radians(az)), 0.0)
        a = spawn_mesh(actors, unreal.load_asset(path), "Prop_altar_%05.1f" % az, ue_loc(pos), -az + 180.0)
        a.set_actor_scale3d(unreal.Vector(scale, scale, scale))
        p += 1
    log("ageing: %d leak decals, %d soot decals, %d marble pieces" % (n, m, p))


# curved drum walls that get slab joints; column shafts that get a polished finish
JOINTED = ("Drum_Lower", "Attic_Wall", "Attic_Dado")
POLISHED = ("Column_", "AedCol_")
# the transom grille too: polished (0.35) its thin bars mirrored the bright portico and shimmered
AGED = ("Bronze_Doors", "Bronze_Grille")
# exterior stone: rough, weathered, with tooled relief (columns, walls, paving)
WEATHERED = ("Portico_", "Orn_Portico_", "Forecourt_", "Drum_Outer", "Dome_Outer", "Bronze_Inscription", "Bronze_Roof")


def add_fire_lights(actors):
    flickers = {"stand": unreal.load_asset(MAT_DIR + "/M_LampFlicker")}
    default_flicker = unreal.load_asset(MAT_DIR + "/M_FireFlicker")
    for slot in MANIFEST.get("light_slots", []):
        spec = FIRE[slot["kind"]]
        light = actors.spawn_actor_from_class(unreal.PointLight, ue_loc(slot["position"]))
        light.set_actor_label("Fire_" + slot["name"])
        c = light.get_component_by_class(unreal.PointLightComponent)
        c.set_editor_property("mobility", unreal.ComponentMobility.MOVABLE)
        c.set_editor_property("intensity_units", unreal.LightUnits.CANDELAS)
        c.set_editor_property("intensity", spec["intensity"])
        c.set_editor_property("use_temperature", True)
        c.set_editor_property("temperature", 1850.0)
        c.set_editor_property("attenuation_radius", spec["radius"])
        c.set_editor_property("source_radius", spec["source"])
        c.set_editor_property("cast_shadows", True)
        c.set_editor_property("volumetric_scattering_intensity", 1.5)
        flicker = flickers.get(slot["kind"]) or default_flicker
        if flicker is not None:
            c.set_editor_property("light_function_material", flicker)
        c.set_editor_property("lighting_channels", ALL_CHANNELS)
    log("fire lights %d" % len(MANIFEST.get("light_slots", [])))


def main():
    level_editor = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)

    # PANTHEON_STEPS=level skips material creation and import and only rebuilds the level
    steps = os.environ.get("PANTHEON_STEPS", "textures,materials,import,collision,level").split(",")
    keys = sorted({s["statue"] for s in MANIFEST["statue_slots"]})
    names = [o["name"] for o in MANIFEST["objects"]]

    if "textures" in steps:
        import_textures()
    if "materials" in steps:
        mis = build_instances(build_master_material())
    # PANTHEON_ONLY=Name1,Name2 with PANTHEON_STEPS=import re-imports just those architecture meshes in
    # place (no statues, no level rebuild): the level's actors and both camera sequences stay as they are
    only = [n for n in os.environ.get("PANTHEON_ONLY", "").split(",") if n]
    if "import" in steps:
        mis = load_materials()
        objects = [o for o in MANIFEST["objects"] if not only or o["name"] in only]
        arch_files = [os.path.join(ARCH_DIR, o["file"]) for o in objects]
        arch = import_fbx(arch_files, ARCH_PKG)
        for o in objects:
            mesh = arch.get(o["name"])
            if mesh is not None:
                mat = mis.get(o["material"])
                if o["name"].startswith("Floor_"):
                    mat = mis.get(o["material"] + "_Floor", mat)
                elif o["name"] in EXT_WALLS:
                    mat = mis.get(o["material"] + "_ExtWall", mat)
                elif o["name"].startswith(WEATHERED):
                    mat = mis.get(o["material"] + "_Ext", mat)
                elif o["name"].startswith("Bay_"):
                    # the entrance and apse vaults: matte. Honed (0.45) they mirrored the bright
                    # doorway and the sunlit Jupiter, and Lumen's reflection rays made that shimmer
                    # (user, 2026-11-23: "flicker that the actual stone would not show")
                    mat = mis.get(o["material"] + "_Matte", mat)
                elif o["name"].startswith(("Attic_Wall", "Attic_Dado")):
                    mat = mis.get(o["material"] + "_WallMatte", mat)
                elif o["name"].startswith("Attic_"):
                    mat = mis.get(o["material"] + "_Matte", mat)
                elif o["name"].startswith(JOINTED):
                    mat = mis.get(o["material"] + "_Wall", mat)
                elif o["name"].startswith(POLISHED):
                    mat = mis.get(o["material"] + "_Polished", mat)
                elif o["name"].startswith(AGED):
                    mat = mis.get(o["material"] + "_Aged", mat)
                if o["name"] == "Entablature_Frieze":
                    mat = mis.get("M_Porphyry_Frieze", mat)
                if o["name"] == "Gilded_Rosettes":
                    mat = mis.get("M_Gilded_Satin", mat)
                if o["name"] == "Dome_Inner":
                    mat = mis.get("M_DomeSky", mat)
                if o["name"].startswith(("Dome_Outer", "Portico_Eagle")):
                    mat = mis.get("M_Gilded_Roof", mat)
                if o["name"] == "Forecourt_Paving":
                    mat = mis.get("M_Travertine_Paving", mat)
                if o["material"] == "M_Painted":
                    mat = painted_material(o["name"]) or mat
                # No Nanite on the architecture: hardware ray tracing traces a simplified proxy of Nanite
                # meshes, whose gaps let reflection rays escape to the bright sky (grazing walls went
                # white). The building is only ~270k triangles. Flames are translucent anyway.
                enable_nanite(mesh, mat, nanite=False)
        # a re-import resets collision to automatic hulls (a blocked doorway, walls to slip through):
        # every import sets per-triangle collision again
        set_collision({o["name"]: arch[o["name"]] for o in objects if o["name"] in arch})
        if only:
            log("re-imported %s" % ", ".join(o["name"] for o in objects))
            return
        # painted statues (vertex colour) when blender/paint_statues.py has made them
        statue_files = []
        for k in keys:
            for d in (PAINTED_DIR, STATUE_DIR):
                f = os.path.join(d, k + ".fbx")
                if os.path.exists(f):
                    statue_files.append(f)
                    break
        # Interchange keeps the vertex colours (its default pipeline is set to Replace); the classic FBX
        # importer brought the statues in at the wrong scale. has_vertex_colors() reports False in a
        # commandlet while meshes still build, so it is not a usable check here.
        statues = import_fbx(statue_files, STATUE_PKG)
        for mesh in statues.values():
            enable_nanite(mesh, mis.get("M_Statue"))
        if os.path.exists(CAPITAL_FBX):
            for mesh in import_fbx([CAPITAL_FBX], CAPITAL_PKG).values():
                enable_nanite(mesh, mis.get("M_WhiteMarble"))
    if "collision" in steps:
        set_collision(load_meshes(ARCH_PKG, names))
    if "level" not in steps:
        return
    arch = load_meshes(ARCH_PKG, names)
    statues = load_meshes(STATUE_PKG, keys)
    log("loaded %d architecture meshes, %d statues" % (len(arch), len(statues)))

    # a blank map saved over the old one; new_level refuses when the map already exists
    world = unreal.EditorLoadingAndSavingUtils.new_blank_map(False)

    for o in MANIFEST["objects"]:
        mesh = arch.get(o["name"])
        if mesh is not None and o["name"] != "Flames":   # the crossed cards are replaced by add_flames
            spawn_mesh(actors, mesh, o["name"])
    for s in MANIFEST["statue_slots"]:
        mesh = statues.get(s["statue"])
        if mesh is not None:
            st = spawn_mesh(actors, mesh, "Statue_" + s["statue"], ue_loc(s["position"]), -s["yaw"])
            # soot and streak decals are for the walls, not the statues standing in front of them
            st.get_component_by_class(unreal.StaticMeshComponent).set_editor_property("receives_decals", False)

    capital = unreal.load_asset(CAPITAL_PKG + "/capital") if assets.does_asset_exist(CAPITAL_PKG + "/capital") else None
    if capital is not None:
        # the processed capital is 1 m tall, its base ring centred on the origin (process_capital.py);
        # across, it is scaled so the ring meets the shaft top exactly (user, 2026-11-23: the shafts
        # stood off-centre and the ring overhung or fell short)
        info_path = os.path.join(os.path.dirname(CAPITAL_FBX), "capital.json")
        ring = json.load(open(info_path)).get("ring_diameter") if os.path.exists(info_path) else None
        for slot in MANIFEST.get("capital_slots", []):
            a = spawn_mesh(actors, capital, "Capital_" + slot["column"], ue_loc(slot["position"]), -slot["yaw"])
            k = slot["height"]
            kxy = slot["diameter"] / ring if ring else k
            a.set_actor_scale3d(unreal.Vector(kxy, kxy, k))
        log("capitals %d" % len(MANIFEST.get("capital_slots", [])))

    add_lighting(actors)
    add_fire_lights(actors)
    add_flames(actors)
    add_ageing(actors)
    if not unreal.EditorLoadingAndSavingUtils.save_map(world, MAP):
        raise RuntimeError("could not save " + MAP)

    # sanity check of the axis conversion: the doors must sit at UE y about -2800
    door = arch.get("Bronze_Doors")
    if door is not None:
        b = door.get_bounding_box()
        log("Bronze_Doors bounds min=%s max=%s" % (b.min, b.max))
    log("level saved: %d actors" % len(actors.get_all_level_actors()))


main()
