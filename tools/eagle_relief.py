"""Height map of the Trajanic eagle relief (Santi Apostoli, Rome) for the pediment's gilded bronze eagle.

    tools/polychromy_venv/bin/python -I tools/eagle_relief.py

The user asked (2026-11-25) for a good model, or one made with a visual model, instead of a hand-drawn
eagle. No downloadable scan of a Roman eagle relief was found, so the relief is taken from a photo of
the real one: Depth Anything V2 (run locally) estimates its depth, a plane fitted to the slab behind it
is subtracted, and what stands proud of the slab is kept. The slab's upper moulding is cut away outside
the wreath. Writes, in assets/eagle/:
    eagle_height.npy   float32, rows top to bottom, 0 on the slab, 1 at the highest point
    eagle_mask.png     the cut-out
    eagle_preview.png  the height map shaded from the upper left, to check by eye
The photo is by Sailko, CC BY 3.0 (assets/eagle/photos/SOURCES.md). Only the model's weights are
downloaded (Hugging Face); the photo is not sent anywhere.
"""
import os

import numpy as np
import torch
from PIL import Image, ImageFilter
from scipy import ndimage
from transformers import AutoImageProcessor, AutoModelForDepthEstimation

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
PHOTO = os.path.join(ROOT, "assets/eagle/photos/eagle_sailko_4_3840.jpg")
OUT = os.path.join(ROOT, "assets/eagle")
MODEL = "depth-anything/Depth-Anything-V2-Large-hf"
CROP = (0, 50, 3840, 1856)       # the relief between the slab's mouldings, in the 3840 px photo
WIDTH = 900                      # columns of the height map
WREATH = (1930.0, 960.0, 920.0)  # centre x, y and outer radius of the wreath, photo pixels
BIRD_SLAB_PERCENTILE = float(os.environ.get("EAGLE_SLAB_P", 32))   # share of the disc that is bare slab
BIRD_GAMMA = float(os.environ.get("EAGLE_GAMMA", 0.5))
INNER = 690.0                    # the wreath's inner edge (photo pixels): the bird's disc inside it
RIBBONS_TOP = 1250.0             # photo y: below it, the ribbons either side of the wreath
MOULDING_TOP = 1770.0            # photo y: the slab's lower moulding starts here
THRESHOLD = float(os.environ.get("EAGLE_THRESHOLD", 0.05))   # height (of the maximum) above which a pixel is relief
OPENING = int(os.environ.get("EAGLE_OPENING", 91))             # pixels: wider than any carved form


def depth_map(img):
    device = "mps" if torch.backends.mps.is_available() else "cpu"
    proc = AutoImageProcessor.from_pretrained(MODEL)
    model = AutoModelForDepthEstimation.from_pretrained(MODEL).to(device).eval()
    # two input sizes, averaged: finer detail than the default 518 alone
    outs = []
    for size in (518, 770):
        w = img.width * size // img.height // 14 * 14
        inputs = proc(images=img, return_tensors="pt", size={"height": size, "width": w}, do_resize=True,
                      keep_aspect_ratio=False)
        with torch.no_grad():
            pred = model(**{k: v.to(device) for k, v in inputs.items()}).predicted_depth
        pred = torch.nn.functional.interpolate(pred[:, None], size=(img.height, img.width), mode="bicubic",
                                               align_corners=False)[0, 0].cpu().numpy()
        outs.append((pred - pred.min()) / (pred.max() - pred.min()))
    return np.mean(outs, axis=0)


def fit_plane(d, keep):
    """Least-squares plane through the pixels where keep is true, over the whole image."""
    h, w = d.shape
    yy, xx = np.mgrid[0:h, 0:w]
    A = np.stack([xx[keep], yy[keep], np.ones(keep.sum())], 1)
    c, *_ = np.linalg.lstsq(A, d[keep], rcond=None)
    return c[0] * xx + c[1] * yy + c[2]


def main():
    src = Image.open(PHOTO).convert("RGB").crop(CROP)
    scale = WIDTH / src.width
    img = src.resize((WIDTH, round(src.height * scale)), Image.LANCZOS)
    cache = os.path.join(OUT, "eagle_depth_cache.npy")
    if os.path.exists(cache):
        d = np.load(cache)
    else:
        d = depth_map(img)
        np.save(cache, d)
    # the slab: the depth model's slab is not a plane (it bows with the photo's perspective and
    # shading), so it is estimated locally, as a rolling ball would: a grey opening wider than any
    # carved form leaves the slab under the relief, then smoothed
    if os.environ.get("EAGLE_SLAB", "opening") == "plane":
        keep = np.ones_like(d, bool)
        for _ in range(6):
            r = d - fit_plane(d, keep)
            keep = r < np.percentile(r[keep], 45)
        slab = fit_plane(d, keep)
    else:
        slab = ndimage.gaussian_filter(ndimage.grey_opening(d, size=(OPENING, OPENING)), OPENING / 4.0)
    height = d - slab

    h, w = height.shape
    yy, xx = np.mgrid[0:h, 0:w]
    px, py = xx / scale + CROP[0], yy / scale + CROP[1]          # back to photo pixels
    r_w = np.hypot(px - WREATH[0], py - WREATH[1])
    in_wreath = r_w < WREATH[2]
    # Inside the wreath the bird is measured from a plane fitted to the flat slab behind it. The
    # opening above is narrower than the bird's body and wings and ate into them, so the first cut-out
    # lost a wing and holed the head (user, 2026-11-25: "the eagle came out distorted"). The whole
    # disc is kept: on the pediment its flat slab lies just behind the tympanum's face and hides,
    # so the bird's outline is where its relief comes through the stone, not a cut.
    interior = r_w < INNER
    keep = interior.copy()
    for _ in range(6):
        r = d - fit_plane(d, keep)
        keep = interior & (r < np.percentile(r[keep], 35))
    # pits filled, and only they (a closing everywhere smoothed the feathers away): the deep shadow
    # under the head read as a hole in the depth
    closed = ndimage.grey_closing(d, size=(17, 17))
    pit = ndimage.gaussian_filter(((closed - d) > 0.025).astype(float), 2.0) > 0.3
    bird = np.where(pit, ndimage.gaussian_filter(closed, 2.0), d) - fit_plane(d, keep)
    # the slab at zero (its pixels' level), so on the pediment it lies behind the tympanum's face
    bird = bird - np.percentile(bird[interior], BIRD_SLAB_PERCENTILE)
    # lift the low relief (the far wing is carved shallow against the slab) by a gamma on the height
    # above the slab, so it comes through the tympanum's face with the rest of the bird
    top = np.percentile(bird[interior], 99.7)
    bird = np.where(bird > 0.0, top * np.power(np.clip(bird / top, 0.0, 1.0), BIRD_GAMMA), bird)
    blend = np.clip((INNER - r_w) / 60.0 + 0.5, 0.0, 1.0)        # over 60 photo pixels at the edge
    height = blend * bird + (1.0 - blend) * height
    height = np.clip(height / np.percentile(height[in_wreath], 99.7), 0.0, 1.0)

    # the wreath and the ribbons below are cut out; the loose wings on the slab either side (low,
    # patchy in the depth) and the slab's lower moulding are left out
    mask = (((height > THRESHOLD) & in_wreath) | ((height > THRESHOLD + 0.04) & (py > RIBBONS_TOP))) & (py < MOULDING_TOP)
    mask = ndimage.binary_opening(mask, iterations=2)
    mask = ndimage.binary_closing(mask, iterations=3)
    lab, n = ndimage.label(mask | interior)
    sizes = ndimage.sum(mask | interior, lab, range(1, n + 1))
    mask = np.isin(lab, 1 + np.flatnonzero(sizes > 0.002 * mask.size))
    mask |= interior
    # feather the cut edges down to the slab over a few pixels
    dist = ndimage.distance_transform_edt(mask)
    height = np.where(mask, np.maximum(height, 0.0) * np.clip(dist / 4.0, 0.0, 1.0), 0.0)
    height = ndimage.gaussian_filter(height, 0.6).astype(np.float32) * mask
    OUT_ = os.environ.get("EAGLE_OUT", OUT)
    os.makedirs(OUT_, exist_ok=True)
    np.save(os.path.join(OUT_, "eagle_height.npy"), height)
    Image.fromarray((mask * 255).astype(np.uint8)).save(os.path.join(OUT_, "eagle_mask.png"))
    gy, gx = np.gradient(height * 60.0)
    shade = np.clip(0.55 + (-gx - gy) * 0.35, 0, 1) * mask + 0.15 * (~mask)
    Image.fromarray((shade * 255).astype(np.uint8)).filter(ImageFilter.SMOOTH).save(
        os.path.join(OUT_, "eagle_preview.png"))
    print("height map %dx%d, relief %.0f %% of the area" % (w, h, 100.0 * mask.mean()))


main()
