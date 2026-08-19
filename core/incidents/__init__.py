"""Public entry point for the incidents layer.

Typical usage:

    from core.incidents import load_all_incidents

    incidents = load_all_incidents()
"""
from __future__ import annotations

from pathlib import Path

from .loader import IncidentLoadError, load_incident_file, load_incidents_from_dir
from .schema import Incident, IncidentStep

__all__ = [
    "load_all_incidents",
    "load_incident_file",
    "load_incidents_from_dir",
    "Incident",
    "IncidentStep",
    "IncidentLoadError",
    "INCIDENTS_DIR",
]

INCIDENTS_DIR = Path(__file__).parent / "basics"


def load_all_incidents() -> list[Incident]:
    """Loads every incident, in the order they're conventionally numbered."""
    return load_incidents_from_dir(INCIDENTS_DIR)
