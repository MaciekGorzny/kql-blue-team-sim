"""Tests for the synthetic EmailEvents dataset."""
from core.datasets import email_events as ee


def test_every_row_has_exactly_the_schema_columns():
    expected_columns = {c.name for c in ee.SCHEMA.columns}
    for row in ee.ROWS:
        assert set(row.keys()) == expected_columns


def test_generation_is_deterministic():
    assert ee._build_rows() == ee._build_rows()


def test_contains_four_delivered_phishing_emails():
    matches = [r for r in ee.ROWS if r["ThreatTypes"] == "Phish"]
    assert len(matches) == 4
    assert all(r["DeliveryAction"] == "Delivered" for r in matches)
    assert {r["RecipientEmailAddress"] for r in matches} == {
        "anowak@contoso.com",
        "jkowalski@contoso.com",
        "mwisniewski@contoso.com",
        "biuro@contoso.com",
    }
