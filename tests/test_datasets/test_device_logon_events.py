"""Tests for the synthetic DeviceLogonEvents dataset."""
from core.datasets import device_logon_events as dle


def test_every_row_has_exactly_the_schema_columns():
    expected_columns = {c.name for c in dle.SCHEMA.columns}
    for row in dle.ROWS:
        assert set(row.keys()) == expected_columns


def test_generation_is_deterministic():
    assert dle._build_rows() == dle._build_rows()


def test_contains_exactly_one_remote_interactive_logon_anomaly():
    matches = [r for r in dle.ROWS if r["LogonType"] == "RemoteInteractive"]
    assert len(matches) == 1
    assert matches[0]["DeviceName"] == "WIN-SRV02"
    assert matches[0]["AccountName"] == "administrator"
    assert matches[0]["RemoteIP"] != "-"
