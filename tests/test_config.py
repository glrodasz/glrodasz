from profilecard.config import Settings, load_dotenv


def test_github_token_is_the_default_and_access_token_the_private_one():
    s = Settings.from_env({"GITHUB_TOKEN": "actions", "ACCESS_TOKEN": "pat"})
    assert s.token == "actions"
    assert s.priv_token == "pat"


def test_access_token_backfills_a_missing_github_token():
    s = Settings.from_env({"ACCESS_TOKEN": "pat"})
    assert s.token == "pat" and s.priv_token == "pat"


def test_github_token_backfills_a_missing_access_token():
    s = Settings.from_env({"GITHUB_TOKEN": "actions"})
    assert s.token == "actions" and s.priv_token == "actions"


def test_no_tokens_yields_empty_strings_rather_than_none():
    s = Settings.from_env({})
    assert s.token == "" and s.priv_token == ""


def test_hmac_key_is_none_when_unset():
    assert Settings.from_env({}).cache_hmac_key is None
    assert Settings.from_env({"CACHE_HMAC_KEY": "k"}).cache_hmac_key == "k"


def test_path_overrides_are_carried_through():
    s = Settings.from_env({}, art_path="a.json", loc_cache_path="c.json", out_dir="out")
    assert (s.art_path, s.loc_cache_path, s.out_dir) == ("a.json", "c.json", "out")


def test_load_dotenv_is_a_no_op_when_the_file_is_absent(tmp_path):
    load_dotenv(tmp_path / "nope")  # must not raise -- this is the CI path


def test_load_dotenv_parses_and_strips_quotes(tmp_path, monkeypatch):
    path = tmp_path / ".env"
    path.write_text('# comment\n\nA="quoted"\nB=  plain  \nC=\'single\'\nnot_a_pair\n', encoding="utf-8")
    for k in ("A", "B", "C"):
        monkeypatch.delenv(k, raising=False)
    load_dotenv(path)
    import os
    assert os.environ["A"] == "quoted"
    assert os.environ["B"] == "plain"
    assert os.environ["C"] == "single"
    assert "not_a_pair" not in os.environ


def test_load_dotenv_never_overrides_a_real_environment_variable(tmp_path, monkeypatch):
    # In Actions the secrets are already in the environment; a stray .env must not win.
    path = tmp_path / ".env"
    path.write_text("TOKEN_X=from_file\n", encoding="utf-8")
    monkeypatch.setenv("TOKEN_X", "from_actions")
    load_dotenv(path)
    import os
    assert os.environ["TOKEN_X"] == "from_actions"
