"""Thin lesson lookup helpers, mirroring app/scenario_registry.py.

Reloads lessons from disk on every call rather than caching - same rationale
as scenario_registry.py: cheap at this file count, and it means editing a
lesson file takes effect without restarting the server.
"""
from __future__ import annotations

from typing import Any

from fastapi import HTTPException

from core.lessons import Lesson, load_all_lessons


def get_all_lessons() -> list[Lesson]:
    return load_all_lessons()


def get_lesson_or_404(lesson_id: str) -> Lesson:
    for lesson in load_all_lessons():
        if lesson.id == lesson_id:
            return lesson
    raise HTTPException(status_code=404, detail=f"Nieznana lekcja '{lesson_id}'.")


def lesson_to_summary_dict(lesson: Lesson) -> dict[str, Any]:
    return {"id": lesson.id, "title": lesson.title}


def lesson_to_dict(lesson: Lesson) -> dict[str, Any]:
    return {
        "id": lesson.id,
        "title": lesson.title,
        "description": lesson.description,
        "example_query": lesson.example_query,
        "example_explanation": lesson.example_explanation,
    }
