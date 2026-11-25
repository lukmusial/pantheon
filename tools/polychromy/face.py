"""Face landmarks on a frontal statue render (MediaPipe Face Landmarker) and painted-eye decals.

Statue eyes are blank and the scans are soft, so MediaPipe's lid contours are unreliable (it tends
to see the eyes nearly closed); its eye corners, eye centres, brows and mouth are good. The eyes are
therefore drawn from a template fitted to the corners (almond opening, iris, pupil, upper-lid
line) and made symmetric by mirroring about the facial midline.
All shapes live in the pixel space of the frontal face view; vertices are tested after projection
into that view.
"""

import math
import os

import numpy as np

MODEL = os.path.join(os.path.dirname(__file__), "..", "polychromy_venv", "models", "mediapipe",
                     "face_landmarker.task")

# MediaPipe face-mesh indices (subject's right = image left)
R_IN, R_OUT, L_IN, L_OUT = 133, 33, 362, 263
R_IRIS, L_IRIS = 468, 473
MIDLINE = [10, 151, 9, 8, 168, 6, 197, 195, 5, 4, 1, 2, 164, 0, 17, 18, 200, 199, 175, 152]
R_BROW_UP, R_BROW_LO = [70, 63, 105, 66, 107], [46, 53, 52, 65, 55]
L_BROW_UP, L_BROW_LO = [300, 293, 334, 296, 336], [276, 283, 282, 295, 285]
LIPS_OUTER = [61, 146, 91, 181, 84, 17, 314, 405, 321, 375, 291, 409, 270, 269, 267, 0, 37, 39, 40, 185]


class Landmarker:
    def __init__(self):
        from mediapipe.tasks.python import BaseOptions, vision
        opts = vision.FaceLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=os.path.abspath(MODEL)), num_faces=1,
            output_facial_transformation_matrixes=True, min_face_detection_confidence=0.1,
            min_face_presence_confidence=0.1)
        self.lm = vision.FaceLandmarker.create_from_options(opts)

    def detect(self, image):
        import mediapipe as mp
        r = self.lm.detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=np.ascontiguousarray(np.array(image))))
        if not r.face_landmarks:
            return None, None
        w, h = image.size
        L = np.array([[p.x * w, p.y * h] for p in r.face_landmarks[0]])
        M = np.array(r.facial_transformation_matrixes[0])
        return L, M


def face_direction_world(view, M):
    """Face normal (pointing out of the face) in world space from MediaPipe's transformation."""
    n = M[:3, 2]
    Vi = np.linalg.inv(view.V)
    nw = n[0] * Vi[:3, 0] + n[1] * Vi[:3, 1] + n[2] * Vi[:3, 2]
    return nw / np.linalg.norm(nw)


def az_el(d):
    return math.degrees(math.atan2(d[0], -d[1])), math.degrees(math.asin(max(-1, min(1, d[2]))))


# --------------------------------------------------------------------------- template geometry

def _midline(L):
    """Fit x = a*y + b through midline landmarks; returns (point, unit direction pointing down)."""
    P = L[MIDLINE]
    c = P.mean(0)
    u, s, vt = np.linalg.svd(P - c)
    d = vt[0]
    if d[1] < 0:
        d = -d
    return c, d


def _mirror(p, c, d):
    v = p - c
    along = (v @ d) * d
    return c + 2 * along - v


def face_geometry(L, sym=True):
    """Eye corners, brow strokes and lip polygon in view pixels, symmetrised about the midline."""
    c, d = _midline(L)
    g = {"midline": [c.tolist(), d.tolist()]}
    rin, rout, lin, lout = L[R_IN], L[R_OUT], L[L_IN], L[L_OUT]
    riris, liris = L[R_IRIS], L[L_IRIS]
    if sym:
        rin, lin = (rin + _mirror(lin, c, d)) / 2, (lin + _mirror(rin, c, d)) / 2
        rout, lout = (rout + _mirror(lout, c, d)) / 2, (lout + _mirror(rout, c, d)) / 2
        riris, liris = (riris + _mirror(liris, c, d)) / 2, (liris + _mirror(riris, c, d)) / 2
    g["eyes"] = []
    for name, i0, o0, ir in (("right", rin, rout, riris), ("left", lin, lout, liris)):
        w = float(np.linalg.norm(o0 - i0))
        u = (o0 - i0) / w
        n_up = np.array([u[1], -u[0]])
        if n_up[1] > 0:  # image y points down: "up" must have negative y
            n_up = -n_up
        # vertical placement: MediaPipe's iris centre height relative to the corner line
        t_iris = float((ir - i0) @ n_up / w)
        g["eyes"].append({"name": name, "inner": i0.tolist(), "outer": o0.tolist(), "width": w,
                          "u": u.tolist(), "up": n_up.tolist(), "t_iris": t_iris})
    # brows: centre line between upper and lower contour, thickness from their spacing
    brows = []
    for up, lo in ((R_BROW_UP, R_BROW_LO), (L_BROW_UP, L_BROW_LO)):
        U, Lo = L[up], L[lo]
        # stroke centre nearer the upper contour: the lower contour often reaches the underside
        # of the brow ridge, which faces down and is not where the painted brow sits
        brows.append((0.6 * U + 0.4 * Lo, np.linalg.norm(U - Lo, axis=1)))
    if sym:
        (rc, rt), (lc, lt) = brows
        rc2 = (rc + np.array([_mirror(p, c, d) for p in lc])) / 2
        lc2 = (lc + np.array([_mirror(p, c, d) for p in rc])) / 2
        t = (rt + lt) / 2
        brows = [(rc2, t), (lc2, t)]
    g["brows"] = [{"line": b[0].tolist(), "thick": b[1].tolist()} for b in brows]
    lips = L[LIPS_OUTER]
    if sym:
        mir = np.array([_mirror(p, c, d) for p in lips])
        # mirrored polygon has reversed left/right order: pair each point with nearest mirrored one
        from scipy.spatial import cKDTree
        idx = cKDTree(mir).query(lips)[1]
        lips = (lips + mir[idx]) / 2
    g["lips"] = lips.tolist()
    g["iod"] = float(np.linalg.norm(np.array(g["eyes"][0]["inner"]) - np.array(g["eyes"][1]["inner"])))
    return g


def _smoothstep_cov(sd, soft):
    """Coverage from a signed distance (negative inside), soft edge of width `soft`."""
    return np.clip(0.5 - sd / max(soft, 1e-6), 0.0, 1.0)


def eye_layers(px, py, eye, P, soft):
    """Coverage of sclera, iris, pupil and upper-lid line for points (px,py) for one eye.
    P: template parameters (fractions of eye width)."""
    i0 = np.array(eye["inner"])
    u = np.array(eye["u"])
    up = np.array(eye["up"])
    w = eye["width"]
    q = np.c_[px, py] - i0
    s = (q @ u) / w
    t = (q @ up) / w
    sc = np.clip(s, 0, 1)
    peak_up, peak_lo = P["upper_peak"], P["lower_peak"]

    def arc(sv, peak, height, power):
        # asymmetric arc: 0 at the corners, `height` at sv = peak
        x = np.where(sv < peak, sv / peak * 0.5, 0.5 + (sv - peak) / (1 - peak) * 0.5)
        return height * np.sin(np.pi * np.clip(x, 0, 1)) ** power

    t_off = P.get("centre_offset", 0.0) + eye.get("t_shift", 0.0)
    t_up = arc(sc, peak_up, P["upper_height"], 0.75) + t_off
    t_lo = -arc(sc, peak_lo, P["lower_height"], 0.9) + t_off
    # signed distance (in eye-width units) to the almond opening
    sd_open = np.maximum.reduce([t - t_up, t_lo - t, -s, s - 1])
    cov_open = _smoothstep_cov(sd_open * w, soft)
    ic = np.array([0.5 + P.get("iris_shift", 0.0), t_off + P["iris_raise"]])
    r_iris = P["iris_radius"]
    dist = np.sqrt((s - ic[0]) ** 2 + (t - ic[1]) ** 2)
    cov_iris = _smoothstep_cov((dist - r_iris) * w, soft) * cov_open
    cov_pupil = _smoothstep_cov((dist - r_iris * P["pupil_ratio"]) * w, soft) * cov_open
    # upper-lid line: band just above the upper lid curve, thickest in the middle, small wing
    s_ext = np.clip((s + 0.03) / (1 + 0.03 + P["lid_wing"]), 0, 1)
    thick = P["lid_thickness"] * (0.35 + 0.65 * np.sin(np.pi * s_ext) ** 0.6)
    t_up_ext = arc(np.clip(s, 0, 1), peak_up, P["upper_height"], 0.75) + t_off
    # past the outer corner the line continues slightly upwards (wing)
    t_up_ext = np.where(s > 1, t_off + (s - 1) * 0.35, t_up_ext)
    band = np.maximum.reduce([(t_up_ext - 0.01) - t, t - (t_up_ext + thick), -0.03 - s, s - (1 + P["lid_wing"])])
    cov_lid = _smoothstep_cov(band * w, soft)
    # darker limbal ring on the outer part of the iris; pink caruncle at the inner corner
    ring = P.get("ring_width", 0.22) * r_iris
    cov_ring = cov_iris * np.clip((dist - (r_iris - ring)) * w / max(soft, 1e-6) + 0.5, 0, 1)
    dc = np.sqrt((s - 0.02) ** 2 + (t - t_off) ** 2)
    cov_corner = _smoothstep_cov((dc - P.get("corner_radius", 0.08)) * w, soft) * (1 - cov_iris)
    return {"eye_white": cov_open, "iris": cov_iris, "iris_ring": cov_ring, "pupil": cov_pupil,
            "lid_line": cov_lid, "eye_corner": cov_corner}


def polyline_band(px, py, line, thick, soft, taper=True):
    """Coverage of a stroke along a polyline with per-point thickness (full width)."""
    pts = np.c_[px, py]
    line = np.asarray(line)
    thick = np.asarray(thick)
    best = np.full(len(pts), np.inf)
    n = len(line)
    for k in range(n - 1):
        a, b = line[k], line[k + 1]
        ab = b - a
        L2 = float(ab @ ab) + 1e-12
        tt = np.clip(((pts - a) @ ab) / L2, 0, 1)
        proj = a + tt[:, None] * ab
        dist = np.linalg.norm(pts - proj, axis=1)
        frac = (k + tt) / (n - 1)
        th = np.interp(k + tt, np.arange(n), thick)
        if taper:
            th = th * (0.45 + 0.55 * np.sin(np.pi * np.clip(frac * 0.85 + 0.15, 0, 1)))
        best = np.minimum(best, dist - th / 2)
    return _smoothstep_cov(best, soft)


def polygon_cov(px, py, poly, soft):
    import cv2
    poly = np.asarray(poly, dtype=np.float32).reshape(-1, 1, 2)
    sd = np.array([-cv2.pointPolygonTest(poly, (float(x), float(y)), True) for x, y in zip(px, py)])
    return _smoothstep_cov(sd, soft)


def geometry_from_boxes(eye_boxes, mouth_box=None):
    """Fallback when MediaPipe finds no face: eye template from two GroundingDINO "eye" boxes
    (x0, y0, x1, y1, image pixels) and an optional mouth box. Same structure as face_geometry()."""
    (a, b) = sorted(eye_boxes, key=lambda bx: bx[0] + bx[2])  # image left = subject's right eye
    ca = np.array([(a[0] + a[2]) / 2, (a[1] + a[3]) / 2])
    cb = np.array([(b[0] + b[2]) / 2, (b[1] + b[3]) / 2])
    w = 0.85 * float(np.mean([a[2] - a[0], b[2] - b[0]]))  # boxes include the lids
    axis = (cb - ca) / np.linalg.norm(cb - ca)
    mid = (ca + cb) / 2
    half = np.linalg.norm(cb - ca) / 2
    up = np.array([axis[1], -axis[0]])
    if up[1] > 0:
        up = -up
    g = {"midline": [mid.tolist(), (-up).tolist()], "eyes": [], "brows": [], "fallback": "dino_boxes"}
    for side, sgn in (("right", -1), ("left", 1)):
        c = mid + sgn * half * axis
        inner = c - sgn * axis * w / 2
        outer = c + sgn * axis * w / 2
        u = (outer - inner) / w
        n_up = np.array([u[1], -u[0]])
        if n_up[1] > 0:
            n_up = -n_up
        g["eyes"].append({"name": side, "inner": inner.tolist(), "outer": outer.tolist(), "width": w,
                          "u": u.tolist(), "up": n_up.tolist(), "t_iris": 0.0})
        s = np.linspace(-0.1, 1.15, 6)
        line = [(outer + (inner - outer) * t + up * w * (0.55 + 0.12 * np.sin(np.pi * t))).tolist() for t in s]
        g["brows"].append({"line": line, "thick": [0.22 * w] * len(line)})
    if mouth_box is not None:
        mc = np.array([(mouth_box[0] + mouth_box[2]) / 2, (mouth_box[1] + mouth_box[3]) / 2])
        rx = 0.42 * (mouth_box[2] - mouth_box[0])
        ry = 0.3 * (mouth_box[3] - mouth_box[1])
        ang = np.linspace(0, 2 * np.pi, 20, endpoint=False)
        g["lips"] = [(mc + rx * np.cos(t) * axis - ry * np.sin(t) * up).tolist() for t in ang]
    else:
        g["lips"] = []
    g["iod"] = float(2 * half - w)
    return g
