"""`join` operator: `kind=inner` or `kind=leftouter` against a nested tabular
sub-query (`join kind=inner (RightTable | where ...) on Key`).

Column handling mirrors real Kusto: a join key referenced via the `on Col`
shorthand appears once in the output (from the left side); any other
non-key column present in both tables gets its right-hand copy suffixed
with `1` to avoid silently overwriting the left column.

This module imports `executor.execute` inside the function body, not at
module load time - the executor imports the operator registry (this
package), so a module-level import here would create a circular import.
"""
from __future__ import annotations

from .. import ast_nodes as ast
from ..eval import EvalContext, Row, eval_expr


def execute_join(rows: list[Row], stage: ast.JoinStage, ctx: EvalContext) -> list[Row]:
    from ..executor import execute  # deferred to avoid a circular import

    # Thread the outer query's `let` bindings into the right-hand subquery so
    # they're visible there too, even though the right side never parses its
    # own `let` chain (see parser.py's _parse_let_statement docstring).
    right_rows = execute(stage.right, ctx.tables or {}, ctx.query_text, bindings=ctx.bindings)
    right_columns = list(right_rows[0].keys()) if right_rows else []

    same_name_keys = {
        key.right_expr.name
        for key in stage.on
        if isinstance(key.left_expr, ast.ColumnRef)
        and isinstance(key.right_expr, ast.ColumnRef)
        and key.left_expr.name == key.right_expr.name
    }

    right_index: dict[tuple, list[Row]] = {}
    for r_row in right_rows:
        key = tuple(eval_expr(k.right_expr, r_row, ctx) for k in stage.on)
        right_index.setdefault(key, []).append(r_row)

    result: list[Row] = []
    for l_row in rows:
        key = tuple(eval_expr(k.left_expr, l_row, ctx) for k in stage.on)
        matches = right_index.get(key, [])
        if matches:
            for r_row in matches:
                result.append(_merge(l_row, r_row, right_columns, same_name_keys))
        elif stage.kind == "leftouter":
            result.append(_merge(l_row, None, right_columns, same_name_keys))
    return result


def _merge(left_row: Row, right_row: Row | None, right_columns: list[str], same_name_keys: set[str]) -> Row:
    merged = dict(left_row)
    for col_name in right_columns:
        if col_name in same_name_keys:
            continue
        value = right_row.get(col_name) if right_row is not None else None
        out_name = f"{col_name}1" if col_name in merged else col_name
        merged[out_name] = value
    return merged
