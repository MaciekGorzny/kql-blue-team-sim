"""Data model for KQL lessons.

A lesson is data, not code, same philosophy as `core.scenarios.schema.Scenario`
- but much simpler: lessons are never graded, so there's nothing resembling a
validation criterion. Each lesson just pairs a short explanation with one
runnable example query, meant to be loaded into the trainee's editor and run
against the live shared log pool (see `core.scenarios.log_store.all_tables`).

On-disk JSON shape::

    {
      "id": "where",
      "title": "where - filtrowanie wierszy",
      "description": "...",
      "example_query": "DeviceProcessEvents | where FileName == 'powershell.exe'",
      "example_explanation": "..."
    }
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Lesson:
    id: str
    title: str
    description: str
    example_query: str
    example_explanation: str
