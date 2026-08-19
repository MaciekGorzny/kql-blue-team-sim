"""String scalar functions/operators available in `where`/`extend`/`project`.

`kql_matches_regex` uses Python's `re` module - close to, but not identical
with, the RE2 dialect real Kusto uses (e.g. no lookbehind differences aside,
most everyday hunting patterns behave the same). Good enough for training
scenarios; worth revisiting if a scenario needs RE2-specific behavior.
"""
from __future__ import annotations

import re

_TOKEN_RE = re.compile(r"[A-Za-z0-9_]+")


def kql_contains(haystack: str, needle: str) -> bool:
    return needle.lower() in haystack.lower()


def kql_startswith(haystack: str, needle: str) -> bool:
    return haystack.lower().startswith(needle.lower())


def kql_endswith(haystack: str, needle: str) -> bool:
    return haystack.lower().endswith(needle.lower())


def kql_has(haystack: str, needle: str) -> bool:
    """KQL `has`: exact, case-insensitive match against a whole token, where a
    token is a maximal run of alphanumeric/underscore characters. This is
    NOT a substring test: `"cmd.exe" has "cmd"` is True, but
    `"scmd.exe" has "cmd"` is False.
    """
    needle_lower = needle.lower()
    return any(tok.lower() == needle_lower for tok in _TOKEN_RE.findall(haystack))


def kql_matches_regex(haystack: str, pattern: str) -> bool:
    return re.search(pattern, haystack) is not None


def tolower(value: str) -> str:
    return value.lower()


def toupper(value: str) -> str:
    return value.upper()


def strcat(*parts: object) -> str:
    return "".join(str(p) for p in parts)


def split(value: str, delimiter: str) -> list[str]:
    return value.split(delimiter)
