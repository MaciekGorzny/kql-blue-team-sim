"""Tests for `dynamic([...])` list literals and the `in` membership operator
(parser.py's `_parse_in_operand`/`[...]` primary rule, eval.py's ListExpr
evaluation and "in" BinaryExpr handling)."""
from __future__ import annotations

import pytest

from core.kql_engine import KqlError, ast_nodes as ast, run_query
from core.kql_engine.errors import KqlParseError
from core.kql_engine.parser import parse


def test_parse_bracket_list_literal():
    query = parse("T | project X = [1, 2, 3]")
    expr = query.stages[0].columns[0].expr
    assert isinstance(expr, ast.ListExpr)
    assert [item.value for item in expr.items] == [1, 2, 3]


def test_parse_empty_bracket_list_literal():
    query = parse("T | project X = []")
    expr = query.stages[0].columns[0].expr
    assert isinstance(expr, ast.ListExpr)
    assert expr.items == []


def test_parse_in_with_multiple_items_becomes_list_expr():
    query = parse("T | where Name in ('a', 'b')")
    cond = query.stages[0].condition
    assert isinstance(cond, ast.BinaryExpr)
    assert cond.op == "in"
    assert isinstance(cond.right, ast.ListExpr)
    assert len(cond.right.items) == 2


def test_parse_in_with_single_column_ref_is_not_wrapped():
    # `in (x)` where x is a name reference passes it through unwrapped, so a
    # `let`-bound dynamic variable works directly without double-wrapping.
    query = parse("T | where Name in (allowed)")
    cond = query.stages[0].condition
    assert isinstance(cond.right, ast.ColumnRef)
    assert cond.right.name == "allowed"


def test_parse_in_with_single_literal_is_wrapped_into_a_one_item_list():
    # Unlike a name reference, a bare literal can never itself already be a
    # list, so `in ('z')` means "the 1-element set {'z'}", not "z" raw.
    query = parse("T | where Name in ('z')")
    cond = query.stages[0].condition
    assert isinstance(cond.right, ast.ListExpr)
    assert len(cond.right.items) == 1


def test_parse_in_missing_closing_paren_raises():
    with pytest.raises(KqlParseError):
        parse("T | where Name in ('a', 'b'")


@pytest.fixture
def tables() -> dict[str, list[dict]]:
    return {
        "T": [
            {"Name": "a", "Value": 1},
            {"Name": "b", "Value": 5},
            {"Name": "c", "Value": 9},
        ]
    }


def test_in_with_literal_list(tables):
    result = run_query("T | where Name in ('a', 'c')", tables)
    assert [r["Name"] for r in result] == ["a", "c"]


def test_in_with_dynamic_literal(tables):
    result = run_query("T | where Name in (dynamic(['a', 'c']))", tables)
    assert [r["Name"] for r in result] == ["a", "c"]


def test_in_with_let_bound_dynamic_list(tables):
    result = run_query("let allowed = dynamic(['a', 'b']); T | where Name in (allowed)", tables)
    assert [r["Name"] for r in result] == ["a", "b"]


def test_negated_in_via_not_function(tables):
    result = run_query("T | where not(Name in ('a', 'c'))", tables)
    assert [r["Name"] for r in result] == ["b"]


def test_dynamic_value_usable_in_extend(tables):
    result = run_query("T | take 1 | extend Tags = dynamic(['x', 'y']) | project Tags", tables)
    assert result == [{"Tags": ["x", "y"]}]


def test_in_with_let_bound_non_list_scalar_raises(tables):
    # A bare literal in parens (`in (5)`) is always wrapped into a 1-element
    # list (see _parse_in_operand), so it's never ambiguous - but a `let`
    # name that turns out to be bound to a non-list value only fails at
    # evaluation time, once it's resolved.
    with pytest.raises(KqlError):
        run_query("let notAList = 5; T | where Name in (notAList)", tables)


def test_in_membership_false_is_not_an_error(tables):
    result = run_query("T | where Name in ('z')", tables)
    assert result == []
