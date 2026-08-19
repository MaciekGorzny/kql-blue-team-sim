"""Schema metadata for datasets: column names/types/descriptions, independent
of any particular dataset's data.

Not enforced by the KQL engine itself (the engine works on plain dicts and
doesn't know about `TableSchema`) - this exists for documentation and future
tooling (e.g. showing a trainee which columns a table has).
"""
from __future__ import annotations

from dataclasses import dataclass

from core.kql_engine.ast_nodes import KqlType


@dataclass(frozen=True)
class ColumnSchema:
    name: str
    kql_type: KqlType
    description: str = ""


@dataclass(frozen=True)
class TableSchema:
    name: str
    columns: list[ColumnSchema]
