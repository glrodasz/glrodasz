import json

import pytest

from profilecard import cli
from profilecard.stats import Stats

STATS = Stats(followers=1, repos=2, contributed=3, stars=4, commits=5,
              loc=6, loc_add=8, loc_del=2)


@pytest.fixture
def repo_files(tmp_path):
    """A minimal working directory: art.json, profile.toml, and a seeded LOC cache."""
    (tmp_path / "art.json").write_text(json.dumps({
        "cols": 2, "rows": 1, "cell_aspect": 1.66,
        "dark": {"chars": ["ab"], "colors": [["#111111", "#222222"]]},
        "light": {"chars": ["ab"], "colors": [["#333333", "#444444"]]},
    }), encoding="utf-8")
    (tmp_path / "profile.toml").write_text(
        '[github]\nuser = "u"\njoined_year = 2020\n'
        "[career]\nstart = 2020-01-01\n"
        '[about]\nos = "o"\nhost = "h"\nkernel = "k"\nide = "i"\nhobbies = "b"\n'
        '[languages]\nprogramming = "p"\nspoken = "s"\n'
        '[contact]\nemail = "e"\nlinkedin = "l"\n',
        encoding="utf-8",
    )
    (tmp_path / "loc_cache.json").write_text('{"old": {"add": 1, "del": 0, "head": "h"}}', encoding="utf-8")
    return tmp_path


def run(tmp_path, monkeypatch, extra_argv=(), fetch=None):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cli, "load_dotenv", lambda *a, **k: None)  # never read the real .env

    def default_fetch(client, profile, settings, cache):
        cache["new"] = {"add": 5, "del": 1, "head": "abc"}
        return STATS

    monkeypatch.setattr(cli, "fetch_stats", fetch or default_fetch)
    return cli.main(list(extra_argv))


def test_writes_both_svgs_and_the_updated_cache(tmp_path, monkeypatch, repo_files):
    assert run(repo_files, monkeypatch) == 0
    for name in ("dark_mode.svg", "light_mode.svg"):
        assert (repo_files / name).read_text(encoding="utf-8").startswith("<svg")
    cache = json.loads((repo_files / "loc_cache.json").read_text(encoding="utf-8"))
    assert set(cache) == {"old", "new"}  # existing entries survive the round trip


def test_dry_run_writes_nothing(tmp_path, monkeypatch, repo_files):
    before = (repo_files / "loc_cache.json").read_text(encoding="utf-8")
    assert run(repo_files, monkeypatch, ["--dry-run"]) == 0
    assert not (repo_files / "dark_mode.svg").exists()
    assert (repo_files / "loc_cache.json").read_text(encoding="utf-8") == before


def test_out_dir_redirects_the_svgs(tmp_path, monkeypatch, repo_files):
    (repo_files / "out").mkdir()
    run(repo_files, monkeypatch, ["--out-dir", "out"])
    assert (repo_files / "out" / "dark_mode.svg").exists()
    assert not (repo_files / "dark_mode.svg").exists()


def test_a_failed_fetch_leaves_the_previous_svgs_and_cache_untouched(tmp_path, monkeypatch, repo_files):
    (repo_files / "dark_mode.svg").write_text("PREVIOUS", encoding="utf-8")
    before = (repo_files / "loc_cache.json").read_text(encoding="utf-8")

    def boom(*a, **k):
        raise RuntimeError("api down")

    with pytest.raises(RuntimeError):
        run(repo_files, monkeypatch, fetch=boom)
    assert (repo_files / "dark_mode.svg").read_text(encoding="utf-8") == "PREVIOUS"
    assert (repo_files / "loc_cache.json").read_text(encoding="utf-8") == before


def test_settings_and_profile_reach_fetch_stats(tmp_path, monkeypatch, repo_files):
    seen = {}

    def spy(client, profile, settings, cache):
        seen.update(user=profile.github_user, token=settings.token, hmac=settings.cache_hmac_key)
        return STATS

    monkeypatch.setenv("GITHUB_TOKEN", "tok")
    monkeypatch.setenv("CACHE_HMAC_KEY", "hmackey")
    run(repo_files, monkeypatch, fetch=spy)
    assert seen == {"user": "u", "token": "tok", "hmac": "hmackey"}


def test_custom_paths_are_honoured(tmp_path, monkeypatch, repo_files):
    (repo_files / "art.json").rename(repo_files / "custom_art.json")
    (repo_files / "profile.toml").rename(repo_files / "custom.toml")
    assert run(repo_files, monkeypatch,
               ["--art", "custom_art.json", "--profile", "custom.toml",
                "--loc-cache", "custom_cache.json"]) == 0
    assert (repo_files / "custom_cache.json").exists()


def test_parse_args_defaults_match_the_repo_layout():
    args = cli.parse_args([])
    assert (args.art, args.loc_cache, args.profile, args.out_dir) == \
        ("art.json", "loc_cache.json", "profile.toml", ".")
    assert args.dry_run is False
