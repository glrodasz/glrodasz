import json

import pytest

from profilecard.loc import cache_key, load_cache, save_cache, walk_loc


class FakeClient:
    """Serves canned history pages keyed by repo name; records every call."""

    def __init__(self, pages=None, raises=None):
        self.pages = pages or {}
        self.raises = raises or {}
        self.calls = []

    def graphql(self, query, variables=None, token=None):
        name = variables["name"]
        self.calls.append((name, variables["cursor"]))
        if name in self.raises:
            raise self.raises[name]
        remaining = self.pages[name]
        page = remaining.pop(0)
        if page is None:
            return {"repository": {"defaultBranchRef": None}}
        return {"repository": {"defaultBranchRef": {"target": {"history": page}}}}


def history(nodes, next_cursor=None):
    return {
        "pageInfo": {"hasNextPage": next_cursor is not None, "endCursor": next_cursor},
        "nodes": nodes,
    }


def commit(oid, add, dele):
    return {"oid": oid, "additions": add, "deletions": dele}


# --- cache_key -------------------------------------------------------------------
# loc_cache.json is committed to a public repo, so these digests are load-bearing:
# if they change, every cached entry is orphaned and the LOC walk silently restarts
# from zero. The literals below pin the current scheme.
def test_cache_key_unkeyed_digest_is_pinned():
    assert cache_key("glrodasz", "dotfiles") == "a9d83d833517652d"


def test_cache_key_hmac_digest_is_pinned():
    assert cache_key("glrodasz", "dotfiles", "testkey") == "96f89f6c8f6f9b0e"


def test_cache_key_is_stable_across_calls():
    assert cache_key("glrodasz", "dotfiles", "k") == cache_key("glrodasz", "dotfiles", "k")


def test_cache_key_hmac_differs_from_unkeyed():
    assert cache_key("glrodasz", "dotfiles", "testkey") != cache_key("glrodasz", "dotfiles")


def test_cache_key_is_16_hex_chars():
    for key in (cache_key("u", "r"), cache_key("u", "r", "secret")):
        assert len(key) == 16
        int(key, 16)  # raises if not hex


def test_cache_key_never_contains_the_repo_name():
    assert "supersecret" not in cache_key("glrodasz", "supersecret", "k")


# --- walk_loc --------------------------------------------------------------------
def test_full_walk_when_cache_is_empty():
    client = FakeClient({"a": [history([commit("c2", 10, 3), commit("c1", 5, 1)])]})
    cache = {}
    totals = walk_loc(client, ["a"], "uid", cache, "glrodasz")
    assert totals == {"loc_add": 15, "loc_del": 4, "loc": 11}
    assert cache[cache_key("glrodasz", "a")] == {"add": 15, "del": 4, "head": "c2"}


def test_paginates_until_has_next_page_is_false():
    client = FakeClient({"a": [
        history([commit("c3", 1, 0)], next_cursor="CUR"),
        history([commit("c2", 2, 0), commit("c1", 3, 0)]),
    ]})
    totals = walk_loc(client, ["a"], "uid", {}, "glrodasz")
    assert totals["loc_add"] == 6
    assert client.calls == [("a", None), ("a", "CUR")]


def test_stops_at_the_cached_head_and_adds_only_new_commits():
    key = cache_key("glrodasz", "a")
    cache = {key: {"add": 100, "del": 20, "head": "old"}}
    client = FakeClient({"a": [history([commit("new", 7, 2), commit("old", 999, 999)])]})
    totals = walk_loc(client, ["a"], "uid", cache, "glrodasz")
    assert cache[key] == {"add": 107, "del": 22, "head": "new"}
    assert totals == {"loc_add": 107, "loc_del": 22, "loc": 85}


def test_cached_head_still_at_the_top_adds_nothing():
    key = cache_key("glrodasz", "a")
    cache = {key: {"add": 100, "del": 20, "head": "head"}}
    client = FakeClient({"a": [history([commit("head", 999, 999)])]})
    walk_loc(client, ["a"], "uid", cache, "glrodasz")
    assert cache[key] == {"add": 100, "del": 20, "head": "head"}


def test_empty_repo_has_no_default_branch_and_is_recorded_at_zero():
    client = FakeClient({"a": [None]})
    cache = {}
    totals = walk_loc(client, ["a"], "uid", cache, "glrodasz")
    assert totals == {"loc_add": 0, "loc_del": 0, "loc": 0}
    assert cache[cache_key("glrodasz", "a")] == {"add": 0, "del": 0, "head": None}


def test_hmac_key_selects_a_different_cache_entry():
    client = FakeClient({"a": [history([commit("c1", 4, 0)])]})
    cache = {}
    walk_loc(client, ["a"], "uid", cache, "glrodasz", hmac_key="secret")
    assert list(cache) == [cache_key("glrodasz", "a", "secret")]


def test_priv_token_is_forwarded_to_every_graphql_call():
    class TokenSpy(FakeClient):
        def graphql(self, query, variables=None, token=None):
            self.seen = token
            return super().graphql(query, variables, token)

    client = TokenSpy({"a": [history([commit("c1", 1, 0)])]})
    walk_loc(client, ["a"], "uid", {}, "glrodasz", token="pat")
    assert client.seen == "pat"


def test_a_failing_repo_is_skipped_and_the_others_still_count():
    client = FakeClient(
        {"ok": [history([commit("c1", 9, 0)])]},
        raises={"boom": RuntimeError("Could not resolve to a Repository with the name 'glrodasz/boom'.")},
    )
    totals = walk_loc(client, ["boom", "ok"], "uid", {}, "glrodasz")
    assert totals["loc_add"] == 9


def test_failure_log_leaks_neither_the_repo_name_nor_the_api_message(capsys):
    # These logs are public Actions output and GitHub's error text embeds private repo
    # names, so only the hashed key, index, and exception type may be printed.
    secret = "private-client-work"
    leaky = RuntimeError(f"Could not resolve to a Repository with the name 'glrodasz/{secret}'.")
    client = FakeClient(raises={secret: leaky})
    walk_loc(client, [secret], "uid", {}, "glrodasz", hmac_key="k")
    out = capsys.readouterr().out
    assert secret not in out
    assert "Could not resolve" not in out
    assert cache_key("glrodasz", secret, "k") in out
    assert "RuntimeError" in out
    assert "[1/1]" in out


# --- cache file I/O --------------------------------------------------------------
def test_load_cache_returns_empty_dict_when_the_file_is_absent(tmp_path):
    assert load_cache(tmp_path / "nope.json") == {}


def test_save_cache_round_trips_sorted_and_indented(tmp_path):
    path = tmp_path / "loc_cache.json"
    save_cache({"b": {"add": 1}, "a": {"add": 2}}, path)
    raw = path.read_text(encoding="utf-8")
    assert list(json.loads(raw)) == ["a", "b"]
    assert "\n  " in raw  # indent=2, so the diff stays reviewable
    assert load_cache(path) == {"b": {"add": 1}, "a": {"add": 2}}


def test_load_cache_propagates_a_corrupt_file(tmp_path):
    path = tmp_path / "loc_cache.json"
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(json.JSONDecodeError):
        load_cache(path)
