"""Expression evaluation: turns an Expr AST node + a data row into a Python value.

Kept separate from executor.py/operators/ specifically to avoid a circular
import: operator handlers need to evaluate expressions, and the executor
needs to run operator handlers. Both depend on this module; this module
depends on neither of them.
"""
from __future__ import annotations

from typing import Any

from . import ast_nodes as ast
from .errors import KqlEvalError
from .functions import FUNCTIONS
from .functions.string_funcs import kql_contains, kql_endswith, kql_has, kql_matches_regex, kql_startswith

Row = dict[str, Any]


class EvalContext:
    """Carries whatever expression/operator evaluation needs besides the
    current row: the original query text (for error messages), a reference
    to all tables (needed by `join` to execute its right-hand sub-query), and
    the query's `let`-bound variable values (see executor.py)."""

    def __init__(
        self,
        query_text: str,
        tables: dict[str, list[Row]] | None = None,
        bindings: dict[str, Any] | None = None,
    ):
        self.query_text = query_text
        self.tables = tables
        self.bindings = bindings if bindings is not None else {}


_STRING_INFIX_OPS = {
    "contains": kql_contains,
    "startswith": kql_startswith,
    "endswith": kql_endswith,
    "has": kql_has,
    "matches regex": kql_matches_regex,
}

_COMPARISON_OPS = {
    "==": lambda a, b: a == b,
    "!=": lambda a, b: a != b,
    "<": lambda a, b: a < b,
    "<=": lambda a, b: a <= b,
    ">": lambda a, b: a > b,
    ">=": lambda a, b: a >= b,
}

_ARITHMETIC_OPS = {
    "+": lambda a, b: a + b,
    "-": lambda a, b: a - b,
    "*": lambda a, b: a * b,
    "/": lambda a, b: a / b,
    "%": lambda a, b: a % b,
}


def eval_expr(expr: ast.Expr, row: Row, ctx: EvalContext) -> Any:
    if isinstance(expr, ast.Literal):
        return expr.value
    if isinstance(expr, ast.ColumnRef):
        # A `let`-bound name takes priority over a same-named column - `let`
        # bindings are query-global constants, not per-row data, so this
        # avoids ambiguity if a trainee ever names a variable the same as a
        # column.
        if expr.name in ctx.bindings:
            return ctx.bindings[expr.name]
        if expr.name not in row:
            raise KqlEvalError(f"Nieznana kolumna '{expr.name}'.", ctx.query_text, expr.span)
        return row[expr.name]
    if isinstance(expr, ast.UnaryExpr):
        return _eval_unary(expr, row, ctx)
    if isinstance(expr, ast.BinaryExpr):
        return _eval_binary(expr, row, ctx)
    if isinstance(expr, ast.FunctionCall):
        return _eval_function_call(expr, row, ctx)
    if isinstance(expr, ast.ListExpr):
        return [eval_expr(item, row, ctx) for item in expr.items]
    raise KqlEvalError(f"Nieobsługiwany typ wyrażenia: {type(expr).__name__}.", ctx.query_text, expr.span)


def _eval_unary(expr: ast.UnaryExpr, row: Row, ctx: EvalContext) -> Any:
    value = eval_expr(expr.operand, row, ctx)
    if expr.op == "-":
        try:
            return -value
        except TypeError as e:
            raise KqlEvalError("Operator '-' wymaga wartości liczbowej.", ctx.query_text, expr.span) from e
    raise KqlEvalError(f"Nieznany operator jednoargumentowy '{expr.op}'.", ctx.query_text, expr.span)


def _eval_binary(expr: ast.BinaryExpr, row: Row, ctx: EvalContext) -> Any:
    op = expr.op

    if op == "and":
        left_val = _truthy(eval_expr(expr.left, row, ctx), ctx, expr.left.span)
        if not left_val:
            return False
        return _truthy(eval_expr(expr.right, row, ctx), ctx, expr.right.span)
    if op == "or":
        left_val = _truthy(eval_expr(expr.left, row, ctx), ctx, expr.left.span)
        if left_val:
            return True
        return _truthy(eval_expr(expr.right, row, ctx), ctx, expr.right.span)

    left = eval_expr(expr.left, row, ctx)
    right = eval_expr(expr.right, row, ctx)

    if op in _STRING_INFIX_OPS:
        if not isinstance(left, str) or not isinstance(right, str):
            raise KqlEvalError(
                f"Operator '{op}' wymaga wartości tekstowych po obu stronach.", ctx.query_text, expr.span
            )
        return _STRING_INFIX_OPS[op](left, right)

    if op in _COMPARISON_OPS:
        try:
            return _COMPARISON_OPS[op](left, right)
        except TypeError as e:
            raise KqlEvalError(
                f"Nie można porównać wartości operatorem '{op}' (niekompatybilne typy).", ctx.query_text, expr.span
            ) from e

    if op in _ARITHMETIC_OPS:
        try:
            return _ARITHMETIC_OPS[op](left, right)
        except TypeError as e:
            raise KqlEvalError(
                f"Nie można wykonać '{op}' na wartościach niekompatybilnych typów.", ctx.query_text, expr.span
            ) from e
        except ZeroDivisionError as e:
            raise KqlEvalError("Dzielenie przez zero.", ctx.query_text, expr.span) from e

    if op == "in":
        if not isinstance(right, (list, tuple, set)):
            raise KqlEvalError(
                "Operator 'in' wymaga listy po prawej stronie (np. z 'dynamic([...])' lub zmiennej 'let').",
                ctx.query_text,
                expr.span,
            )
        return left in right

    raise KqlEvalError(f"Nieznany operator '{op}'.", ctx.query_text, expr.span)


def _eval_function_call(expr: ast.FunctionCall, row: Row, ctx: EvalContext) -> Any:
    func = FUNCTIONS.get(expr.name)
    if func is None:
        raise KqlEvalError(f"Nieznana funkcja '{expr.name}()'.", ctx.query_text, expr.span)
    args = [eval_expr(a, row, ctx) for a in expr.args]
    try:
        return func(*args)
    except TypeError as e:
        raise KqlEvalError(f"Nieprawidłowe argumenty w wywołaniu {expr.name}(): {e}", ctx.query_text, expr.span) from e
    except ValueError as e:
        raise KqlEvalError(f"Błąd w wywołaniu {expr.name}(): {e}", ctx.query_text, expr.span) from e


def _truthy(value: Any, ctx: EvalContext, span: Any) -> bool:
    if not isinstance(value, bool):
        raise KqlEvalError(
            "Wyrażenie logiczne ('and'/'or') musi mieć wartość typu bool po obu stronach.", ctx.query_text, span
        )
    return value
