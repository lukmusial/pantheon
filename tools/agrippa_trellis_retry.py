"""One attempt at the Agrippa statue mesh through a public TRELLIS Space (anonymous, no token).

Command (run from any directory):
    tools/venv-gen3d/bin/python -I tools/agrippa_trellis_retry.py

Steps: background-removed photo -> trellis-community/TRELLIS (then microsoft/TRELLIS.2 if the first fails)
-> assets/statues/raw/agrippa_gen3d/agrippa_trellis.glb -> 4-view check with blender/render_preview.py
-> renders/previews/statues_candidates/agrippa_trellis.png.

Input: assets/statues/raw/agrippa_gen3d/a4_hunyuan21_input_rgba.png (the public-domain photo
assets/statues/raw/agrippa_photo/agrippa_venice_pd_19c.jpg, cropped and background-removed with rembg/BiRefNet).
If that file is missing it is rebuilt from the photo with rembg (downloads a ~1 GB model on first use).
Only this image is sent to the Space.

Exit codes: 0 success (prints AGRIPPA_OK), 2 quota/queue refusal on every Space tried, 1 any other error.
Settings and outcome are appended to assets/statues/raw/agrippa_gen3d/agrippa_trellis_log.jsonl.
"""
import datetime
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
PHOTO = os.path.join(ROOT, "assets/statues/raw/agrippa_photo/agrippa_venice_pd_19c.jpg")
OUT_DIR = os.path.join(ROOT, "assets/statues/raw/agrippa_gen3d")
RGBA = os.path.join(OUT_DIR, "a4_hunyuan21_input_rgba.png")
GLB = os.path.join(OUT_DIR, "agrippa_trellis.glb")
PREVIEW = os.path.join(ROOT, "renders/previews/statues_candidates/agrippa_trellis.png")
LOG = os.path.join(OUT_DIR, "agrippa_trellis_log.jsonl")
BLENDER = "/usr/local/bin/blender"
CROP = (300, 30, 1240, 1885)  # figure only, in photo pixels
REFUSAL = ("quota", "runs limit", "queue is full", "too many requests", "429", "rate limit")

# Keep the Hugging Face cache and gradio downloads out of the user's home cache, and never send a token.
WORK = os.path.join(tempfile.gettempdir(), "agrippa_trellis_work")
os.makedirs(WORK, exist_ok=True)
os.environ["HF_HOME"] = os.path.join(WORK, "hf")
os.environ["HF_HUB_DISABLE_IMPLICIT_TOKEN"] = "1"
os.environ.pop("HF_TOKEN", None)
# Opt-in (user approved 2026-11-21): PANTHEON_HF_TOKEN_FILE points at a token file to use the user's own
# Hugging Face account quota. The token is read here and passed only to gradio_client; never printed.
TOKEN = None
if os.environ.get("PANTHEON_HF_TOKEN_FILE"):
    with open(os.path.expanduser(os.environ["PANTHEON_HF_TOKEN_FILE"])) as fh:
        TOKEN = fh.read().strip() or None
os.environ["GRADIO_TEMP_DIR"] = os.path.join(WORK, "gtmp")
os.environ.setdefault("U2NET_HOME", os.path.join(WORK, "u2net"))

from gradio_client import Client, handle_file  # noqa: E402


def log(entry):
    entry["time"] = datetime.datetime.now().isoformat(timespec="seconds")
    with open(LOG, "a") as fh:
        fh.write(json.dumps(entry) + "\n")


def ensure_rgba():
    if os.path.exists(RGBA):
        return RGBA
    import numpy as np
    from PIL import Image
    from rembg import new_session, remove
    im = Image.open(PHOTO).convert("RGB").crop(CROP)
    rgba = remove(im, session=new_session("birefnet-general"))
    a = np.array(rgba)
    ys, xs = np.where(a[..., 3] > 16)
    crop = rgba.crop((xs.min(), ys.min(), xs.max() + 1, ys.max() + 1))
    w, h = crop.size
    side = int(max(w, h) * 1.1)
    sq = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    sq.paste(crop, ((side - w) // 2, (side - h) // 2))
    sq.save(RGBA)
    return RGBA


def path_of(x):
    if isinstance(x, dict):
        x = x.get("value", x)
        x = x.get("path", x) if isinstance(x, dict) else x
    return x


def run_trellis1(img):
    c = Client("trellis-community/TRELLIS", verbose=False, token=TOKEN)
    try:
        c.predict(api_name="/start_session")
    except Exception:  # noqa: BLE001
        pass
    pre = path_of(c.predict(handle_file(img), api_name="/preprocess_image"))
    settings = dict(seed=0, ss_guidance_strength=7.5, ss_sampling_steps=50, slat_guidance_strength=3.0,
                    slat_sampling_steps=50, multiimage_algo="stochastic", mesh_simplify=0.9, texture_size=2048)
    res = c.predict(handle_file(pre), [], api_name="/generate_and_extract_glb", **settings)
    return path_of(res[2]) or path_of(res[1]), settings


def run_trellis2(img):
    c = Client("microsoft/TRELLIS.2", verbose=False, token=TOKEN)
    try:
        c.predict(api_name="/start_session")
    except Exception:  # noqa: BLE001
        pass
    pre = path_of(c.predict(handle_file(img), api_name="/preprocess_image"))
    settings = dict(seed=0, resolution="1536",
                    ss_guidance_strength=7.5, ss_guidance_rescale=0.7, ss_sampling_steps=12, ss_rescale_t=5.0,
                    shape_slat_guidance_strength=7.5, shape_slat_guidance_rescale=0.5,
                    shape_slat_sampling_steps=12, shape_slat_rescale_t=3.0,
                    tex_slat_guidance_strength=1.0, tex_slat_guidance_rescale=0.0,
                    tex_slat_sampling_steps=12, tex_slat_rescale_t=3.0)
    c.predict(handle_file(pre), api_name="/image_to_3d", **settings)
    ext = dict(decimation_target=500000, texture_size=4096)
    glb, dl = c.predict(api_name="/extract_glb", **ext)
    settings["extract_glb"] = ext
    return path_of(dl) or path_of(glb), settings


def main():
    try:
        img = ensure_rgba()
    except Exception as e:  # noqa: BLE001
        print("ERROR preparing input:", e)
        return 1
    refused_all = True
    spaces = (("trellis-community/TRELLIS", run_trellis1), ("microsoft/TRELLIS.2", run_trellis2))
    only = os.environ.get("PANTHEON_TRELLIS_SPACE")  # optional: run just this Space
    for space, fn in spaces:
        if only and space != only:
            continue
        t0 = time.time()
        try:
            src, settings = fn(img)
            if not src or not os.path.exists(src):
                raise RuntimeError("Space returned no GLB file")
            shutil.copy(src, GLB)
        except Exception as e:  # noqa: BLE001
            msg = str(e)
            refused = any(k in msg.lower() for k in REFUSAL)
            refused_all &= refused
            print("%s %s: %s" % ("REFUSED" if refused else "FAILED", space, msg[:300]))
            log(dict(space=space, ok=False, refused=refused, error=msg[:500]))
            continue
        os.makedirs(os.path.dirname(PREVIEW), exist_ok=True)
        r = subprocess.run([BLENDER, "-b", "--factory-startup", "--python",
                            os.path.join(ROOT, "blender/render_preview.py"), "--", PREVIEW, GLB],
                           capture_output=True, text=True, cwd=WORK)
        if r.returncode != 0 or not os.path.exists(PREVIEW):
            print("FAILED preview render:", r.stdout[-500:], r.stderr[-500:])
            log(dict(space=space, ok=False, refused=False, error="preview render failed", glb=GLB))
            return 1
        log(dict(space=space, ok=True, settings=settings, glb=GLB, preview=PREVIEW,
                 seconds=round(time.time() - t0)))
        print("GLB", GLB)
        print("PREVIEW", PREVIEW)
        print("AGRIPPA_OK")
        return 0
    return 2 if refused_all else 1


if __name__ == "__main__":
    sys.exit(main())
