import xml.etree.ElementTree as ET
from dataclasses import replace
from datetime import date

from profilecard.art import art_lines
from profilecard.render import PALETTES, render


def test_output_is_well_formed_xml(stats, profile, art):
    for mode in PALETTES:
        root = ET.fromstring(render(mode, stats, art, profile, today=date(2026, 9, 3)))
        assert root.tag.endswith("svg")
        assert root.get("width") == "840" and root.get("height") == "500"


def test_each_mode_paints_its_own_background(stats, profile, art):
    for mode, palette in PALETTES.items():
        svg = render(mode, stats, art, profile, today=date(2026, 9, 3))
        assert f'fill="{palette["bg"]}"' in svg
        assert f'stroke="{palette["border"]}"' in svg


def test_markup_in_profile_values_is_escaped(stats, profile, art):
    hostile = replace(profile, host="A & B <script>alert(1)</script>")
    svg = render("dark", stats, art, hostile, today=date(2026, 9, 3))
    assert "<script>" not in svg
    assert "A &amp; B &lt;script&gt;" in svg
    ET.fromstring(svg)  # still parses


def test_blank_lines_produce_no_text_element(stats, profile, art):
    svg = render("dark", stats, art, profile, today=date(2026, 9, 3))
    root = ET.fromstring(svg)
    texts = [t for t in root.iter() if t.tag.endswith("text")]
    info_texts = [t for t in texts if t.get("x") == "390"]
    assert len(info_texts) == 16  # 20 rows minus the 4 blank separators


def test_info_rows_are_spaced_21px_apart(stats, profile, art):
    root = ET.fromstring(render("dark", stats, art=art, profile=profile, today=date(2026, 9, 3)))
    ys = [float(t.get("y")) for t in root.iter() if t.tag.endswith("text") and t.get("x") == "390"]
    assert ys[0] == 45
    assert all((b - a) % 21 == 0 for a, b in zip(ys, ys[1:], strict=False))


def test_art_rows_merge_adjacent_cells_of_the_same_colour(art):
    lines = art_lines("dark", art)
    assert len(lines) == 2  # the all-whitespace middle row is skipped
    assert lines[0].count("<tspan") == 2  # "##" then "." -> two colour runs
    assert lines[1].count("<tspan") == 3  # "x", "&", "<" all differ


def test_art_escapes_glyphs_that_are_xml_metacharacters(art):
    row = art_lines("dark", art)[1]
    assert "&amp;" in row and "&lt;" in row


def test_art_gives_every_glyph_an_explicit_x(art):
    xs = art_lines("dark", art)[0].split('x="')[1].split('"')[0].split()
    assert len(xs) == 3  # one coordinate per cell, so pitch ignores the viewer's font


def test_empty_art_row_is_skipped_without_error(art):
    assert len(art_lines("light", art)) == 2
