"""Exception types for the KQL engine.

Every error carries a `Span` (line/col/offset into the original query text)
so callers can render a caret-style message pointing at exactly what's wrong -
this is part of the tool's educational value, not just an internal detail.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Span:
    """A range in the original query string, in both line/col and raw offset form."""

    line: int
    col: int
    offset: int
    length: int


class KqlError(Exception):
    """Base class for all errors raised by the KQL engine."""

    def __init__(self, message: str, query: str, span: Span | None = None):
        self.message = message
        self.query = query
        self.span = span
        super().__init__(self._format())

    def _format(self) -> str:
        if self.span is None:
            return self.message
        lines = self.query.splitlines() or [""]
        line_idx = self.span.line - 1
        line_text = lines[line_idx] if 0 <= line_idx < len(lines) else ""
        caret_pad = " " * self.span.col
        caret = "^" * max(1, self.span.length)
        return (
            f"{self.message}\n"
            f"  linia {self.span.line}, kolumna {self.span.col + 1}:\n"
            f"  {line_text}\n"
            f"  {caret_pad}{caret}"
        )


class KqlSyntaxError(KqlError):
    """Raised by the tokenizer for invalid characters or malformed literals."""


class KqlParseError(KqlError):
    """Raised by the parser when the token stream doesn't form a valid query."""


class KqlEvalError(KqlError):
    """Raised by the executor at runtime (unknown column/table, type mismatch, ...)."""
