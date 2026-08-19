"""Tests for the synthetic DeviceNetworkEvents dataset."""
from core.datasets import device_network_events as dne


def test_every_row_has_exactly_the_schema_columns():
    expected_columns = {c.name for c in dne.SCHEMA.columns}
    for row in dne.ROWS:
        assert set(row.keys()) == expected_columns


def test_generation_is_deterministic():
    assert dne._build_rows() == dne._build_rows()


def test_contains_four_c2_callback_anomalies():
    matches = [r for r in dne.ROWS if r["RemoteIP"] == "185.220.101.5"]
    assert len(matches) == 4
    assert {r["DeviceName"] for r in matches} == {"WIN-CLIENT01", "WIN-CLIENT02", "WIN-SRV01"}


def test_contains_the_separate_formbook_c2_beacon_anomaly():
    matches = [r for r in dne.ROWS if r["RemoteIP"] == "195.201.57.82"]
    assert len(matches) == 1
    assert matches[0]["InitiatingProcessFileName"] == "Faktura_Zalegla_Setup.exe"


def test_contains_ta569_driveby_beacons_on_two_devices():
    ta569_ips = {"176.53.147.97", "185.76.79.50", "185.159.129.211"}
    matches = [r for r in dne.ROWS if r["RemoteIP"] in ta569_ips]
    assert {r["DeviceName"] for r in matches} == {"WIN-CLIENT07", "WIN-CLIENT08"}


def test_contains_theatercraft_dga_beacon():
    matches = [r for r in dne.ROWS if r["RemoteUrl"].endswith("theatercraft.buzz")]
    assert len(matches) == 1
    assert matches[0]["DeviceName"] == "WIN-CLIENT09"
