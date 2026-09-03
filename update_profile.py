"""Regenerate dark_mode.svg / light_mode.svg with live GitHub stats.

Runs daily via GitHub Actions. Stdlib only, no dependencies.
"""
import calendar
import hashlib
import hmac
import html
import json
import os
import urllib.request
from datetime import date, datetime, timezone


def load_dotenv(path=".env"):
    """Minimal stdlib .env loader for local runs. In GitHub Actions no .env file
    exists and real secrets come from the workflow's env/secrets instead, so this
    is a no-op there."""
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
    except FileNotFoundError:
        pass


load_dotenv()

USER = "glrodasz"
CAREER_START = date(2012, 8, 1)  # first job; day is a placeholder, month-precision only
JOINED_YEAR = 2012  # account creation year, never changes
W = 56  # info column width in characters
LOC_CACHE_PATH = "loc_cache.json"

ART_PATH = "art.json"  # colour glyph grid, generated once by make_art.py

# two tokens by design: the Actions GITHUB_TOKEN yields the contribution-style
# commit count (public + private activity), while a PAT (ACCESS_TOKEN secret)
# sees private repos for the repo list and LOC walk. Either falls back to the other.
TOKEN = os.environ.get("GITHUB_TOKEN") or os.environ.get("ACCESS_TOKEN") or ""
PRIV_TOKEN = os.environ.get("ACCESS_TOKEN") or TOKEN

# Secret key for hashing repo names before they touch loc_cache.json (see cache_key()
# below). Must stay stable across runs -- local via .env, CI via the CACHE_HMAC_KEY
# repo secret -- or every key changes and the incremental cache is defeated. See
# .env.example for how to set this up locally.
CACHE_HMAC_KEY = os.environ.get("CACHE_HMAC_KEY")


def gh(url, payload=None, token=None):
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode() if payload else None,
        headers={"Authorization": f"Bearer {token or TOKEN}", "Accept": "application/vnd.github+json"},
    )
    with urllib.request.urlopen(req) as r:
        return r.status, json.loads(r.read() or "{}")


def graphql(query, variables=None, token=None):
    _, resp = gh("https://api.github.com/graphql", {"query": query, "variables": variables or {}}, token)
    if resp.get("errors"):
        raise RuntimeError(resp["errors"])
    return resp["data"]


def age(b, t):
    """Month-precision age: (years, months). Ignores day-of-month entirely."""
    years = t.year - b.year
    months = t.month - b.month
    if months < 0:
        years -= 1
        months += 12
    return years, months


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
}""" % USER


def fetch_repos_and_meta():
    """Paginate repositories() fully so repo/star counts aren't truncated at 100."""
    cursor = None
    user_id = followers = contributed = total_count = None
    stars = 0
    names = []
    while True:
        u = graphql(REPOS_QUERY, {"cursor": cursor}, token=PRIV_TOKEN)["user"]
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


def fetch_stats(cache):
    yr_aliases = "\n".join(
        f'y{y}: contributionsCollection(from: "{y}-01-01T00:00:00Z", to: "{y + 1}-01-01T00:00:00Z")'
        " { totalCommitContributions restrictedContributionsCount }"
        for y in range(JOINED_YEAR, datetime.now(timezone.utc).year + 1)
    )
    contrib = graphql(f'query {{ user(login: "{USER}") {{ {yr_aliases} }} }}')["user"]
    commits = sum(
        v["totalCommitContributions"] + v["restrictedContributionsCount"]
        for v in contrib.values()
    )
    meta = fetch_repos_and_meta()
    stats = {
        "followers": meta["followers"],
        "repos": meta["repos"],
        "contributed": meta["contributed"],
        "stars": meta["stars"],
        "commits": commits,
    }
    stats.update(loc(meta["names"], meta["id"], cache))
    return stats


LOC_QUERY = """
query($owner: String!, $name: String!, $id: ID!, $cursor: String) {
  repository(owner: $owner, name: $name) {
    defaultBranchRef { target { ... on Commit {
      history(first: 100, author: {id: $id}, after: $cursor) {
        pageInfo { hasNextPage endCursor }
        nodes { oid additions deletions }
      }
    } } }
  }
}"""


def cache_key(name):
    """Derive the loc_cache.json key for a repo. loc_cache.json is committed to this
    PUBLIC repo, so a plaintext key would leak the existence/name of private repos to
    anyone browsing the repo or its history. Keyed with CACHE_HMAC_KEY (HMAC-SHA256)
    when available, so the name -> key mapping can't be reversed by guessing candidate
    repo names (a plain unkeyed hash can be, since repo names are low-entropy and
    guessable). Falls back to an unkeyed hash if the secret isn't set -- weaker, but
    still keeps plaintext names off disk."""
    msg = f"{USER}/{name}".encode()
    if CACHE_HMAC_KEY:
        return hmac.new(CACHE_HMAC_KEY.encode(), msg, "sha256").hexdigest()[:16]
    return hashlib.sha256(msg).hexdigest()[:16]


def loc(repo_names, user_id, cache):
    """Incremental LOC walk: stop as soon as the cached head commit is seen again,
    so only new commits since the last run are fetched. Falls back to a full walk
    for repos with no cache entry yet (new repo, or first run)."""
    total_add = total_del = 0
    for i, name in enumerate(repo_names):
        key = cache_key(name)
        entry = cache.get(key, {"add": 0, "del": 0, "head": None})
        cached_head = entry.get("head")
        cursor = None
        new_add = new_del = 0
        newest_head = None
        stop = False
        try:
            while not stop:
                ref = graphql(
                    LOC_QUERY,
                    {"owner": USER, "name": name, "id": user_id, "cursor": cursor},
                    token=PRIV_TOKEN,
                )["repository"]["defaultBranchRef"]
                if ref is None:
                    break  # empty repo
                h = ref["target"]["history"]
                for n in h["nodes"]:
                    if newest_head is None:
                        newest_head = n["oid"]
                    if cached_head and n["oid"] == cached_head:
                        stop = True
                        break
                    new_add += n["additions"]
                    new_del += n["deletions"]
                if stop or not h["pageInfo"]["hasNextPage"]:
                    break
                cursor = h["pageInfo"]["endCursor"]
        except Exception as e:
            # Deliberately omit both `name` and str(e): GitHub's GraphQL error text for a
            # missing/renamed repo (e.g. "Could not resolve to a Repository with the name
            # 'owner/name'.") can embed the repo name too, and these logs are public Actions
            # output. Only the hashed key, loop index, and exception type are safe to print.
            print(f"loc [{i + 1}/{len(repo_names)}] {key}: {type(e).__name__}")
            continue
        if newest_head:
            entry["head"] = newest_head
        entry["add"] = entry.get("add", 0) + new_add
        entry["del"] = entry.get("del", 0) + new_del
        cache[key] = entry
        total_add += entry["add"]
        total_del += entry["del"]
    return {"loc_add": total_add, "loc_del": total_del, "loc": total_add - total_del}


PALETTES = {
    "dark": {"bg": "#0d1117", "border": "#30363d", "h": "#58a6ff",
             "k": "#ffa657", "v": "#c9d1d9", "d": "#484f58", "g": "#3fb950", "r": "#f85149"},
    "light": {"bg": "#ffffff", "border": "#d0d7de", "h": "#0969da",
              "k": "#953800", "v": "#24292f", "d": "#afb8c1", "g": "#1a7f37", "r": "#cf222e"},
}


def kv(key, val, width=W):
    dots = "." * max(width - len(key) - len(str(val)) - 3, 1)
    return [(f"{key}: ", "k"), (dots + " ", "d"), (str(val), "v")]


def kv2(k1, v1, k2, v2):
    left = kv(k1, v1, 30)
    return left + [(" | ", "d")] + kv(k2, v2, 23)


def rule(title=""):
    label = f"─ {title} " if title else ""
    return [(label, "h"), ("─" * (W - len(label)), "d")]


def info_lines(s):
    y, m = age(CAREER_START, date.today())
    n = lambda x: f"{x:,}"
    return [
        [(f"{USER.lower()}@github ", "h"), ("─" * (W - len(USER) - 8), "d")],
        [],
        kv("OS", "macOS"),
        kv("Uptime", f"{y} years, {m} months"),
        kv("Host", "Stockholm.Sweden"),
        kv("Kernel", "Senior Full-stack AI Engineer"),
        kv("IDE", "Cursor, Claude Code, VS Code"),
        [],
        kv("Languages.Programming", "TypeScript, JavaScript, Python"),
        kv("Languages.Spoken", "English, Spanish"),
        kv("Hobbies", "Oil Painting"),
        [],
        rule("Contact"),
        kv("Email", "me@guillermorodas.com"),
        kv("LinkedIn", "in/guillermorodas"),
        [],
        rule("GitHub Stats"),
        kv2("Repos", f"{s['repos']} {{Contributed: {s['contributed']}}}", "Stars", n(s["stars"])),
        kv2("Commits", n(s["commits"]), "Followers", n(s["followers"])),
        [("Lines of Code: ", "k"), (n(s["loc"]), "v"), (" ( ", "d"),
         (n(s["loc_add"]) + "++", "g"), (", ", "d"), (n(s["loc_del"]) + "--", "r"), (" )", "d")],
    ]


ART_X, ART_Y, ART_W = 25, 32, 345  # glyph grid box; info column starts at x=390


def load_art():
    with open(ART_PATH, encoding="utf-8") as f:
        return json.load(f)


def art_lines(mode, art):
    """One <text> per row. Every glyph gets an explicit x (SVG positions characters
    from the x list in order, across tspans), so glyph pitch is independent of the
    viewer's monospace font; tspans carry the per-cell colour, merged into runs."""
    a = art[mode]
    cw = ART_W / art["cols"]
    ch = cw * art["cell_aspect"]
    font = f'font-family="\'Courier New\',Courier,monospace" font-weight="bold" font-size="{ch * 0.68:.2f}px"'
    out = []
    for r, (line, colors) in enumerate(zip(a["chars"], a["colors"])):
        if not line.strip():
            continue
        xs = " ".join(f"{ART_X + (c + 0.5) * cw:.1f}" for c in range(len(line)))
        runs = []
        for c, glyph in enumerate(line):
            if runs and runs[-1][0] == colors[c]:
                runs[-1][1] += glyph
            else:
                runs.append([colors[c], glyph])
        spans = "".join(f'<tspan fill="{col}">{html.escape(t)}</tspan>' for col, t in runs)
        out.append(f'<text x="{xs}" y="{ART_Y + (r + 0.5) * ch:.2f}" {font} text-anchor="middle" xml:space="preserve">{spans}</text>')
    return out


def render(mode, stats, art):
    p = PALETTES[mode]
    out = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="840" height="500" viewBox="0 0 840 500" '
        f'font-family="Consolas, Menlo, monospace" font-size="13px">',
        f'<rect x="0.5" y="0.5" width="839" height="499" rx="10" fill="{p["bg"]}" stroke="{p["border"]}"/>',
    ]
    out += art_lines(mode, art)
    for i, segs in enumerate(info_lines(stats)):
        if not segs:
            continue
        spans = "".join(f'<tspan fill="{p[c]}">{html.escape(t)}</tspan>' for t, c in segs)
        out.append(f'<text x="390" y="{45 + i * 21}" xml:space="preserve">{spans}</text>')
    out.append("</svg>")
    return "\n".join(out)


def selfcheck():
    assert age(CAREER_START, date(2026, 9, 3)) == (14, 1)
    assert age(date(2000, 3, 1), date(2026, 1, 1)) == (25, 10)
    assert age(date(2000, 1, 1), date(2026, 1, 1)) == (26, 0)
    assert len("".join(t for t, _ in kv("OS", "macOS"))) == W


def load_cache():
    try:
        with open(LOC_CACHE_PATH, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


if __name__ == "__main__":
    selfcheck()
    cache = load_cache()
    stats = fetch_stats(cache)
    print("stats:", stats)
    with open(LOC_CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2, sort_keys=True)
    art = load_art()
    for mode in PALETTES:
        with open(f"{mode}_mode.svg", "w", encoding="utf-8") as f:
            f.write(render(mode, stats, art))
    print("wrote dark_mode.svg, light_mode.svg")
