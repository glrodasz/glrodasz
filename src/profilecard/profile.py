"""Personal facts for the card, loaded from profile.toml.

Kept out of code on purpose: updating a bio should be a data edit. The strings are
stored pre-joined (e.g. "TypeScript, JavaScript, Python") because the separator style
is part of the rendered SVG.
"""
import tomllib
from dataclasses import dataclass
from datetime import date

DEFAULT_PROFILE_PATH = "profile.toml"


@dataclass(frozen=True)
class ProfileData:
    github_user: str
    joined_year: int
    career_start: date
    os: str
    host: str
    kernel: str
    ide: str
    hobbies: str
    languages_programming: str
    languages_spoken: str
    email: str
    linkedin: str

    @classmethod
    def load(cls, path=DEFAULT_PROFILE_PATH):
        with open(path, "rb") as f:
            raw = tomllib.load(f)
        return cls.from_dict(raw, path)

    @classmethod
    def from_dict(cls, raw, path=DEFAULT_PROFILE_PATH):
        def pick(section, key):
            try:
                return raw[section][key]
            except KeyError:
                raise KeyError(f"{path}: missing required key [{section}].{key}") from None

        career_start = pick("career", "start")
        if not isinstance(career_start, date):
            raise TypeError(f"{path}: [career].start must be a TOML date (e.g. 2012-08-01)")
        return cls(
            github_user=pick("github", "user"),
            joined_year=pick("github", "joined_year"),
            career_start=career_start,
            os=pick("about", "os"),
            host=pick("about", "host"),
            kernel=pick("about", "kernel"),
            ide=pick("about", "ide"),
            hobbies=pick("about", "hobbies"),
            languages_programming=pick("languages", "programming"),
            languages_spoken=pick("languages", "spoken"),
            email=pick("contact", "email"),
            linkedin=pick("contact", "linkedin"),
        )
