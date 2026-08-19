"""Public entry point for the KQL engine.

Typical usage:

    from core.kql_engine import run_query

    results = run_query(
        "DeviceProcessEvents | where FileName == 'cmd.exe' | take 10",
        tables,
    )
"""
from __future__ import annotations

from typing import Any

from .ast_nodes import Query
from .errors import KqlError, KqlEvalError, KqlParseError, KqlSyntaxError
from .executor import execute
from .parser import parse

__all__ = [
    "run_query",
    "parse_query",
    "Query",
    "KqlError",
    "KqlSyntaxError",
    "KqlParseError",
    "KqlEvalError",
]


def parse_query(query_text: str) -> Query:
    """Tokenize + parse a KQL query string into an AST, without executing it."""
    return parse(query_text)


def run_query(query_text: str, tables: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    """Parse and execute a KQL query against the given in-memory tables."""
    query = parse_query(query_text)
    return execute(query, tables, query_text)
