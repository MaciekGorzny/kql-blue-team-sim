"""Loads Lesson objects from JSON files on disk.

One lesson = one JSON file. See schema.py for the on-disk JSON shape. Mirrors
`core.scenarios.loader`'s pattern, minus everything specific to
validation/custom_datasets - there's nothing to coerce here.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .schema import Lesson


class LessonLoadError(Exception):
    """Raised when a lesson JSON file is missing required fields or malformed."""


def load_lesson_file(path: Path) -> Lesson:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise LessonLoadError(f"{path}: nieprawidłowy JSON ({e}).") from e
    return _parse_lesson(data, source=str(path))


def load_lessons_from_dir(directory: Path) -> list[Lesson]:
    """Loads every `*.json` file in `directory`, sorted by filename (lesson
    files are conventionally numbered, e.g. `01_where.json`, to control the
    order they're presented in)."""
    return [load_lesson_file(p) for p in sorted(directory.glob("*.json"))]


def _parse_lesson(data: dict[str, Any], source: str) -> Lesson:
    try:
        return Lesson(
            id=data["id"],
            title=data["title"],
            description=data["description"],
            example_query=data["example_query"],
            example_explanation=data["example_explanation"],
        )
    except KeyError as e:
        raise LessonLoadError(f"{source}: brakuje wymaganego pola {e}.") from e
