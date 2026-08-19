"""Tests for the synthetic SigninLogs dataset."""
from core.datasets import signin_logs as sl


def test_every_row_has_exactly_the_schema_columns():
    expected_columns = {c.name for c in sl.SCHEMA.columns}
    for row in sl.ROWS:
        assert set(row.keys()) == expected_columns


def test_generation_is_deterministic():
    assert sl._build_rows() == sl._build_rows()


def test_contains_password_spray_burst_and_a_suspicious_success():
    failures = [r for r in sl.ROWS if r["UserPrincipalName"] == "anowak@contoso.com" and r["ResultType"] != "0"]
    assert len(failures) == 6
    assert all(r["IPAddress"] == "185.220.101.5" for r in failures)

    suspicious_success = [
        r
        for r in sl.ROWS
        if r["UserPrincipalName"] == "anowak@contoso.com"
        and r["ResultType"] == "0"
        and r["IPAddress"] == "185.220.101.5"
    ]
    assert len(suspicious_success) == 1


def test_contains_aitm_token_replay_anomaly_for_a_different_account():
    matches = [
        r
        for r in sl.ROWS
        if r["UserPrincipalName"] == "jkowalski@contoso.com" and r["Location"] != "Warszawa, PL"
    ]
    assert len(matches) == 1
    assert matches[0]["ResultType"] == "0"
    assert matches[0]["ConditionalAccessStatus"] == "success"


def test_contains_device_code_registration_anomaly():
    matches = [r for r in sl.ROWS if r["AppDisplayName"] == "Microsoft Authentication Broker"]
    assert len(matches) == 1
    assert matches[0]["UserPrincipalName"] == "mwisniewski@contoso.com"
    assert matches[0]["ResultType"] == "0"
