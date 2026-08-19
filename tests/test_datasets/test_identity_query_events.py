"""Tests for the synthetic IdentityQueryEvents dataset."""
from core.datasets import identity_query_events as iqe


def test_every_row_has_exactly_the_schema_columns():
    expected_columns = {c.name for c in iqe.SCHEMA.columns}
    for row in iqe.ROWS:
        assert set(row.keys()) == expected_columns


def test_generation_is_deterministic():
    assert iqe._build_rows() == iqe._build_rows()


def test_contains_exactly_one_spn_enumeration_anomaly():
    matches = [r for r in iqe.ROWS if "servicePrincipalName" in r["Query"]]
    assert len(matches) == 1
    assert matches[0]["AccountName"] == "hkrawczyk"
    assert matches[0]["DeviceName"] == "WIN-CLIENT10"
