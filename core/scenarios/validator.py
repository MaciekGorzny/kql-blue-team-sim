"""Validates a trainee's submitted KQL query against a Scenario's criteria.

The "expected result" for mode (a) is never hardcoded in a scenario file -
it's computed by actually running the scenario's `reference_query` against
the live dataset at validation time. This means the dataset and the expected
answers can never drift apart: change the dataset, and every scenario's
notion of "correct" updates automatically.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from core.kql_engine import KqlError, ast_nodes as ast, parse_query, run_query

from .schema import RequiredUsageCriterion, ResultMatchCriterion, Scenario

Row = dict[str, Any]


@dataclass
class ValidationResult:
    correct: bool
    message: str
    user_result: list[Row] | None = None
    expected_result: list[Row] | None = None


def validate(scenario: Scenario, user_query: str, tables: dict[str, list[Row]] | None = None) -> ValidationResult:
    if tables is None:
        # Deferred import breaks a circular dependency (log_store -> loader ->
        # schema, none of which import validator; validator importing
        # log_store at module scope would only cycle back through __init__,
        # so importing here at call time avoids that entirely) and lets every
        # existing 2-arg `validate(scenario, query)` call keep working against
        # the live, always-fresh shared log pool by default.
        from .log_store import all_tables

        tables = all_tables()

    try:
        user_rows = run_query(user_query, tables)
    except KqlError as e:
        return ValidationResult(correct=False, message=str(e))

    if scenario.required_usage is not None:
        usage_result = _check_required_usage(scenario.required_usage, user_query)
        if not usage_result.correct:
            # The query itself ran fine (we already have user_rows) - only the
            # *technique* requirement failed, so still surface what the user's
            # query actually produced instead of treating this like a hard error.
            usage_result.user_result = user_rows
            return usage_result

    if scenario.result_match is not None:
        return _check_result_match(scenario.result_match, user_rows, tables)

    return ValidationResult(correct=True, message="Poprawnie! Użyto wymaganej techniki.", user_result=user_rows)


def _check_result_match(
    criterion: ResultMatchCriterion, user_rows: list[Row], tables: dict[str, list[Row]]
) -> ValidationResult:
    expected_rows = run_query(criterion.reference_query, tables)

    matches = user_rows == expected_rows if criterion.ordered else _unordered_equal(user_rows, expected_rows)

    if matches:
        return ValidationResult(correct=True, message="Poprawnie! Wynik zgodny z oczekiwanym.", user_result=user_rows)
    return ValidationResult(
        correct=False,
        message="Wynik zapytania różni się od oczekiwanego.",
        user_result=user_rows,
        expected_result=expected_rows,
    )


def _unordered_equal(a: list[Row], b: list[Row]) -> bool:
    if len(a) != len(b):
        return False

    def sort_key(row: Row) -> tuple:
        return tuple(sorted(row.items(), key=lambda kv: kv[0]))

    return sorted(map(sort_key, a)) == sorted(map(sort_key, b))


def _check_required_usage(criterion: RequiredUsageCriterion, user_query: str) -> ValidationResult:
    try:
        query = parse_query(user_query)
    except KqlError as e:
        return ValidationResult(correct=False, message=str(e))

    used_stage_types = {type(stage).__name__ for stage in query.stages}
    missing_ops = [op for op in criterion.required_operators if op not in used_stage_types]
    if missing_ops:
        return ValidationResult(
            correct=False, message=f"To zadanie wymaga użycia operatora(ów): {', '.join(missing_ops)}."
        )

    used_columns = _collect_column_names(query)
    missing_cols = [c for c in criterion.required_columns if c not in used_columns]
    if missing_cols:
        return ValidationResult(
            correct=False,
            message=f"To zadanie wymaga odwołania się do kolumny(kolumn): {', '.join(missing_cols)}.",
        )

    return ValidationResult(correct=True, message="Użyto wymaganej techniki.")


def _collect_column_names(query: ast.Query) -> set[str]:
    """Walks the whole query AST (all stages, including a join's nested
    right-hand sub-query) and collects every ColumnRef name referenced
    anywhere - used to check the `required_columns` criterion."""
    names: set[str] = set()

    def walk_expr(expr: ast.Expr) -> None:
        if isinstance(expr, ast.ColumnRef):
            names.add(expr.name)
        elif isinstance(expr, ast.BinaryExpr):
            walk_expr(expr.left)
            walk_expr(expr.right)
        elif isinstance(expr, ast.UnaryExpr):
            walk_expr(expr.operand)
        elif isinstance(expr, ast.FunctionCall):
            for arg in expr.args:
                walk_expr(arg)

    def walk_query(q: ast.Query) -> None:
        for stage in q.stages:
            if isinstance(stage, ast.WhereStage):
                walk_expr(stage.condition)
            elif isinstance(stage, (ast.ProjectStage, ast.ExtendStage)):
                for col in stage.columns:
                    walk_expr(col.expr)
            elif isinstance(stage, ast.SortStage):
                for key in stage.keys:
                    walk_expr(key.expr)
            elif isinstance(stage, ast.SummarizeStage):
                for agg in stage.aggregates:
                    if agg.arg is not None:
                        walk_expr(agg.arg)
                for col in stage.group_by:
                    walk_expr(col.expr)
            elif isinstance(stage, ast.JoinStage):
                for key in stage.on:
                    walk_expr(key.left_expr)
                    walk_expr(key.right_expr)
                walk_query(stage.right)

    walk_query(query)
    return names
