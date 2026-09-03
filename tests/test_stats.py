import pytest

from profilecard.config import Settings
from profilecard.stats import Stats, fetch_repos_and_meta, fetch_stats


class ScriptedClient:
    """Answers GraphQL by looking at the shape of the query, so the tests don't
    depend on call ordering inside fetch_stats()."""

    def __init__(self, repo_pages, contributions, histories=None):
        self.repo_pages = list(repo_pages)
        self.contributions = contributions
        self.histories = histories or {}
        self.tokens = []

    def graphql(self, query, variables=None, token=None):
        self.tokens.append(token)
        if "contributionsCollection" in query:
            return {"user": self.contributions}
        if "repositories(" in query:
            return {"user": self.repo_pages.pop(0)}
        pages = self.histories[variables["name"]]
        return {"repository": {"defaultBranchRef": {"target": {"history": pages.pop(0)}}}}


def repo_page(nodes, total, next_cursor=None, followers=10, contributed=3):
    return {
        "id": "UID",
        "followers": {"totalCount": followers},
        "repositoriesContributedTo": {"totalCount": contributed},
        "repositories": {
            "totalCount": total,
            "pageInfo": {"hasNextPage": next_cursor is not None, "endCursor": next_cursor},
            "nodes": nodes,
        },
    }


def repo(name, stars=0, fork=False):
    return {"name": name, "stargazerCount": stars, "isFork": fork}


def history(nodes):
    return {"pageInfo": {"hasNextPage": False, "endCursor": None}, "nodes": nodes}


def test_repo_pagination_sums_stars_across_every_page():
    client = ScriptedClient(
        [repo_page([repo("a", 5)], total=150, next_cursor="C"),
         repo_page([repo("b", 7)], total=150)],
        contributions={},
    )
    meta = fetch_repos_and_meta(client, "glrodasz")
    assert meta["stars"] == 12
    assert meta["repos"] == 150  # totalCount, not len(nodes)
    assert meta["names"] == ["a", "b"]


def test_forks_count_toward_stars_but_not_the_loc_walk():
    client = ScriptedClient([repo_page([repo("mine", 1), repo("forked", 9, fork=True)], total=2)], {})
    meta = fetch_repos_and_meta(client, "glrodasz")
    assert meta["stars"] == 10
    assert meta["names"] == ["mine"]


def test_fetch_stats_sums_public_and_restricted_contributions():
    client = ScriptedClient(
        [repo_page([], total=0)],
        contributions={
            "y2012": {"totalCommitContributions": 100, "restrictedContributionsCount": 5},
            "y2013": {"totalCommitContributions": 200, "restrictedContributionsCount": 0},
        },
    )
    stats = fetch_stats(client, _profile(), Settings(), {})
    assert stats.commits == 305


def test_fetch_stats_returns_a_stats_dataclass_with_loc_totals():
    client = ScriptedClient(
        [repo_page([repo("a", 4)], total=1, followers=42, contributed=7)],
        contributions={"y2012": {"totalCommitContributions": 9, "restrictedContributionsCount": 1}},
        histories={"a": [history([{"oid": "c1", "additions": 30, "deletions": 12}])]},
    )
    stats = fetch_stats(client, _profile(), Settings(), {})
    assert isinstance(stats, Stats)
    assert (stats.followers, stats.repos, stats.contributed, stats.stars) == (42, 1, 7, 4)
    assert (stats.loc_add, stats.loc_del, stats.loc) == (30, 12, 18)


def test_the_private_token_is_used_for_repos_and_loc_but_not_contributions():
    client = ScriptedClient(
        [repo_page([repo("a")], total=1)],
        contributions={"y2012": {"totalCommitContributions": 0, "restrictedContributionsCount": 0}},
        histories={"a": [history([])]},
    )
    fetch_stats(client, _profile(), Settings(token="pub", priv_token="pat"), {})
    # first call is the contribution query (client default token), the rest use the PAT
    assert client.tokens[0] is None
    assert set(client.tokens[1:]) == {"pat"}


def test_stats_is_frozen(stats):
    with pytest.raises(AttributeError):
        stats.commits = 0


def _profile():
    from datetime import date

    from profilecard.profile import ProfileData
    return ProfileData(
        github_user="glrodasz", joined_year=2012, career_start=date(2012, 8, 1),
        os="o", host="h", kernel="k", ide="i", hobbies="b",
        languages_programming="p", languages_spoken="s", email="e", linkedin="l",
    )
