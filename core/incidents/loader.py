"""Loads Incident objects from JSON files on disk.

One incident = one JSON file. See schema.py for the on-disk JSON shape.
Mirrors `core.lessons.loader`'s pattern - deliberately doesn't check that a
step's `scenario_id` resolves to a real scenario (that would require
importing `core.scenarios` here); that referential-integrity check lives in
tests instead (`tests/test_incidents/test_incident_files.py`).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .schema import Incident, IncidentStep


class IncidentLoadError(Exception):
    """Raised when an incident JSON file is missing required fields or malformed."""


def load_incident_file(path: Path) -> Incident:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise IncidentLoadError(f"{path}: nieprawidłowy JSON ({e}).") from e
    return _parse_incident(data, source=str(path))


def load_incidents_from_dir(directory: Path) -> list[Incident]:
    """Loads every `*.json` file in `directory`, sorted by filename (incident
    files are conventionally numbered, e.g. `01_...json`, to control the
    order they're presented in)."""
    return [load_incident_file(p) for p in sorted(directory.glob("*.json"))]


def _parse_step(data: dict[str, Any], source: str) -> IncidentStep:
    try:
        return IncidentStep(
            narrative=data["narrative"],
            kind=data.get("kind", "investigation"),
            scenario_id=data.get("scenario_id"),
            title=data.get("title"),
            actions=tuple(data.get("actions", [])),
        )
    except KeyError as e:
        raise IncidentLoadError(f"{source}: krok incydentu - brakuje wymaganego pola {e}.") from e
    except ValueError as e:
        raise IncidentLoadError(f"{source}: krok incydentu - {e}") from e


def _parse_incident(data: dict[str, Any], source: str) -> Incident:
    try:
        steps = tuple(_parse_step(s, source) for s in data["steps"])
        return Incident(
            id=data["id"],
            title=data["title"],
            summary=data["summary"],
            steps=steps,
        )
    except KeyError as e:
        raise IncidentLoadError(f"{source}: brakuje wymaganego pola {e}.") from e
    except ValueError as e:
        raise IncidentLoadError(f"{source}: {e}") from e
