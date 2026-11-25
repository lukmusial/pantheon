"""Camera flythrough and Movie Render Queue presets for the Pantheon level.

Run headless after build_scene.py:
    UnrealEditor-Cmd ue/Pantheon/Pantheon.uproject -run=pythonscript \
        -script=ue/scripts/sequence.py -AllowCommandletRendering -unattended -nosplash -nop4

Creates /Game/Cinematics/SEQ_Flythrough (60 s at 24 fps, one continuous Cine Camera move)
and render presets /Game/Cinematics/MRQ_Stills, MRQ_Draft1080, MRQ_Final4K.

Camera keys are written in Blender coordinates (metres, +Y towards the entrance) and
converted to Unreal (centimetres, Y flipped), matching build_pantheon.py.
"""

import math

import unreal

MAP = "/Game/Maps/Pantheon"
CINE = "/Game/Cinematics"
SEQ_NAME = "SEQ_Flythrough"
FPS = 24

import json
import os

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
MANIFEST = json.load(open(os.path.join(ROOT, "assets", "architecture", "fbx", "manifest.json")))
R = 21.72

# Order of the circuit round the rotunda (azimuth of each statue); Jupiter (270) is kept for the end.
# starts next to the apse, where the panorama ends, and goes once round, finishing beside the apse
CIRCUIT = [247.5, 225.0, 202.5, 180.0, 157.5, 135.0, 112.5, 67.5, 45.0, 22.5, 0.0, 337.5, 315.0, 292.5]
HOLD = 4.5        # seconds on each statue (slow push-in)
TRANSIT = 4.5     # seconds between neighbouring statues (3 s swung too fast between light and dark)


def statue_height(key):
    for d in ("painted", "processed"):
        f = os.path.join(ROOT, "assets", "statues", d, key + ".json")
        if os.path.exists(f):
            info = json.load(open(f))
            if "size_m" in info:
                return info["size_m"][2]
    return 2.6


# portico figures without clothing over the hips, kept out of wide or distant framing
NUDE = ("agrippa_portico",)


def statue_keys(slot, t, inward, d0, d1, side=0.0, lens=(28.0, 32.0), aim=0.72, eye=0.5):
    """Two keys framing one statue: from distance d0 at time t, pushing in to d1 over HOLD seconds."""
    x, y, z = slot["position"]
    h = statue_height(slot["statue"])
    ix, iy = inward
    sx, sy = -iy, ix                                  # sideways, for a slight three-quarter view
    target = (x, y, z + aim * h)                      # aim and eye: heights as fractions of the statue
    keys = []
    for k, (dt, d, f) in enumerate(((0.0, d0, lens[0]), (HOLD, d1, lens[1]))):
        cam = (x + ix * d + sx * side, y + iy * d + sy * side, z + eye * h)
        keys.append((t + dt, cam, target, f, 2.8))
    return keys


def build_keys():
    """Camera keys (time s, position, look-at, focal mm, f-stop) in Blender coordinates."""
    slots = {s["statue"]: s for s in MANIFEST["statue_slots"]}
    by_az = {round(s["azimuth"], 1): s for s in MANIFEST["statue_slots"]
             if not s["statue"].startswith("attic_") and s["statue"] not in ("augustus_portico", "agrippa_portico")}
    # 1 portico: in along the clear central aisle (inner columns stand at x = +-6.8 and +-15.9), then
    # Augustus and Agrippa in the aisle niches; cameras stay at y < 36.5, well clear of the column
    # row at y = 39.3, and transits pass through the centre looking in through the doors
    # Transits run along y = 38.2, between the rear wall (y = 33.4) and the inner columns, and
    # always look at the next figure (or the door) from afar: moving sideways 3 m from the wall
    # while facing it smeared the whole frame into a dark blur (drafts 9 and 10).
    def chest(key):
        x, y, z = slots[key]["position"]
        return (x, y, z + 0.9 * statue_height(key))

    order = [k for k in ("augustus_portico", "agrippa_portico") if k in slots]
    first = chest(order[0]) if order else (0.0, 15.0, 5.0)
    # starts on the forecourt's paving, 1.4 below the portico floor since the podium and its steps
    # were built (2026-11-25), at eye height above it
    keys = [(0.0, (0.0, 58.0, 0.3), (0.0, 36.0, 6.0), 24.0, 8.0),
            (6.0, (0.0, 38.2, 2.6), first, 30.0, 8.0)]
    t = 8.4
    for n, key in enumerate(order):
        # chest-up framing from a raised camera: these two are seen close and from below
        hold = statue_keys(slots[key], t, (0.0, 1.0), 4.0, 3.2, side=0.5, lens=(38.0, 42.0),
                           aim=0.9, eye=0.82)
        keys += hold
        t += HOLD + 7.0
        # dolly straight back out of the niche bay, still on the figure (a turn this close to the
        # wall smears the frame), then turn on the transit line towards the next figure or the door
        cx, _, cz = hold[-1][1]

        def above(k):
            # a point well above a nude figure's head: seen from afar on a long lens from a raised
            # camera, the frame then ends above the hips (user: no stills of private regions)
            x_, y_, z_ = slots[k]["position"]
            return (x_, y_, z_ + 1.5 * statue_height(k))

        if key in NUDE and n + 1 == len(order):
            # leaving the last figure: rise and turn towards the door, so the figure slides out of
            # frame at chest height (looking above its head left only a blank wall in frame)
            keys.append((t - 5.5, (cx, 38.2, cz + 1.0), (0.0, 20.0, 6.5), 35.0, 8.0))
        elif key in NUDE:
            keys.append((t - 5.5, (cx, 38.2, cz + 1.0), above(key), 50.0, 8.0))
        else:
            keys.append((t - 5.5, (cx, 38.2, cz), hold[-1][2], 35.0, 8.0))
        if n + 1 < len(order):
            nxt = order[n + 1]
            if nxt in NUDE:
                keys.append((t - 3.0, (0.0, 38.2, cz + 1.0), above(nxt), 50.0, 8.0))
            else:
                keys.append((t - 3.0, (0.0, 38.2, cz), chest(nxt), 35.0, 8.0))
        else:
            keys.append((t - 3.0, (0.4 * cx, 38.2, 3.0), (0.0, 20.0, 6.0), 28.0, 8.0))
    # 2 through the door, slow tilt up to the dome
    keys += [(t + 1.0, (0.0, 34.0, 1.7), (0.0, 0.0, 7.0), 24.0, 8.0),
             (t + 5.0, (0.0, 26.0, 1.7), (0.0, 0.0, 8.0), 24.0, 8.0),
             (t + 9.0, (0.0, 15.0, 1.8), (0.0, 0.0, 22.0), 20.0, 8.0),
             (t + 15.0, (0.0, 6.0, 2.0), (0.0, -3.0, 40.0), 16.0, 8.0),
             (t + 19.0, (0.0, 3.0, 2.0), (0.0, -6.0, 40.0), 16.0, 8.0)]
    t += 22.0
    # 2b slow 360-degree panorama from the centre, to take in the whole interior
    for k in range(5):
        a = math.radians(90.0 - 90.0 * k)          # start facing the apse side, turn clockwise
        keys.append((t + 4.0 + 6.0 * k, (0.0, -1.0, 1.9),
                     (14.0 * math.cos(a - math.pi), 14.0 * math.sin(a - math.pi) - 1.0, 6.5), 20.0, 8.0))
    t += 32.0
    # 3 the circuit: each exedra and aedicula statue in turn
    prev = None
    for az in CIRCUIT:
        slot = by_az.get(round(az, 1))
        if slot is None:
            continue
        if prev is not None:
            t += TRANSIT + (1.5 if abs(prev - az) > 30.0 else 0.0)
        a = math.radians(az)
        inward = (-math.cos(a), -math.sin(a))
        if abs(az / 45.0 - round(az / 45.0)) < 1e-6:      # exedra statue, behind the column screen
            keys += statue_keys(slot, t, inward, 5.8, 4.6)
        else:                                            # aedicula statue, raised on its podium
            keys += statue_keys(slot, t, inward, 5.0, 4.0, side=0.6)
        t += HOLD
        prev = az
    # 4 crane past the attic niches
    t += 4.0
    keys += [(t, (8.0, -4.0, 11.0), (20.0, -9.0, 17.0), 24.0, 8.0),
             (t + 8.0, (-8.0, -4.0, 12.0), (-20.0, -9.0, 17.0), 24.0, 8.0)]
    t += 12.0
    # 5 slow final approach to Jupiter, ending on the full figure
    keys += [(t, (0.0, 3.0, 7.0), (0.0, -22.5, 7.0), 24.0, 5.6),
             (t + 12.0, (0.0, -5.0, 5.5), (0.0, -22.5, 6.5), 28.0, 4.0),
             (t + 22.0, (0.0, -9.5, 4.4), (0.0, -22.5, 5.6), 32.0, 2.8),
             (t + 25.0, (0.0, -9.8, 4.4), (0.0, -22.5, 5.6), 32.0, 2.8)]
    return keys


def build_vertical_keys():
    """Camera keys for the 70 s portrait (9:16) film for phones (follow-up F1), in seconds.

    Its own path rather than a crop of the landscape film: tall subjects suit a portrait frame, so it
    rises with the portico columns, spins under the oculus, follows the light shaft down and ends on the
    full height of Jupiter. Statues are clothed ones only (Ceres, Minerva), so full-figure framing is safe.
    """
    slots = {s["statue"]: s for s in MANIFEST["statue_slots"]}

    def inward(az):
        a = math.radians(az)
        return (-math.cos(a), -math.sin(a))

    marks = {}
    # 1 portico: low walk up the central aisle looking up at the columns, then level out on the door
    # (looking up all the way filled the frame with the portico ceiling for four seconds, stills v1)
    # from the forecourt (its paving 1.4 below the portico floor since 2026-11-25), at eye height
    keys = [(0.0, (0.0, 56.0, 0.2), (0.0, 40.0, 12.0), 20.0, 8.0),
            (6.0, (0.0, 41.0, 1.7), (0.0, 20.0, 5.0), 20.0, 8.0),
            # 2 through the door and tilt up into the dome
            (10.0, (0.0, 34.0, 1.7), (0.0, 0.0, 7.0), 20.0, 8.0),
            (14.0, (0.0, 22.0, 1.8), (0.0, 0.0, 14.0), 20.0, 8.0),
            (18.5, (0.0, 4.0, 1.9), (0.0, -2.0, 40.0), 16.0, 8.0)]
    # 3 under the oculus, looking almost straight up and turning 135 degrees, so the coffer rings wheel
    # about the open eye (an exact vertical look would leave the yaw undefined); 15 s was too long
    for k in range(4):
        a = math.radians(90.0 - 45.0 * k)
        keys.append((20.5 + 2.5 * k, (0.0, 0.0, 1.9), (3.0 * math.cos(a), 3.0 * math.sin(a), 43.0), 14.0, 8.0))
    # 4 down the light shaft to the apse
    keys += [(31.0, (-1.0, -2.0, 2.0), (-0.5, -20.0, 9.0), 18.0, 8.0)]
    # 5 Ceres (aedicula, raised on its podium) and Minerva (exedra, square on between the screen columns):
    # full figure, camera at mid-height
    t = 34.0
    marks["statues"] = t
    keys += statue_keys(slots["ceres_louvre"], t, inward(202.5), 5.0, 4.2, side=0.6, lens=(26.0, 28.0),
                        aim=0.5, eye=0.45)
    t += HOLD
    # transit through the open floor, not along the drum: from beside Ceres the line of sight to
    # Minerva crossed the pier between them and filled the frame (stills v1)
    athena = slots["athena_giustiniani"]
    ax, ay, az_ = athena["position"]
    a = math.radians(213.75)
    keys.append((t + 2.0, (11.0 * math.cos(a), 11.0 * math.sin(a), 2.4), (ax, ay, az_ + 1.4), 24.0, 8.0))
    t += 4.0
    # a longer lens than for Ceres: at 28 mm the lit screen columns either side took half the frame
    keys += statue_keys(athena, t, inward(225.0), 6.4, 5.4, lens=(34.0, 38.0), aim=0.5, eye=0.45)
    t += HOLD
    # back straight out of the exedra mouth still on Minerva, then turn to Jupiter in the open
    ix, iy = inward(225.0)
    keys.append((t + 2.0, (ax + 9.0 * ix, ay + 9.0 * iy, 2.6), (ax, ay, az_ + 1.4), 28.0, 8.0))
    # 6 approach the colossal Jupiter, ending on his full height with the altar fire low in the frame;
    # the turn takes 4 s (3 s smeared the frame, stills v3)
    marks["final"] = t + 6.0
    keys += [(t + 6.0, (-3.5, -7.0, 4.8), (0.0, -22.5, 6.0), 24.0, 5.6),
             (t + 16.0, (0.0, -10.5, 4.2), (0.0, -22.5, 5.6), 28.0, 4.0),
             (t + 23.0, (0.0, -11.5, 4.1), (0.0, -22.5, 5.6), 28.0, 2.8)]
    return keys, marks


# The user asked for the whole film about 20 % faster (after draft 7): every key time is divided
# by SPEED, so holds become 3.75 s and the panorama turns at about 18 degrees per second.
SPEED = 1.5      # 1.2 (first speed-up) x 1.25 (second)
KEYS = [(k[0] / SPEED,) + tuple(k[1:]) for k in build_keys()]
DURATION_S = int(math.ceil(KEYS[-1][0]))
_ENTER = next(k[0] for k in KEYS if k[1][1] < 26.5)      # passing the door
_FINAL = KEYS[-4][0]                                     # start of the final approach

# Camera exposure compensation (EV) over time: daylight in the portico, about 3.5 stops brighter
# once inside, and down again for the sunlit Jupiter at the end (his paint clips above about -0.6 EV).
_CIRCUIT = next(k[0] for k in KEYS if k[0] > _ENTER + 10.0 and k[3] >= 28.0)   # first statue hold inside
# During the statue close-ups the pale marbles (albedo ~0.87) clip at the wide-shot exposure, so the
# circuit runs 0.8 EV darker.
# Interior exposure is 0.4 EV higher than before now that the pale wall stones are darker, so the
# columns, altars and paintings come up while the walls stay where they were.
# Surface-cache lighting removed the wall glow, which left the statue tour about half a stop dark.
EXPOSURE = [(0.0, 1.5), (_ENTER - 5.0, 1.5), (_ENTER, 5.2), (_CIRCUIT - 2.0, 5.2), (_CIRCUIT, 4.8),
            (_FINAL - 14.0, 4.8), (_FINAL - 10.0, 5.0), (_FINAL, 5.0), (_FINAL + 12.0, 0.6),
            (float(DURATION_S), -0.6)]

# PANTHEON_CUT=vertical builds the portrait film instead (SEQ_Vertical, its own camera and presets);
# the landscape film and its presets are left as they are.
CUT = os.environ.get("PANTHEON_CUT", "main")
CAMERA_LABEL = "FlythroughCamera"
SENSOR_MM = (36.0, 20.25)            # filmback width, height: 16:9
if CUT == "vertical":
    SEQ_NAME = "SEQ_Vertical"
    CAMERA_LABEL = "VerticalCamera"
    SENSOR_MM = (20.25, 36.0)        # 9:16, the same 36 mm across the long side
    KEYS, _marks = build_vertical_keys()
    DURATION_S = int(math.ceil(KEYS[-1][0]))
    _V_ENTER = next(k[0] for k in KEYS if k[1][1] < 26.5)
    _V_STATUES, _V_FINAL = _marks["statues"], _marks["final"]
    # the sunlit Jupiter clipped with the landscape film's slower ramp (stills v1), so exposure comes
    # down as soon as the camera turns towards him
    EXPOSURE = [(0.0, 1.5), (_V_ENTER - 4.0, 1.5), (_V_ENTER, 5.2), (_V_STATUES - 2.0, 5.2),
                (_V_STATUES, 4.8), (_V_FINAL - 3.0, 4.8), (_V_FINAL, 3.0), (_V_FINAL + 5.5, 0.6),
                (float(DURATION_S), -0.6)]

assets = unreal.EditorAssetLibrary
tools = unreal.AssetToolsHelpers.get_asset_tools()


def log(msg):
    unreal.log("PANTHEON " + msg)


def ue_vec(p):
    return (p[0] * 100.0, -p[1] * 100.0, p[2] * 100.0)


def look_rotation(pos, target):
    d = [target[i] - pos[i] for i in range(3)]
    yaw = math.degrees(math.atan2(d[1], d[0]))
    pitch = math.degrees(math.atan2(d[2], math.hypot(d[0], d[1])))
    return pitch, yaw


def unwrap(values):
    out = [values[0]]
    for v in values[1:]:
        while v - out[-1] > 180.0:
            v -= 360.0
        while v - out[-1] < -180.0:
            v += 360.0
        out.append(v)
    return out


def recreate(name, cls, factory):
    path = CINE + "/" + name
    if assets.does_asset_exist(path):
        assets.delete_asset(path)
    return tools.create_asset(name, CINE, cls, factory)


def build_sequence(level_editor, actors):
    for a in actors.get_all_level_actors():
        if a.get_actor_label() == CAMERA_LABEL:
            actors.destroy_actor(a)
    seq = recreate(SEQ_NAME, unreal.LevelSequence, unreal.LevelSequenceFactoryNew())
    seq.set_display_rate(unreal.FrameRate(FPS, 1))
    # fine tick resolution so Movie Render Queue can place temporal sub-samples between frames
    seq.set_tick_resolution(unreal.FrameRate(24000, 1))
    end = FPS * DURATION_S
    seq.set_playback_start(0)
    seq.set_playback_end(end)

    cam = actors.spawn_actor_from_class(unreal.CineCameraActor, unreal.Vector(*ue_vec(KEYS[0][1])))
    cam.set_actor_label(CAMERA_LABEL)
    comp = cam.get_cine_camera_component()
    fb = comp.get_editor_property("filmback")
    fb.set_editor_property("sensor_width", SENSOR_MM[0])
    fb.set_editor_property("sensor_height", SENSOR_MM[1])
    comp.set_editor_property("filmback", fb)
    focus = comp.get_editor_property("focus_settings")
    focus.set_editor_property("focus_method", unreal.CameraFocusMethod.MANUAL)
    comp.set_editor_property("focus_settings", focus)

    binding = seq.add_possessable(cam)
    track = binding.add_track(unreal.MovieScene3DTransformTrack)
    section = track.add_section()
    section.set_range(0, end)
    ch = section.get_all_channels()  # loc x y z, rot roll pitch yaw, scale x y z

    positions = [ue_vec(k[1]) for k in KEYS]
    rots = [look_rotation(ue_vec(k[1]), ue_vec(k[2])) for k in KEYS]
    yaws = unwrap([r[1] for r in rots])
    interp = unreal.MovieSceneKeyInterpolation.AUTO
    for k, pos, (pitch, _), yaw in zip(KEYS, positions, rots, yaws):
        f = unreal.FrameNumber(int(round(k[0] * FPS)))
        for i in range(3):
            ch[i].add_key(f, pos[i], interpolation=interp)
        ch[3].add_key(f, 0.0, interpolation=interp)
        ch[4].add_key(f, pitch, interpolation=interp)
        ch[5].add_key(f, yaw, interpolation=interp)

    pp = comp.get_editor_property("post_process_settings")
    pp.set_editor_property("override_auto_exposure_bias", True)
    pp.set_editor_property("auto_exposure_bias", EXPOSURE[0][1])
    comp.set_editor_property("post_process_settings", pp)
    comp.set_editor_property("post_process_blend_weight", 1.0)

    comp_binding = seq.add_possessable(comp)

    def float_track(prop, values):
        t = comp_binding.add_track(unreal.MovieSceneFloatTrack)
        t.set_property_name_and_path(prop.split(".")[-1], prop)
        s = t.add_section()
        s.set_range(0, end)
        c = s.get_all_channels()[0]
        for k, v in zip(KEYS, values):
            c.add_key(unreal.FrameNumber(int(round(k[0] * FPS))), v, interpolation=interp)

    float_track("CurrentFocalLength", [k[3] for k in KEYS])
    float_track("CurrentAperture", [k[4] for k in KEYS])
    dists = [math.dist(k[1], k[2]) * 100.0 for k in KEYS]
    float_track("FocusSettings.ManualFocusDistance", dists)

    t = comp_binding.add_track(unreal.MovieSceneFloatTrack)
    t.set_property_name_and_path("AutoExposureBias", "PostProcessSettings.AutoExposureBias")
    s = t.add_section()
    s.set_range(0, end)
    c = s.get_all_channels()[0]
    for sec, ev in EXPOSURE:
        c.add_key(unreal.FrameNumber(int(round(sec * FPS))), ev, interpolation=interp)

    cut_track = seq.add_track(unreal.MovieSceneCameraCutTrack)
    cut = cut_track.add_section()
    cut.set_range(0, end)
    if hasattr(seq, "get_portable_binding_id"):
        cam_id = seq.get_portable_binding_id(seq, binding)
    else:
        cam_id = seq.get_binding_id(binding)
    cut.set_camera_binding_id(cam_id)

    assets.save_loaded_asset(seq)
    level_editor.save_current_level()
    log("sequence %s: %d keys, %d frames" % (SEQ_NAME, len(KEYS), end))


def build_render_presets():
    factory_cls = getattr(unreal, "MoviePipelinePrimaryConfigFactory", None) or \
        getattr(unreal, "MoviePipelineMasterConfigFactory", None)
    config_cls = getattr(unreal, "MoviePipelinePrimaryConfig", None) or unreal.MoviePipelineMasterConfig
    if factory_cls is None:
        log("no config factory class found; presets skipped")
        return

    cvars = {
        # 4 px x 256 slices overflowed the fog grid at 1080p and left a camera-locked rectangle of
        # missing fog; the engine's 8 px with 128 slices covers the whole frame
        "r.VolumetricFog.GridPixelSize": 8,
        "r.VolumetricFog.GridSizeZ": 128,
        "r.VolumetricFog.HistoryMissSupersampleCount": 16,
        "r.Lumen.Reflections.DownsampleFactor": 1,
        # Lumen screen traces only see what is on screen, which gave a camera-locked dimmed rectangle and
        # blotches on the dome; hardware ray tracing alone gives even, stable indirect light
        "r.Lumen.ScreenProbeGather.ScreenTraces": 0,
        "r.Lumen.Reflections.ScreenTraces": 0,
        # indirect light: denser screen probes, hit lighting, longer temporal accumulation
        "r.Lumen.ScreenProbeGather.DownsampleFactor": 8,
        "r.Lumen.ScreenProbeGather.TracingOctahedronResolution": 16,
        "r.Lumen.ScreenProbeGather.Temporal.MaxFramesAccumulated": 32,
        # 0 = light from the surface cache. Hit lighting (1, 2) put several times too much cool light
        # on the pale exedra walls compared with the path tracer; mode 0 matches the reference.
        "r.Lumen.HardwareRayTracing.LightingMode": 0,
        "r.Lumen.Reflections.HardwareRayTracing.Translucent.Refraction.EnableForProject": 0,
        "r.Shadow.Virtual.SMRT.RayCountDirectional": 16,
        "r.MotionBlurQuality": 4,
        "r.DepthOfFieldQuality": 4,
        "r.Tonemapper.Sharpen": 0.5,
    }

    def preset(name, res, spatial, temporal, ext_cls, out_dir, frame_step=1, pass_cls=None, frames=None,
               extra_cvars=None):
        cfg = recreate(name, config_cls, factory_cls())
        out = cfg.find_or_add_setting_by_class(unreal.MoviePipelineOutputSetting)
        out.set_editor_property("output_resolution", unreal.IntPoint(res[0], res[1]))
        out.set_editor_property("output_directory", unreal.DirectoryPath(out_dir))
        out.set_editor_property("file_name_format", "flythrough.{frame_number}")
        out.set_editor_property("zero_pad_frame_numbers", 4)
        out.set_editor_property("output_frame_step", frame_step)
        cfg.find_or_add_setting_by_class(pass_cls or unreal.MoviePipelineDeferredPassBase)
        if frames:
            out.set_editor_property("use_custom_playback_range", True)
            out.set_editor_property("custom_start_frame", frames[0])
            out.set_editor_property("custom_end_frame", frames[1])
        cfg.find_or_add_setting_by_class(ext_cls)
        aa = cfg.find_or_add_setting_by_class(unreal.MoviePipelineAntiAliasingSetting)
        aa.set_editor_property("spatial_sample_count", spatial)
        aa.set_editor_property("temporal_sample_count", temporal)
        aa.set_editor_property("override_anti_aliasing", True)
        aa.set_editor_property("anti_aliasing_method", unreal.AntiAliasingMethod.AAM_NONE)
        aa.set_editor_property("engine_warm_up_count", 64)
        aa.set_editor_property("render_warm_up_count", 64)
        aa.set_editor_property("use_camera_cut_for_warm_up", False)
        game = cfg.find_or_add_setting_by_class(unreal.MoviePipelineGameOverrideSetting)
        game.set_editor_property("cinematic_quality_settings", True)
        cv = cfg.find_or_add_setting_by_class(unreal.MoviePipelineConsoleVariableSetting)
        for k, v in dict(cvars, **(extra_cvars or {})).items():
            cv.add_or_update_console_variable(k, v)
        assets.save_loaded_asset(cfg)
        log("preset %s %dx%d samples %dx%d" % (name, res[0], res[1], spatial, temporal))

    root = "{project_dir}/../../renders"
    if CUT == "vertical":
        # portrait presets; the 2160x3840 final has the same pixel count as the landscape 4K
        preset("MRQ_VertStills", (540, 960), 1, 8, unreal.MoviePipelineImageSequenceOutput_PNG,
               root + "/vertical_stills", frame_step=FPS)
        preset("MRQ_VertDraft", (1080, 1920), 1, 8, unreal.MoviePipelineImageSequenceOutput_PNG,
               root + "/vertical_draft")
        preset("MRQ_VertFinal", (2160, 3840), 1, 16, unreal.MoviePipelineImageSequenceOutput_PNG,
               root + "/vertical_final")
        return
    preset("MRQ_Draft1080", (1920, 1080), 1, 8, unreal.MoviePipelineImageSequenceOutput_PNG, root + "/draft1080")
    # 16 temporal samples give the anti-aliasing and motion blur (spatial 2 would double a ~10 h
    # render for little gain); PNG like the drafts, so the encode matches what was approved
    preset("MRQ_Final4K", (3840, 2160), 1, 16, unreal.MoviePipelineImageSequenceOutput_PNG, root + "/final4k")
    # one frame every two seconds, for checking lighting and framing
    preset("MRQ_Stills", (1920, 1080), 1, 8, unreal.MoviePipelineImageSequenceOutput_PNG, root + "/stills",
           frame_step=4 * FPS)
    # Lumen at higher settings on one frame (east wall orbit), to compare with the path tracer
    preset("MRQ_LumenTest", (1920, 1080), 4, 16, unreal.MoviePipelineImageSequenceOutput_PNG,
           root + "/lumentest", frame_step=1, frames=(624, 625),
           extra_cvars={"r.Lumen.ScreenProbeGather.DownsampleFactor": 4,
                        "r.Lumen.ScreenProbeGather.RadianceCache.ProbeResolution": 64,
                        "r.Lumen.ScreenProbeGather.ImportanceSample.IncomingLighting": 1,
                        "r.Lumen.ScreenProbeGather.SpatialFilterNumPasses": 6})
    # ageing and smoke: five frames across the film
    preset("MRQ_AgeTest", (1920, 1080), 1, 8, unreal.MoviePipelineImageSequenceOutput_PNG,
           root + "/agetest", frame_step=960, frames=(576, 4417))
    # portico framing: every third of a second across both niche figures and the turns between them
    preset("MRQ_PorticoTest", (960, 540), 1, 8, unreal.MoviePipelineImageSequenceOutput_PNG,
           root + "/porticotest", frame_step=8, frames=(120, 568))
    # exterior sun level: two frames of the opening walk through the portico
    preset("MRQ_SunTest", (1920, 1080), 1, 8, unreal.MoviePipelineImageSequenceOutput_PNG,
           root + "/suntest", frame_step=48, frames=(0, 97))
    # attic zone: four frames of the crane pass before the final approach
    preset("MRQ_AtticTest", (1920, 1080), 1, 8, unreal.MoviePipelineImageSequenceOutput_PNG,
           root + "/attictest", frame_step=48, frames=(int((_FINAL - 7.0) * FPS), int(_FINAL * FPS)))
    # attic diagnosis on one frame: without indirect light, and with hit lighting instead of the surface cache
    for tag, cv in (("NoGI", {"r.Lumen.DiffuseIndirect.Allow": 0}),
                    ("Hit", {"r.Lumen.HardwareRayTracing.LightingMode": 2})):
        preset("MRQ_Attic" + tag, (1920, 1080), 1, 8, unreal.MoviePipelineImageSequenceOutput_PNG,
               root + "/attic_" + tag.lower(), frames=(int((_FINAL - 3.0) * FPS), int((_FINAL - 3.0) * FPS) + 1),
               extra_cvars=cv)
    # dome looks: three frames of the dome tilt and panorama
    preset("MRQ_DomeTest", (1920, 1080), 1, 8, unreal.MoviePipelineImageSequenceOutput_PNG,
           root + "/dometest", frame_step=336, frames=(864, 1540))
    # four seconds past the door braziers, for judging flame motion
    preset("MRQ_FireTest", (1920, 1080), 1, 8, unreal.MoviePipelineImageSequenceOutput_PNG,
           root + "/firetest", frames=(648, 744))
    # Lumen lighting-mode test (panorama frame 1824, Apollo hold 3744): the default above is 0 (surface cache); 1 = hit lighting
    # for reflections, 2 = full hit lighting, both of which over-brighten the pale walls
    for mode in (1, 2):
        preset("MRQ_LightMode%d" % mode, (1920, 1080), 1, 8, unreal.MoviePipelineImageSequenceOutput_PNG,
               root + "/lightmode%d" % mode, frame_step=1920, frames=(1824, 3745),
               extra_cvars={"r.Lumen.HardwareRayTracing.LightingMode": mode})
    # path tracer reference on two statue holds with bright exedra walls (Apollo, Venus in draft 6):
    # ground truth for Lumen
    pt = getattr(unreal, "MoviePipelineDeferredPass_PathTracer", None)
    if pt is not None:
        preset("MRQ_PathTraceTest", (1920, 1080), 512, 1, unreal.MoviePipelineImageSequenceOutput_PNG,
               root + "/pathtrace", frame_step=576, pass_cls=pt, frames=(3744, 4321))
    else:
        log("path tracer pass class not found; MRQ_PathTraceTest skipped")


def main():
    level_editor = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    level_editor.load_level(MAP)
    build_sequence(level_editor, actors)
    build_render_presets()


main()
