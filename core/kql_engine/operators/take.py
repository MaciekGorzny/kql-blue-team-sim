"""`take` / `limit` operator: return the first N rows."""
from __future__ import annotations

from .. import ast_nodes as ast
from ..eval import EvalContext, Row


def execute_take(rows: list[Row], stage: ast.TakeStage, ctx: EvalContext) -> list[Row]:
    return rows[: stage.count]
