"""Logical scalar functions.

Real KQL negation is the `not()` function, not a prefix keyword:
`where not(FileName == "cmd.exe")`.
"""
from __future__ import annotations


def kql_not(value: bool) -> bool:
    if not isinstance(value, bool):
        raise TypeError("not() wymaga argumentu typu bool.")
    return not value
