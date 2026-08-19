"""End-to-end tests for the `summarize` operator."""
from core.kql_engine import run_query


def test_count_by_device(tables):
    result = run_query("DeviceProcessEvents | summarize count() by DeviceName", tables)
    by_device = {r["DeviceName"]: r["Count"] for r in result}
    assert by_device == {"WIN-CLIENT01": 2, "WIN-SRV02": 1}


def test_default_column_names(tables):
    result = run_query("DeviceProcessEvents | summarize sum(ProcessId) by DeviceName", tables)
    row = next(r for r in result if r["DeviceName"] == "WIN-CLIENT01")
    assert row["sum_ProcessId"] == 4321 + 4355


def test_explicit_column_name(tables):
    result = run_query("DeviceProcessEvents | summarize Total = count() by DeviceName", tables)
    assert all("Total" in r for r in result)


def test_multiple_aggregates(tables):
    result = run_query(
        "DeviceProcessEvents | summarize Events = count(), Uniq = dcount(AccountName) by DeviceName", tables
    )
    row = next(r for r in result if r["DeviceName"] == "WIN-CLIENT01")
    assert row["Events"] == 2
    assert row["Uniq"] == 1


def test_min_max_avg(tables):
    result = run_query(
        "DeviceProcessEvents | where DeviceName == 'WIN-CLIENT01' "
        "| summarize Lo = min(ProcessId), Hi = max(ProcessId), Avg = avg(ProcessId)",
        tables,
    )
    assert result == [{"Lo": 4321, "Hi": 4355, "Avg": (4321 + 4355) / 2}]


def test_summarize_without_by_aggregates_whole_table(tables):
    result = run_query("DeviceProcessEvents | summarize count()", tables)
    assert result == [{"Count": 3}]


def test_summarize_over_empty_result_still_returns_one_row(tables):
    result = run_query("DeviceProcessEvents | where FileName == 'nope.exe' | summarize count()", tables)
    assert result == [{"Count": 0}]


def test_summarize_with_by_over_empty_result_returns_no_rows(tables):
    result = run_query("DeviceProcessEvents | where FileName == 'nope.exe' | summarize count() by DeviceName", tables)
    assert result == []
