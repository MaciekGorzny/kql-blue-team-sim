"""Data model for incident walkthroughs.

An incident is a curated, ordered playlist of *existing* scenario ids plus
narrative framing text between them - it adds no grading logic, no log data
and no validation criteria of its own. Solving a step is solving the
underlying `core.scenarios.Scenario` it points to (see `app/incident_registry.py`
for how steps get resolved into full scenario detail).

A step has a `kind`: `"investigation"` (the default, for backward
compatibility with files that predate this field) points at a real,
gradeable `core.scenarios.Scenario` by id; `"action"` is a non-graded IR
response checklist with no scenario behind it at all - block an account,
revoke tokens, check registered devices, etc. - tracked as "done" purely
client-side (see app/static/app.js's action-progress localStorage helpers).

On-disk JSON shape::

    {
      "id": "01_prinz_eugen_ransomware",
      "title": "...",
      "summary": "...",
      "steps": [
        {"scenario_id": "014_backdoor_admin_account", "narrative": "..."},
        {
          "kind": "action",
          "title": "Natychmiastowe powstrzymanie",
          "narrative": "...",
          "actions": ["Zablokuj konto...", "Odwołaj sesje..."]
        }
      ]
    }
"""
from __future__ import annotations

import re
from dataclasses import dataclass

_ID_RE = re.compile(r"^[A-Za-z0-9_-]+$")
_KINDS = ("investigation", "action")


@dataclass(frozen=True)
class IncidentStep:
    narrative: str
    kind: str = "investigation"
    scenario_id: str | None = None
    title: str | None = None
    actions: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.kind not in _KINDS:
            raise ValueError(f"Nieprawidłowy rodzaj kroku incydentu: '{self.kind}'.")
        if self.kind == "investigation" and not self.scenario_id:
            raise ValueError("Krok typu 'investigation' wymaga pola 'scenario_id'.")
        if self.kind == "action" and not self.title:
            raise ValueError("Krok typu 'action' wymaga pola 'title'.")
        if self.kind == "action" and not self.actions:
            raise ValueError("Krok typu 'action' wymaga niepustej listy 'actions'.")


@dataclass(frozen=True)
class Incident:
    id: str
    title: str
    summary: str
    steps: tuple[IncidentStep, ...]

    def __post_init__(self) -> None:
        if not _ID_RE.match(self.id):
            raise ValueError(
                f"Nieprawidłowe id incydentu '{self.id}' - dozwolone są tylko litery, cyfry, '_' i '-'."
            )
        if not self.steps:
            raise ValueError(f"Incydent '{self.id}' nie ma żadnych kroków.")
