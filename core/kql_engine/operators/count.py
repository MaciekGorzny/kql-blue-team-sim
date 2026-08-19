"""`count` operator (bare, no args): returns a single row `{"Count": N}`."""
from __future__ import annotations

from .. import ast_nodes as ast
from ..eval import EvalContext, Row


def execute_count(rows: list[Row], stage: ast.CountStage, ctx: EvalContext) -> list[Row]:
    return [{"Count": len(rows)}]
