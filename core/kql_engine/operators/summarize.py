"""`summarize` operator: groups rows by the `by` columns and computes one or
more aggregations per group. Without a `by` clause, the whole table is a
single group (matching real Kusto: `T | summarize count()` returns one row).
"""
from __future__ import annotations

from .. import ast_nodes as ast
from ..errors import KqlEvalError
from ..eval import EvalContext, Row, eval_expr


def execute_summarize(rows: list[Row], stage: ast.SummarizeStage, ctx: EvalContext) -> list[Row]:
    groups: dict[tuple, list[Row]] = {}
    group_values: dict[tuple, dict[str, object]] = {}

    for row in rows:
        key = tuple(eval_expr(g.expr, row, ctx) for g in stage.group_by)
        groups.setdefault(key, []).append(row)
        group_values.setdefault(key, {g.name: eval_expr(g.expr, row, ctx) for g in stage.group_by})

    if not stage.group_by and not rows:
        # Aggregating an empty table with no `by` clause still yields one row
        # (e.g. `count()` is meaningfully 0), matching real Kusto.
        groups[()] = []
        group_values[()] = {}

    result: list[Row] = []
    for key, group_rows in groups.items():
        out_row: Row = dict(group_values[key])
        for agg in stage.aggregates:
            out_row[agg.name] = _compute_aggregate(agg, group_rows, ctx)
        result.append(out_row)
    return result


def _compute_aggregate(agg: ast.AggregateSpec, group_rows: list[Row], ctx: EvalContext) -> object:
    if agg.func == "count":
        return len(group_rows)

    if agg.arg is None:
        raise KqlEvalError(f"'{agg.func}()' wymaga argumentu.", ctx.query_text, agg.span)

    values = [v for v in (eval_expr(agg.arg, row, ctx) for row in group_rows) if v is not None]

    if agg.func == "dcount":
        return len(set(values))
    if not values:
        return None
    if agg.func == "sum":
        return sum(values)
    if agg.func == "avg":
        return sum(values) / len(values)
    if agg.func == "min":
        return min(values)
    if agg.func == "max":
        return max(values)

    raise KqlEvalError(f"Nieznana funkcja agregująca '{agg.func}'.", ctx.query_text, agg.span)
