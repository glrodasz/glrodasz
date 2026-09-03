"""Lines-of-code walk and its incremental, name-hashed cache."""
import hashlib
import hmac
import json

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


def cache_key(user, name, hmac_key=None):
    """Derive the loc_cache.json key for a repo. loc_cache.json is committed to this
    PUBLIC repo, so a plaintext key would leak the existence/name of private repos to
    anyone browsing the repo or its history. Keyed with CACHE_HMAC_KEY (HMAC-SHA256)
    when available, so the name -> key mapping can't be reversed by guessing candidate
    repo names (a plain unkeyed hash can be, since repo names are low-entropy and
    guessable). Falls back to an unkeyed hash if the secret isn't set -- weaker, but
    still keeps plaintext names off disk."""
    msg = f"{user}/{name}".encode()
    if hmac_key:
        return hmac.new(hmac_key.encode(), msg, "sha256").hexdigest()[:16]
    return hashlib.sha256(msg).hexdigest()[:16]


def load_cache(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def save_cache(cache, path):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2, sort_keys=True)


def walk_loc(client, repo_names, user_id, cache, user, hmac_key=None, token=None):
    """Incremental LOC walk: stop as soon as the cached head commit is seen again,
    so only new commits since the last run are fetched. Falls back to a full walk
    for repos with no cache entry yet (new repo, or first run). Mutates `cache`."""
    total_add = total_del = 0
    for i, name in enumerate(repo_names):
        key = cache_key(user, name, hmac_key)
        entry = cache.get(key, {"add": 0, "del": 0, "head": None})
        cached_head = entry.get("head")
        cursor = None
        new_add = new_del = 0
        newest_head = None
        stop = False
        try:
            while not stop:
                ref = client.graphql(
                    LOC_QUERY,
                    {"owner": user, "name": name, "id": user_id, "cursor": cursor},
                    token=token,
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
