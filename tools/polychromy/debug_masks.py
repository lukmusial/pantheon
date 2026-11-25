"""Contact sheet of the segmentation masks of one statue (for checking prompts).

    tools/polychromy_venv/bin/python tools/polychromy/debug_masks.py <key> <body|head> <out.png> [region ...]
"""

import os
import sys

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from polychromy.views import View  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def main():
    key, group, out = sys.argv[1:4]
    only = set(sys.argv[4:])
    work = os.path.join(ROOT, "tools", "polychromy_cache", key)
    masks = np.load(os.path.join(work, "masks_%s.npz" % group))
    import json
    views = [v["name"] for v in json.load(open(os.path.join(work, "views_%s.json" % group)))]
    regions = sorted({k.split("|")[1] for k in masks.files if not k.endswith("shape")})
    if only:
        regions = [r for r in regions if r in only]
    rng = np.random.RandomState(5)
    cols = {r: rng.randint(60, 255, 3) for r in regions}
    tiles = []
    for name in views:
        v = View(os.path.join(work, "views"), name)
        a = np.array(v.image()).astype(float)
        for r in regions:
            k = "%s|%s" % (name, r)
            if k not in masks.files:
                continue
            sh = tuple(masks[k + "|shape"])
            m = np.unpackbits(masks[k])[:sh[0] * sh[1]].reshape(sh).astype(bool)
            a[m] = a[m] * 0.45 + cols[r] * 0.55
        t = Image.fromarray(a.astype(np.uint8))
        t = t.resize((t.size[0] * 400 // t.size[1], 400))
        ImageDraw.Draw(t).text((4, 4), name, fill=(255, 255, 255))
        tiles.append(t)
    per = 8
    rows = [tiles[i:i + per] for i in range(0, len(tiles), per)]
    W = max(sum(t.size[0] for t in r) for r in rows)
    sheet = Image.new("RGB", (W, 400 * len(rows) + 20), (0, 0, 0))
    for j, r in enumerate(rows):
        x = 0
        for t in r:
            sheet.paste(t, (x, j * 400))
            x += t.size[0]
    d = ImageDraw.Draw(sheet)
    x = 4
    for r in regions:
        d.rectangle([x, 400 * len(rows) + 4, x + 12, 400 * len(rows) + 16], fill=tuple(int(c) for c in cols[r]))
        d.text((x + 16, 400 * len(rows) + 4), r, fill=(255, 255, 255))
        x += 16 + 8 * len(r) + 12
    sheet.save(out)


if __name__ == "__main__":
    main()
