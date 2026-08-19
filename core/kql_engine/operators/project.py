"""`project` operator: keep only the given columns, evaluating any
computed/renamed ones. A column expression can reference a column produced
earlier in the same `project` list (e.g. `project Upper = toupper(X), Y = Upper == "A"`).
"""
from __future__ import annotations

from .. import ast_nodes as ast
from ..eval import EvalContext, Row, eval_expr


def execute_project(rows: list[Row], stage: ast.ProjectStage, ctx: EvalContext) -> list[Row]:
    result: list[Row] = []
    for row in rows:
        new_row: Row = {}
        for col in stage.columns:
            visible = {**row, **new_row}
            new_row[col.name] = eval_expr(col.expr, visible, ctx)
        result.append(new_row)
    return result
