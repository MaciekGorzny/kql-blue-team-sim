"""`distinct` operator: deduplicate rows, optionally on a subset of columns
(`distinct *` keeps all columns)."""
from __future__ import annotations

from .. import ast_nodes as ast
from ..eval import EvalContext, Row


def execute_distinct(rows: list[Row], stage: ast.DistinctStage, ctx: EvalContext) -> list[Row]:
    columns = stage.columns or (list(rows[0].keys()) if rows else [])
    seen: set[tuple] = set()
    result: list[Row] = []
    for row in rows:
        key = tuple(row.get(c) for c in columns)
        if key not in seen:
            seen.add(key)
            result.append({c: row.get(c) for c in columns})
    return result
