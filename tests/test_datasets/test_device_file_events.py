"""Tests for the synthetic DeviceFileEvents dataset."""
from core.datasets import device_file_events as dfe


def test_every_row_has_exactly_the_schema_columns():
    expected_columns = {c.name for c in dfe.SCHEMA.columns}
    for row in dfe.ROWS:
        assert set(row.keys()) == expected_columns


def test_generation_is_deterministic():
    assert dfe._build_rows() == dfe._build_rows()


def test_contains_the_dropped_payload_anomalies():
    names = {
        r["FileName"]
        for r in dfe.ROWS
        if r["FileName"] in ("update.dll", "payload.exe", "update.exe", "oledlg.dll")
    }
    assert names == {"update.dll", "payload.exe", "update.exe", "oledlg.dll"}


def test_contains_a_mass_file_rename_burst():
    renames = [r for r in dfe.ROWS if r["ActionType"] == "FileRenamed"]
    assert len(renames) == 40
    assert all(r["DeviceName"] == "WIN-SRV02" for r in renames)
    assert all(r["FileName"].endswith(".prinzeugen") for r in renames)
    # all within the same few minutes - the burst itself is the signal
    span = max(r["Timestamp"] for r in renames) - min(r["Timestamp"] for r in renames)
    assert span.total_seconds() < 300
