"""Paint statue scans in the style of Roman polychromy, as per-vertex colour for Unreal.

Usage (run with the pipeline's virtualenv, not with Blender's Python):
    tools/polychromy_venv/bin/python blender/paint_statues.py <key> [<key> ...]
    tools/polychromy_venv/bin/python blender/paint_statues.py --all
    tools/polychromy_venv/bin/python blender/paint_statues.py <key> --from label   # redo from a stage
    tools/polychromy_venv/bin/python blender/paint_statues.py --list

Input:  assets/statues/processed/<key>.fbx (output of process_statues.py: Z up, metres, base at z=0,
        facing -Y). Any key with an FBX there works; keys without an entry in the config files
        get the default regions and colours.
Output: assets/statues/painted/<key>.fbx  the processed mesh with exact duplicate vertices welded
        (most scans are triangle soup), smooth normals (sharp only above 50 degrees; the soup's flat
        per-face normals are dropped) and faces around the eyes and mouth subdivided so painted eyes
        are sharp; point-domain colour attribute "Col" exported as FBX vertex colours:
        RGB = paint colour (sRGB), A = paint coverage (0 bare marble, 1 opaque; skin is a 0.2-0.5
        glaze). Unreal should lerp(marble, VertexColor.rgb, VertexColor.a).
        assets/statues/painted/<key>.json  regions, vertex counts, face/eye data, verification line.
        renders/previews/painted/<key>.png  check image: front, three-quarter, face, eyes.
Config: blender/polychromy_palette.json  every colour and coverage (from reference/polychromy.md).
        blender/polychromy_regions.json  segmentation prompts, priorities and limits per statue.
        A new statue works without entries (default regions and colours); add entries to name its
        garments/attributes and give its colours, then run this script with its key.
Cache:  tools/polychromy_cache/<key>/ (renders, masks, work meshes); safe to delete. A changed
        processed FBX (mtime/size) invalidates the cache automatically.
Debug:  tools/polychromy_venv/bin/python tools/polychromy/debug_masks.py <key> body|head out.png

Software (all inside tools/polychromy_venv, Python 3.12; weights under its models/ folder):
        torch 2.15.0 (MPS), transformers 5.24.0, mediapipe 1.2.3, opencv-python-headless 5.1.0.95,
        scipy 1.18.1, numpy 2.5.5, pillow 13.0.0, OpenEXR 3.5.4; see tools/polychromy/requirements.txt.
        Models: IDEA-Research/grounding-dino-base, facebook/sam2.1-hiera-large (Hugging Face),
        MediaPipe face_landmarker.task float16 v1 (storage.googleapis.com/mediapipe-models).
        Blender 5.3 for rendering, subdivision and FBX export.

Method
 1. mesh0       Blender: import, weld, write the coarse mesh arrays.
 2. views_body  Blender Workbench renders (grey studio shading with cavity) of the whole figure from
                20 orthographic views (8 level, 8 from above, 4 from below) + depth + camera matrices.
 3. seg_body    For each region prompt: GroundingDINO boxes -> SAM 2.1 masks. Boxes that cover the
                whole figure and masks larger than a per-kind share of the silhouette are rejected
                (GroundingDINO answers phrases it cannot place with a box around everything).
 4. face        GroundingDINO "face" box -> 3D point; frontal close-ups re-aimed along the head pose
                from MediaPipe Face Landmarker (2 damped iterations, retries with other framings if
                no face is found); landmarks -> eye corners, iris centres, brows, lips, symmetrised
                about the facial midline.
 5. views_head / seg_head  16 close-ups around the head for hair, beard, face skin, head attributes.
 6. mesh        Blender: weld + local subdivision (eyes to 1/45 of the eye width, face to 1/12).
 7. label       Back-projection: every vertex is projected into every view, kept if it passes the
                depth test and faces the camera, and collects votes from the masks. Votes and
                visibility are diffused over the mesh graph (normalised); a region needs 35 % of the
                views that see a vertex; overlaps are resolved by kind priority (beard, hair,
                sandals, skin, attribute, plinth, support, garment; per-region "rank" overrides);
                the brow/eye/nose/mid-forehead hull is forced to skin; islands are merged; garment
                holes are filled; several garments are split with heavy smoothing; rest = skin.
 8. paint       Palette colours, darker in recesses / lighter or gilded on crests where configured;
                hems = band along garment edges that meet non-garment regions (smoothed geodesic
                distance) with optional ornamental lines; coverage thinned on ridges plus
                low-frequency noise (worn wash); eye white, pink inner corner, iris with darker ring,
                pupil, upper-lid line (on camera-facing surfaces), brows and lips (on skin only)
                drawn as decals from the face view. Blender writes "Col", exports FBX, re-imports it
                and checks every vertex used by a face (PAINT_VERIFY).
 9. preview     EEVEE check image with the paint over a marble-white base.
"""

import argparse
import glob
import json
import os
import subprocess
import sys
import time

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "tools"))
os.environ.setdefault("HF_HOME", os.path.join(ROOT, "tools", "polychromy_venv", "models"))
os.environ.setdefault("TRANSFORMERS_VERBOSITY", "error")

import numpy as np  # noqa: E402

from polychromy import face as facemod  # noqa: E402
from polychromy import labels as lab  # noqa: E402
from polychromy.views import View, body_views, head_views, write_views  # noqa: E402

BLENDER = os.environ.get("BLENDER", "/usr/local/bin/blender")
BLENDER_SCRIPT = os.path.join(ROOT, "blender", "polychromy_blender.py")
PROCESSED = os.path.join(ROOT, "assets", "statues", "processed")
PAINTED = os.path.join(ROOT, "assets", "statues", "painted")
PREVIEWS = os.path.join(ROOT, "renders", "previews", "painted")
CACHE = os.path.join(ROOT, "tools", "polychromy_cache")
PALETTE = os.path.join(ROOT, "blender", "polychromy_palette.json")
REGIONS = os.path.join(ROOT, "blender", "polychromy_regions.json")

STAGES = ["mesh0", "views_body", "seg_body", "face", "views_head", "seg_head", "mesh", "label", "paint", "preview"]
KIND_PRIORITY = ["beard", "hair", "sandals", "skin", "attribute", "plinth", "support", "garment"]
# height range (fraction of the statue height) where a kind may occur
KIND_ZRANGE = {"plinth": (0.0, 0.3), "beard": (0.5, 1.0), "sandals": (0.0, 0.2)}
# largest plausible mask per region kind, as a fraction of the statue's silhouette in that view;
# larger masks come from boxes GroundingDINO draws around the whole figure for a phrase it cannot place
MAX_MASK_FRAC = {"beard": 0.12, "hair": 0.3, "sandals": 0.1, "skin": 0.2, "attribute": 0.2,
                 "garment": 0.85, "support": 0.4, "plinth": 0.5}

EYE_TEMPLATE = {"upper_height": 0.20, "lower_height": 0.14, "upper_peak": 0.45, "lower_peak": 0.55,
                "iris_radius": 0.18, "iris_raise": 0.02, "pupil_ratio": 0.42, "lid_thickness": 0.07,
                "lid_wing": 0.12, "centre_offset": 0.0}


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def blender(*args):
    cmd = [BLENDER, "-b", "--factory-startup", "--python-exit-code", "1", "--python", BLENDER_SCRIPT, "--"] + list(args)
    r = subprocess.run(cmd, capture_output=True, text=True)
    out = r.stdout + r.stderr
    for line in out.splitlines():
        if any(t in line for t in ("_DONE", "WELD", "SUBDIV", "PAINT_VERIFY", "Error", "Traceback")):
            log("  blender:", line.strip())
    if r.returncode != 0:
        raise RuntimeError("Blender failed (%s):\n%s" % (args[0], out[-3000:]))
    return out


# --------------------------------------------------------------------------- config

def load_regions(key):
    cfg = json.load(open(REGIONS))
    st = cfg.get("statues", {}).get(key, {"inherit": True, "regions": []})
    if st.get("inherit", False):
        regs = {r["name"]: dict(r) for r in cfg["default_regions"]}
        for r in st.get("regions", []):
            regs[r["name"]] = dict(r)
        regs = list(regs.values())
    else:
        regs = [dict(r) for r in st.get("regions", [])]
    if st.get("beard") is False:
        regs = [r for r in regs if r["kind"] != "beard"]
    regs = [r for r in regs if r.get("prompts")]
    return regs, st


class Palette:
    def __init__(self, key):
        self.cfg = json.load(open(PALETTE))
        self.pig = self.cfg["pigments"]
        self.st = self.cfg.get("statues", {}).get(key, {})
        self.df = self.cfg["default"]

    def entry(self, name, kind=None):
        for src in (self.st, self.df):
            if name in src:
                return src[name]
            if kind and kind in src:
                return src[kind]
        raise KeyError("no palette entry for %s/%s" % (name, kind))

    def value(self, name, default=None):
        return self.st.get(name, self.df.get(name, default))

    def rgb(self, c):
        h = self.pig.get(c, c)
        h = h.lstrip("#")
        return np.array([int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)])


# --------------------------------------------------------------------------- statue run

class Run:
    def __init__(self, key):
        self.key = key
        self.fbx = os.path.join(PROCESSED, key + ".fbx")
        if not os.path.exists(self.fbx):
            raise SystemExit("no processed statue " + self.fbx)
        self.work = os.path.join(CACHE, key)
        os.makedirs(self.work, exist_ok=True)
        self.regions, self.stcfg = load_regions(key)
        self._seg = None
        self._lm = None

    # stage bookkeeping ------------------------------------------------------
    def done(self, stage):
        return os.path.exists(os.path.join(self.work, stage + ".done"))

    def mark(self, stage):
        open(os.path.join(self.work, stage + ".done"), "w").write(time.strftime("%Y-%m-%d %H:%M:%S"))

    def reset_from(self, stage):
        for s in STAGES[STAGES.index(stage):]:
            p = os.path.join(self.work, s + ".done")
            if os.path.exists(p):
                os.remove(p)

    @property
    def seg(self):
        if self._seg is None:
            from polychromy.segment import Segmenter
            log("  loading GroundingDINO + SAM 2.1")
            self._seg = Segmenter()
        return self._seg

    @property
    def lm(self):
        if self._lm is None:
            self._lm = facemod.Landmarker()
        return self._lm

    def run(self, start=None):
        # the cache belongs to one version of the processed FBX: start over if it changed
        st = os.stat(self.fbx)
        stamp = {"fbx": self.fbx, "mtime": st.st_mtime, "size": st.st_size}
        sp = os.path.join(self.work, "source.json")
        old = json.load(open(sp)) if os.path.exists(sp) else None
        if old != stamp:
            if old is not None:
                log("[%s] processed FBX changed since the cache was made: redoing all stages" % self.key)
            self.reset_from(STAGES[0])
            json.dump(stamp, open(sp, "w"))
        if start:
            self.reset_from(start)
        for s in STAGES:
            if self.done(s):
                continue
            log("[%s] %s" % (self.key, s))
            getattr(self, "stage_" + s)()
            self.mark(s)
        log("[%s] finished" % self.key)

    # 1 ---------------------------------------------------------------------
    def stage_mesh0(self):
        blender("mesh", self.fbx, os.path.join(self.work, "coarse"))

    def coarse(self):
        return np.load(os.path.join(self.work, "coarse", "mesh.npz"))

    # 2 ---------------------------------------------------------------------
    def stage_views_body(self):
        views = body_views(self.coarse()["co"])
        p = os.path.join(self.work, "views_body.json")
        write_views(p, views)
        blender("views", self.fbx, self.work, p)

    def view_names(self, group):
        return [v["name"] for v in json.load(open(os.path.join(self.work, "views_%s.json" % group)))]

    # 3, 5 ------------------------------------------------------------------
    def _segment_group(self, group):
        out = {}
        regs = [r for r in self.regions if r.get("views", "body") in (group, "both")]
        for name in self.view_names(group):
            v = View(os.path.join(self.work, "views"), name)
            im = v.image()
            for r in regs:
                m = np.zeros(v.alpha.shape, bool)
                found = []
                for prompt in r["prompts"]:
                    mmf = r.get("max_mask_frac", MAX_MASK_FRAC.get(r["kind"], 0.85))
                    if group == "head" and r["kind"] in ("hair", "beard", "skin", "attribute"):
                        mmf = max(mmf, 0.92 if r["kind"] == "hair" else 0.7)  # close-ups: the head fills the frame
                    res = self.seg.segment(im, name, prompt, v.alpha, threshold=r.get("threshold", 0.3),
                                           max_box_frac=r.get("max_box_frac", 0.8), max_mask_frac=mmf)
                    for mk, sc, b in res:
                        m |= mk
                        found.append(round(sc, 2))
                if m.any():
                    out["%s|%s" % (name, r["name"])] = np.packbits(m, axis=None)
                    out["%s|%s|shape" % (name, r["name"])] = np.array(m.shape)
            log("  %s: %s" % (name, ", ".join(k.split("|")[1] for k in out if k.startswith(name + "|") and not k.endswith("shape"))))
        np.savez_compressed(os.path.join(self.work, "masks_%s.npz" % group), **out)

    def stage_seg_body(self):
        self._segment_group("body")

    def stage_seg_head(self):
        self._segment_group("head")

    # 4 ---------------------------------------------------------------------
    def _render_view(self, spec):
        p = os.path.join(self.work, "views_%s.json" % spec["name"])
        write_views(p, [spec])
        blender("views", self.fbx, self.work, p)
        return View(os.path.join(self.work, "views"), spec["name"])

    def stage_face(self):
        info = {"found": False}
        if self.stcfg.get("face", True):
            info = self._find_face()
        json.dump(info, open(os.path.join(self.work, "face.json"), "w"), indent=1)

    def _find_face(self):
        best = None
        for az in (0, 45, 315, 90, 270):
            name = "body_e5_a%03d" % az
            v = View(os.path.join(self.work, "views"), name)
            b, s = self.seg.detect(v.image(), "face", 0.25)
            if len(b):
                i = int(s.argmax())
                # prefer frontal views: small penalty for oblique ones
                score = float(s[i]) - (0.0 if az == 0 else 0.05)
                if best is None or score > best[0]:
                    best = (score, az, v, b[i])
        if best is None:
            log("  no face found")
            return {"found": False}
        _, az, v, b = best
        cx, cy = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2
        point = v.unproject(cx, cy)
        fh = float((b[3] - b[1]) * v.pixel)
        el = 0.0
        L = None
        for it in range(3):
            res = 1024 if it < 2 else 1536
            # first iteration: if MediaPipe sees no face (helmets, turned heads, a bad DINO box),
            # retry with other framings and directions before giving up
            tries = [(0, 0, 1.5)] if it else [(0, 0, 1.5), (0, 0, 2.3), (0, -15, 1.5), (0, 0, 1.1), (-25, 0, 1.6),
                                              (25, 0, 1.6), (-45, -10, 1.8), (45, -10, 1.8), (0, 0, 3.2)]
            for k, (daz, del_, sc) in enumerate(tries):
                spec = dict(name="face_%d" % it, target=list(map(float, point)), az=float(az + daz),
                            el=float(el + del_), ortho_scale=float(sc * fh), res=[res, res], dist=float(20 * fh),
                            depth_range=float(19 * fh))
                fv = self._render_view(spec)
                L, M = self.lm.detect(fv.image())
                if L is not None:
                    if k:
                        log("  face found on retry %d (az %+d, el %+d, scale %.1f)" % (k, daz, del_, sc))
                        az, el = az + daz, el + del_
                    break
            if L is None:
                log("  MediaPipe found no face in iteration %d" % it)
                if it == 0:
                    return self._face_from_boxes(point, fh, az, el)
                break
            n = facemod.face_direction_world(fv, M)
            fh = float(np.linalg.norm(L[10] - L[152]) * fv.pixel)
            centre_px = (L[10] + L[152]) / 2
            point = fv.unproject(*centre_px)
            if not np.all(np.isfinite(point)):
                point = fv.unproject(*L[4])
            if it < 2:
                naz, nel = facemod.az_el(n)
                # damped update: MediaPipe's pose on statues is approximate
                az = az + 0.7 * (((naz - az + 180) % 360) - 180)
                el = float(np.clip(el + 0.7 * (nel - el), -25, 25))
            last = (fv, L, n)
        fv, L, n = last
        geo = facemod.face_geometry(L, sym=True)
        eyes3d = []
        for e in geo["eyes"]:
            c = (np.array(e["inner"]) + np.array(e["outer"])) / 2
            eyes3d.append(fv.unproject(*c).tolist())
        eye_w_m = float(np.mean([e["width"] for e in geo["eyes"]]) * fv.pixel)
        head_centre = (np.array(point) - n * 0.45 * fh).tolist()
        log("  face: view az %.1f el %.1f, face height %.3f m, eye width %.3f m" % (az, el, fh, eye_w_m))
        return {"found": True, "view": fv.name, "az": float(az), "el": float(el), "face_h": fh,
                "centre": list(map(float, point)), "normal": n.tolist(), "head_centre": head_centre,
                "eyes3d": eyes3d, "eye_width_m": eye_w_m, "landmarks": L.tolist(), "geometry": geo}

    def _face_from_boxes(self, point, fh, az, el):
        """MediaPipe failed: place the eye template from GroundingDINO "eye" / "lips" boxes on a
        frontal close-up. Several azimuths are tried (heads are often turned); the view whose two
        eye boxes are most alike in width (= most frontal) is used."""
        best = None
        for daz in (0, -30, 30, -55, 55):
            spec = dict(name="face_2", target=list(map(float, point)), az=float(az + daz), el=float(el),
                        ortho_scale=float(1.3 * fh), res=[1536, 1536], dist=float(20 * fh),
                        depth_range=float(19 * fh))
            fv = self._render_view(spec)
            im = fv.image()
            b, s = self.seg.detect(im, "eye", 0.15)
            ok = [(bb, sc) for bb, sc in zip(b, s) if (bb[2] - bb[0]) < 0.3 * fv.w]
            for i in range(len(ok)):
                for j in range(i + 1, len(ok)):
                    bi, bj = ok[i][0], ok[j][0]
                    ci, cj = (bi[:2] + bi[2:]) / 2, (bj[:2] + bj[2:]) / 2
                    wi, wj = bi[2] - bi[0], bj[2] - bj[0]
                    if abs(ci[1] - cj[1]) < 0.5 * max(wi, wj) and abs(ci[0] - cj[0]) > 1.2 * max(wi, wj):
                        ratio = min(wi, wj) / max(wi, wj)
                        score = ratio + 0.5 * (ok[i][1] + ok[j][1])
                        if ratio > 0.6 and (best is None or score > best[0]):
                            best = (score, daz, (bi, bj))
        if best is None:
            log("  no face: MediaPipe and the eye-box fallback both failed")
            return {"found": False, "point": list(map(float, point)), "face_h": fh}
        _, daz, pair = best
        az = az + daz
        spec = dict(name="face_2", target=list(map(float, point)), az=float(az), el=float(el),
                    ortho_scale=float(1.3 * fh), res=[1536, 1536], dist=float(20 * fh), depth_range=float(19 * fh))
        fv = self._render_view(spec)
        im = fv.image()
        mb, ms = self.seg.detect(im, "lips", 0.2)
        mouth = mb[int(ms.argmax())] if len(mb) else None
        geo = facemod.geometry_from_boxes([pair[0].tolist(), pair[1].tolist()],
                                          mouth.tolist() if mouth is not None else None)
        eyes3d = []
        for e in geo["eyes"]:
            c = (np.array(e["inner"]) + np.array(e["outer"])) / 2
            eyes3d.append(fv.unproject(*c).tolist())
        n = -fv.forward
        eye_w_m = float(geo["eyes"][0]["width"] * fv.pixel)
        log("  face from eye boxes (fallback): eye width %.3f m" % eye_w_m)
        return {"found": True, "fallback": True, "view": fv.name, "az": float(az), "el": float(el), "face_h": fh,
                "centre": list(map(float, point)), "normal": n.tolist(),
                "head_centre": (np.array(point) - n * 0.45 * fh).tolist(), "eyes3d": eyes3d,
                "eye_width_m": eye_w_m, "landmarks": None, "geometry": geo}

    def face_info(self):
        return json.load(open(os.path.join(self.work, "face.json")))

    # 5 ---------------------------------------------------------------------
    def stage_views_head(self):
        f = self.face_info()
        if "face_h" not in f:
            write_views(os.path.join(self.work, "views_head.json"), [])
            return
        centre = f.get("head_centre", f.get("point"))
        views = head_views(centre, 2.6 * f["face_h"])
        p = os.path.join(self.work, "views_head.json")
        write_views(p, views)
        blender("views", self.fbx, self.work, p)

    # 6 ---------------------------------------------------------------------
    def stage_mesh(self):
        f = self.face_info()
        regions = []
        if f.get("found"):
            ew = f["eye_width_m"]
            for c in f["eyes3d"]:
                regions.append({"centre": c, "radius": 0.9 * ew, "max_edge": ew / 45.0})
            regions.append({"centre": f["centre"], "radius": 0.75 * f["face_h"], "max_edge": ew / 12.0})
        json.dump(regions, open(os.path.join(self.work, "subdivide.json"), "w"))
        blender("mesh", self.fbx, self.work)

    # 7 ---------------------------------------------------------------------
    def stage_label(self):
        m = np.load(os.path.join(self.work, "mesh.npz"))
        co, tris, vn = m["co"].astype(np.float64), m["tris"], m["vnormal"].astype(np.float64)
        n = len(co)
        H = float(co[:, 2].max() - co[:, 2].min())
        A = lab.adjacency(tris, n)
        Al = lab.adjacency(tris, n, co)
        el = np.asarray(Al.data)
        edge = float(np.median(el))
        regs = self.regions
        R = len(regs)
        votes = np.zeros((n, R))
        vis = {"body": np.zeros(n), "head": np.zeros(n)}
        for group in ("body", "head"):
            masks = np.load(os.path.join(self.work, "masks_%s.npz" % group))
            keys = set(masks.files)
            for name in self.view_names(group):
                v = View(os.path.join(self.work, "views"), name)
                ok, px, py, facing = v.visible(co, vn)
                idx = np.where(ok)[0]
                w = np.clip(facing[idx], 0, 1) ** 0.5
                vis[group][idx] += w
                ix = np.clip(px[idx].astype(int), 0, v.w - 1)
                iy = np.clip(py[idx].astype(int), 0, v.h - 1)
                for ri, r in enumerate(regs):
                    k = "%s|%s" % (name, r["name"])
                    if k not in keys:
                        continue
                    shape = tuple(masks[k + "|shape"])
                    mk = np.unpackbits(masks[k])[:shape[0] * shape[1]].reshape(shape).astype(bool)
                    votes[idx, ri] += w * mk[iy, ix]
        # region denominators: views of the groups the region uses
        den = np.zeros((n, R))
        for ri, r in enumerate(regs):
            g = r.get("views", "body")
            den[:, ri] = (vis["body"] if g in ("body", "both") else 0) + (vis["head"] if g in ("head", "both") else 0)
        target = 0.004 * H
        iters = int(np.clip(2 * (target / edge) ** 2, 4, 150))
        log("  smoothing: edge %.4f m, %d iterations" % (edge, iters))
        num = lab.diffuse(votes, A, iters)
        dd = lab.diffuse(den, A, iters)
        p = np.where(dd > 1e-6, num / np.maximum(dd, 1e-6), 0.0)
        seen = (vis["body"] + vis["head"]) > 0
        log("  vertices seen by at least one view: %.1f%%" % (100 * seen.mean()))
        # decision by priority of kinds; within a kind the strongest region wins
        names = ["skin_default"] + [r["name"] for r in regs]
        label = np.zeros(n, np.int32)
        decided = np.zeros(n, bool)
        zrel = (co[:, 2] - co[:, 2].min()) / H
        # rank: position of the region's kind in KIND_PRIORITY, or the region's own "rank"
        # (e.g. 0.5 puts a helmet between beard and hair)
        rank = [r.get("rank", KIND_PRIORITY.index(r["kind"])) for r in regs]
        face = self.face_info()
        for rk in sorted(set(rank)):
            ids = [i for i in range(len(regs)) if rank[i] == rk]
            kind = regs[ids[0]]["kind"]
            thr = np.array([regs[i].get("vote", 0.35) for i in ids])
            pk = p[:, ids]
            ok = pk >= thr[None, :]
            for j, i in enumerate(ids):
                zmin, zmax = KIND_ZRANGE.get(regs[i]["kind"], (0.0, 1.0))
                zmin = regs[i].get("zmin_rel", zmin)
                zmax = regs[i].get("zmax_rel", zmax)
                ok[:, j] &= (zrel >= zmin) & (zrel <= zmax)
                # height limit relative to the face: zmin_face face heights above the eye line
                if "zmin_face" in regs[i] and face.get("found"):
                    eye_z = float(np.mean([e[2] for e in face["eyes3d"]]))
                    ok[:, j] &= co[:, 2] >= eye_z + regs[i]["zmin_face"] * face["face_h"]
            best = np.where(ok, pk, -1).argmax(1)
            take = ok.any(1) & ~decided
            label[take] = np.array(ids)[best[take]] + 1
            decided |= take
        # eyes, brows and nose are never hair or beard: force skin inside the hull of those landmarks
        f = self.face_info()
        if f.get("found"):
            protect = self.upper_face_mask(co, vn, f)
            skin_ids = [i + 1 for i, r in enumerate(regs) if r["kind"] == "skin" and r["name"] == "face"]
            hairy = np.isin(label, [i + 1 for i, r in enumerate(regs) if r["kind"] in ("hair", "beard")])
            label[protect & hairy] = skin_ids[0] if skin_ids else 0
            log("  upper face protected: %d vertices, %d relabelled" % (protect.sum(), (protect & hairy).sum()))
        for h in self.stcfg.get("hints", []):
            ri = names.index(h["region"])
            inside = np.linalg.norm(co - np.array(h["centre"]), axis=1) < h["radius"]
            label[inside] = ri
        vert_area = 0.87 * edge ** 2
        min_size = int(max(30, (0.012 * H) ** 2 / vert_area))
        label = lab.clean_islands(label, A, min_size)
        # several garments: which garment a vertex belongs to is decided with much heavier
        # smoothing and a large minimum patch, so the split is coherent instead of speckled
        g_ids = [i + 1 for i, r in enumerate(regs) if r["kind"] == "garment"]
        # holes in garments (unpainted islands that would get a hem ring) and stray garment
        # islands on bare figure are merged at a larger scale; other regions are left alone
        if g_ids:
            hole = int(max(min_size, (0.06 * H) ** 2 / vert_area))
            gl = np.where(np.isin(label, g_ids), g_ids[0], label)  # garments as one for this pass
            gl2 = lab.clean_islands(gl, A, hole, only=[0, g_ids[0]])
            to_g = (gl == 0) & (gl2 == g_ids[0])
            to_s = (gl == g_ids[0]) & (gl2 == 0)
            if to_g.any():
                # filled holes take the garment label that dominates around them
                ohe = np.stack([(label == g) for g in g_ids], 1).astype(float)
                nb = lab.diffuse(ohe, A, 30, keep=0.0)
                label[to_g] = np.array(g_ids)[nb[to_g].argmax(1)]
            label[to_s] = 0
        if len(g_ids) > 1:
            gm = np.isin(label, g_ids)
            q = lab.diffuse(p[:, [i - 1 for i in g_ids]] * gm[:, None], A, min(8 * iters, 600))
            label[gm] = np.array(g_ids)[q[gm].argmax(1)]
            big = int(max(min_size, (0.06 * H) ** 2 / vert_area))
            label = lab.clean_islands(label, A, big, only=g_ids)
        counts = {names[i]: int((label == i).sum()) for i in range(len(names)) if (label == i).any()}
        log("  labels:", counts)
        np.savez_compressed(os.path.join(self.work, "labels.npz"), label=label, names=np.array(names), p=p.astype(np.float16))

    def upper_face_mask(self, co, vn, f):
        """Vertices visible in the face view inside the convex hull of brow, eye and nose landmarks."""
        import cv2
        fv = View(os.path.join(self.work, "views"), f["view"])
        if f.get("landmarks") is None:
            # eye-box fallback: region from brow height to below the nose, between the outer corners
            pts = []
            for e in f["geometry"]["eyes"]:
                w, up = e["width"], np.array(e["up"])
                for c in (np.array(e["inner"]), np.array(e["outer"])):
                    pts += [c + up * 0.7 * w, c - up * 1.5 * w]
            hull_pts = np.array(pts, np.float32)
        else:
            Lm = np.array(f["landmarks"])
            ids = (facemod.R_BROW_UP + facemod.L_BROW_UP + [33, 133, 263, 362, 145, 374] +
                   [1, 2, 98, 327, 64, 294, 168, 6] + [151, 108, 337] +  # mid-forehead
                   [116, 345, 205, 425])  # upper cheeks beside the nose
            hull_pts = Lm[ids].astype(np.float32)
        hull = cv2.convexHull(hull_pts).astype(np.int32)
        img = np.zeros((fv.h, fv.w), np.uint8)
        cv2.fillPoly(img, [hull], 1)
        near = np.linalg.norm(co - np.array(f["centre"]), axis=1) < 1.0 * f["face_h"]
        idx = np.where(near)[0]
        # loose depth test: anything within 0.3 eye widths behind the visible surface (eye sockets,
        # under the lid fold) counts; the strict test misses vertices next to occluding edges
        px, py, d = fv.project(co[idx])
        ix = np.clip(px.astype(int), 0, fv.w - 1)
        iy = np.clip(py.astype(int), 0, fv.h - 1)
        ok = d <= fv.depth[iy, ix] + 0.3 * f["eye_width_m"]
        out = np.zeros(len(co), bool)
        out[idx[ok]] = img[iy[ok], ix[ok]] > 0
        return out

    # 8 ---------------------------------------------------------------------
    def stage_paint(self):
        m = np.load(os.path.join(self.work, "mesh.npz"))
        co, tris, vn = m["co"].astype(np.float64), m["tris"], m["vnormal"].astype(np.float64)
        n = len(co)
        H = float(co[:, 2].max() - co[:, 2].min())
        L = np.load(os.path.join(self.work, "labels.npz"))
        label, names = L["label"], list(L["names"])
        regs = {r["name"]: r for r in self.regions}
        pal = Palette(self.key)
        A = lab.adjacency(tris, n)
        Al = lab.adjacency(tris, n, co)
        rgb = np.zeros((n, 3))
        alpha = np.zeros(n)
        kinds = {}
        # concavity: +1 in folds, drill channels and recesses, -1 on crests and ridges
        cav = lab.cavity(co, vn, A)
        z = np.clip(cav / (np.percentile(np.abs(cav), 90) + 1e-9), -1, 1)
        for i, name in enumerate(names):
            sel = label == i
            if not sel.any():
                continue
            kind = "skin" if name == "skin_default" else regs[name]["kind"]
            kinds[name] = kind
            e = pal.entry("skin" if name == "skin_default" else name, kind)
            if kind == "plinth":
                if e.get("mode", "bare") == "bare":
                    continue
                up = sel & (vn[:, 2] > 0.8)
                top = float(np.median(co[up, 2])) if up.sum() > 20 else float(np.percentile(co[sel, 2], 90))
                band = e.get("band_rel", 0.01) * H
                side = np.abs(vn[:, 2]) < 0.5
                bsel = sel & side & (co[:, 2] < top - 0.4 * band) & (co[:, 2] > top - 1.4 * band)
                rgb[bsel] = pal.rgb(e["color"])
                alpha[bsel] = e["alpha"]
                continue
            rgb[sel] = pal.rgb(e["color"])
            alpha[sel] = e["alpha"]
            # optional shading in the paint: darker in recesses, lighter (or gilded) on crests
            for key_, sign in (("recess", 1), ("crest", -1)):
                sh = e.get(key_)
                if sh:
                    k = np.clip(sign * z[sel], 0, 1) * sh.get("mix", 0.5)
                    rgb[sel] = rgb[sel] * (1 - k[:, None]) + pal.rgb(sh["color"])[None, :] * k[:, None]
        # worn wash: thinner on ridges, fuller in folds; low-frequency variation
        wear = float(pal.value("wear", 0.3))
        noise = lab.value_noise(co, 0.04 * H, seed=7)
        wash = float(pal.value("wash_noise", 0.12))
        mod = (1 - wear * 0.5 * (1 - z)) * (1 + wash * (2 * noise - 1))
        painted = alpha > 0
        alpha = np.where(painted, np.clip(alpha * mod, 0, 1), 0)
        # hems
        for i, name in enumerate(names):
            if kinds.get(name) != "garment":
                continue
            e = pal.entry(name, "garment")
            b = e.get("border")
            if not b:
                continue
            width = b.get("width_rel", 0.007) * H
            # hems only where the garment meets something that is not a garment: seams between
            # two garments are where the segmentation is least reliable
            is_garment = np.isin(label, [j for j, nm in enumerate(names) if kinds.get(nm) == "garment"])
            d = lab.boundary_distance(label, label == i, Al, width * 1.2, outside=~is_garment)
            # edge-graph distances zigzag on coarse meshes: smooth the field inside the garment
            reg = label == i
            dc = np.where(np.isfinite(d), d, width * 1.3)
            dc = np.where(reg, lab.diffuse(dc, A, 4, keep=0.4), np.inf)
            d = np.where(reg & (dc < width * 1.2), dc, np.inf)
            cov = np.clip((width - d) / (0.25 * width), 0, 1)
            cov[~np.isfinite(d)] = 0
            ba = b["alpha"] * np.clip(mod, 0.6, 1.2) * cov
            rgb, alpha = over(rgb, alpha, pal.rgb(b["color"]), ba)
            # ornamental lines inside the band: pos and width as fractions of the band width
            for ln in b.get("lines", []):
                c0, hw = ln["pos"] * width, 0.5 * ln["width"] * width
                lc = np.clip((hw - np.abs(d - c0)) / max(0.3 * hw, 1e-6), 0, 1)
                lc[~np.isfinite(d)] = 0
                rgb, alpha = over(rgb, alpha, pal.rgb(ln["color"]), ln.get("alpha", 1.0) * lc)
        # face decals
        f = self.face_info()
        decal_counts = {}
        if f.get("found"):
            rgb, alpha, decal_counts = self.paint_face(co, vn, f, pal, rgb, alpha, Al, label, names)
        rgba = np.c_[np.clip(rgb, 0, 1), np.clip(alpha, 0, 1)].astype(np.float32)
        np.savez_compressed(os.path.join(self.work, "paint.npz"), rgba=rgba)
        out_fbx = os.path.join(PAINTED, self.key + ".fbx")
        out = blender("paint", self.work, out_fbx)
        ver = [l for l in out.splitlines() if l.startswith("PAINT_VERIFY")]
        info = {"key": self.key, "source": os.path.relpath(self.fbx, ROOT), "vertices": n, "triangles": int(len(tris)),
                "regions": {nm: {"kind": kinds.get(nm), "vertices": int((label == i).sum())}
                            for i, nm in enumerate(names) if (label == i).any()},
                "decal_vertices": decal_counts, "verify": ver[-1] if ver else None,
                "face": {k: f.get(k) for k in ("found", "az", "el", "face_h", "eye_width_m", "eyes3d")},
                "palette": os.path.relpath(PALETTE, ROOT),
                "colour_attribute": "Col (point domain, exported as FBX vertex colours, sRGB RGB + linear A)"}
        json.dump(info, open(os.path.join(PAINTED, self.key + ".json"), "w"), indent=1)

    def paint_face(self, co, vn, f, pal, rgb, alpha, Al, label, names):
        fv = View(os.path.join(self.work, "views"), f["view"])
        near = np.linalg.norm(co - np.array(f["centre"]), axis=1) < 1.0 * f["face_h"]
        idx = np.where(near)[0]
        ok, px, py, facing = fv.visible(co[idx], vn[idx], tol_px=1.5, min_facing=0.1)
        idx, px, py, facing = idx[ok], px[ok], py[ok], facing[ok]
        geo = f["geometry"]
        # soft edge ~ local edge length in pixels
        A = Al.tocoo()
        el = np.bincount(A.row, A.data, minlength=len(co)) / np.maximum(np.bincount(A.row, minlength=len(co)), 1)
        soft = max(0.75, float(np.median(el[idx])) / fv.pixel) if len(idx) else 1.0
        P = dict(EYE_TEMPLATE)
        P.update(self.stcfg.get("eye_template", {}))
        t_iris = np.mean([e["t_iris"] for e in geo["eyes"]])
        P["centre_offset"] = P.get("centre_offset", 0.0) + float(np.clip(t_iris, -0.08, 0.08)) * 0.5
        counts = {}
        lay = {}
        for e in geo["eyes"]:
            el_ = facemod.eye_layers(px, py, e, P, soft)
            # steep surfaces (the underside of the lid fold) make sliver triangles in the view:
            # keep the lid line on surfaces that face the camera
            el_["lid_line"] = el_["lid_line"] * np.clip((facing - 0.35) / 0.25, 0, 1)
            for k, c in el_.items():
                lay[k] = np.maximum(lay.get(k, 0), c)
        brow = 0
        for b in geo["brows"]:
            line, thick = np.array(b["line"]), np.array(b["thick"])
            # MediaPipe brows run outer -> inner; the inner end dips into the eye socket on deep-set
            # eyes, so trim the innermost 10 % and keep the stroke on camera-facing surfaces only
            t = np.linspace(0, 1, len(line))
            tt = np.linspace(0, 0.9, 12)
            line = np.c_[np.interp(tt, t, line[:, 0]), np.interp(tt, t, line[:, 1])]
            thick = np.interp(tt, t, thick)
            brow = np.maximum(brow, facemod.polyline_band(px, py, line, thick * 0.45, soft))
        lay["eyebrows"] = brow * (facing > 0.45)
        lay["lips"] = facemod.polygon_cov(px, py, geo["lips"], soft) if len(geo["lips"]) else 0 * px
        # lips only on skin (under a moustache the beard stays beard)
        lab_here = np.array(names)[label[idx]]
        skinish = np.isin(lab_here, ["skin_default"] + [r["name"] for r in self.regions if r["kind"] == "skin"])
        lay["lips"] = lay["lips"] * skinish
        for k in ("eyebrows", "lips", "eye_white", "eye_corner", "iris", "iris_ring", "pupil", "lid_line"):
            c = lay.get(k, 0)
            if np.ndim(c) == 0:
                continue
            try:
                e = pal.entry(k)
            except KeyError:
                continue
            sub_rgb, sub_a = rgb[idx], alpha[idx]
            sub_rgb, sub_a = over(sub_rgb, sub_a, pal.rgb(e["color"]), e["alpha"] * c)
            rgb[idx], alpha[idx] = sub_rgb, sub_a
            counts[k] = int((c > 0.5).sum())
        log("  decals:", counts)
        return rgb, alpha, counts

    # 9 ---------------------------------------------------------------------
    def stage_preview(self):
        co = self.coarse()["co"]
        lo, hi = co.min(0), co.max(0)
        H = float(hi[2] - lo[2])
        c = ((lo + hi) / 2).tolist()
        r = float(np.sqrt(((co[:, :2] - np.array(c[:2])) ** 2).sum(1)).max())
        scale = 1.05 * max(H, 2 * r)
        hp = 1200
        wp = int(round(hp * min(1.0, 2 * r * 1.05 / scale) / 8)) * 8
        views = [dict(name="front", target=c, az=0, el=5, ortho_scale=scale, res=[wp, hp], dist=3 * H, depth_range=2 * H),
                 dict(name="threequarter", target=c, az=35, el=10, ortho_scale=scale * 1.05, res=[wp, hp], dist=3 * H, depth_range=2 * H)]
        f = self.face_info()
        if f.get("found"):
            views.append(dict(name="face", target=f["centre"], az=f["az"], el=f["el"], ortho_scale=1.25 * f["face_h"],
                              res=[hp, hp], dist=20 * f["face_h"], depth_range=19 * f["face_h"]))
            eyes = np.mean(np.array(f["eyes3d"]), 0).tolist()
            views.append(dict(name="eyes", target=eyes, az=f["az"], el=f["el"], ortho_scale=0.62 * f["face_h"],
                              res=[hp, hp // 2], dist=20 * f["face_h"], depth_range=19 * f["face_h"]))
        elif "face_h" in f:
            views.append(dict(name="head", target=f["point"], az=0, el=5, ortho_scale=2.5 * f["face_h"],
                              res=[hp, hp], dist=20 * f["face_h"], depth_range=19 * f["face_h"]))
        p = os.path.join(self.work, "preview.json")
        json.dump({"views": views}, open(p, "w"))
        os.makedirs(PREVIEWS, exist_ok=True)
        blender("preview", os.path.join(PAINTED, self.key + ".fbx"), self.work,
                os.path.join(PREVIEWS, self.key + ".png"), p)


def over(rgb, a, c, ca):
    """Paint layer (colour c, coverage ca) over existing paint (rgb, a); unpremultiplied."""
    ca = np.asarray(ca, dtype=np.float64)
    if ca.ndim == 0:
        ca = np.full(len(a), float(ca))
    na = ca + a * (1 - ca)
    w = np.where(na > 1e-6, ca / np.maximum(na, 1e-6), 0)
    nrgb = rgb * (1 - w[:, None]) + np.asarray(c)[None, :] * w[:, None]
    return nrgb, na


def all_keys():
    return sorted(os.path.splitext(os.path.basename(p))[0] for p in glob.glob(os.path.join(PROCESSED, "*.fbx")))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("keys", nargs="*")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--from", dest="start", choices=STAGES)
    a = ap.parse_args()
    if a.list:
        print(" ".join(all_keys()))
        return
    keys = all_keys() if a.all else a.keys
    if not keys:
        ap.error("give statue keys or --all")
    failed = []
    for k in keys:
        try:
            Run(k).run(a.start)
        except Exception as ex:  # keep going with the other statues
            import traceback
            traceback.print_exc()
            log("[%s] FAILED: %s" % (k, ex))
            failed.append(k)
    if failed:
        log("failed:", " ".join(failed))
        sys.exit(1)


if __name__ == "__main__":
    main()
