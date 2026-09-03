"""Byte-identity tripwire for the rendered card.

The SVGs are committed and a daily Action rewrites them, so any accidental change to
layout, art, or palette shows up as a diff on the public profile. These hashes are the
output of the pre-package code (commit f0a3fbe) for the fixture stats below; if a test
here fails, the rendering changed -- confirm it was intended before updating the hash.

On an intended rendering change, run the test and copy the digest it prints in the
failure message into GOLDEN below.
"""
import hashlib
from datetime import date

import pytest

from profilecard.art import load_art
from profilecard.profile import ProfileData
from profilecard.render import render
from profilecard.stats import Stats

FIXTURE_DATE = date(2026, 9, 3)
FIXTURE_STATS = Stats(
    followers=123, repos=45, contributed=6, stars=789,
    commits=12345, loc=654321, loc_add=900000, loc_del=245679,
)
GOLDEN = {
    "dark": "365352da89e6a37d7b2ea39889995bdb17413120acd1e2fda89ad6229bd4074d",
    "light": "b5e14855ea0ae2de545c132ff82b8efebac004088e3c5988a3a3aa7fe359c09e",
}


@pytest.mark.parametrize("mode", sorted(GOLDEN))
def test_rendered_svg_is_byte_identical_to_the_pre_refactor_output(mode):
    svg = render(mode, FIXTURE_STATS, load_art("art.json"), ProfileData.load("profile.toml"),
                 today=FIXTURE_DATE)
    digest = hashlib.sha256(svg.encode()).hexdigest()
    assert digest == GOLDEN[mode], (
        f"{mode} rendering changed. If that was intended, set GOLDEN['{mode}'] = '{digest}'"
    )
