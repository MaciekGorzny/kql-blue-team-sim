"""AST node definitions produced by the parser.

These are consumed by two very different readers: the executor (which
evaluates the tree against data) and scenario validators (which will inspect
the tree to check things like "did the user's query use a `where` stage
touching column X" - see scenarios/ once that layer exists). Keeping the AST
typed and structured (rather than a flat list of opaque strings) is what
makes both of those possible.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto

from .errors import Span


class KqlType(Enum):
    STRING = auto()
    LONG = auto()
    REAL = auto()
    BOOL = auto()
    DATETIME = auto()
    TIMESPAN = auto()
    DYNAMIC = auto()
    NULL = auto()


class Expr:
    """Base class for all scalar expressions (used in where/extend/project)."""

    span: Span


@dataclass
class Literal(Expr):
    value: object
    kql_type: KqlType
    span: Span


@dataclass
class ColumnRef(Expr):
    name: str
    span: Span


@dataclass
class UnaryExpr(Expr):
    op: str  # currently only "-"
    operand: Expr
    span: Span


@dataclass
class BinaryExpr(Expr):
    op: str  # "and" "or" "==" "!=" "<" "<=" ">" ">=" "+" "-" "*" "/" "%"
    # "contains" "startswith" "endswith" "has" "matches regex" "in"
    left: Expr
    right: Expr
    span: Span


@dataclass
class FunctionCall(Expr):
    name: str
    args: list[Expr]
    span: Span


@dataclass
class ListExpr(Expr):
    """A `[expr, expr, ...]` list literal - evaluates to a Python list.
    Produced either directly (`[1, 2, 3]`, typically as `dynamic(...)`'s
    argument) or by the parenthesized form of the `in`/`!in` right-hand side
    (`Col in ("a", "b")` - see parser.py's `_parse_in_operand`)."""

    items: list[Expr]
    span: Span


@dataclass
class ColumnSpec:
    """One column in a `project`/`extend` list: a bare reference (`project Foo`)
    or a computed/renamed column (`project Bar = Foo + 1`)."""

    name: str
    expr: Expr
    span: Span


@dataclass
class LetStatement:
    """One `let name = expr;` binding at the top of a query. Evaluated once,
    row-independently, before the source table is scanned - see executor.py."""

    name: str
    expr: Expr
    span: Span


class Stage:
    """Base class for one `| operator ...` step in the pipeline."""

    span: Span


@dataclass
class WhereStage(Stage):
    condition: Expr
    span: Span


@dataclass
class ProjectStage(Stage):
    columns: list[ColumnSpec]
    span: Span


@dataclass
class ExtendStage(Stage):
    columns: list[ColumnSpec]
    span: Span


@dataclass
class SortKey:
    expr: Expr
    ascending: bool


@dataclass
class SortStage(Stage):
    keys: list[SortKey]
    span: Span


@dataclass
class TakeStage(Stage):
    count: int
    span: Span


@dataclass
class DistinctStage(Stage):
    columns: list[str]  # empty list means "*" (all columns)
    span: Span


@dataclass
class CountStage(Stage):
    span: Span


@dataclass
class AggregateSpec:
    """One aggregation in a `summarize` list, e.g. `Total = count()` or
    `dcount(AccountName)` (name defaults to `dcount_AccountName` if omitted)."""

    name: str
    func: str  # "count" | "sum" | "avg" | "dcount" | "min" | "max"
    arg: Expr | None  # None only for count()
    span: Span


@dataclass
class SummarizeStage(Stage):
    aggregates: list[AggregateSpec]
    group_by: list[ColumnSpec]  # empty if no `by` clause (aggregate over the whole table)
    span: Span


@dataclass
class JoinKey:
    """One equality condition in a join's `on` clause. For the `on Col`
    shorthand, `left_expr` and `right_expr` are the same ColumnRef."""

    left_expr: Expr
    right_expr: Expr
    span: Span


@dataclass
class JoinStage(Stage):
    kind: str  # "inner" | "leftouter"
    right: "Query"
    on: list[JoinKey]
    span: Span


@dataclass
class Query:
    source_table: str
    source_span: Span
    stages: list[Stage]
    span: Span
    lets: list[LetStatement] = field(default_factory=list)
