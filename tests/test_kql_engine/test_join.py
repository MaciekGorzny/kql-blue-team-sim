"""End-to-end tests for the `join` operator (kind=inner, kind=leftouter)."""
from core.kql_engine import run_query


def test_inner_join_drops_unmatched_left_rows(tables):
    # `logon_events` (see conftest) has no entry for WIN-SRV02, so its one
    # process-event row must be dropped by an inner join.
    result = run_query(
        "DeviceProcessEvents | join kind=inner (DeviceLogonEvents) on DeviceName", tables
    )
    assert {r["DeviceName"] for r in result} == {"WIN-CLIENT01"}
    assert len(result) == 2  # both WIN-CLIENT01 process events matched


def test_inner_join_dedupes_shorthand_key_column(tables):
    result = run_query(
        "DeviceProcessEvents | join kind=inner (DeviceLogonEvents) on DeviceName", tables
    )
    # The `on DeviceName` shorthand key must come from the left side only -
    # no separate "DeviceName1" for the right table's copy of the same column.
    row = result[0]
    assert row["DeviceName"] == "WIN-CLIENT01"
    assert "DeviceName1" not in row


def test_inner_join_suffixes_colliding_non_key_column(tables):
    # Both tables have `AccountName` - the right one must be suffixed, not silently overwrite the left.
    result = run_query(
        "DeviceProcessEvents | join kind=inner (DeviceLogonEvents) on DeviceName", tables
    )
    row = result[0]
    assert row["AccountName"] == "jkowalski"       # left (process event)
    assert row["AccountName1"] == "jkowalski"      # right (logon event)
    assert row["LogonType"] == "Interactive"        # right-only column, no collision


def test_leftouter_join_keeps_unmatched_left_rows_with_nulls(tables):
    result = run_query(
        "DeviceProcessEvents | join kind=leftouter (DeviceLogonEvents) on DeviceName", tables
    )
    assert len(result) == 3  # all process events kept
    srv_row = next(r for r in result if r["DeviceName"] == "WIN-SRV02")
    assert srv_row["LogonType"] is None
    assert srv_row["AccountName1"] is None


def test_join_with_explicit_dollar_left_right_and_different_key_names(tables):
    # Rename the join column on the right side to prove the explicit
    # `$left.X == $right.Y` form (differing names) works, not just the shorthand.
    renamed_logons = [{"Device": "WIN-CLIENT01", "AccountName": "jkowalski", "LogonType": "Interactive"}]
    tables = {**tables, "DeviceLogonEventsRenamed": renamed_logons}
    result = run_query(
        "DeviceProcessEvents | join kind=inner (DeviceLogonEventsRenamed) "
        "on $left.DeviceName == $right.Device",
        tables,
    )
    assert len(result) == 2
    assert result[0]["Device"] == "WIN-CLIENT01"


def test_join_right_side_can_be_a_sub_pipeline(tables):
    result = run_query(
        "DeviceProcessEvents | join kind=inner "
        "(DeviceLogonEvents | where LogonType == 'Interactive') on DeviceName",
        tables,
    )
    assert len(result) == 2
