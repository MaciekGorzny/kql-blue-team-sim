"""Registry mapping KQL scalar function names to their Python implementations.

Adding a new function means adding one entry here - no other file needs to
change.
"""
from __future__ import annotations

from typing import Any, Callable

from . import datetime_funcs, logical_funcs, string_funcs

def _dynamic(value: Any) -> Any:
    """KQL `dynamic(x)`: tags a value as dynamically-typed. This engine has no
    separate boxed "dynamic" runtime type - a Python list/dict already
    behaves like one - so this is just an identity pass-through, almost
    always called as `dynamic([...])` (a list literal, see ast.ListExpr)."""
    return value


FUNCTIONS: dict[str, Callable[..., Any]] = {
    "tolower": string_funcs.tolower,
    "toupper": string_funcs.toupper,
    "strcat": string_funcs.strcat,
    "split": string_funcs.split,
    "ago": datetime_funcs.ago,
    "now": datetime_funcs.now,
    "bin": datetime_funcs.bin,
    "not": logical_funcs.kql_not,
    "dynamic": _dynamic,
}
