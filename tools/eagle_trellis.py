"""3D models of the Trajanic eagle relief through public TRELLIS Spaces (anonymous, or with the user's token: EAGLE_HF_TOKEN_FILE), for the
pediment's gilded bronze eagle.

    tools/venv-gen3d/bin/python -I tools/eagle_trellis.py

The height map from one photo (tools/eagle_relief.py) still read poorly as a bird (user, 2026-11-25:
"the eagle still looks terrible. why don't you model it properly in trellis"). Inputs, cut from Sailko's
photo (CC BY 3.0, assets/eagle/photos/SOURCES.md), which is the only thing sent to the Spaces:
    roundel  the eagle in its oak wreath, the slab outside the wreath made transparent
    bird     the eagle alone, inside the wreath
Each goes to microsoft/TRELLIS.2, then to trellis-community/TRELLIS if that fails. Writes
assets/eagle/trellis/<input>_<space>.glb and a four-view preview .png beside it; appends to log.jsonl.
EAGLE_INPUTS=roundel,bird and EAGLE_SPACES=trellis2,trellis1 choose what runs.
"""
import datetime
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

from PIL import Image, ImageDraw, ImageFilter

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
PHOTO = os.path.join(ROOT, "assets/eagle/photos/eagle_sailko_4_3840.jpg")
OUT = os.path.join(ROOT, "assets/eagle/trellis")
LOG = os.path.join(OUT, "log.jsonl")
BLENDER = "/usr/local/bin/blender"
WREATH = (1930, 960, 935)            # centre and outer radius of the wreath, photo pixels
BIRD = (1330, 300, 2560, 1700)       # the eagle inside the wreath, photo pixels

WORK = os.path.join(tempfile.gettempdir(), "eagle_trellis_work")
os.makedirs(WORK, exist_ok=True)
os.environ["HF_HOME"] = os.path.join(WORK, "hf")
os.environ["HF_HUB_DISABLE_IMPLICIT_TOKEN"] = "1"
os.environ.pop("HF_TOKEN", None)
os.environ["GRADIO_TEMP_DIR"] = os.path.join(WORK, "gtmp")
# Opt-in (user, 2026-11-25: "use the token you found"): EAGLE_HF_TOKEN_FILE names a file with the user's
# Hugging Face token, for their account's GPU quota when the anonymous one is used up. Read here and
# passed only to gradio_client; never printed or logged.
TOKEN = None
if os.environ.get("EAGLE_HF_TOKEN_FILE"):
    with open(os.path.expanduser(os.environ["EAGLE_HF_TOKEN_FILE"])) as fh:
        TOKEN = fh.read().strip() or None

from gradio_client import Client, handle_file  # noqa: E402


def log(entry):
    entry["time"] = datetime.datetime.now().isoformat(timespec="seconds")
    with open(LOG, "a") as fh:
        fh.write(json.dumps(entry) + "\n")


def inputs():
    src = Image.open(PHOTO).convert("RGB")
    out = {}
    cx, cy, r = WREATH
    box = (cx - r - 20, max(0, cy - r - 20), cx + r + 20, cy + r + 20)
    crop = src.crop(box).convert("RGBA")
    mask = Image.new("L", crop.size, 0)
    ImageDraw.Draw(mask).ellipse((cx - r - box[0], cy - r - box[1], cx + r - box[0], cy + r - box[1]), fill=255)
    crop.putalpha(mask.filter(ImageFilter.GaussianBlur(3)))
    side = max(crop.size)
    sq = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    sq.paste(crop, ((side - crop.width) // 2, (side - crop.height) // 2))
    out["roundel"] = os.path.join(OUT, "input_roundel.png")
    sq.resize((1024, 1024), Image.LANCZOS).save(out["roundel"])
    bird = src.crop(BIRD)
    side = max(bird.size)
    sq = Image.new("RGB", (side, side), (128, 128, 128))
    sq.paste(bird, ((side - bird.width) // 2, (side - bird.height) // 2))
    out["bird"] = os.path.join(OUT, "input_bird.png")
    sq.resize((1024, 1024), Image.LANCZOS).save(out["bird"])
    return out


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
    ext = dict(decimation_target=500000, texture_size=2048)
    glb, dl = c.predict(api_name="/extract_glb", **ext)
    settings["extract_glb"] = ext
    return path_of(dl) or path_of(glb), settings


SPACES = {"trellis2": run_trellis2, "trellis1": run_trellis1}


def main():
    os.makedirs(OUT, exist_ok=True)
    ins = inputs()
    want_in = os.environ.get("EAGLE_INPUTS", "roundel,bird").split(",")
    want_sp = os.environ.get("EAGLE_SPACES", "trellis2,trellis1").split(",")
    made = 0
    for name in want_in:
        for sp in want_sp:
            t0 = time.time()
            glb = os.path.join(OUT, "%s_%s.glb" % (name, sp))
            try:
                src, settings = SPACES[sp](ins[name])
                if not src or not os.path.exists(src):
                    raise RuntimeError("Space returned no GLB file")
                shutil.copy(src, glb)
            except Exception as e:  # noqa: BLE001
                print("FAILED %s %s: %s" % (name, sp, str(e)[:300]))
                log(dict(input=name, space=sp, ok=False, error=str(e)[:500]))
                continue
            preview = glb[:-4] + ".png"
            subprocess.run([BLENDER, "-b", "--factory-startup", "--python",
                            os.path.join(ROOT, "blender/render_preview.py"), "--", preview, glb],
                           capture_output=True, text=True, cwd=WORK)
            log(dict(input=name, space=sp, ok=True, settings=settings, glb=glb, seconds=round(time.time() - t0)))
            print("OK %s %s %s" % (name, sp, glb))
            made += 1
            break                      # one model per input is enough
    return 0 if made else 1


if __name__ == "__main__":
    sys.exit(main())
