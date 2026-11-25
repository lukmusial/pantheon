"""Material graphs for the Pantheon level (imported by build_scene.py).

- build_stone_master: world-aligned (triplanar) colour, roughness and normal maps with large-scale
  colour variation; two-sided because the Blender shells have mixed winding.
- build_painted_master: UV-mapped painting (fresco or painted decoration) with matte roughness.
- build_flame: unlit additive camera-facing flame playing a flipbook rendered from a fluid simulation
  (blender/render_fire_flipbook.py).
- build_flicker: light function that makes the fire lights flicker.
- build_statue_master: marble with subsurface scattering; vertex colour paints over it
  (RGB = paint colour, A = coverage, written by blender/paint_statues.py).
"""

import unreal

assets = unreal.EditorAssetLibrary
mel = unreal.MaterialEditingLibrary
tools = unreal.AssetToolsHelpers.get_asset_tools()

WAT = "/Engine/Functions/Engine_MaterialFunctions01/Texturing/WorldAlignedTexture.WorldAlignedTexture"
WAN = "/Engine/Functions/Engine_MaterialFunctions01/Texturing/WorldAlignedNormal.WorldAlignedNormal"
# the Noise expression's input pin is not reachable from Python in 5.9; a panned noise texture instead
NOISE_TEX = "/Engine/Functions/Engine_MaterialFunctions02/ExampleContent/Textures/LowResBlurredNoise"


def noise_sample(g, uv_expr, x, y):
    """R channel of the engine's blurred noise texture at the given UVs (0..1)."""
    tex = g.expr(unreal.MaterialExpressionTextureSample, x, y, texture=unreal.load_asset(NOISE_TEX))
    g.connect(uv_expr, "", tex, "UVs")
    return g.mask(tex, x + 200, y, a_out="R")


def log(msg):
    unreal.log("PANTHEON " + msg)


class Graph:
    """Small helper around MaterialEditingLibrary."""

    def __init__(self, mat):
        self.mat = mat

    def expr(self, cls, x, y, **props):
        e = mel.create_material_expression(self.mat, cls, x, y)
        for k, v in props.items():
            e.set_editor_property(k, v)
        return e

    def connect(self, a, out, b, inp):
        if not mel.connect_material_expressions(a, out, b, inp):
            log("connect failed in %s: %s.%s -> %s.%s" % (self.mat.get_name(), a.get_name(), out, b.get_name(), inp))

    def out(self, e, prop, name=""):
        if not mel.connect_material_property(e, name, prop):
            log("output failed in %s: %s -> %s" % (self.mat.get_name(), e.get_name(), prop))

    def scalar(self, name, value, x, y):
        return self.expr(unreal.MaterialExpressionScalarParameter, x, y, parameter_name=name, default_value=value)

    def vector(self, name, rgb, x, y):
        return self.expr(unreal.MaterialExpressionVectorParameter, x, y, parameter_name=name,
                         default_value=unreal.LinearColor(rgb[0], rgb[1], rgb[2], 1.0))

    def const(self, value, x, y):
        return self.expr(unreal.MaterialExpressionConstant, x, y, r=value)

    def op(self, cls, a, b, x, y, a_out="", b_out=""):
        e = self.expr(cls, x, y)
        self.connect(a, a_out, e, "A")
        self.connect(b, b_out, e, "B")
        return e

    def mul(self, a, b, x, y, a_out="", b_out=""):
        return self.op(unreal.MaterialExpressionMultiply, a, b, x, y, a_out, b_out)

    def add(self, a, b, x, y, a_out="", b_out=""):
        return self.op(unreal.MaterialExpressionAdd, a, b, x, y, a_out, b_out)

    def append(self, a, b, x, y):
        return self.op(unreal.MaterialExpressionAppendVector, a, b, x, y)

    def lerp(self, a, b, alpha, x, y, a_out="", b_out="", alpha_out=""):
        e = self.expr(unreal.MaterialExpressionLinearInterpolate, x, y)
        self.connect(a, a_out, e, "A")
        self.connect(b, b_out, e, "B")
        self.connect(alpha, alpha_out, e, "Alpha")
        return e

    def unary(self, cls, a, x, y, a_out=""):
        e = self.expr(cls, x, y)
        self.connect(a, a_out, e, "")
        return e

    def mask(self, a, x, y, r=True, g=False, b=False, a_out=""):
        e = self.expr(unreal.MaterialExpressionComponentMask, x, y, r=r, g=g, b=b, a=False)
        self.connect(a, a_out, e, "")
        return e


def fresh_material(path):
    folder, name = path.rsplit("/", 1)
    if assets.does_asset_exist(path):
        mat = unreal.load_asset(path)
        mel.delete_all_material_expressions(mat)
    else:
        mat = tools.create_asset(name, folder, unreal.Material, unreal.MaterialFactoryNew())
    return mat


def finish(mat):
    mel.recompile_material(mat)
    assets.save_loaded_asset(mat)
    return mat


def world_tex(g, param, default, fn, x, y, size):
    tex = g.expr(unreal.MaterialExpressionTextureObjectParameter, x, y, parameter_name=param, texture=default)
    call = g.expr(unreal.MaterialExpressionMaterialFunctionCall, x + 350, y)
    call.set_material_function(fn)
    g.connect(tex, "", call, "TextureObject")
    g.connect(size, "", call, "TextureSize")
    return call


def relief_normal(g, ncall, strength, x, y):
    """The world normal for a world-aligned normal map (ncall: a WorldAlignedNormal call): the
    vertex normal tilted by the map's sideways part only, normalize(N + s * (W - (W.N) N)).

    Blending the map's output straight into the vertex normal (lerp) went wrong on every face that
    looks down -X or -Y: there the function's normal points the other way, so at strength 0.5 the
    two cancelled and the normal came out pointing up, and at 1.0 it pointed into the wall. Such
    faces were shaded as if they faced elsewhere and caught the light of fires behind them (user,
    2026-11-24: the door braziers glowed on the outside of the bronze door frame). Taking only the
    part across the vertex normal keeps the relief and can never turn a face round."""
    vn = g.expr(unreal.MaterialExpressionVertexNormalWS, x, y + 100)
    d = g.op(unreal.MaterialExpressionDotProduct, ncall, vn, x + 200, y, a_out="XYZ Texture")
    across = g.op(unreal.MaterialExpressionSubtract, ncall, g.mul(d, vn, x + 350, y + 60), x + 500, y,
                  a_out="XYZ Texture")
    tilted = g.add(vn, g.mul(across, strength, x + 650, y), x + 800, y + 60)
    return g.unary(unreal.MaterialExpressionNormalize, tilted, x + 950, y + 60)


def build_stone_master(path):
    mat = fresh_material(path)
    g = Graph(mat)
    white = unreal.load_asset("/Engine/EngineResources/WhiteSquareTexture")
    flat = unreal.load_asset("/Engine/EngineMaterials/DefaultNormal")
    wat_fn, wan_fn = unreal.load_asset(WAT), unreal.load_asset(WAN)
    tile = g.scalar("TileSize", 200.0, -1700, 0)

    albedo = world_tex(g, "Albedo", white, wat_fn, -1600, -400, tile)
    # large-scale variation: the same texture at 7x the tile size, as a brightness modulation
    big = g.mul(tile, g.const(7.0, -1700, -200), -1600, -200)
    macro = world_tex(g, "Albedo", white, wat_fn, -1600, -150, big)
    macro_l = g.mask(macro, -1000, -150, a_out="XYZ Texture")
    macro_m = g.lerp(g.const(0.86, -900, -220), g.const(1.12, -900, -190), macro_l, -800, -170)
    tint = g.vector("BaseColor", (1.0, 1.0, 1.0), -1000, -550)
    bright = g.scalar("Brightness", 1.0, -1000, -470)
    c1 = g.mul(albedo, tint, -800, -450, a_out="XYZ Texture")
    c2 = g.mul(c1, bright, -650, -430)
    c3 = g.mul(c2, macro_m, -520, -400)
    tinted = g.unary(unreal.MaterialExpressionSaturate, c3, -380, -400)

    # Stone recolouring: the texture's own light/dark pattern drives a ground colour and a vein (or
    # speck) colour, so each stone gets its real colours (e.g. pavonazzetto: white with violet veins)
    lum = g.expr(unreal.MaterialExpressionDotProduct, -760, -760)
    g.connect(albedo, "XYZ Texture", lum, "A")
    g.connect(g.expr(unreal.MaterialExpressionConstant3Vector, -900, -700,
                     constant=unreal.LinearColor(0.299, 0.587, 0.114, 1.0)), "", lum, "B")
    # texture samples arrive linear; the thresholds were measured on the sRGB files, so compare in sRGB
    lum_lin = lum
    lum = g.expr(unreal.MaterialExpressionPower, -680, -700)
    g.connect(lum_lin, "", lum, "Base")
    g.connect(g.const(0.4545, -800, -640), "", lum, "Exponent")
    level = g.scalar("VeinLevel", 0.6, -900, -860)
    invert = g.scalar("VeinInvert", 0.0, -900, -930)
    diff = g.op(unreal.MaterialExpressionSubtract, level, lum, -620, -820)
    sign = g.op(unreal.MaterialExpressionSubtract, g.const(1.0, -760, -980),
                g.mul(invert, g.const(2.0, -760, -1040), -640, -980), -520, -960)
    mask = g.unary(unreal.MaterialExpressionSaturate,
                   g.mul(g.mul(diff, sign, -470, -860), g.scalar("VeinContrast", 6.0, -620, -1100), -360, -900),
                   -240, -900)
    veined = g.lerp(g.vector("GroundColor", (0.9, 0.88, 0.84), -400, -1200),
                    g.vector("VeinColor", (0.4, 0.38, 0.36), -400, -1120), mask, -120, -1000)
    ratio = g.op(unreal.MaterialExpressionDivide, lum, g.scalar("TexMedian", 0.7, -620, -1250), -470, -1200)
    detail = g.lerp(g.const(1.0, -360, -1300), ratio, g.scalar("DetailAmount", 0.5, -360, -1360), -220, -1250)
    vc = g.mul(g.mul(veined, detail, 0, -1050), macro_m, 120, -950)
    base = g.lerp(tinted, g.unary(unreal.MaterialExpressionSaturate, vc, 240, -950),
                  g.scalar("VeinMix", 0.0, 120, -800), 360, -600)
    # Per-slab variation: blender/build_pantheon.py gives every separate block or slab a random vertex
    # colour (R, G). R shifts brightness and warmth a little, G the polish, so neighbouring slabs
    # read as separately quarried pieces. Meshes without vertex colour (white) get a uniform shift.
    vcol = g.expr(unreal.MaterialExpressionVertexColor, 300, -300)
    var = g.scalar("SlabVariation", 0.07, 300, -180)
    one = g.const(1.0, 300, -60)
    vc_r = g.mul(vcol, one, 480, -320, a_out="R")     # the single-channel pins; the RGB pin did not connect
    vc_g = g.mul(vcol, one, 480, -80, a_out="G")
    vr = g.add(vc_r, g.const(-0.5, 480, -240), 620, -300)     # -0.5 .. 0.5
    shade = g.add(g.const(1.0, 620, -200), g.mul(g.mul(vr, var, 760, -280), g.const(2.0, 760, -200), 880, -260),
                  1000, -240)
    warm = g.lerp(g.expr(unreal.MaterialExpressionConstant3Vector, 880, -120,
                         constant=unreal.LinearColor(0.985, 1.0, 1.02, 1.0)),
                  g.expr(unreal.MaterialExpressionConstant3Vector, 880, -40,
                         constant=unreal.LinearColor(1.02, 1.0, 0.975, 1.0)),
                  vc_g, 1050, -100)
    base = g.unary(unreal.MaterialExpressionSaturate, g.mul(g.mul(base, shade, 1150, -400), warm, 1280, -300),
                   1400, -300)
    # Slab joints for the curved drum walls (JointMix 1 on the wall instances): thin dark lines every
    # JointHeight up the wall and every JointWidth along its arc (radius JointRadius about the axis)
    jwp = g.expr(unreal.MaterialExpressionWorldPosition, 1500, 300)
    jx = g.mask(jwp, 1650, 300, r=True)
    jy = g.mask(jwp, 1650, 380, r=False, g=True)
    jz = g.mask(jwp, 1650, 460, r=False, b=True)
    ang = g.expr(unreal.MaterialExpressionArctangent2, 1800, 320)
    g.connect(jy, "", ang, "Y")
    g.connect(jx, "", ang, "X")
    arc = g.mul(ang, g.scalar("JointRadius", 2172.0, 1800, 420), 1950, 340)
    half = g.mul(g.scalar("JointLine", 1.2, 1800, 620), g.const(0.5, 1800, 700), 1950, 640)   # half line width, cm

    def joint(coord, period, y):
        fr = g.unary(unreal.MaterialExpressionFrac, g.op(unreal.MaterialExpressionDivide, coord, period, 2100, y),
                     2250, y)
        dist = g.mul(g.unary(unreal.MaterialExpressionAbs, g.add(fr, g.const(-0.5, 2250, y + 70), 2400, y), 2550, y),
                     period, 2700, y)                                   # 0 at the joint .. period/2 mid-slab
        return g.unary(unreal.MaterialExpressionSaturate,
                       g.op(unreal.MaterialExpressionSubtract, g.const(1.0, 2700, y + 80),
                            g.op(unreal.MaterialExpressionDivide, dist, half, 2850, y), 3000, y), 3150, y)

    jmask = g.mul(g.op(unreal.MaterialExpressionMax, joint(arc, g.scalar("JointWidth", 240.0, 1950, 440), 300),
                       joint(jz, g.scalar("JointHeight", 150.0, 1950, 560), 520), 3300, 400),
                  g.scalar("JointMix", 0.0, 3150, 640), 3450, 440)
    base = g.mul(base, g.lerp(g.const(1.0, 3450, 560), g.const(0.5, 3450, 600), jmask, 3600, 500), 3750, 300)

    # Weathering, for the outside (the "_Ext" instances; 0 inside): grime that climbs from the ground
    # (GrimeAmount, fading out by GrimeHeight cm) and long vertical rain streaks, darker runs StreakWidth
    # cm across and StreakLength cm long, placed along the wall by the same arc as the joints
    grime = g.unary(unreal.MaterialExpressionSaturate,
                    g.op(unreal.MaterialExpressionSubtract, g.const(1.0, 3600, 760),
                         g.op(unreal.MaterialExpressionDivide, jz, g.scalar("GrimeHeight", 180.0, 3450, 820), 3600, 820),
                         3750, 780), 3900, 780)
    grime = g.mul(g.mul(grime, grime, 4050, 780), g.scalar("GrimeAmount", 0.0, 4050, 860), 4200, 800)
    suv = g.append(g.op(unreal.MaterialExpressionDivide, arc, g.scalar("StreakWidth", 90.0, 3450, 960), 3600, 940),
                   g.op(unreal.MaterialExpressionDivide, jz, g.scalar("StreakLength", 1400.0, 3450, 1040), 3600, 1020),
                   3750, 980)
    runs = noise_sample(g, suv, 3900, 980)
    cover = g.scalar("StreakCover", 0.55, 4100, 1060)          # the higher, the fewer runs
    streak = g.unary(unreal.MaterialExpressionSaturate,
                     g.mul(g.op(unreal.MaterialExpressionSubtract, runs, cover, 4400, 1000), g.const(4.0, 4400, 1080),
                           4550, 1000), 4700, 1000)
    # broken up along the wall at a larger scale, so the runs gather in places instead of a regular comb
    patch_uv = g.append(g.op(unreal.MaterialExpressionDivide, arc, g.const(1300.0, 3450, 1160), 3600, 1140),
                        g.op(unreal.MaterialExpressionDivide, jz, g.const(5000.0, 3450, 1240), 3600, 1220), 3750, 1180)
    patch = g.unary(unreal.MaterialExpressionSaturate,
                    g.mul(g.add(noise_sample(g, patch_uv, 3900, 1180), g.const(-0.35, 4250, 1260), 4400, 1200),
                          g.const(3.0, 4400, 1280), 4550, 1200), 4700, 1200)
    # only on walls: rain does not run across a roof or a step
    nz = g.unary(unreal.MaterialExpressionAbs,
                 g.mask(g.expr(unreal.MaterialExpressionVertexNormalWS, 4250, 1340), 4400, 1340, r=False, b=True), 4550, 1340)
    upright = g.unary(unreal.MaterialExpressionSaturate,
                      g.op(unreal.MaterialExpressionSubtract, g.const(1.0, 4550, 1420),
                           g.mul(nz, g.const(2.0, 4550, 1480), 4700, 1440), 4850, 1420), 5000, 1420)
    streak = g.mul(g.mul(g.mul(streak, patch, 4850, 1100), upright, 5000, 1100),
                   g.scalar("StreakAmount", 0.0, 4700, 1080), 5150, 1040)
    dirt = g.op(unreal.MaterialExpressionSubtract, g.const(1.0, 4850, 880),
                g.op(unreal.MaterialExpressionMax, grime, streak, 4850, 940), 5000, 900)
    base = g.mul(base, dirt, 5150, 300)
    g.out(base, unreal.MaterialProperty.MP_BASE_COLOR)

    rough_tex = world_tex(g, "RoughnessMap", white, wat_fn, -1600, 250, tile)
    rmask = g.mask(rough_tex, -1000, 250, a_out="XYZ Texture")
    rl = g.lerp(g.const(0.6, -900, 330), g.const(1.4, -900, 360), rmask, -760, 300)
    rough = g.mul(rl, g.scalar("Roughness", 0.3, -900, 420), -600, 320)
    rvar = g.lerp(g.const(0.88, -600, 420), g.const(1.12, -600, 460),
                  vc_g, -450, 440)
    rough = g.mul(rough, rvar, -300, 360)
    g.out(rough, unreal.MaterialProperty.MP_ROUGHNESS)

    ncall = world_tex(g, "NormalMap", flat, wan_fn, -1600, 600, tile)
    nrm = relief_normal(g, ncall, g.scalar("NormalStrength", 0.5, -1100, 780), -1100, 650)
    g.out(nrm, unreal.MaterialProperty.MP_NORMAL)
    mat.set_editor_property("tangent_space_normal", False)

    g.out(g.scalar("Metallic", 0.0, -600, 880), unreal.MaterialProperty.MP_METALLIC)
    mat.set_editor_property("used_with_nanite", True)
    mat.set_editor_property("two_sided", True)
    return finish(mat)


def build_painted_master(path):
    mat = fresh_material(path)
    g = Graph(mat)
    white = unreal.load_asset("/Engine/EngineResources/WhiteSquareTexture")
    uv = g.expr(unreal.MaterialExpressionTextureCoordinate, -1200, 0)
    tex = g.expr(unreal.MaterialExpressionTextureSampleParameter2D, -900, 0, parameter_name="Painting", texture=white)
    g.connect(uv, "", tex, "UVs")
    tint = g.vector("Tint", (1.0, 1.0, 1.0), -900, -250)
    g.out(g.mul(tex, tint, -600, -100, a_out="RGB"), unreal.MaterialProperty.MP_BASE_COLOR)
    g.out(g.scalar("Roughness", 0.75, -600, 150), unreal.MaterialProperty.MP_ROUGHNESS)
    # fresco plaster: faint world-aligned relief so the paint sits on a hand-trowelled surface
    flat = unreal.load_asset("/Engine/EngineMaterials/DefaultNormal")
    ncall = world_tex(g, "PlasterNormal", flat, unreal.load_asset(WAN), -1600, 400,
                      g.scalar("PlasterTile", 120.0, -1700, 500))
    g.out(relief_normal(g, ncall, g.scalar("PlasterStrength", 0.35, -1100, 580), -1100, 450),
          unreal.MaterialProperty.MP_NORMAL)
    mat.set_editor_property("tangent_space_normal", False)
    mat.set_editor_property("used_with_nanite", True)
    mat.set_editor_property("two_sided", True)
    return finish(mat)


def srgb(hex_colour):
    """An sRGB colour "#RRGGBB" as linear (r, g, b)."""
    out = []
    for i in (1, 3, 5):
        c = int(hex_colour[i:i + 2], 16) / 255.0
        out.append(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4)
    return tuple(out)


def build_dome_sky(path, plaster_tex, plaster_normal, centre_cm=(0.0, 0.0, 2172.0), radius_cm=2172.0):
    """The inner dome painted as the night sky (user, 2026-11-24): blue stucco, deepest in the coffers,
    where the gilded stars (the mesh Gilded_Rosettes) sit. A blue starry dome is a scholarly conjecture
    for the Pantheon (Thomas 2017, after Dio's remark that it resembled the heavens), not a finding:
    see reference/attic_niches.md, coffer centres.

    The coffers are told from the ribs by how far a point lies behind the dome's sphere (centre and
    radius in cm): 0 on the ribs and the plain zones, 18 cm and more on the steps of a coffer.
    Parameters: RibColor, CofferColor, DeepColor (the back panel), Mottle (how much of the plaster
    texture shows in the paint), TileSize, Roughness, NormalStrength."""
    mat = fresh_material(path)
    g = Graph(mat)
    wat_fn, wan_fn = unreal.load_asset(WAT), unreal.load_asset(WAN)
    tile = g.scalar("TileSize", 400.0, -1700, 0)
    wp = g.expr(unreal.MaterialExpressionWorldPosition, -1700, -700)
    centre = g.vector("DomeCentre", centre_cm, -1700, -600)
    rel = g.op(unreal.MaterialExpressionSubtract, wp, g.mask(centre, -1500, -600, r=True, g=True, b=True), -1300, -680)
    dist = g.unary(unreal.MaterialExpressionLength, rel, -1150, -680)
    depth = g.op(unreal.MaterialExpressionSubtract, dist, g.scalar("DomeRadius", radius_cm, -1300, -560), -1000, -660)

    def ramp(lo, hi, y):
        t = g.unary(unreal.MaterialExpressionSaturate,
                    g.op(unreal.MaterialExpressionDivide, g.add(depth, g.const(-lo, -1000, y + 60), -850, y),
                         g.const(hi - lo, -850, y + 60), -700, y), -550, y)
        return t

    in_coffer = ramp(3.0, 12.0, -660)      # past the rib's edge
    in_back = ramp(40.0, 70.0, -480)       # the innermost steps and the back panel
    paint = g.lerp(g.vector("RibColor", srgb("#5B7FCC"), -550, -900),
                   g.lerp(g.vector("CofferColor", srgb("#3460BE"), -550, -820),
                          g.vector("DeepColor", srgb("#23479E"), -550, -740), in_back, -350, -780),
                   in_coffer, -200, -820)
    # brushed on plaster: the plaster's own light and dark show through a little
    albedo = world_tex(g, "Albedo", plaster_tex, wat_fn, -1600, -300, tile)
    lum = g.expr(unreal.MaterialExpressionDotProduct, -1000, -300)
    g.connect(albedo, "XYZ Texture", lum, "A")
    g.connect(g.expr(unreal.MaterialExpressionConstant3Vector, -1150, -220,
                     constant=unreal.LinearColor(0.299, 0.587, 0.114, 1.0)), "", lum, "B")
    big = g.mul(tile, g.const(6.0, -1700, -120), -1600, -120)
    macro = world_tex(g, "Albedo", plaster_tex, wat_fn, -1600, -80, big)
    mlum = g.mask(macro, -1000, -80, a_out="XYZ Texture")
    shade = g.mul(g.lerp(g.const(0.7, -850, -340), g.const(1.25, -850, -310), lum, -700, -320),
                  g.lerp(g.const(0.85, -850, -120), g.const(1.15, -850, -90), mlum, -700, -100), -550, -220)
    mottled = g.lerp(paint, g.mul(paint, shade, -50, -700), g.scalar("Mottle", 0.8, -200, -600), 100, -760)
    g.out(g.unary(unreal.MaterialExpressionSaturate, mottled, 250, -760), unreal.MaterialProperty.MP_BASE_COLOR)

    g.out(g.scalar("Roughness", 0.8, -600, 320), unreal.MaterialProperty.MP_ROUGHNESS)
    ncall = world_tex(g, "NormalMap", plaster_normal, wan_fn, -1600, 600, tile)
    nrm = relief_normal(g, ncall, g.scalar("NormalStrength", 0.7, -1100, 780), -1100, 650)
    g.out(nrm, unreal.MaterialProperty.MP_NORMAL)
    mat.set_editor_property("tangent_space_normal", False)
    g.out(g.const(0.0, -600, 880), unreal.MaterialProperty.MP_METALLIC)
    mat.set_editor_property("two_sided", True)
    return finish(mat)


def build_invader_tile(path, glow=0.0):
    """Glazed ceramic tiles of the easter-egg mosaics (blender/build_pantheon.py, build_invaders): the
    colour of each tile and of the grout is the mesh's vertex colour, stored as sRGB values (Unreal
    hands them over unconverted). Parameters: Roughness (glazed: low), Glow (the tiles' own light as
    a share of their colour: 0 unless a mosaic sits where no light reaches)."""
    mat = fresh_material(path)
    g = Graph(mat)
    vc = g.mask(g.expr(unreal.MaterialExpressionVertexColor, -900, 0), -750, 0, r=True, g=True, b=True)
    colour = g.expr(unreal.MaterialExpressionPower, -600, 0)
    g.connect(vc, "", colour, "Base")
    g.connect(g.const(2.2, -750, 100), "", colour, "Exponent")
    g.out(colour, unreal.MaterialProperty.MP_BASE_COLOR)
    g.out(g.scalar("Roughness", 0.25, -600, 200), unreal.MaterialProperty.MP_ROUGHNESS)
    g.out(g.const(0.0, -600, 300), unreal.MaterialProperty.MP_METALLIC)
    g.out(g.mul(colour, g.scalar("Glow", glow, -600, 420), -400, 400), unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    return finish(mat)


def build_flame(path, sheet, tiles=16, fps=24.0, smoke=False, loop=128, views=2):
    """Camera-facing flame playing a flipbook rendered from a fluid simulation.

    For the engine's 1 m Plane mesh placed at the base of a flame (tilted, so that its bounds are a
    box and not a flat slab: see build_scene.add_flames). World position offset turns the
    card to face the camera about the vertical axis and sizes it (Width, Height in cm). Two
    neighbouring flipbook frames are blended, so sub-frame samples in Movie Render Queue see smooth
    motion. Each fire starts at a different frame, taken from its position.

    Variety (user, 2026-11-23: more frames, more varied): the sheet holds `views` loops of `loop`
    frames, each the same simulation seen from another side (tools/assemble_flipbook.py). From a hash
    of its position every fire picks a view, a playback rate (0.8-1.25x), whether it is mirrored, and
    a phase for a slow rise and fall of its height, so no two fires move alike.

    smoke=True builds the matching smoke plume instead: the sheet is a coverage mask from the same
    simulation, used as the opacity of a lit translucent card, so the smoke takes its light from the
    fire below and the room. (Now unlit with a fixed dim warm grey: see the note in the code.)
    """
    mat = fresh_material(path)
    if smoke:
        mat.set_editor_property("blend_mode", unreal.BlendMode.BLEND_TRANSLUCENT)
        # unlit: lit translucency rendered as a dotted veil without temporal anti-aliasing
        mat.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_UNLIT)
    else:
        mat.set_editor_property("blend_mode", unreal.BlendMode.BLEND_ADDITIVE)
        mat.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_UNLIT)
    mat.set_editor_property("two_sided", True)
    g = Graph(mat)
    uv = g.expr(unreal.MaterialExpressionTextureCoordinate, -2400, 0)
    u = g.mask(uv, -2200, -60)
    v = g.mask(uv, -2200, 60, r=False, g=True)
    pivot = g.expr(unreal.MaterialExpressionObjectPositionWS, -2400, 900)
    t = g.expr(unreal.MaterialExpressionTime, -2400, 300)

    # --- per-fire hashes from the position (0..1)
    pxy = g.mask(pivot, -2200, 800, r=True, g=True)
    hsh = g.unary(unreal.MaterialExpressionFrac,
                  g.mul(g.add(g.mask(pxy, -2050, 760), g.mul(g.mask(pxy, -2050, 840, r=False, g=True),
                                                             g.const(1.7, -2050, 900), -1900, 860), -1750, 800),
                        g.const(0.0137, -1750, 880), -1600, 820), -1450, 820)

    def rehash(mult, add, y):
        return g.unary(unreal.MaterialExpressionFrac,
                       g.add(g.mul(hsh, g.const(mult, -1450, y), -1300, y), g.const(add, -1300, y + 40), -1150, y),
                       -1000, y)

    h_view, h_rate, h_mirror, h_phase = rehash(7.31, 0.37, 2000), rehash(13.7, 0.71, 2100), \
        rehash(29.3, 0.13, 2200), rehash(3.9, 0.55, 2300)

    # --- billboard about the vertical axis
    cam = g.expr(unreal.MaterialExpressionCameraPositionWS, -2400, 1000)
    to_cam = g.op(unreal.MaterialExpressionSubtract, cam, pivot, -2200, 950)
    up = g.expr(unreal.MaterialExpressionConstant3Vector, -2200, 1100, constant=unreal.LinearColor(0.0, 0.0, 1.0, 0.0))
    right = g.unary(unreal.MaterialExpressionNormalize,
                    g.op(unreal.MaterialExpressionCrossProduct, up, to_cam, -2000, 1000), -1850, 1000)
    side = g.mul(g.add(u, g.const(-0.5, -2000, 1200), -1850, 1180), g.scalar("Width", 50.0, -2000, 1260), -1700, 1200)
    # slow rise and fall of the flame height, two incommensurate rates, phase per fire
    def wave(rate, amp, y):
        ph = g.add(g.mul(t, g.const(rate, -2000, y), -1850, y), h_phase, -1700, y)
        return g.mul(g.unary(unreal.MaterialExpressionSine, ph, -1550, y), g.const(amp, -1550, y + 40), -1400, y)
    breathe = g.add(g.const(1.0, -1400, 1700), g.add(wave(0.21, 0.07, 1750), wave(0.53, 0.05, 1850), -1250, 1800),
                    -1100, 1750)
    rise = g.mul(g.mul(g.unary(unreal.MaterialExpressionOneMinus, v, -2000, 1380),
                       g.scalar("Height", 75.0, -2000, 1450), -1850, 1400), breathe, -1700, 1400)
    target = g.add(g.add(pivot, g.mul(right, side, -1550, 1100), -1400, 1000), g.mul(up, rise, -1550, 1350), -1250, 1100)
    wp = g.expr(unreal.MaterialExpressionWorldPosition, -1550, 1550,
                world_position_shader_offset=unreal.WorldPositionIncludedOffsets.WPT_EXCLUDE_ALL_SHADER_OFFSETS)
    g.out(g.op(unreal.MaterialExpressionSubtract, target, wp, -1050, 1250),
          unreal.MaterialProperty.MP_WORLD_POSITION_OFFSET)

    # --- flipbook frame: per fire a start frame, a playback rate and one of the views
    n = float(loop)
    rate = g.lerp(g.const(0.8, -2250, 420), g.const(1.25, -2250, 460), h_rate, -2100, 440)
    frame = g.add(g.mul(g.mul(t, g.scalar("FramesPerSecond", fps, -2250, 360), -2050, 320), rate, -1950, 340),
                  g.mul(hsh, g.const(n, -1450, 900), -1300, 840), -1150, 400)
    view_base = g.mul(g.unary(unreal.MaterialExpressionFloor,
                              g.mul(h_view, g.const(float(views) - 0.001, -1000, 2050), -850, 2000), -700, 2000),
                      g.const(n, -700, 2060), -550, 2000)
    mirror = g.unary(unreal.MaterialExpressionFloor, g.add(h_mirror, g.const(0.5, -1000, 2250), -850, 2200), -700, 2200)
    blend = g.unary(unreal.MaterialExpressionFrac, frame, -1000, 480)
    f0 = g.unary(unreal.MaterialExpressionFloor, frame, -1000, 380)
    # narrower fires use the middle of the sheet frame
    span = g.scalar("USpan", 1.0, -2250, -200)
    u_m = g.lerp(u, g.unary(unreal.MaterialExpressionOneMinus, u, -2200, -300), mirror, -2100, -260)
    cell_u = g.add(g.mul(g.add(u_m, g.const(-0.5, -2050, -220), -1900, -200), span, -1750, -200),
                   g.const(0.5, -1750, -120), -1600, -180)
    cell = g.append(cell_u, v, -1450, -100)

    def sample(f, y):
        idx = g.add(g.op(unreal.MaterialExpressionFmod, f, g.const(n, -850, y + 60), -800, y), view_base, -700, y)
        col = g.op(unreal.MaterialExpressionFmod, idx, g.const(float(tiles), -700, y + 80), -550, y)
        row = g.unary(unreal.MaterialExpressionFloor,
                      g.op(unreal.MaterialExpressionDivide, idx, g.const(float(tiles), -700, y + 140), -550, y + 100),
                      -400, y + 100)
        uvs = g.op(unreal.MaterialExpressionDivide, g.add(cell, g.append(col, row, -250, y + 40), -100, y),
                   g.const(float(tiles), -100, y + 120), 50, y)
        tex = g.expr(unreal.MaterialExpressionTextureSample, 200, y, texture=sheet)
        g.connect(uvs, "", tex, "UVs")
        return tex

    a = sample(f0, 300)
    b = sample(g.add(f0, g.const(1.0, -1000, 620), -850, 600), 600)
    rgb = g.lerp(a, b, blend, 450, 450, a_out="RGB", b_out="RGB")
    # fade the lowest 6 % so the flame does not end in a hard line at the bowl
    base = g.unary(unreal.MaterialExpressionSaturate,
                   g.mul(g.unary(unreal.MaterialExpressionOneMinus, v, 300, 800), g.const(16.0, 300, 870), 450, 820),
                   600, 820)
    if smoke:
        # thin towards the top of the card so the plume dissolves instead of ending at an edge
        top = g.unary(unreal.MaterialExpressionSaturate, g.mul(v, g.const(3.0, 300, 950), 450, 930), 600, 930)
        # drop the faint render noise around the plume, so the card is fully clear outside it
        dens = g.unary(unreal.MaterialExpressionSaturate,
                       g.mul(g.add(g.mask(rgb, 600, 450), g.const(-0.06, 600, 380), 720, 430),
                             g.const(1.1, 720, 360), 840, 420), 960, 420)
        cover = g.mul(g.mul(dens, base, 1080, 500), top, 1200, 560)
        g.out(g.mul(cover, g.scalar("Opacity", 0.22, 1080, 650), 1350, 560), unreal.MaterialProperty.MP_OPACITY)
        g.out(g.vector("SmokeColor", (0.035, 0.03, 0.026), 1200, 300), unreal.MaterialProperty.MP_EMISSIVE_COLOR)
        return finish(mat)
    # From far away a flame is only a few pixels wide and its licking tongues become a sparkle. With
    # distance (FarStart..FarEnd, cm) the flipbook fades to a third and a steady glow of the flame's
    # shape and colour takes over, breathing gently.
    dist = g.unary(unreal.MaterialExpressionLength, to_cam, 300, 1100)
    far = g.unary(unreal.MaterialExpressionSaturate,
                  g.op(unreal.MaterialExpressionDivide,
                       g.op(unreal.MaterialExpressionSubtract, dist, g.scalar("FarStart", 1000.0, 300, 1180), 450, 1120),
                       g.op(unreal.MaterialExpressionSubtract, g.scalar("FarEnd", 2500.0, 300, 1260),
                            g.scalar("FarStart", 1000.0, 300, 1180), 450, 1220), 600, 1150), 750, 1150)
    du = g.mul(g.add(cell_u, g.const(-0.5, 300, 1400), 450, 1380), g.const(1.0 / 0.12, 450, 1440), 600, 1400)
    dv = g.mul(g.add(v, g.const(-0.62, 300, 1520), 450, 1500), g.const(1.0 / 0.19, 450, 1560), 600, 1520)
    r2 = g.add(g.mul(du, du, 750, 1400), g.mul(dv, dv, 750, 1520), 900, 1450)
    blob = g.expr(unreal.MaterialExpressionPower, 1200, 1450)
    g.connect(g.const(2.718, 900, 1380), "", blob, "Base")
    g.connect(g.mul(r2, g.const(-1.0, 900, 1540), 1050, 1480), "", blob, "Exponent")
    gentle = g.add(g.const(1.0, 900, 1650), g.add(wave(5.3, 0.05, 1700), wave(8.9, 0.04, 1800), 1050, 1750), 1200, 1680)
    glow = g.mul(g.mul(g.mul(blob, gentle, 1350, 1500), far, 1500, 1450),
                 g.vector("FarGlow", (0.6, 0.27, 0.07), 1350, 1250), 1650, 1400)
    flick = g.mul(rgb, g.lerp(g.const(1.0, 750, 1000), g.const(0.33, 750, 1040), far, 900, 1000), 1050, 700)
    em = g.mul(g.mul(g.add(flick, glow, 1800, 900), base, 1950, 700), g.scalar("EmissiveStrength", 30.0, 600, 650), 2100, 520)
    g.out(em, unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    return finish(mat)


def build_soot(path):
    """Deferred decal: a soft, uneven patch of lamp soot for the wall behind and above a fire."""
    mat = fresh_material(path)
    mat.set_editor_property("material_domain", unreal.MaterialDomain.MD_DEFERRED_DECAL)
    mat.set_editor_property("blend_mode", unreal.BlendMode.BLEND_TRANSLUCENT)
    g = Graph(mat)
    uv = g.expr(unreal.MaterialExpressionTextureCoordinate, -900, 0)
    dist = g.op(unreal.MaterialExpressionDistance, uv,
                g.expr(unreal.MaterialExpressionConstant2Vector, -900, 120, r=0.5, g=0.5), -700, 40)
    fall = g.unary(unreal.MaterialExpressionSaturate,
                   g.op(unreal.MaterialExpressionSubtract, g.const(1.0, -700, 160),
                        g.mul(dist, g.const(2.0, -700, 220), -550, 120), -400, 100), -250, 100)
    soft = g.mul(fall, fall, -100, 100)
    uneven = g.lerp(g.const(0.55, -250, 260), g.const(1.0, -250, 300),
                    noise_sample(g, g.mul(uv, g.const(1.7, -700, 340), -550, 320), -450, 320), -100, 280)
    g.out(g.mul(g.mul(soft, uneven, 50, 160), g.scalar("Strength", 0.85, -100, 400), 200, 200),
          unreal.MaterialProperty.MP_OPACITY)
    g.out(g.vector("SootColor", (0.012, 0.010, 0.009), 50, -100), unreal.MaterialProperty.MP_BASE_COLOR)
    g.out(g.const(0.95, 50, 0), unreal.MaterialProperty.MP_ROUGHNESS)
    return finish(mat)


def build_leak(path, default_tex):
    """Deferred decal for the Megascans water streaks (BaseColor in RGB, opacity in A).

    User, 2026-11-23: the streaks were too strong and did not follow gravity: projected along the
    wall's radius, a decal box also lands on the cornices and soffits it crosses, where the texture
    is smeared into straight lines. The surface normal is rebuilt from the screen-space derivatives
    of the surface position (decals cannot read the scene normal before the base pass), and the
    streak fades out on any surface that is not close to vertical, so it only runs down walls.
    Strength scales the whole decal.
    """
    mat = fresh_material(path)
    mat.set_editor_property("material_domain", unreal.MaterialDomain.MD_DEFERRED_DECAL)
    mat.set_editor_property("blend_mode", unreal.BlendMode.BLEND_TRANSLUCENT)
    g = Graph(mat)
    tex = g.expr(unreal.MaterialExpressionTextureSampleParameter2D, -900, 0, parameter_name="Streaks",
                 texture=default_tex)
    wp = g.expr(unreal.MaterialExpressionWorldPosition, -1300, 400)
    dx = g.unary(unreal.MaterialExpressionDDX, wp, -1150, 360)
    dy = g.unary(unreal.MaterialExpressionDDY, wp, -1150, 440)
    nrm = g.unary(unreal.MaterialExpressionNormalize, g.op(unreal.MaterialExpressionCrossProduct, dx, dy, -1000, 400),
                  -850, 400)
    nz = g.unary(unreal.MaterialExpressionAbs, g.mask(nrm, -700, 400, r=False, b=True), -600, 400)
    # 1 on walls (|nz| < 0.15), 0 from |nz| 0.35 on (cornice tops, soffits, the dome)
    upright = g.unary(unreal.MaterialExpressionSaturate,
                      g.mul(g.op(unreal.MaterialExpressionSubtract, g.const(0.35, -600, 480), nz, -450, 440),
                            g.const(5.0, -450, 520), -300, 460), -150, 460)
    op = g.mul(g.mul(tex, upright, -300, 160, a_out="A"),
               g.scalar("Strength", 0.45, -300, 260), -100, 200)
    g.out(op, unreal.MaterialProperty.MP_OPACITY)
    g.out(g.mul(tex, g.const(1.0, -300, 0), -150, 0, a_out="RGB"), unreal.MaterialProperty.MP_BASE_COLOR)
    g.out(g.const(0.9, -100, 320), unreal.MaterialProperty.MP_ROUGHNESS)
    return finish(mat)


GHOST_HLSL = """
// Count groups of 15 texels: a bounding sphere (centre, radius), then 14 capsules
// (row 0: A and radius, row 1: B and strength). A group out of reach is skipped.
float m = 0.0;
int n = (int)Count;
for (int g = 0; g < n; g++)
{
    int base = g * 15;
    float4 s = Tex.Load(int3(base, 0, 0));
    if (length(P - s.xyz) > s.w + Soft)
        continue;
    for (int k = 1; k < 15; k++)
    {
        float4 a = Tex.Load(int3(base + k, 0, 0));
        float4 b = Tex.Load(int3(base + k, 1, 0));
        float3 pa = P - a.xyz;
        float3 ba = b.xyz - a.xyz;
        float h = saturate(dot(pa, ba) / max(dot(ba, ba), 1.0));
        float d = length(pa - ba * h) - a.w;
        m = max(m, b.w * saturate(1.0 - d / Soft));
    }
}
return m;
"""


def build_ghost_fog(path, placeholder_tex):
    """F3: Volume-domain fog over the floor, with the ghosts carved out.

    The look (user, 2026-11-23): held to about figure height, but not a flat sheet. Its top rises and
    falls in slow waves; inside, denser and lighter areas drift past, with streaky wisps that reach
    above the top. A thin haze fills the rest of the box so the oculus beam shows too.

        top     = FogTop + WaveAmp * wave(x, y, t)            slow 2D waves that evolve over time
        floor   = saturate((top + WispReach * wisp - z) / FogFade)
        density = Density * (floor * patches * wisp' + Haze) * (1 - carve)

    patches: large, slow lighter/denser areas; wisp: smaller noise stretched along the drift. The carve
    comes from capsules written by AF3GhostDriver into CapsuleData (row 0: endpoint A and radius, row 1:
    endpoint B and strength, cm, relative to the fog box) with a soft edge of Soft cm. CarveDebug 1
    shows the carved shapes themselves as fog.
    """
    mat = fresh_material(path)
    mat.set_editor_property("material_domain", unreal.MaterialDomain.MD_VOLUME)
    mat.set_editor_property("blend_mode", unreal.BlendMode.BLEND_ADDITIVE)
    g = Graph(mat)

    def noise(pos, x, y, levels=3):
        n = g.expr(unreal.MaterialExpressionNoise, x, y, noise_function=unreal.NoiseFunction.NOISEFUNCTION_GRADIENT_TEX,
                   levels=levels, scale=1.0, output_min=0.0, output_max=1.0, turbulence=False)
        g.connect(pos, "", n, "")   # first input, Position
        return n

    wp = g.expr(unreal.MaterialExpressionWorldPosition, -2000, 0)
    t = g.expr(unreal.MaterialExpressionTime, -2000, 200)
    wind = g.vector("FogWind", (14.0, 5.0, 0.0), -2000, 300)           # cm/s drift
    moved = g.op(unreal.MaterialExpressionSubtract, wp, g.mul(t, wind, -1800, 250), -1650, 100)
    x = g.mask(wp, -1650, 400)
    y = g.mask(wp, -1650, 460, r=False, g=True)
    z = g.mask(wp, -1650, 520, r=False, b=True)

    # slow waves of the top surface: 2D noise over the floor, its third axis running with time
    wave_pos = g.append(g.append(g.mul(x, g.const(0.0007, -1500, 380), -1350, 380),
                                 g.mul(y, g.const(0.0007, -1500, 460), -1350, 460), -1200, 420),
                        g.mul(t, g.scalar("WaveSpeed", 0.025, -1500, 540), -1350, 540), -1050, 460)
    wave = g.add(noise(wave_pos, -900, 460, levels=2), g.const(-0.5, -900, 560), -750, 480)
    top = g.add(g.scalar("FogTop", 150.0, -750, 380), g.mul(wave, g.scalar("WaveAmp", 90.0, -750, 600), -600, 560),
                -450, 450)

    # lighter and denser areas, several metres across
    patch_n = noise(g.mul(moved, g.scalar("PatchScale", 0.0009, -1500, 0), -1350, 0), -1200, 0, levels=2)
    patches = g.lerp(g.scalar("PatchLow", 0.15, -1050, -80), g.scalar("PatchHigh", 1.5, -1050, -20), patch_n, -900, 0)
    # wisps: finer noise stretched along the drift (longer in x and y than in z)
    wisp_pos = g.mul(moved, g.vector("WispScale", (0.0025, 0.0035, 0.009), -1500, 140), -1350, 140)
    wisp_n = noise(wisp_pos, -1200, 140, levels=3)
    wisp = g.unary(unreal.MaterialExpressionSaturate,
                   g.add(g.mul(wisp_n, g.const(2.2, -1050, 200), -900, 160), g.const(-0.55, -900, 220), -750, 160),
                   -600, 160)
    reach = g.add(top, g.mul(wisp, g.scalar("WispReach", 70.0, -600, 260), -450, 240), -300, 300)
    floor = g.unary(unreal.MaterialExpressionSaturate,
                    g.op(unreal.MaterialExpressionDivide,
                         g.op(unreal.MaterialExpressionSubtract, reach, z, -150, 350),
                         g.scalar("FogFade", 70.0, -150, 430), 0, 380), 150, 380)
    body = g.add(g.mul(g.mul(floor, patches, 300, 200), g.lerp(g.const(0.35, 300, 280), g.const(1.0, 300, 320),
                                                              wisp, 450, 300), 600, 250),
                 g.scalar("Haze", 0.035, 450, 420), 750, 300)

    custom = g.expr(unreal.MaterialExpressionCustom, -600, 900, code=GHOST_HLSL,
                    output_type=unreal.CustomMaterialOutputType.CMOT_FLOAT1, description="GhostCarve")
    inputs = []
    for name in ("P", "Tex", "Count", "Soft"):
        ci = unreal.CustomInput()
        ci.set_editor_property("input_name", name)
        inputs.append(ci)
    custom.set_editor_property("inputs", inputs)
    # relative to the fog box: large-world coordinates do not arrive in a custom node as plain world
    # centimetres; the driver writes the capsules relative to the box as well
    rel = g.op(unreal.MaterialExpressionSubtract, wp,
               g.expr(unreal.MaterialExpressionObjectPositionWS, -1050, 960), -800, 920)
    g.connect(rel, "", custom, "P")
    tex = g.expr(unreal.MaterialExpressionTextureObjectParameter, -900, 1000, parameter_name="CapsuleData",
                 texture=placeholder_tex)
    g.connect(tex, "", custom, "Tex")
    g.connect(g.scalar("CapsuleCount", 0.0, -900, 1080), "", custom, "Count")
    g.connect(g.scalar("Soft", 14.0, -900, 1140), "", custom, "Soft")
    # Ghosts made of fog (user, 2026-11-23): thin ambient fog, and the figures and their wakes as
    # denser, misty shapes (the wisp noise breaks them up). CarveAmount still thins the ambient fog
    # inside them a little; CarveDebug 1 shows the shapes alone.
    ambient = g.mul(body, g.unary(unreal.MaterialExpressionOneMinus,
                                  g.mul(custom, g.scalar("CarveAmount", 0.0, -400, 980), -250, 950), -100, 950),
                    900, 400)
    ghost = g.mul(g.mul(custom, g.lerp(g.const(0.45, 300, 1000), g.const(1.0, 300, 1040), wisp, 450, 1000), 600, 980),
                  g.scalar("GhostDensity", 1.0, 600, 1080), 750, 1000)
    normal = g.add(g.mul(ambient, g.scalar("Density", 0.8, 900, 560), 1050, 480), ghost, 1150, 600)
    dens = g.lerp(normal, custom, g.scalar("CarveDebug", 0.0, 1050, 700), 1250, 600)
    g.out(dens, unreal.MaterialProperty.MP_SUBSURFACE_COLOR)                 # extinction
    g.out(g.vector("FogAlbedo", (0.92, 0.9, 0.86), 1050, 100), unreal.MaterialProperty.MP_BASE_COLOR)
    return finish(mat)


GHOST_MIST_HLSL = r"""
struct FGhostMist
{
	float Hash(float3 p)
	{
		p = frac(p * 0.3183099 + 0.1);
		p *= 17.0;
		return frac(p.x * p.y * p.z * (p.x + p.y + p.z));
	}
	float Noise(float3 x)
	{
		float3 i = floor(x);
		float3 f = frac(x);
		f = f * f * (3.0 - 2.0 * f);
		float a = lerp(lerp(Hash(i), Hash(i + float3(1, 0, 0)), f.x), lerp(Hash(i + float3(0, 1, 0)), Hash(i + float3(1, 1, 0)), f.x), f.y);
		float b = lerp(lerp(Hash(i + float3(0, 0, 1)), Hash(i + float3(1, 0, 1)), f.x), lerp(Hash(i + float3(0, 1, 1)), Hash(i + float3(1, 1, 1)), f.x), f.y);
		return lerp(a, b, f.z);
	}
	float Fbm(float3 x)
	{
		return 0.62 * Noise(x) + 0.38 * Noise(x * 2.17 + 11.3);
	}
	float Cone(float3 p, float3 a, float3 b, float ra, float rb)
	{
		float3 ab = b - a;
		float h = saturate(dot(p - a, ab) / max(dot(ab, ab), 0.001));
		return length(p - a - ab * h) - lerp(ra, rb, h);
	}
	float SMin(float a, float b, float k)
	{
		float h = saturate(0.5 + 0.5 * (b - a) / k);
		return lerp(b, a, h) - k * h * (1.0 - h);
	}
};
FGhostMist Fn;
float3 RayO = CamRel + QuadPos;
float3 ToPix = PixRel - CamRel;
float PixT = max(length(ToPix), 0.001);
float3 RayD = ToPix / PixT;
float MaxT = SceneD * PixT / max(PixD, 0.001);
float3 ToBound = Bound - RayO;
float BoundT = dot(ToBound, RayD);
if (dot(ToBound, ToBound) - BoundT * BoundT > BoundR * BoundR)
{
	return 0.0;
}
int NumPrims = min(int(Count + 0.5), 40);
int Row3 = int(Row + 0.5) * 3;
// the capsules this ray passes: the body's, and the trail's ribbon segments (a puff and the next)
float4 BodyA[28];
float4 BodyB[28];
float4 TrA0[12];
float4 TrB0[12];
float4 TrC0[12];
float4 TrA1[12];
float4 TrB1[12];
float4 TrC1[12];
float4 TrAxis[12];
float3 TrMid[12];
float4 TrNow[12];
int NumBody = 0;
int NumTrail = 0;
float BodyPad = 0.0;
float NearT = 1.0e9;
float FarT = -1.0e9;
for (int i = 0; i < NumPrims; i++)
{
	float4 a = Tex.Load(int3(i, Row3, 0));
	float4 b = Tex.Load(int3(i, Row3 + 1, 0));
	float4 c = Tex.Load(int3(i, Row3 + 2, 0));
	if (c.y < 0.5)
	{
		float3 Mid = 0.5 * (a.xyz + b.xyz);
		float Rad = 0.5 * length(a.xyz - b.xyz) + max(a.w, b.w) + c.z;
		float3 ToMid = Mid - RayO;
		float MidT = dot(ToMid, RayD);
		if (NumBody < 28 && dot(ToMid, ToMid) - MidT * MidT < Rad * Rad && MidT + Rad > 0.0)
		{
			BodyA[NumBody] = a;
			BodyB[NumBody] = b;
			BodyPad = max(BodyPad, c.z);
			NumBody++;
			NearT = min(NearT, MidT - Rad);
			FarT = max(FarT, MidT + Rad);
		}
	}
	else if (c.y < 1.5)
	{
		float4 a1 = Tex.Load(int3(i + 1, Row3, 0));
		float4 b1 = Tex.Load(int3(i + 1, Row3 + 1, 0));
		float4 c1 = Tex.Load(int3(i + 1, Row3 + 2, 0));
		float3 Mid = 0.25 * (a.xyz + b.xyz + a1.xyz + b1.xyz);
		float Rad = max(max(length(a.xyz - Mid) + a.w, length(b.xyz - Mid) + b.w),
			max(length(a1.xyz - Mid) + a1.w, length(b1.xyz - Mid) + b1.w)) + max(c.z, c1.z);
		float3 ToMid = Mid - RayO;
		float MidT = dot(ToMid, RayD);
		if (NumTrail < 12 && dot(ToMid, ToMid) - MidT * MidT < Rad * Rad && MidT + Rad > 0.0)
		{
			TrA0[NumTrail] = a;
			TrB0[NumTrail] = b;
			TrC0[NumTrail] = c;
			TrA1[NumTrail] = a1;
			TrB1[NumTrail] = b1;
			TrC1[NumTrail] = c1;
			float3 M0 = 0.5 * (a.xyz + b.xyz);
			float3 E = 0.5 * (a1.xyz + b1.xyz) - M0;
			TrMid[NumTrail] = M0;
			TrAxis[NumTrail] = float4(E, 1.0 / max(dot(E, E), 0.01));
			NumTrail++;
			NearT = min(NearT, MidT - Rad);
			FarT = max(FarT, MidT + Rad);
		}
	}
}
if (NumBody + NumTrail == 0)
{
	return 0.0;
}
NearT = max(NearT, 0.0);
FarT = min(FarT, MaxT);
if (FarT <= NearT)
{
	return 0.0;
}
float Frame = fmod(floor(Secs * 60.0), 8.0);
float Jitter = frac(52.9829189 * frac(dot(Parameters.SvPosition.xy + 5.588238 * Frame, float2(0.06711056, 0.00583715))));
float MinStep = max(2.5, NearT * 0.0035);
float RayT = NearT + Jitter * MinStep * 2.0;
float Tau = 0.0;
for (int s = 0; s < 72; s++)
{
	if (RayT >= FarT || Tau > 6.0)
	{
		break;
	}
	float3 p = RayO + RayD * RayT;
	float BodyD = 1.0e6;
	float AnyD = 1.0e6;
	for (int j = 0; j < NumBody; j++)
	{
		BodyD = Fn.SMin(BodyD, Fn.Cone(p, BodyA[j].xyz, BodyB[j].xyz, BodyA[j].w, BodyB[j].w), Blend);
	}
	AnyD = BodyD - BodyPad;
	for (int k = 0; k < NumTrail; k++)
	{
		// the ribbon between two puffs: the capsule interpolated to where p lies along it
		float h = saturate(dot(p - TrMid[k], TrAxis[k].xyz) * TrAxis[k].w);
		float4 a = lerp(TrA0[k], TrA1[k], h);
		float4 b = lerp(TrB0[k], TrB1[k], h);
		float4 c = lerp(TrC0[k], TrC1[k], h);
		float d = Fn.Cone(p, a.xyz, b.xyz, a.w, b.w);
		TrNow[k] = float4(d, 0.5 * (a.w + b.w), c.x, c.w);
		AnyD = min(AnyD, d - c.z);
	}
	if (AnyD > 0.0)
	{
		RayT += max(AnyD, MinStep);
		continue;
	}
	float BodyN = Fn.Fbm((p - Anchor) * NoiseScale + float3(0.0, 0.0, -Secs * 0.22));
	float WideN = Fn.Fbm(p * (NoiseScale * 0.4) + float3(Secs * 0.02, 0.0, -Secs * 0.07));
	// The figure is a garment of mist, not a solid: densest in a layer ShellT thick under its
	// surface, with a few broad folds winding down it, thinner inside (Hollow), so the edges
	// of the shape read stronger than its middle. Round it a faint, wispy halo (Halo, HaloReach).
	float EdgeD = BodyD + (BodyN - 0.5) * 2.0 * BodyNoise;
	float Outer = saturate(0.5 - EdgeD / Soft);
	Outer = Outer * Outer * (3.0 - 2.0 * Outer);
	float Deep = saturate((-EdgeD - ShellT) / (ShellT * 1.5));
	float2 Round = p.xy - Anchor.xy;
	// a few broad folds that wind down round the figure, as a draped toga's do (not upright pleats)
	float Fold = 0.5 + 0.5 * sin((atan2(Round.y, Round.x) - Yaw) * PleatCount + p.z * PleatRise + (WideN - 0.5) * 2.0);
	float BodyF = Outer * lerp(1.0 - Pleat * Fold, Hollow, Deep) * lerp(0.7, 1.0, WideN);
	float HaloF = saturate(1.0 - max(EdgeD, 0.0) / HaloReach);
	BodyF = max(BodyF, Halo * HaloF * HaloF * lerp(0.3, 1.7, BodyN));
	float TrailF = 0.0;
	for (int m = 0; m < NumTrail; m++)
	{
		float u = saturate(-(TrNow[m].x + (WideN - 0.5) * 2.0 * TrNow[m].w) / TrNow[m].y);
		TrailF = max(TrailF, TrNow[m].z * u * u * (3.0 - 2.0 * u));
	}
	float Field = max(BodyF, TrailF * TrailDensity) * lerp(FeetLow, 1.0, saturate(p.z / 70.0));
	float Step = clamp(0.3 * abs(BodyD), MinStep, 9.0);
	Tau += Field * Density * Step;
	RayT += Step;
}
return 1.0 - exp(-Tau);
"""


def build_ghost_mist(path, placeholder_tex):
    """F3: the ghosts themselves, as volumes of mist marched in the pixel shader.

    AF3GhostDriver describes each ghost as up to 40 tapered capsules in a float texture (three rows
    per ghost: end A and radius, end B and radius, then strength / kind / pad / noise amplitude; world
    cm). Kind 0 capsules are the robed body: they melt into one smooth shape (smooth minimum, Blend
    cm), so there are no joints, and the shape's edge is eroded by noise that rises through the
    figure; the mist reaches at most their pad beyond them (HaloReach + BodyNoise must fit in it).
    The body is drawn as a garment rather than a solid: see the shader. Kind 1 and 2 capsules are the trail the
    figure leaves behind, newest first: upright puffs with their own strength, each joined to the
    next into a ribbon (kind 2 ends it), densest along its middle and fading outwards. The shader
    runs on a camera-facing quad that the driver keeps in front of the
    ghost; for each pixel it walks the camera ray through the capsules near it (skipping empty space
    by distance, stopping at the scene depth) and returns 1 - exp(-density along the ray).

    Lit like smoke (volumetric, non-directional translucency), so the fires and the sky colour it.
    The floor is z = 0: the mist thins towards it (FeetLow) to sink into the floor fog.
    """
    mat = fresh_material(path)
    mat.set_editor_property("blend_mode", unreal.BlendMode.BLEND_TRANSLUCENT)
    mat.set_editor_property("translucency_lighting_mode",
                            unreal.TranslucencyLightingMode.TLM_VOLUMETRIC_NON_DIRECTIONAL)
    mat.set_editor_property("two_sided", True)
    g = Graph(mat)

    custom = g.expr(unreal.MaterialExpressionCustom, -300, 0, code=GHOST_MIST_HLSL,
                    output_type=unreal.CustomMaterialOutputType.CMOT_FLOAT1, description="GhostMist")
    names = ("CamRel", "PixRel", "QuadPos", "SceneD", "PixD", "Tex", "Row", "Count", "Secs", "Anchor", "Bound",
             "BoundR", "Density", "Soft", "Blend", "BodyNoise", "NoiseScale", "TrailDensity", "FeetLow", "ShellT",
             "Hollow", "Pleat", "PleatCount", "Halo", "HaloReach", "PleatRise", "Yaw")
    inputs = []
    for name in names:
        ci = unreal.CustomInput()
        ci.set_editor_property("input_name", name)
        inputs.append(ci)
    custom.set_editor_property("inputs", inputs)

    # camera and pixel relative to the quad (large-world positions do not go into a custom node);
    # the driver passes the quad's own position as QuadPos, so the shader works in world cm
    obj = g.expr(unreal.MaterialExpressionObjectPositionWS, -1100, -300)
    cam = g.op(unreal.MaterialExpressionSubtract, g.expr(unreal.MaterialExpressionCameraPositionWS, -1100, -400), obj,
               -850, -380)
    pix = g.op(unreal.MaterialExpressionSubtract, g.expr(unreal.MaterialExpressionWorldPosition, -1100, -200), obj,
               -850, -220)
    g.connect(cam, "", custom, "CamRel")
    g.connect(pix, "", custom, "PixRel")
    g.connect(g.vector("QuadPos", (0.0, 0.0, 0.0), -850, -100), "", custom, "QuadPos")
    g.connect(g.expr(unreal.MaterialExpressionSceneDepth, -850, 20), "", custom, "SceneD")
    g.connect(g.expr(unreal.MaterialExpressionPixelDepth, -850, 100), "", custom, "PixD")
    tex = g.expr(unreal.MaterialExpressionTextureObjectParameter, -850, 180, parameter_name="PrimData",
                 texture=placeholder_tex)
    g.connect(tex, "", custom, "Tex")
    g.connect(g.scalar("Row", 0.0, -850, 380), "", custom, "Row")
    g.connect(g.scalar("Count", 0.0, -850, 440), "", custom, "Count")
    g.connect(g.expr(unreal.MaterialExpressionTime, -850, 500), "", custom, "Secs")
    anchor = g.vector("Anchor", (0.0, 0.0, 0.0), -850, 560)   # the ghost's feet; alpha: its yaw (radians)
    g.connect(anchor, "", custom, "Anchor")
    g.connect(anchor, "A", custom, "Yaw")
    bound = g.vector("Bound", (0.0, 0.0, 0.0), -850, 760)
    g.connect(bound, "", custom, "Bound")
    g.connect(bound, "A", custom, "BoundR")
    y = 960
    for name, value in (("Density", 0.02), ("Soft", 5.0), ("Blend", 6.0), ("BodyNoise", 3.5), ("NoiseScale", 0.085),
                        ("TrailDensity", 0.22), ("FeetLow", 0.45), ("ShellT", 5.0), ("Hollow", 0.3), ("Pleat", 0.5),
                        ("PleatCount", 1.5), ("Halo", 0.12), ("HaloReach", 20.0), ("PleatRise", 0.11)):
        g.connect(g.scalar(name, value, -850, y), "", custom, name)
        y += 60

    g.out(custom, unreal.MaterialProperty.MP_OPACITY)
    g.out(g.vector("GhostColor", (0.62, 0.66, 0.72), 0, -250), unreal.MaterialProperty.MP_BASE_COLOR)
    g.out(g.vector("GhostGlow", (0.012, 0.014, 0.018), 0, -150), unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    return finish(mat)


def build_flicker(path, low=0.68, high=1.12):
    mat = fresh_material(path)
    mat.set_editor_property("material_domain", unreal.MaterialDomain.MD_LIGHT_FUNCTION)
    g = Graph(mat)
    # Fire flicker: two noise rates mixed, offset by world position so neighbouring fires do not pulse
    # together. Open bowl fires swing about +-25 %, lamp flames only a few percent (measured flame
    # behaviour, reference/revision3_research.md); the flame animation carries the liveliness.
    t = g.expr(unreal.MaterialExpressionTime, -1100, 0)
    wp = g.expr(unreal.MaterialExpressionWorldPosition, -1100, 200)
    offs = g.mul(g.mask(wp, -950, 200, r=True, g=True), g.const(0.0007, -950, 280), -800, 220)
    fast = g.add(g.append(g.mul(t, g.const(0.9, -950, 60), -820, 40), g.const(0.3, -820, 110), -700, 40),
                 offs, -560, 100)
    slow = g.add(g.append(g.mul(t, g.const(0.23, -950, 340), -820, 320), g.const(0.7, -820, 390), -700, 320),
                 offs, -560, 360)
    n = g.add(g.mul(noise_sample(g, fast, -450, 0), g.const(0.65, -250, 80), -150, 40),
              g.mul(noise_sample(g, slow, -450, 300), g.const(0.35, -250, 360), -150, 320), -20, 150)
    g.out(g.lerp(g.const(low, 100, 60), g.const(high, 100, 100), n, 240, 120),
          unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    return finish(mat)


STATUE_EYES_HLSL = r"""
struct FStatueEye
{
	float Arc(float s, float Peak, float Height, float Power)
	{
		float x = s < Peak ? s / Peak * 0.5 : 0.5 + (s - Peak) / (1.0 - Peak) * 0.5;
		return Height * pow(max(sin(3.14159265 * saturate(x)), 0.0), Power);
	}
	float4 Draw(float4 Old, float3 P, float3 Cam, float3 C, float W, float3 U, float3 V, float TOff, float3 Iris)
	{
		float3 d = P - C;
		if (W < 0.01 || dot(d, d) > 0.5625 * W * W)
		{
			return Old;
		}
		// the painted eye's own template (tools/polychromy/face.py, eye_layers): s from the inner
		// to the outer corner, t up the face, both in eye widths
		float s = 0.5 + dot(d, U) / W;
		float t = dot(d, V) / W;
		float sc = saturate(s);
		float Up = Arc(sc, 0.45, 0.20, 0.75) + TOff;
		float Lo = -Arc(sc, 0.55, 0.14, 0.9) + TOff;
		float Open = saturate(0.5 - (max(max(t - Up, Lo - t), max(-s, s - 1.0)) + 0.008) / 0.02);
		if (Open <= 0.0)
		{
			return Old;
		}
		float2 Centre = float2(0.5, TOff + 0.02);
		// the eyeball turned towards the camera: the iris slides in the opening, more sideways than up
		float3 Gaze = normalize(Cam - C);
		float2 Shift = float2(clamp(dot(Gaze, U) * 0.45, -0.2, 0.2), clamp(dot(Gaze, V) * 0.3, -0.06, 0.07));
		float Was = saturate(0.5 - (length(float2(s, t) - Centre) - 0.2) / 0.02) * Open;
		float Dist = length(float2(s, t) - Centre - Shift);
		float IrisF = saturate(0.5 - (Dist - 0.18) / 0.02) * Open;
		float RingF = IrisF * saturate((Dist - 0.1404) / 0.02 + 0.5) * 0.9;
		float PupilF = saturate(0.5 - (Dist - 0.0756) / 0.02) * Open;
		// eye white where the painted iris was, then the iris, its darker ring and the pupil
		float4 New = lerp(Old, float4(0.8388, 0.7767, 0.6790, 0.25), Was);
		New = lerp(New, float4(Iris, 1.0), IrisF);
		New.rgb = lerp(New.rgb, float3(0.0232, 0.0091, 0.0037), RingF);
		New.rgb = lerp(New.rgb, float3(0.0037, 0.0022, 0.0020), PupilF);
		return New;
	}
};
float4 Paint = float4(PaintIn, CovIn);
if (Follow < 0.5)
{
	return Paint;
}
FStatueEye Eye;
Paint = Eye.Draw(Paint, P, Cam, EyeAC, EyeAW, EyeAU, EyeAV, EyeAT, Iris);
Paint = Eye.Draw(Paint, P, Cam, EyeBC, EyeBW, EyeBU, EyeBV, EyeBT, Iris);
return Paint;
"""


def statue_eyes(g, paint_rgb, cov):
    """F3 ghost mode: the statue's eyes follow the visitor. Returns the paint colour and coverage
    with the painted iris moved towards the camera.

    The eyes are painted (vertex colour) from a template fitted to the eye corners; the app's ghost
    driver hands each statue the template's frame (tools/statue_eyes.py -> F3StatueEyes.inl) through
    a dynamic instance: EyeAC / EyeBC centre and width (alpha), EyeAU / EyeBU the axis from the inner
    to the outer corner and the template's vertical offset (alpha), EyeAV / EyeBV the axis up the
    face, all in the mesh's own space (cm), and EyeIris. The shader redraws the template's opening
    there: eye white over the painted iris, and the iris, ring and pupil shifted towards the camera.
    With EyesFollow 0 (the default: the films, and the app outside ghost mode) nothing changes.
    """
    wp = g.expr(unreal.MaterialExpressionWorldPosition, -1500, 900)
    cam = g.expr(unreal.MaterialExpressionCameraPositionWS, -1500, 1000)
    local = []
    for src, y in ((wp, 900), (cam, 1000)):
        t = g.expr(unreal.MaterialExpressionTransformPosition, -1250, y,
                   transform_source_type=unreal.MaterialPositionTransformSource.TRANSFORMPOSSOURCE_WORLD,
                   transform_type=unreal.MaterialPositionTransformSource.TRANSFORMPOSSOURCE_LOCAL)
        g.connect(src, "", t, "")
        local.append(t)
    custom = g.expr(unreal.MaterialExpressionCustom, -850, 900, code=STATUE_EYES_HLSL,
                    output_type=unreal.CustomMaterialOutputType.CMOT_FLOAT4, description="StatueEyes")
    names = ("PaintIn", "CovIn", "P", "Cam", "Follow", "Iris", "EyeAC", "EyeAW", "EyeAU", "EyeAT", "EyeAV",
             "EyeBC", "EyeBW", "EyeBU", "EyeBT", "EyeBV")
    inputs = []
    for name in names:
        ci = unreal.CustomInput()
        ci.set_editor_property("input_name", name)
        inputs.append(ci)
    custom.set_editor_property("inputs", inputs)
    g.connect(paint_rgb, "", custom, "PaintIn")
    g.connect(cov, "", custom, "CovIn")
    g.connect(local[0], "", custom, "P")
    g.connect(local[1], "", custom, "Cam")
    g.connect(g.scalar("EyesFollow", 0.0, -1250, 1100), "", custom, "Follow")
    g.connect(g.vector("EyeIris", (0.1, 0.04, 0.013), -1250, 1160), "", custom, "Iris")
    y = 1360
    for eye in ("A", "B"):
        c = g.vector("Eye%sC" % eye, (0.0, 0.0, 0.0), -1250, y)
        u = g.vector("Eye%sU" % eye, (1.0, 0.0, 0.0), -1250, y + 200)
        v = g.vector("Eye%sV" % eye, (0.0, 0.0, 1.0), -1250, y + 400)
        g.connect(c, "", custom, "Eye%sC" % eye)
        g.connect(c, "A", custom, "Eye%sW" % eye)
        g.connect(u, "", custom, "Eye%sU" % eye)
        g.connect(u, "A", custom, "Eye%sT" % eye)
        g.connect(v, "", custom, "Eye%sV" % eye)
        y += 600
    rgb = g.mask(custom, -550, 880, r=True, g=True, b=True)
    a = g.expr(unreal.MaterialExpressionComponentMask, -550, 960, r=False, g=False, b=False, a=True)
    g.connect(custom, "", a, "")
    return rgb, a


def build_statue_master(path, marble_tex):
    mat = fresh_material(path)
    mat.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_SUBSURFACE)
    g = Graph(mat)
    wat_fn = unreal.load_asset(WAT)
    tile = g.scalar("TileSize", 120.0, -1500, 0)
    call = world_tex(g, "Albedo", marble_tex, wat_fn, -1500, -250, tile)
    marble = g.mul(call, g.vector("MarbleTint", (1.0, 0.97, 0.92), -1100, -400), -850, -250, a_out="XYZ Texture")
    vc = g.expr(unreal.MaterialExpressionVertexColor, -1100, 100)
    # the painted FBX stores sRGB colours and Unreal hands them to the material unconverted, which made
    # every paint read too pale (Jupiter's violet mantle came out pink); approximate sRGB -> linear
    paint_srgb = g.mask(vc, -1000, 80, r=True, g=True, b=True)
    paint_rgb = g.expr(unreal.MaterialExpressionPower, -880, 80)
    g.connect(paint_srgb, "", paint_rgb, "Base")
    g.connect(g.const(2.2, -1000, 160), "", paint_rgb, "Exponent")
    cov = g.mul(vc, g.scalar("PaintStrength", 1.0, -900, 250), -750, 200, a_out="A")
    paint_rgb, cov = statue_eyes(g, paint_rgb, cov)
    g.out(g.lerp(marble, paint_rgb, cov, -550, -50), unreal.MaterialProperty.MP_BASE_COLOR)
    rough = g.lerp(g.scalar("MarbleRoughness", 0.32, -750, 350), g.scalar("PaintRoughness", 0.6, -750, 420), cov, -550, 380)
    g.out(rough, unreal.MaterialProperty.MP_ROUGHNESS)
    sss = g.mul(g.vector("SubsurfaceColor", (0.9, 0.78, 0.62), -750, 550),
                g.unary(unreal.MaterialExpressionOneMinus, cov, -750, 650), -550, 600)
    g.out(sss, unreal.MaterialProperty.MP_SUBSURFACE_COLOR)
    g.out(g.scalar("Opacity", 0.35, -550, 720), unreal.MaterialProperty.MP_OPACITY)
    mat.set_editor_property("used_with_nanite", True)
    return finish(mat)
