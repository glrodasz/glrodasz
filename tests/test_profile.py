from datetime import date

import pytest

from profilecard.profile import ProfileData

MINIMAL = {
    "github": {"user": "u", "joined_year": 2012},
    "career": {"start": date(2012, 8, 1)},
    "about": {"os": "macOS", "host": "h", "kernel": "k", "ide": "i", "hobbies": "b"},
    "languages": {"programming": "p", "spoken": "s"},
    "contact": {"email": "e", "linkedin": "l"},
}


def test_the_repo_profile_toml_loads():
    p = ProfileData.load("profile.toml")
    assert p.github_user == "glrodasz"
    assert p.career_start == date(2012, 8, 1)
    assert p.joined_year == 2012


def test_career_start_is_a_real_date_not_a_string():
    assert isinstance(ProfileData.load("profile.toml").career_start, date)


def test_profile_is_frozen():
    p = ProfileData.from_dict(MINIMAL)
    with pytest.raises(AttributeError):
        p.host = "elsewhere"


def test_missing_key_names_the_file_and_the_key():
    broken = {**MINIMAL, "contact": {"email": "e"}}
    with pytest.raises(KeyError, match=r"\[contact\].linkedin"):
        ProfileData.from_dict(broken, path="profile.toml")


def test_missing_section_is_reported_the_same_way():
    broken = {k: v for k, v in MINIMAL.items() if k != "languages"}
    with pytest.raises(KeyError, match=r"\[languages\].programming"):
        ProfileData.from_dict(broken)


def test_career_start_as_a_string_is_rejected():
    broken = {**MINIMAL, "career": {"start": "2012-08-01"}}
    with pytest.raises(TypeError, match="must be a TOML date"):
        ProfileData.from_dict(broken)


def test_load_parses_toml_from_disk(tmp_path):
    path = tmp_path / "p.toml"
    path.write_text(
        '[github]\nuser = "x"\njoined_year = 2020\n'
        "[career]\nstart = 2020-01-02\n"
        '[about]\nos = "o"\nhost = "h"\nkernel = "k"\nide = "i"\nhobbies = "b"\n'
        '[languages]\nprogramming = "p"\nspoken = "s"\n'
        '[contact]\nemail = "e"\nlinkedin = "l"\n',
        encoding="utf-8",
    )
    p = ProfileData.load(path)
    assert p.github_user == "x" and p.career_start == date(2020, 1, 2)
