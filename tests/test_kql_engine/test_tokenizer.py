"""Unit tests for core.kql_engine.tokenizer."""
import pytest

from core.kql_engine.errors import KqlSyntaxError
from core.kql_engine.tokenizer import TokenType, tokenize


def test_tokenize_simple_pipeline():
    tokens = tokenize("Table | where X == 1")
    types = [t.type for t in tokens]
    assert types == [
        TokenType.IDENT,
        TokenType.PIPE,
        TokenType.IDENT,
        TokenType.IDENT,
        TokenType.EQ,
        TokenType.NUMBER,
        TokenType.EOF,
    ]


def test_tokenize_string_literal_with_escape():
    tokens = tokenize(r'where X == "a\"b"')
    string_tok = next(t for t in tokens if t.type == TokenType.STRING)
    assert string_tok.value == 'a"b'


def test_tokenize_single_quoted_string():
    tokens = tokenize("where X == 'cmd.exe'")
    string_tok = next(t for t in tokens if t.type == TokenType.STRING)
    assert string_tok.value == "cmd.exe"


def test_unrecognized_escape_keeps_backslash():
    # Regex patterns like `\s`, `\d` must survive tokenization intact - this
    # is not a recognized escape (only \n \t \\ \" \' are), so the backslash
    # must be preserved rather than silently dropped.
    tokens = tokenize(r"where X matches regex '\s+\d'")
    string_tok = next(t for t in tokens if t.type == TokenType.STRING)
    assert string_tok.value == r"\s+\d"


def test_tokenize_timespan_literal():
    tokens = tokenize("ago(1d)")
    timespan_tok = next(t for t in tokens if t.type == TokenType.TIMESPAN)
    assert timespan_tok.value == "1d"


def test_tokenize_ms_unit_not_confused_with_m():
    tokens = tokenize("500ms")
    assert tokens[0].type == TokenType.TIMESPAN
    assert tokens[0].value == "500ms"


def test_number_followed_by_unrelated_identifier_is_not_a_timespan():
    tokens = tokenize("1x")
    assert tokens[0].type == TokenType.NUMBER
    assert tokens[0].value == "1"
    assert tokens[1].type == TokenType.IDENT
    assert tokens[1].value == "x"


def test_unterminated_string_raises_with_position():
    with pytest.raises(KqlSyntaxError) as exc_info:
        tokenize('where X == "abc')
    assert exc_info.value.span is not None
    assert exc_info.value.span.line == 1


def test_unexpected_character_raises():
    with pytest.raises(KqlSyntaxError):
        tokenize("Table | where X == 1 @")


def test_line_comment_is_ignored():
    tokens = tokenize("Table // a comment\n| take 1")
    types = [t.type for t in tokens]
    assert TokenType.PIPE in types


def test_dollar_left_and_right_tokenize_as_single_ident():
    tokens = tokenize("$left.DeviceId == $right.DeviceId")
    assert tokens[0].type == TokenType.IDENT
    assert tokens[0].value == "$left"
    assert tokens[1].type == TokenType.DOT


def test_lone_trailing_dollar_does_not_hang():
    # Regression test: a leading `$` used to be treated as a repeatable
    # identifier character, so a lone trailing `$` produced a zero-width
    # token and never advanced - an infinite loop. It must now always
    # consume at least one character.
    tokens = tokenize("Table | where X == 1 $")
    assert tokens[-1].type == TokenType.EOF
