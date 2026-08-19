"""Realistic multi-stage pipelines, close to what an actual training scenario
would ask a user to write."""
from core.kql_engine import run_query


def test_find_suspicious_encoded_powershell(tables):
    query = (
        "DeviceProcessEvents "
        "| where FileName == 'powershell.exe' and CommandLine contains '-enc' "
        "| project DeviceName, AccountName, CommandLine"
    )
    result = run_query(query, tables)
    assert result == [
        {
            "DeviceName": "WIN-CLIENT01",
            "AccountName": "jkowalski",
            "CommandLine": "powershell.exe -enc SGVsbG8=",
        }
    ]


def test_distinct_devices_sorted_ascending(tables):
    query = "DeviceProcessEvents | distinct DeviceName | sort by DeviceName asc"
    result = run_query(query, tables)
    assert [r["DeviceName"] for r in result] == ["WIN-CLIENT01", "WIN-SRV02"]


def test_unknown_table_raises_with_helpful_message(tables):
    import pytest

    from core.kql_engine.errors import KqlEvalError

    with pytest.raises(KqlEvalError) as exc_info:
        run_query("NoSuchTable | take 1", tables)
    assert "DeviceProcessEvents" in str(exc_info.value)
