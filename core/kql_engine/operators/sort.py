"""`sort by` / `order by` operator. KQL's default sort order is descending."""
from __future__ import annotations

import functools

from .. import ast_nodes as ast
from ..eval import EvalContext, Row, eval_expr


def execute_sort(rows: list[Row], stage: ast.SortStage, ctx: EvalContext) -> list[Row]:
    def compare(row_a: Row, row_b: Row) -> int:
        for key in stage.keys:
            a = eval_expr(key.expr, row_a, ctx)
            b = eval_expr(key.expr, row_b, ctx)
            if a == b:
                continue
            if a is None:
                return 1
            if b is None:
                return -1
            result = -1 if a < b else 1
            return result if key.ascending else -result
        return 0

    return sorted(rows, key=functools.cmp_to_key(compare))
