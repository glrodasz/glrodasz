"""Thin GitHub REST/GraphQL client. Stdlib only."""
import json
import urllib.request

API_ROOT = "https://api.github.com"


class GitHubClient:
    """Holds the default token; per-call `token=` still overrides it so the
    public/private token split stays explicit at each call site."""

    def __init__(self, token=""):
        self.token = token

    def request(self, url, payload=None, token=None):
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode() if payload else None,
            headers={
                "Authorization": f"Bearer {token or self.token}",
                "Accept": "application/vnd.github+json",
            },
        )
        with urllib.request.urlopen(req) as r:
            return r.status, json.loads(r.read() or "{}")

    def graphql(self, query, variables=None, token=None):
        _, resp = self.request(f"{API_ROOT}/graphql", {"query": query, "variables": variables or {}}, token)
        if resp.get("errors"):
            raise RuntimeError(resp["errors"])
        return resp["data"]
