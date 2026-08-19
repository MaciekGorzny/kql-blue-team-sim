"""Safety net for the on-disk lesson files: every lesson's example_query must
actually execute against the live shared log pool. Catches a broken/rotted
lesson example immediately instead of a trainee hitting it first."""
from core.kql_engine import KqlError, run_query
from core.lessons import load_all_lessons
from core.scenarios import all_tables


def test_every_lesson_example_query_executes_successfully():
    tables = all_tables()
    for lesson in load_all_lessons():
        try:
            run_query(lesson.example_query, tables)
        except KqlError as e:
            raise AssertionError(f"{lesson.id}: example_query failed to execute: {e}") from e
