"""Runs a parsed Query AST against in-memory tables
(`{table_name: list[row_dict]}`) - no database involved.

Stage dispatch goes through the `OPERATORS` registry (see operators/__init__.py)
so adding a new operator never requires touching this file.
"""
from __future__ import annotations

from typing import Any

from . import ast_nodes as ast
from .errors import KqlEvalError
from .eval import EvalContext, eval_expr
from .operators import OPERATORS

Row = dict[str, Any]


def execute(
    query: ast.Query,
    tables: dict[str, list[Row]],
    query_text: str,
    bindings: dict[str, Any] | None = None,
) -> list[Row]:
    if query.source_table not in tables:
        available = ", ".join(sorted(tables)) or "(brak)"
        raise KqlEvalError(
            f"Nieznana tabela '{query.source_table}'. Dostępne tabele: {available}.",
            query_text,
            query.source_span,
        )

    ctx = EvalContext(query_text=query_text, tables=tables, bindings=dict(bindings or {}))
    for let_stmt in query.lets:
        # Evaluated once against an empty row, before the source table is
        # even scanned - `let` bindings are row-independent constants (real
        # KQL semantics), which falls out for free here: if the expression
        # references a real column, eval_expr's ColumnRef branch raises the
        # same "unknown column" error it would anywhere else, since {} has no
        # keys and this name isn't a prior binding either.
        ctx.bindings[let_stmt.name] = eval_expr(let_stmt.expr, {}, ctx)

    rows: list[Row] = list(tables[query.source_table])

    for stage in query.stages:
        stage_key = type(stage).__name__
        handler = OPERATORS.get(stage_key)
        if handler is None:
            raise KqlEvalError(
                f"Brak zarejestrowanego handlera dla operatora '{stage_key}'.", query_text, stage.span
            )
        rows = handler(rows, stage, ctx)

    return rows
