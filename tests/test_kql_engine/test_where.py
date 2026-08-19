"""End-to-end tests for the `where` operator (parse + execute)."""
import pytest

from core.kql_engine import run_query
from core.kql_engine.errors import KqlEvalError


def test_where_equality(tables):
    result = run_query("DeviceProcessEvents | where FileName == 'cmd.exe'", tables)
    assert len(result) == 1
    assert result[0]["FileName"] == "cmd.exe"


def test_where_has(tables):
    result = run_query("DeviceProcessEvents | where CommandLine has 'whoami'", tables)
    assert len(result) == 1


def test_where_has_does_not_match_substring_inside_token(tables):
    # "md" is not a whole token anywhere - checks `has` is token-based, not substring-based
    result = run_query("DeviceProcessEvents | where CommandLine has 'md'", tables)
    assert result == []


def test_where_contains_does_match_substring(tables):
    result = run_query("DeviceProcessEvents | where CommandLine contains 'who'", tables)
    assert len(result) == 1


def test_where_and(tables):
    result = run_query(
        "DeviceProcessEvents | where DeviceName == 'WIN-CLIENT01' and FileName == 'cmd.exe'", tables
    )
    assert len(result) == 1


def test_where_or(tables):
    result = run_query(
        "DeviceProcessEvents | where FileName == 'cmd.exe' or FileName == 'notepad.exe'", tables
    )
    assert len(result) == 2


def test_where_not_function(tables):
    result = run_query("DeviceProcessEvents | where not(FileName == 'cmd.exe')", tables)
    assert len(result) == 2


def test_where_matches_regex(tables):
    result = run_query(
        r"DeviceProcessEvents | where CommandLine matches regex '-enc\s+\S+'", tables
    )
    assert len(result) == 1
    assert result[0]["FileName"] == "powershell.exe"


def test_where_non_bool_condition_raises(tables):
    with pytest.raises(KqlEvalError):
        run_query("DeviceProcessEvents | where FileName", tables)


def test_where_unknown_column_raises_with_span(tables):
    with pytest.raises(KqlEvalError) as exc_info:
        run_query("DeviceProcessEvents | where NoSuchColumn == 1", tables)
    assert exc_info.value.span is not None
