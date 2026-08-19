"""Best-effort background-noise padding for imported scenarios' custom
datasets, so a real IoC isn't literally the only row in its table.

Applied to the raw uploaded JSON (before parsing) by `importer.import_scenario`.

Padding rows are deep copies of existing rows with only their datetime
column(s) jittered to a random point within the existing time span - never
invented values - so padding can add volume/noise but can never fabricate a
brand new distinct value.

That alone isn't enough, though: a scenario's "correct answer" here is always
computed live by re-running its own reference_query (see validator.py), never
hardcoded, so padding can't make a *correct* query wrong - but it could still
dilute the *lesson*, e.g. randomly padding a reference_query like
`where RequestCount > 10` could push some originally-benign row's count over
that threshold too, turning a single clear answer into several. To rule that
out generically, without knowing anything about a given reference_query, no
distinct (non-timestamp) row content is ever duplicated past
`max_occurrences_per_row` - a hard cap, not a preference. A low-diversity
sample (few distinct rows) therefore won't necessarily reach `target_rows`:
reaching the cap on every distinct row it has is treated as "no more safe
padding available," and padding stops there instead of over-representing
whatever content it has left.
"""
from __future__ import annotations

import copy
import random
from collections import Counter
from datetime import datetime, timedelta
from typing import Any

DEFAULT_TARGET_ROWS = 150
DEFAULT_MAX_OCCURRENCES_PER_ROW = 3


def _parse_iso(value: str) -> datetime:
    text = value[:-1] + "+00:00" if value.endswith("Z") else value
    return datetime.fromisoformat(text)


def _format_iso(value: datetime, like: str) -> str:
    text = value.isoformat()
    return text.replace("+00:00", "Z") if like.endswith("Z") else text


def _row_signature(row: dict[str, Any], datetime_cols: set[str]) -> tuple:
    return tuple(sorted((k, v) for k, v in row.items() if k not in datetime_cols))


def _time_spans(rows: list[dict[str, Any]], datetime_cols: set[str]) -> dict[str, tuple[datetime, datetime, str]]:
    spans: dict[str, tuple[datetime, datetime, str]] = {}
    for col in datetime_cols:
        parsed: list[datetime] = []
        sample_text = None
        for row in rows:
            raw = row.get(col)
            if isinstance(raw, str):
                try:
                    parsed.append(_parse_iso(raw))
                    sample_text = sample_text or raw
                except ValueError:
                    continue
        if parsed:
            spans[col] = (min(parsed), max(parsed), sample_text or "")
    return spans


def pad_dataset_rows(
    dataset: dict[str, Any],
    target_rows: int,
    rng: random.Random,
    max_occurrences_per_row: int = DEFAULT_MAX_OCCURRENCES_PER_ROW,
) -> dict[str, Any]:
    """Returns a copy of `dataset` with extra rows duplicated (with jittered
    datetime columns, if any) from its existing rows, up to `target_rows`
    rows total - or fewer, if the sample doesn't have enough distinct
    (non-timestamp) row content to reach `target_rows` without pushing any
    one of them past `max_occurrences_per_row`. Reaching the cap on every
    distinct row is treated as "no more safe padding available" rather than
    as license to ignore the cap - see the module docstring for why."""
    rows = list(dataset.get("rows", []))
    if not rows:
        return dataset

    datetime_cols = {
        c["name"] for c in dataset.get("columns", []) if str(c.get("type", "")).lower() == "datetime"
    }
    occurrences = Counter(_row_signature(r, datetime_cols) for r in rows)
    capacity = sum(max(0, max_occurrences_per_row - count) for count in occurrences.values())
    to_add = min(max(0, target_rows - len(rows)), capacity)
    if to_add == 0:
        return dataset

    spans = _time_spans(rows, datetime_cols)
    candidates = [r for r in rows if occurrences[_row_signature(r, datetime_cols)] < max_occurrences_per_row]

    padded_rows = list(rows)
    for _ in range(to_add):
        template = rng.choice(candidates)
        sig = _row_signature(template, datetime_cols)

        row = copy.deepcopy(template)
        for col, (lo, hi, sample_text) in spans.items():
            span_seconds = max((hi - lo).total_seconds(), 1.0)
            offset = rng.uniform(0, span_seconds)
            row[col] = _format_iso(lo + timedelta(seconds=offset), sample_text)
        padded_rows.append(row)

        occurrences[sig] += 1
        if occurrences[sig] >= max_occurrences_per_row:
            candidates = [r for r in candidates if _row_signature(r, datetime_cols) != sig]

    if spans:
        primary_col = next(iter(spans))
        padded_rows.sort(key=lambda r: r.get(primary_col) or "")

    padded = dict(dataset)
    padded["rows"] = padded_rows
    return padded


def pad_scenario_data(data: dict[str, Any], target_rows: int = DEFAULT_TARGET_ROWS) -> dict[str, Any]:
    """Returns a copy of a scenario's raw JSON with every custom_datasets
    entry padded with background noise. Seeded by the scenario's own id so
    re-importing the identical file reproduces the same padding."""
    if not data.get("custom_datasets"):
        return data
    rng = random.Random(data.get("id"))
    padded = dict(data)
    padded["custom_datasets"] = [pad_dataset_rows(cd, target_rows, rng) for cd in data["custom_datasets"]]
    return padded
