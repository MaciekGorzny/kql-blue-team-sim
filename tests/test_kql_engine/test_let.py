"""Tests for `let` statements (parser.py's `_parse_let_statement`, executor.py's
one-time evaluation into EvalContext.bindings, and eval.py's ColumnRef lookup)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from core.kql_engine import KqlError, ast_nodes as ast, run_query
from core.kql_engine.errors import KqlParseError
from core.kql_engine.parser import parse


def test_parse_single_let_binding():
    query = parse("let x = 5; T | take 1")
    assert len(query.lets) == 1
    assert query.lets[0].name == "x"
    assert isinstance(query.lets[0].expr, ast.Literal)
    assert query.lets[0].expr.value == 5


def test_parse_multiple_sequential_let_bindings():
    query = parse("let a = 1; let b = 2; T | take 1")
    assert [let.name for let in query.lets] == ["a", "b"]


def test_parse_query_without_let_has_empty_lets_list():
    query = parse("T | take 1")
    assert query.lets == []


def test_parse_let_missing_equals_raises():
    with pytest.raises(KqlParseError):
        parse("let x 5; T | take 1")


def test_parse_let_missing_semicolon_raises():
    with pytest.raises(KqlParseError):
        parse("let x = 5 T | take 1")


def test_parse_let_missing_name_raises():
    with pytest.raises(KqlParseError):
        parse("let = 5; T | take 1")


def test_let_bound_string_used_in_where(tables):
    with_literal = run_query("DeviceProcessEvents | where FileName == 'cmd.exe'", tables)
    with_let = run_query("let target = 'cmd.exe'; DeviceProcessEvents | where FileName == target", tables)
    assert with_let == with_literal
    assert len(with_let) == 1


def test_chained_let_bindings_in_extend(tables):
    result = run_query(
        "let a = 1; let b = a + 4; DeviceProcessEvents | take 1 | extend Five = b | project Five",
        tables,
    )
    assert result == [{"Five": 5}]


def test_let_bound_ago_value_filters_recent_rows():
    now = datetime.now(timezone.utc)
    rows = [
        {"Timestamp": now - timedelta(minutes=5), "Label": "recent"},
        {"Timestamp": now - timedelta(hours=3), "Label": "old"},
    ]
    result = run_query(
        "let cutoff = ago(1h); T | where Timestamp > cutoff | project Label",
        {"T": rows},
    )
    assert result == [{"Label": "recent"}]


def test_undefined_variable_reference_raises_kql_eval_error(tables):
    with pytest.raises(KqlError):
        run_query("DeviceProcessEvents | where FileName == undefinedVar", tables)


def test_let_referencing_a_real_column_is_rejected(tables):
    # Top-level `let` bindings must be row-independent constants (real KQL
    # semantics) - evaluated once against an empty row, so referencing an
    # actual column fails the same way an unknown column would anywhere else.
    with pytest.raises(KqlError):
        run_query("let x = FileName; DeviceProcessEvents | where FileName == x", tables)


def test_let_binding_visible_inside_join_subquery():
    tables = {
        "Left": [{"Key": "k1", "X": 1}],
        "Right": [{"Key": "k1", "Y": "match"}, {"Key": "k1", "Y": "nomatch"}],
    }
    result = run_query(
        "let target = 'match'; Left | join kind=inner (Right | where Y == target) on Key",
        tables,
    )
    assert result == [{"Key": "k1", "X": 1, "Y": "match"}]
