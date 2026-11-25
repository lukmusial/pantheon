"""Contact sheet of painted-statue check images: renders/previews/painted/_contact_sheet.png

    tools/polychromy_venv/bin/python tools/polychromy/contact_sheet.py [key ...]
"""

import glob
import os
import sys

from PIL import Image, ImageDraw

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DIR = os.path.join(ROOT, "renders", "previews", "painted")


def main():
    keys = sys.argv[1:] or sorted(os.path.splitext(os.path.basename(p))[0]
                                  for p in glob.glob(os.path.join(DIR, "*.png")) if not os.path.basename(p).startswith("_"))
    H, cols = 320, 2
    tiles = []
    for k in keys:
        im = Image.open(os.path.join(DIR, k + ".png")).convert("RGB")
        im = im.resize((im.size[0] * H // im.size[1], H))
        ImageDraw.Draw(im).text((6, 6), k, fill=(255, 255, 0))
        tiles.append(im)
    W = max(t.size[0] for t in tiles)
    rows = (len(tiles) + cols - 1) // cols
    sheet = Image.new("RGB", (W * cols, H * rows), (40, 40, 40))
    for i, t in enumerate(tiles):
        sheet.paste(t, ((i % cols) * W, (i // cols) * H))
    out = os.path.join(DIR, "_contact_sheet.png")
    sheet.save(out)
    print(out)


if __name__ == "__main__":
    main()
