"""Datetime scalar functions (`ago()`, `now()`, `bin()`).

`ago`/`bin` take a `timedelta` (parsed from a KQL timespan literal like `1d`
by the parser), not a string - matching real KQL syntax `ago(1d)`, not
`ago("1d")`.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone


def now() -> datetime:
    return datetime.now(timezone.utc)


def ago(delta: timedelta) -> datetime:
    return now() - delta


def bin(value: datetime, delta: timedelta) -> datetime:
    """Rounds `value` down to the nearest multiple of `delta` since the Unix epoch."""
    epoch = datetime(1970, 1, 1, tzinfo=value.tzinfo)
    total_seconds = (value - epoch).total_seconds()
    bin_seconds = delta.total_seconds()
    binned_seconds = (total_seconds // bin_seconds) * bin_seconds
    return epoch + timedelta(seconds=binned_seconds)
