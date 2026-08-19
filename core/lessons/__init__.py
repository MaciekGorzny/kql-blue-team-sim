"""Public entry point for the lessons layer.

Typical usage:

    from core.lessons import load_all_lessons

    lessons = load_all_lessons()
"""
from __future__ import annotations

from pathlib import Path

from .loader import LessonLoadError, load_lesson_file, load_lessons_from_dir
from .schema import Lesson

__all__ = [
    "load_all_lessons",
    "load_lesson_file",
    "load_lessons_from_dir",
    "Lesson",
    "LessonLoadError",
    "LESSONS_DIR",
]

LESSONS_DIR = Path(__file__).parent / "basics"


def load_all_lessons() -> list[Lesson]:
    """Loads every lesson, in the order they're conventionally numbered."""
    return load_lessons_from_dir(LESSONS_DIR)
