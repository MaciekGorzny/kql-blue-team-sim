"""Converts a KQL query string into a flat list of Tokens.

The tokenizer is deliberately "dumb": it has no notion of KQL keywords or
operator names (`where`, `contains`, `and`, ...) - those are just IDENT
tokens whose meaning the parser decides. Adding a new keyword therefore never
requires touching this file.

One exception: timespan literals (`1d`, `30m`, `2h`) get their own token type,
because they're written as bare number+unit (not a string), and the parser
needs to tell them apart from a plain NUMBER followed by an unrelated
identifier.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto

from .errors import KqlSyntaxError, Span


class TokenType(Enum):
    IDENT = auto()
    STRING = auto()
    NUMBER = auto()
    TIMESPAN = auto()
    PIPE = auto()       # |
    LPAREN = auto()      # (
    RPAREN = auto()      # )
    LBRACKET = auto()    # [
    RBRACKET = auto()    # ]
    COMMA = auto()       # ,
    DOT = auto()         # .
    SEMICOLON = auto()   # ;
    ASSIGN = auto()       # =
    EQ = auto()          # ==
    NEQ = auto()          # !=
    LT = auto()          # <
    LE = auto()          # <=
    GT = auto()          # >
    GE = auto()          # >=
    PLUS = auto()        # +
    MINUS = auto()        # -
    STAR = auto()        # *
    SLASH = auto()        # /
    PERCENT = auto()      # %
    EOF = auto()


_SINGLE_CHAR = {
    "|": TokenType.PIPE,
    "(": TokenType.LPAREN,
    ")": TokenType.RPAREN,
    "[": TokenType.LBRACKET,
    "]": TokenType.RBRACKET,
    ",": TokenType.COMMA,
    ".": TokenType.DOT,
    ";": TokenType.SEMICOLON,
    "+": TokenType.PLUS,
    "-": TokenType.MINUS,
    "*": TokenType.STAR,
    "/": TokenType.SLASH,
    "%": TokenType.PERCENT,
}

_TIMESPAN_UNITS = ("ms", "d", "h", "m", "s")  # "ms" must be checked before "m"/"s"

_ESCAPES = {"n": "\n", "t": "\t", "\\": "\\", '"': '"', "'": "'"}


@dataclass(frozen=True)
class Token:
    type: TokenType
    value: str
    span: Span

    def __repr__(self) -> str:
        return f"Token({self.type.name}, {self.value!r})"


def tokenize(query: str) -> list[Token]:
    """Tokenize a KQL query string. Raises KqlSyntaxError on invalid input."""
    tokens: list[Token] = []
    i = 0
    line = 1
    col = 0
    n = len(query)

    def make_span(start_offset: int, start_line: int, start_col: int, length: int) -> Span:
        return Span(line=start_line, col=start_col, offset=start_offset, length=length)

    while i < n:
        ch = query[i]

        if ch == "\n":
            i += 1
            line += 1
            col = 0
            continue
        if ch in " \t\r":
            i += 1
            col += 1
            continue
        if ch == "/" and i + 1 < n and query[i + 1] == "/":
            while i < n and query[i] != "\n":
                i += 1
            continue

        start_i, start_line, start_col = i, line, col

        two = query[i : i + 2]
        two_char_map = {"==": TokenType.EQ, "!=": TokenType.NEQ, "<=": TokenType.LE, ">=": TokenType.GE}
        if two in two_char_map:
            tokens.append(Token(two_char_map[two], two, make_span(start_i, start_line, start_col, 2)))
            i += 2
            col += 2
            continue

        if ch == "=":
            tokens.append(Token(TokenType.ASSIGN, ch, make_span(start_i, start_line, start_col, 1)))
            i += 1
            col += 1
            continue
        if ch == "<":
            tokens.append(Token(TokenType.LT, ch, make_span(start_i, start_line, start_col, 1)))
            i += 1
            col += 1
            continue
        if ch == ">":
            tokens.append(Token(TokenType.GT, ch, make_span(start_i, start_line, start_col, 1)))
            i += 1
            col += 1
            continue

        if ch in _SINGLE_CHAR:
            tokens.append(Token(_SINGLE_CHAR[ch], ch, make_span(start_i, start_line, start_col, 1)))
            i += 1
            col += 1
            continue

        if ch in "\"'":
            quote = ch
            j = i + 1
            buf: list[str] = []
            while j < n and query[j] != quote:
                if query[j] == "\\" and j + 1 < n:
                    # Unrecognized escapes (e.g. `\s`, `\d` in a regex pattern)
                    # keep their backslash instead of silently dropping it.
                    buf.append(_ESCAPES.get(query[j + 1], "\\" + query[j + 1]))
                    j += 2
                else:
                    buf.append(query[j])
                    j += 1
            if j >= n:
                raise KqlSyntaxError(
                    "Niezamknięty literał tekstowy (brakuje cudzysłowu zamykającego).",
                    query,
                    make_span(start_i, start_line, start_col, j - i),
                )
            length = j + 1 - i
            tokens.append(
                Token(TokenType.STRING, "".join(buf), make_span(start_i, start_line, start_col, length))
            )
            col += length
            i = j + 1
            continue

        if ch.isdigit():
            j = i
            seen_dot = False
            while j < n and (query[j].isdigit() or (query[j] == "." and not seen_dot)):
                if query[j] == ".":
                    seen_dot = True
                j += 1

            unit = None
            for candidate in _TIMESPAN_UNITS:
                end = j + len(candidate)
                if query[j:end] == candidate:
                    after_is_ident_char = end < n and (query[end].isalnum() or query[end] == "_")
                    if not after_is_ident_char:
                        unit = candidate
                        break
            if unit:
                length = j + len(unit) - i
                tokens.append(
                    Token(TokenType.TIMESPAN, query[i : i + length], make_span(start_i, start_line, start_col, length))
                )
                col += length
                i += length
                continue

            length = j - i
            tokens.append(
                Token(TokenType.NUMBER, query[i:j], make_span(start_i, start_line, start_col, length))
            )
            col += length
            i = j
            continue

        if ch.isalpha() or ch == "_" or ch == "$":
            # `$` (used only by `$left`/`$right` in `join`) is a leading sigil,
            # not a repeatable identifier character - start scanning from the
            # next character so a lone trailing `$` can't produce a zero-width
            # token (which would leave `i` stuck and loop forever).
            j = i + 1
            while j < n and (query[j].isalnum() or query[j] == "_"):
                j += 1
            length = j - i
            tokens.append(
                Token(TokenType.IDENT, query[i:j], make_span(start_i, start_line, start_col, length))
            )
            col += length
            i = j
            continue

        raise KqlSyntaxError(
            f"Nieoczekiwany znak {ch!r}.", query, make_span(start_i, start_line, start_col, 1)
        )

    tokens.append(Token(TokenType.EOF, "", make_span(n, line, col, 0)))
    return tokens
