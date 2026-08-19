"""Registry mapping AST Stage subclasses (by class name) to their execution
handlers. Adding a new operator = add one module in this package + one
`register(...)` line below; the executor and parser don't need to change.
"""
from __future__ import annotations

from typing import Any, Callable

from .. import ast_nodes as ast

Row = dict[str, Any]
Handler = Callable[[list[Row], ast.Stage, Any], list[Row]]

OPERATORS: dict[str, Handler] = {}


def register(stage_class_name: str, handler: Handler) -> None:
    OPERATORS[stage_class_name] = handler


from . import count as _count  # noqa: E402
from . import distinct as _distinct  # noqa: E402
from . import extend as _extend  # noqa: E402
from . import join as _join  # noqa: E402
from . import project as _project  # noqa: E402
from . import sort as _sort  # noqa: E402
from . import summarize as _summarize  # noqa: E402
from . import take as _take  # noqa: E402
from . import where as _where  # noqa: E402

register("WhereStage", _where.execute_where)
register("ProjectStage", _project.execute_project)
register("ExtendStage", _extend.execute_extend)
register("SortStage", _sort.execute_sort)
register("TakeStage", _take.execute_take)
register("DistinctStage", _distinct.execute_distinct)
register("CountStage", _count.execute_count)
register("SummarizeStage", _summarize.execute_summarize)
register("JoinStage", _join.execute_join)
