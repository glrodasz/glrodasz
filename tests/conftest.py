from datetime import date

import pytest

from profilecard.profile import ProfileData
from profilecard.stats import Stats


@pytest.fixture
def profile():
    return ProfileData(
        github_user="glrodasz",
        joined_year=2012,
        career_start=date(2012, 8, 1),
        os="macOS",
        host="Stockholm.Sweden",
        kernel="Senior Full-stack AI Engineer",
        ide="Cursor, Claude Code, VS Code",
        hobbies="Oil Painting",
        languages_programming="TypeScript, JavaScript, Python",
        languages_spoken="English, Spanish",
        email="me@guillermorodas.com",
        linkedin="in/guillermorodas",
    )


@pytest.fixture
def stats():
    return Stats(
        followers=123, repos=45, contributed=6, stars=789,
        commits=12345, loc=654321, loc_add=900000, loc_del=245679,
    )


@pytest.fixture
def art():
    """A tiny 3x3 grid, enough to exercise run merging and the blank-row skip."""
    return {
        "cols": 3,
        "rows": 3,
        "cell_aspect": 58.8 / 35.4,
        "dark": {
            "chars": ["##.", "   ", "x&<"],
            "colors": [["#111111", "#111111", "#222222"],
                       ["#333333", "#333333", "#333333"],
                       ["#444444", "#555555", "#666666"]],
        },
        "light": {
            "chars": ["ab ", "", "c=d"],
            "colors": [["#aaaaaa", "#aaaaaa", "#bbbbbb"],
                       ["#cccccc", "#cccccc", "#cccccc"],
                       ["#dddddd", "#eeeeee", "#ffffff"]],
        },
    }
