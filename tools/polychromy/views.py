"""Camera views: specification, loading of Blender renders, projection and per-vertex visibility."""

import json
import os

import numpy as np
from PIL import Image

BG_RGB = (70, 70, 72)  # background the segmentation models see behind the statue


def body_views(co, res_h=1536):
    """Orthographic views of the whole figure: 8 azimuths level, 8 from above, 4 from below."""
    lo, hi = co.min(0), co.max(0)
    c = (lo + hi) / 2
    H = float(hi[2] - lo[2])
    r = float(np.sqrt(((co[:, :2] - c[:2]) ** 2).sum(1)).max())
    scale = 1.04 * max(H, 2 * r)
    wp = int(round(res_h * min(1.0, 2 * r * 1.04 / scale) / 8)) * 8
    views = []
    for el, step in ((5, 45), (35, 45), (-25, 90)):
        for az in range(0, 360, step):
            views.append(dict(name="body_e%d_a%03d" % (el, az), target=c.tolist(), az=az, el=el,
                              ortho_scale=float(scale * (1.15 if el else 1.0)), res=[max(wp, 256), res_h],
                              dist=float(3 * H), depth_range=float(2 * H)))
    return views


def head_views(centre, size, res=1024):
    """Close-ups around the head: 8 azimuths level, 4 from above, 4 from below (beard, chin)."""
    views = []
    for el, step in ((5, 45), (40, 90), (-35, 90)):
        for az in range(0, 360, step):
            views.append(dict(name="head_e%d_a%03d" % (el, az), target=list(map(float, centre)), az=az, el=el,
                              ortho_scale=float(size), res=[res, res], dist=float(20 * size),
                              depth_range=float(19 * size)))
    return views


class View:
    def __init__(self, viewdir, name):
        self.name = name
        base = os.path.join(viewdir, name)
        with open(base + ".json") as fh:
            cj = json.load(fh)
        self.spec = cj["view"]
        self.P = np.array(cj["P"], dtype=np.float64)
        self.V = np.array(cj["V"], dtype=np.float64)
        self.w, self.h = cj["w"], cj["h"]
        self.forward = np.array(cj["forward"], dtype=np.float64)
        self.location = np.array(cj["location"], dtype=np.float64)
        self.rgba = np.array(Image.open(base + ".png").convert("RGBA"))
        self.alpha = self.rgba[:, :, 3] > 127
        self.depth = read_depth(base + ".exr")
        self.ortho = cj["type"] == "ORTHO"
        # world size of one pixel (orthographic views)
        self.pixel = float(self.spec.get("ortho_scale", 1.0)) / max(self.w, self.h)

    def image(self):
        """RGB image composited over the neutral background, as PIL image."""
        im = Image.fromarray(self.rgba, "RGBA")
        bg = Image.new("RGBA", im.size, BG_RGB + (255,))
        return Image.alpha_composite(bg, im).convert("RGB")

    def project(self, X):
        """World points (N,3) -> pixel x, pixel y (floats, y down), view depth (N,)."""
        Xh = np.c_[X, np.ones(len(X))]
        cam = Xh @ self.V.T
        clip = cam @ self.P.T
        ndc = clip[:, :3] / clip[:, 3:4]
        px = (ndc[:, 0] + 1) * 0.5 * self.w
        py = (1 - ndc[:, 1]) * 0.5 * self.h
        return px, py, -cam[:, 2]

    def unproject(self, px, py):
        """Pixel (centre) -> world point on the surface using the depth buffer."""
        d = float(self.depth[int(py), int(px)])
        ndc_x = (px / self.w) * 2 - 1
        ndc_y = 1 - (py / self.h) * 2
        Pi = np.linalg.inv(self.P)
        # orthographic: camera-space x, y are linear in ndc; z = -d
        near = Pi @ np.array([ndc_x, ndc_y, -1.0, 1.0])
        near = near[:3] / near[3]
        if self.ortho:
            cam = np.array([near[0], near[1], -d])
        else:
            cam = near / -near[2] * d
        Vi = np.linalg.inv(self.V)
        return (Vi @ np.r_[cam, 1.0])[:3]

    def visible(self, X, N=None, tol_px=2.0, min_facing=0.05):
        """Visibility of points by depth test against the rendered depth buffer.
        Returns (mask, px, py, facing). facing = cos between normal and direction to camera."""
        px, py, d = self.project(X)
        ix = np.floor(px).astype(np.int64)
        iy = np.floor(py).astype(np.int64)
        inside = (ix >= 1) & (iy >= 1) & (ix < self.w - 1) & (iy < self.h - 1)
        zb = np.full(len(X), np.inf)
        ii = np.where(inside)[0]
        # minimum depth in a 3x3 neighbourhood: conservative near occluding edges
        zmin = np.full(len(ii), np.inf)
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                zmin = np.minimum(zmin, self.depth[iy[ii] + dy, ix[ii] + dx])
        zb[ii] = zmin
        tol = tol_px * self.pixel * 1.5
        vis = inside & (d <= zb + tol)
        if N is not None:
            to_cam = -self.forward[None, :] if self.ortho else (self.location[None, :] - X)
            to_cam = to_cam / np.linalg.norm(to_cam, axis=1, keepdims=True)
            facing = (N * to_cam).sum(1)
            vis &= facing > min_facing
        else:
            facing = np.ones(len(X))
        return vis, px, py, facing


def read_depth(path):
    import OpenEXR
    f = OpenEXR.File(path)
    for part in f.parts:
        for k, v in part.channels.items():
            if k.endswith("Depth.Z") or k.endswith(".Z") or k == "Z":
                z = np.array(v.pixels, dtype=np.float32)
                z[z > 1e9] = np.inf
                return z
    raise RuntimeError("no depth channel in " + path)


def write_views(path, views):
    with open(path, "w") as fh:
        json.dump(views, fh, indent=0)
