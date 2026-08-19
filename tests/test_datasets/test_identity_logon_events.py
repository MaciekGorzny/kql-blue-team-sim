"""Tests for the synthetic IdentityLogonEvents dataset."""
from core.datasets import identity_logon_events as ile


def test_every_row_has_exactly_the_schema_columns():
    expected_columns = {c.name for c in ile.SCHEMA.columns}
    for row in ile.ROWS:
        assert set(row.keys()) == expected_columns


def test_generation_is_deterministic():
    assert ile._build_rows() == ile._build_rows()


def test_contains_kerberoasting_burst_for_six_distinct_services():
    matches = [r for r in ile.ROWS if r["TargetAccountName"] != ""]
    assert len(matches) == 6
    assert {r["TargetAccountName"] for r in matches} == {
        "svc-sql",
        "svc-backup",
        "svc-web",
        "svc-print",
        "svc-exchange",
        "svc-reporting",
    }
    assert all(r["AccountName"] == "hkrawczyk" for r in matches)
    assert all(r["DeviceName"] == "WIN-CLIENT10" for r in matches)
