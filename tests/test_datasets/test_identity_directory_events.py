"""Tests for the synthetic IdentityDirectoryEvents dataset."""
from core.datasets import identity_directory_events as ide


def test_every_row_has_exactly_the_schema_columns():
    expected_columns = {c.name for c in ide.SCHEMA.columns}
    for row in ide.ROWS:
        assert set(row.keys()) == expected_columns


def test_generation_is_deterministic():
    assert ide._build_rows() == ide._build_rows()


def test_contains_exactly_one_non_dc_replication_anomaly():
    matches = [
        r
        for r in ide.ROWS
        if r["ActionType"] == "Directory Services replication" and r["DeviceName"] != "DC01"
    ]
    assert len(matches) == 1
    assert matches[0]["AccountName"] == "hkrawczyk"
    assert matches[0]["TargetAccountDisplayName"] == "krbtgt"


def test_legitimate_replication_always_comes_from_dc01():
    matches = [r for r in ide.ROWS if r["ActionType"] == "Directory Services replication"]
    assert len(matches) == 5
    dc01_matches = [r for r in matches if r["DeviceName"] == "DC01"]
    assert len(dc01_matches) == 4
