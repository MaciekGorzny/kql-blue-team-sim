"""Unit tests for scalar functions (string/datetime/logical), independent of
the parser/executor."""
from datetime import datetime, timedelta, timezone

from core.kql_engine.functions.datetime_funcs import ago, bin as kql_bin, now
from core.kql_engine.functions.logical_funcs import kql_not
from core.kql_engine.functions.string_funcs import (
    kql_contains,
    kql_endswith,
    kql_has,
    kql_matches_regex,
    kql_startswith,
    split,
    strcat,
    tolower,
    toupper,
)


def test_contains_is_case_insensitive_substring():
    assert kql_contains("Cmd.EXE", "md.ex")
    assert not kql_contains("cmd.exe", "zzz")


def test_has_matches_whole_token_only():
    assert kql_has("cmd.exe -enc abc", "cmd")
    assert not kql_has("scmd.exe", "cmd")


def test_startswith_endswith_are_case_insensitive():
    assert kql_startswith("cmd.exe", "CMD")
    assert kql_endswith("cmd.exe", ".EXE")


def test_matches_regex():
    assert kql_matches_regex("cmd.exe -enc abc", r"-enc\s+\w+")
    assert not kql_matches_regex("cmd.exe", r"-enc")


def test_strcat_split_case_conversion():
    assert strcat("a", 1, "b") == "a1b"
    assert split("a,b,c", ",") == ["a", "b", "c"]
    assert tolower("ABC") == "abc"
    assert toupper("abc") == "ABC"


def test_ago_is_before_now():
    assert ago(timedelta(days=1)) < now()


def test_bin_rounds_down_to_the_hour():
    value = datetime(2026, 8, 17, 12, 47, 33, tzinfo=timezone.utc)
    binned = kql_bin(value, timedelta(hours=1))
    assert binned == datetime(2026, 8, 17, 12, 0, 0, tzinfo=timezone.utc)


def test_kql_not():
    assert kql_not(False) is True
    assert kql_not(True) is False
