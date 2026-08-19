"""Tests for the synthetic OfficeActivity dataset."""
from core.datasets import office_activity as oa


def test_every_row_has_exactly_the_schema_columns():
    expected_columns = {c.name for c in oa.SCHEMA.columns}
    for row in oa.ROWS:
        assert set(row.keys()) == expected_columns


def test_generation_is_deterministic():
    assert oa._build_rows() == oa._build_rows()


def test_contains_one_suspicious_inbox_rule():
    matches = [r for r in oa.ROWS if r["Operation"] == "New-InboxRule"]
    assert len(matches) == 1
    assert matches[0]["UserId"] == "anowak@contoso.com"
    assert matches[0]["ClientIP"] == "185.220.101.5"
