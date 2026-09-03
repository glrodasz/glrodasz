"""One-off, run locally: turn a portrait photo into art.json for the profilecard package.

Style reverse-engineered from a colour "glyph grid" render: every cell gets a random
glyph from GLYPHS (blank included) coloured with the photo's average colour for that
cell; cells darker than DARK_CUT are left empty so hair/shoulders read as a silhouette.
NOT part of the profilecard runtime package and NOT used by the daily Action -- it is
the only code here that needs third-party deps: `pip install -e ".[art]"`.

    python tools/make_art.py photo.png [--cols 80]
"""
import argparse
import json
from collections import deque

import numpy as np
from PIL import Image, ImageEnhance

GLYPHS = "#80=+;@:xX.S- "   # blank is one of the 14 "glyphs"
CELL_ASPECT = 58.8 / 35.4   # row pitch / column pitch of the reference render
DARK_CUT = 48               # luminance below which a subject cell is left blank (dark mode)
BG_TOL = 26                 # flood-fill tolerance for the studio backdrop


def background_mask(rgb, tol=BG_TOL):
    """True where the (flat, light) backdrop is, via flood fill from the image border."""
    h, w, _ = rgb.shape
    close = np.abs(rgb.astype(int) - rgb[0, 0].astype(int)).max(axis=2) <= tol
    bg = np.zeros((h, w), bool)
    q = deque()
    border = [(y, x) for x in range(w) for y in (0, h - 1)] + [(y, x) for y in range(h) for x in (0, w - 1)]
    for y, x in border:
        if close[y, x] and not bg[y, x]:
            bg[y, x] = True
            q.append((y, x))
    while q:
        y, x = q.popleft()
        for ny, nx in ((y - 1, x), (y + 1, x), (y, x - 1), (y, x + 1)):
            if 0 <= ny < h and 0 <= nx < w and close[ny, nx] and not bg[ny, nx]:
                bg[ny, nx] = True
                q.append((ny, nx))
    return bg


def build(photo, cols, seed=7):
    im = Image.open(photo).convert("RGB")
    bg = background_mask(np.asarray(im))
    ys, xs = np.nonzero(~bg)
    box = (xs.min(), ys.min(), xs.max() + 1, ys.max() + 1)
    im, bg = im.crop(box), bg[box[1]:box[3], box[0]:box[2]]
    rows = round(im.height / im.width * cols / CELL_ASPECT)

    enh = ImageEnhance.Color(ImageEnhance.Contrast(im).enhance(1.3)).enhance(1.6)
    col = np.asarray(enh.resize((cols, rows), Image.LANCZOS)).astype(float)
    bgf = np.asarray(Image.fromarray((bg * 255).astype(np.uint8)).resize((cols, rows), Image.LANCZOS)) / 255.0
    is_bg = bgf > 0.5
    lum = col @ [0.299, 0.587, 0.114]

    rng = np.random.default_rng(seed)
    chars = rng.integers(0, len(GLYPHS), (rows, cols))

    def hexes(colors):
        # percent-format kept verbatim: regenerating art.json is a rare, manual step
        return [["#%02x%02x%02x" % tuple(int(v) for v in c) for c in row] for row in colors.clip(0, 255)]  # noqa: UP031

    # dark mode: like the reference -- grey backdrop glyphs, dark subject cells blank
    dark = col.copy()
    dark[is_bg] = 120
    dark_chars = chars.copy()
    dark_chars[(lum < DARK_CUT) & ~is_bg] = GLYPHS.index(" ")

    # light mode: same grid on white -- darken subject so hair/shirt become the silhouette
    light = col * 0.62
    light[is_bg] = 208

    def rows_of(ch):
        return ["".join(GLYPHS[i] for i in r).rstrip() for r in ch]

    return {
        "cols": cols, "rows": rows, "cell_aspect": CELL_ASPECT,
        "dark": {"chars": rows_of(dark_chars), "colors": hexes(dark)},
        "light": {"chars": rows_of(chars), "colors": hexes(light)},
    }


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("photo")
    ap.add_argument("--cols", type=int, default=80)
    ap.add_argument("--out", default="art.json")
    a = ap.parse_args(argv)
    art = build(a.photo, a.cols)
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(art, f, separators=(",", ":"))
    print(f"wrote {a.out}: {art['cols']}x{art['rows']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
