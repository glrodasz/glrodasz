"""Entry point: fetch stats, refresh the LOC cache, write both SVGs."""
import argparse
import os

from .art import load_art
from .config import DEFAULT_ART_PATH, DEFAULT_LOC_CACHE_PATH, Settings, load_dotenv
from .github import GitHubClient
from .loc import load_cache, save_cache
from .profile import DEFAULT_PROFILE_PATH, ProfileData
from .render import PALETTES, render
from .stats import fetch_stats


def parse_args(argv=None):
    ap = argparse.ArgumentParser(prog="profilecard", description=__doc__)
    ap.add_argument("--art", default=DEFAULT_ART_PATH, help="glyph grid JSON (default: %(default)s)")
    ap.add_argument("--loc-cache", default=DEFAULT_LOC_CACHE_PATH,
                    help="incremental LOC cache (default: %(default)s)")
    ap.add_argument("--profile", default=DEFAULT_PROFILE_PATH,
                    help="personal facts TOML (default: %(default)s)")
    ap.add_argument("--out-dir", default=".", help="where the SVGs are written (default: %(default)s)")
    ap.add_argument("--dry-run", action="store_true", help="render but write nothing to disk")
    return ap.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    load_dotenv()
    settings = Settings.from_env(
        art_path=args.art,
        loc_cache_path=args.loc_cache,
        out_dir=args.out_dir,
    )
    profile = ProfileData.load(args.profile)
    client = GitHubClient(settings.token)

    cache = load_cache(settings.loc_cache_path)
    stats = fetch_stats(client, profile, settings, cache)
    print("stats:", stats)

    art = load_art(settings.art_path)
    svgs = {mode: render(mode, stats, art, profile) for mode in PALETTES}

    if args.dry_run:
        print("dry run: nothing written")
        return 0

    save_cache(cache, settings.loc_cache_path)
    for mode, svg in svgs.items():
        path = os.path.join(settings.out_dir, f"{mode}_mode.svg")
        with open(path, "w", encoding="utf-8") as f:
            f.write(svg)
    print("wrote " + ", ".join(f"{mode}_mode.svg" for mode in svgs))
    return 0
