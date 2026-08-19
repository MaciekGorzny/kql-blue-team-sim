"""`where` operator: keeps rows for which the boolean condition is True."""
from __future__ import annotations

from .. import ast_nodes as ast
from ..errors import KqlEvalError
from ..eval import EvalContext, Row, eval_expr


def execute_where(rows: list[Row], stage: ast.WhereStage, ctx: EvalContext) -> list[Row]:
    result: list[Row] = []
    for row in rows:
        value = eval_expr(stage.condition, row, ctx)
        if not isinstance(value, bool):
            raise KqlEvalError(
                "Warunek 'where' musi być wyrażeniem logicznym (bool).", ctx.query_text, stage.condition.span
            )
        if value:
            result.append(row)
    return result
