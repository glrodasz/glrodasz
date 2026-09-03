"""Runtime settings: tokens from the environment, paths from the CLI.

Nothing here runs at import time -- load_dotenv() is called from cli.main(), so
importing any module of this package has no side effects and tests can build a
Settings directly.
"""
import os
from dataclasses import dataclass

DEFAULT_ART_PATH = "art.json"  # colour glyph grid, generated once by tools/make_art.py
DEFAULT_LOC_CACHE_PATH = "loc_cache.json"


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


@dataclass(frozen=True)
class Settings:
    # two tokens by design: the Actions GITHUB_TOKEN yields the contribution-style
    # commit count (public + private activity), while a PAT (ACCESS_TOKEN secret)
    # sees private repos for the repo list and LOC walk. Either falls back to the other.
    token: str = ""
    priv_token: str = ""
    # Secret key for hashing repo names before they touch loc_cache.json (see
    # loc.cache_key()). Must stay stable across runs -- local via .env, CI via the
    # CACHE_HMAC_KEY repo secret -- or every key changes and the incremental cache is
    # defeated. See .env.example for how to set this up locally.
    cache_hmac_key: str | None = None
    art_path: str = DEFAULT_ART_PATH
    loc_cache_path: str = DEFAULT_LOC_CACHE_PATH
    out_dir: str = "."

    @classmethod
    def from_env(cls, env=None, **overrides):
        env = os.environ if env is None else env
        token = env.get("GITHUB_TOKEN") or env.get("ACCESS_TOKEN") or ""
        return cls(
            token=token,
            priv_token=env.get("ACCESS_TOKEN") or token,
            cache_hmac_key=env.get("CACHE_HMAC_KEY"),
            **overrides,
        )
