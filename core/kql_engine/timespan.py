"""Parsing for KQL timespan literals: `1d`, `30m`, `2h`, `500ms`, `45s`."""
from __future__ import annotations

import re
from datetime import timedelta

_PATTERN = re.compile(r"(\d+(?:\.\d+)?)(ms|d|h|m|s)$")
_UNIT_TO_KWARG = {"d": "days", "h": "hours", "m": "minutes", "s": "seconds", "ms": "milliseconds"}


def parse_timespan(text: str) -> timedelta:
    match = _PATTERN.fullmatch(text.strip())
    if not match:
        raise ValueError(
            f"Nieprawidłowy format timespan: {text!r} (oczekiwano np. '1d', '30m', '2h', '500ms')."
        )
    value, unit = match.groups()
    return timedelta(**{_UNIT_TO_KWARG[unit]: float(value)})
