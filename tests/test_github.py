import io
import json
from contextlib import contextmanager

import pytest

from profilecard import github
from profilecard.github import GitHubClient


@contextmanager
def stub_urlopen(monkeypatch, payload, status=200):
    seen = {}

    class Response(io.BytesIO):
        status = None

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            self.close()

    def fake(req):
        seen["url"] = req.full_url
        seen["headers"] = dict(req.header_items())
        seen["body"] = json.loads(req.data) if req.data else None
        r = Response(json.dumps(payload).encode())
        r.status = status
        return r

    monkeypatch.setattr(github.urllib.request, "urlopen", fake)
    yield seen


def test_request_sets_bearer_and_accept_headers(monkeypatch):
    with stub_urlopen(monkeypatch, {"ok": True}) as seen:
        status, body = GitHubClient("tok").request("https://api.github.com/user")
    assert status == 200 and body == {"ok": True}
    headers = {k.lower(): v for k, v in seen["headers"].items()}
    assert headers["authorization"] == "Bearer tok"
    assert headers["accept"] == "application/vnd.github+json"


def test_per_call_token_overrides_the_client_default(monkeypatch):
    with stub_urlopen(monkeypatch, {}) as seen:
        GitHubClient("public").request("https://api.github.com/user", token="pat")
    headers = {k.lower(): v for k, v in seen["headers"].items()}
    assert headers["authorization"] == "Bearer pat"


def test_empty_response_body_decodes_to_an_empty_dict(monkeypatch):
    class Empty(io.BytesIO):
        status = 204

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            self.close()

    monkeypatch.setattr(github.urllib.request, "urlopen", lambda req: Empty(b""))
    assert GitHubClient("t").request("https://api.github.com/x") == (204, {})


def test_graphql_posts_query_and_variables(monkeypatch):
    with stub_urlopen(monkeypatch, {"data": {"user": {"id": "u"}}}) as seen:
        data = GitHubClient("tok").graphql("query { user { id } }", {"cursor": "C"})
    assert data == {"user": {"id": "u"}}
    assert seen["url"] == "https://api.github.com/graphql"
    assert seen["body"] == {"query": "query { user { id } }", "variables": {"cursor": "C"}}


def test_graphql_sends_empty_variables_when_none_given(monkeypatch):
    with stub_urlopen(monkeypatch, {"data": {}}) as seen:
        GitHubClient("tok").graphql("query {}")
    assert seen["body"]["variables"] == {}


def test_graphql_raises_on_an_errors_payload(monkeypatch):
    with stub_urlopen(monkeypatch, {"errors": [{"message": "Bad credentials"}]}):
        with pytest.raises(RuntimeError, match="Bad credentials"):
            GitHubClient("tok").graphql("query {}")
