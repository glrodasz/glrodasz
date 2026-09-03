"""Generate the glrodasz GitHub profile card SVGs.

Runtime is stdlib-only; the image -> art.json tool lives in tools/make_art.py and
needs Pillow + NumPy (`pip install -e ".[art]"`).

Deliberately re-exports nothing: names like `render` and `profile` would shadow the
submodules of the same name, so import from the submodules directly
(`from profilecard.render import render`).
"""

__version__ = "1.0.0"
