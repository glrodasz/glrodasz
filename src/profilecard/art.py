"""The colour glyph grid on the left of the card, read from art.json."""
import html
import json

ART_X, ART_Y, ART_W = 25, 32, 345  # glyph grid box; info column starts at x=390


def load_art(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def art_lines(mode, art):
    """One <text> per row. Every glyph gets an explicit x (SVG positions characters
    from the x list in order, across tspans), so glyph pitch is independent of the
    viewer's monospace font; tspans carry the per-cell colour, merged into runs."""
    a = art[mode]
    cw = ART_W / art["cols"]
    ch = cw * art["cell_aspect"]
    font = f'font-family="\'Courier New\',Courier,monospace" font-weight="bold" font-size="{ch * 0.68:.2f}px"'
    out = []
    # strict=False on purpose: chars rows are rstrip'd by make_art, colour rows are not.
    for r, (line, colors) in enumerate(zip(a["chars"], a["colors"], strict=False)):
        if not line.strip():
            continue
        xs = " ".join(f"{ART_X + (c + 0.5) * cw:.1f}" for c in range(len(line)))
        runs = []
        for c, glyph in enumerate(line):
            if runs and runs[-1][0] == colors[c]:
                runs[-1][1] += glyph
            else:
                runs.append([colors[c], glyph])
        spans = "".join(f'<tspan fill="{col}">{html.escape(t)}</tspan>' for col, t in runs)
        # Split only at a string boundary -- the concatenation is one SVG element.
        out.append(
            f'<text x="{xs}" y="{ART_Y + (r + 0.5) * ch:.2f}" {font} '
            f'text-anchor="middle" xml:space="preserve">{spans}</text>'
        )
    return out
