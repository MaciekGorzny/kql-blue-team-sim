"""Data model for training scenarios.

A scenario is data, not code: task text + which dataset(s) it uses + how to
validate a submitted query. This module is also the source of truth for the
on-disk JSON shape scenarios are loaded from (see loader.py) - designed now
so that future scenario import/generation has a stable target format, even
though external import isn't implemented yet.

On-disk JSON shape::

    {
      "id": "001_find_lolbin_rundll32",
      "title": "...",
      "prompt": "...",
      "datasets": ["DeviceProcessEvents"],
      "difficulty": "beginner",              // beginner | intermediate | advanced
      "mitre_techniques": ["T1218.011"],      // optional
      "hint": "...",                          // optional
      "source_url": "https://...",            // optional, see below
      "sc200_area": "...",                    // optional, see below
      "validation": {
        "result_match": {                     // mode (a) - optional
          "reference_query": "...",
          "ordered": false                    // optional, default false
        },
        "required_usage": {                   // mode (b) - optional
          "required_operators": ["SummarizeStage"],
          "required_columns": ["DeviceName"]
        }
      },
      "custom_datasets": [                    // optional - see below
        {
          "name": "ImportedProcessEvents",
          "columns": [
            {"name": "Timestamp", "type": "datetime"},
            {"name": "FileName", "type": "string", "description": "..."}
          ],
          "rows": [
            {"Timestamp": "2026-08-10T08:00:00Z", "FileName": "evil.exe"}
          ]
        }
      ]
    }

At least one of `result_match` / `required_usage` must be present; both may
be present at once (e.g. "must use summarize AND produce this exact result").

`custom_datasets` lets an imported scenario bring its own log rows (e.g. built
from a real malware sample's IoCs) instead of only referencing the fixed
built-in tables in `core.datasets` - each entry's `name` must also appear in
`datasets`. `type` is a `KqlType` member name, case-insensitive
(string/long/real/bool/datetime/timespan/dynamic/null). A row may omit a
declared column; it is filled in as `null`. `datetime` values must be
ISO-8601 strings (a bare `Z` suffix is accepted as UTC).

`source_url` is an optional link to the write-up/report a scenario was built
from (if any) - shown to the trainee only after they solve it, as a "read the
real incident" reward rather than a spoiler available up front.

`sc200_area` is an optional free-text label naming which Microsoft product/
workload the scenario's data represents, for trainees studying towards the
SC-200 (Microsoft Security Operations Analyst) exam - e.g. "Microsoft
Defender for Endpoint (MDE)", "Microsoft Entra ID", "Microsoft Defender for
Office 365", or "Korelacja między źródłami (Sentinel)" for a scenario
spanning more than one product's tables. It's descriptive metadata only (not
used by validation), shown alongside the difficulty/MITRE badges.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Any

from core.kql_engine.ast_nodes import KqlType

_ID_RE = re.compile(r"^[A-Za-z0-9_-]+$")


class Difficulty(Enum):
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"


@dataclass(frozen=True)
class ResultMatchCriterion:
    """Validation mode (a): the submitted query's result must match a
    reference query's result, run against the same dataset(s). Row order
    only matters if `ordered` is True."""

    reference_query: str
    ordered: bool = False


@dataclass(frozen=True)
class RequiredUsageCriterion:
    """Validation mode (b): the submitted query's AST must use at least the
    given operators (by Stage class name, e.g. "SummarizeStage") and/or
    reference at least the given column names somewhere in an expression -
    for scenarios that teach a technique, not just a specific result."""

    required_operators: tuple[str, ...] = ()
    required_columns: tuple[str, ...] = ()


@dataclass(frozen=True)
class CustomColumn:
    """One column of a scenario-local dataset (see `CustomDataset`)."""

    name: str
    kql_type: KqlType
    description: str = ""


@dataclass(frozen=True)
class CustomDataset:
    """A log table an imported scenario brings with it, instead of (or
    alongside) the fixed tables in `core.datasets` - e.g. process/logon
    events built from a real malware sample's IoCs."""

    name: str
    columns: tuple[CustomColumn, ...]
    rows: tuple[dict[str, Any], ...]


@dataclass(frozen=True)
class Scenario:
    id: str
    title: str
    prompt: str
    datasets: tuple[str, ...]
    difficulty: Difficulty
    mitre_techniques: tuple[str, ...] = ()
    hint: str | None = None
    source_url: str | None = None
    sc200_area: str | None = None
    result_match: ResultMatchCriterion | None = None
    required_usage: RequiredUsageCriterion | None = None
    custom_datasets: tuple[CustomDataset, ...] = ()

    def __post_init__(self) -> None:
        if self.result_match is None and self.required_usage is None:
            raise ValueError(f"Scenariusz '{self.id}' nie ma żadnego kryterium walidacji.")
        if not _ID_RE.match(self.id):
            raise ValueError(
                f"Nieprawidłowe id scenariusza '{self.id}' - dozwolone są tylko litery, cyfry, '_' i '-'."
            )
        custom_names = {cd.name for cd in self.custom_datasets}
        unused = custom_names - set(self.datasets)
        if unused:
            raise ValueError(
                f"Scenariusz '{self.id}': custom_datasets zawiera tabele nieużyte w 'datasets': "
                f"{sorted(unused)}."
            )
