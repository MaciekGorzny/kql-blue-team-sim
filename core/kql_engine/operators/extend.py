"""`extend` operator: add (or overwrite) computed columns, keeping all
existing ones. Like `project`, later columns can reference earlier ones
defined in the same `extend` list.
"""
from __future__ import annotations

from .. import ast_nodes as ast
from ..eval import EvalContext, Row, eval_expr


def execute_extend(rows: list[Row], stage: ast.ExtendStage, ctx: EvalContext) -> list[Row]:
    result: list[Row] = []
    for row in rows:
        new_row = dict(row)
        for col in stage.columns:
            new_row[col.name] = eval_expr(col.expr, new_row, ctx)
        result.append(new_row)
    return result
