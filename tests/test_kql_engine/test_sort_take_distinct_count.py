"""End-to-end tests for `sort by`, `take`/`limit`, `distinct`, and `count`."""
from core.kql_engine import run_query


def test_sort_default_descending(tables):
    result = run_query("DeviceProcessEvents | sort by ProcessId", tables)
    ids = [r["ProcessId"] for r in result]
    assert ids == sorted(ids, reverse=True)


def test_sort_ascending(tables):
    result = run_query("DeviceProcessEvents | sort by ProcessId asc", tables)
    ids = [r["ProcessId"] for r in result]
    assert ids == sorted(ids)


def test_take_limits_rows(tables):
    result = run_query("DeviceProcessEvents | take 1", tables)
    assert len(result) == 1


def test_limit_is_synonym_for_take(tables):
    result = run_query("DeviceProcessEvents | limit 2", tables)
    assert len(result) == 2


def test_distinct_on_column(tables):
    result = run_query("DeviceProcessEvents | distinct DeviceName", tables)
    names = {r["DeviceName"] for r in result}
    assert names == {"WIN-CLIENT01", "WIN-SRV02"}
    assert len(result) == 2


def test_distinct_star_keeps_all_columns(tables):
    result = run_query("DeviceProcessEvents | distinct *", tables)
    assert len(result) == 3
    assert set(result[0].keys()) == {
        "TimeGenerated", "DeviceName", "FileName", "CommandLine", "AccountName", "ProcessId",
    }


def test_count(tables):
    result = run_query("DeviceProcessEvents | count", tables)
    assert result == [{"Count": 3}]


def test_count_after_where(tables):
    result = run_query("DeviceProcessEvents | where DeviceName == 'WIN-CLIENT01' | count", tables)
    assert result == [{"Count": 2}]
