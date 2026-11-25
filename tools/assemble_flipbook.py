"""Assemble rendered fire frames into one seamlessly looping flipbook sheet.

Usage:
    tools/polychromy_venv/bin/python tools/assemble_flipbook.py <out.png> <loop> <fade> <grid> <dir> [<dir> ...]

Each <dir> holds f_0000.png ... from blender/render_fire_flipbook.py (one view of the simulation) with
at least loop + fade frames. Per view, frames 0 .. loop-1 are kept and the first `fade` of them are
cross-faded with the frames that follow the loop (loop .. loop+fade-1), so the last frame runs on
into the first without a jump. The views are laid out one after another, row by row, in a grid x grid
sheet: view k occupies cells k*loop .. (k+1)*loop-1.
"""

import os
import sys

import numpy as np
from PIL import Image


def load(path):
    a = np.asarray(Image.open(path)).astype(np.float32)
    if a.max() > 255.0:  # 16-bit PNG
        a /= 257.0
    return a[..., :3] if a.ndim == 3 else a


def main():
    out, loop, fade, grid = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4])
    dirs = sys.argv[5:]
    if loop * len(dirs) > grid * grid:
        sys.exit("%d views of %d frames do not fit a %dx%d grid" % (len(dirs), loop, grid, grid))
    size = None
    sheet = None
    for k, d in enumerate(dirs):
        frames = [os.path.join(d, "f_%04d.png" % i) for i in range(loop + fade)]
        missing = [f for f in frames if not os.path.exists(f)]
        if missing:
            sys.exit("missing %d frames in %s, first %s" % (len(missing), d, missing[0]))
        for i in range(loop):
            img = load(frames[i])
            if i < fade:
                w = (i + 0.5) / fade   # weight of the loop's own frame; the rest continues the tail
                img = w * img + (1.0 - w) * load(frames[loop + i])
            if sheet is None:
                size = img.shape[0]
                sheet = np.zeros((grid * size, grid * size, 3), np.float32)
            cell = k * loop + i
            r, c = divmod(cell, grid)
            sheet[r * size:(r + 1) * size, c * size:(c + 1) * size] = img
    Image.fromarray(np.clip(sheet + 0.5, 0, 255).astype(np.uint8)).save(out, optimize=True)
    print("wrote %s: %d views x %d frames, %d px cells, %dx%d" % (out, len(dirs), loop, size, grid, grid))


if __name__ == "__main__":
    main()
