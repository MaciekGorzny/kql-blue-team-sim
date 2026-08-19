"""Tests for core.lessons.loader."""
import json
from pathlib import Path

import pytest

from core.lessons import load_all_lessons
from core.lessons.loader import LessonLoadError, load_lesson_file


def test_load_all_lessons_finds_sixteen_lessons():
    lessons = load_all_lessons()
    assert len(lessons) == 16


def test_lessons_are_sorted_by_filename():
    lessons = load_all_lessons()
    ids = [lesson.id for lesson in lessons]
    # 01_where.json is first, 16_leftouter_join.json is last
    assert ids[0] == "where"
    assert ids[-1] == "leftouter_join"


def test_every_lesson_has_non_empty_fields():
    for lesson in load_all_lessons():
        assert lesson.title.strip()
        assert lesson.description.strip()
        assert lesson.example_query.strip()
        assert lesson.example_explanation.strip()


def test_malformed_json_raises_lesson_load_error(tmp_path: Path):
    bad_file = tmp_path / "bad.json"
    bad_file.write_text("{not valid json", encoding="utf-8")
    with pytest.raises(LessonLoadError):
        load_lesson_file(bad_file)


def test_missing_required_field_raises_lesson_load_error(tmp_path: Path):
    bad_file = tmp_path / "bad.json"
    bad_file.write_text(json.dumps({"id": "x", "title": "y"}), encoding="utf-8")
    with pytest.raises(LessonLoadError):
        load_lesson_file(bad_file)
