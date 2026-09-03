"""The text column: key/value rows, rules, and the full info block.

Every function returns a list of (text, colour-key) segments; render.py turns those
into <tspan>s. Colour keys index PALETTES in render.py.
"""
from datetime import date

W = 56  # info column width in characters


def age(b, t):
    """Month-precision age: (years, months). Ignores day-of-month entirely."""
    years = t.year - b.year
    months = t.month - b.month
    if months < 0:
        years -= 1
        months += 12
    return years, months


def kv(key, val, width=W):
    dots = "." * max(width - len(key) - len(str(val)) - 3, 1)
    return [(f"{key}: ", "k"), (dots + " ", "d"), (str(val), "v")]


def kv2(k1, v1, k2, v2):
    left = kv(k1, v1, 30)
    return left + [(" | ", "d")] + kv(k2, v2, 23)


def rule(title=""):
    label = f"─ {title} " if title else ""
    return [(label, "h"), ("─" * (W - len(label)), "d")]


def info_lines(s, profile, today=None):
    user = profile.github_user
    y, m = age(profile.career_start, today or date.today())
    n = lambda x: f"{x:,}"
    return [
        [(f"{user.lower()}@github ", "h"), ("─" * (W - len(user) - 8), "d")],
        [],
        kv("OS", profile.os),
        kv("Uptime", f"{y} years, {m} months"),
        kv("Host", profile.host),
        kv("Kernel", profile.kernel),
        kv("IDE", profile.ide),
        [],
        kv("Languages.Programming", profile.languages_programming),
        kv("Languages.Spoken", profile.languages_spoken),
        kv("Hobbies", profile.hobbies),
        [],
        rule("Contact"),
        kv("Email", profile.email),
        kv("LinkedIn", profile.linkedin),
        [],
        rule("GitHub Stats"),
        kv2("Repos", f"{s.repos} {{Contributed: {s.contributed}}}", "Stars", n(s.stars)),
        kv2("Commits", n(s.commits), "Followers", n(s.followers)),
        [("Lines of Code: ", "k"), (n(s.loc), "v"), (" ( ", "d"),
         (n(s.loc_add) + "++", "g"), (", ", "d"), (n(s.loc_del) + "--", "r"), (" )", "d")],
    ]
