"""Aggregate the GitHub numbers shown on the card."""
from dataclasses import dataclass
from datetime import UTC, datetime

from .loc import walk_loc

REPOS_QUERY = """
query($cursor: String) {
  user(login: "%s") {
    id
    followers { totalCount }
    repositories(first: 100, after: $cursor, ownerAffiliations: OWNER) {
      totalCount
      pageInfo { hasNextPage endCursor }
      nodes { name stargazerCount isFork }
    }
    repositoriesContributedTo(first: 1, contributionTypes: [COMMIT, PULL_REQUEST, REPOSITORY]) {
      totalCount
    }
  }
}"""


@dataclass(frozen=True)
class Stats:
    followers: int
    repos: int
    contributed: int
    stars: int
    commits: int
    loc: int
    loc_add: int
    loc_del: int


def fetch_repos_and_meta(client, user, token=None):
    """Paginate repositories() fully so repo/star counts aren't truncated at 100."""
    query = REPOS_QUERY % user
    cursor = None
    user_id = followers = contributed = total_count = None
    stars = 0
    names = []
    while True:
        u = client.graphql(query, {"cursor": cursor}, token=token)["user"]
        user_id = u["id"]
        followers = u["followers"]["totalCount"]
        contributed = u["repositoriesContributedTo"]["totalCount"]
        repos = u["repositories"]
        total_count = repos["totalCount"]
        for n in repos["nodes"]:
            stars += n["stargazerCount"]
            if not n["isFork"]:
                names.append(n["name"])
        if not repos["pageInfo"]["hasNextPage"]:
            break
        cursor = repos["pageInfo"]["endCursor"]
    return {
        "id": user_id,
        "followers": followers,
        "contributed": contributed,
        "repos": total_count,
        "stars": stars,
        "names": names,
    }


def fetch_stats(client, profile, settings, cache):
    user = profile.github_user
    yr_aliases = "\n".join(
        f'y{y}: contributionsCollection(from: "{y}-01-01T00:00:00Z", to: "{y + 1}-01-01T00:00:00Z")'
        " { totalCommitContributions restrictedContributionsCount }"
        for y in range(profile.joined_year, datetime.now(UTC).year + 1)
    )
    contrib = client.graphql(f'query {{ user(login: "{user}") {{ {yr_aliases} }} }}')["user"]
    commits = sum(
        v["totalCommitContributions"] + v["restrictedContributionsCount"]
        for v in contrib.values()
    )
    meta = fetch_repos_and_meta(client, user, token=settings.priv_token)
    loc_totals = walk_loc(
        client,
        meta["names"],
        meta["id"],
        cache,
        user,
        hmac_key=settings.cache_hmac_key,
        token=settings.priv_token,
    )
    return Stats(
        followers=meta["followers"],
        repos=meta["repos"],
        contributed=meta["contributed"],
        stars=meta["stars"],
        commits=commits,
        **loc_totals,
    )
