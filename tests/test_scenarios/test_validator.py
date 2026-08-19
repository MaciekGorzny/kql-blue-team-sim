"""Tests for core.scenarios.validator, using hand-built Scenario objects
(not the on-disk JSON ones - those get their own self-consistency test in
test_scenario_files.py)."""
from core.scenarios.schema import RequiredUsageCriterion, ResultMatchCriterion, Scenario, Difficulty
from core.scenarios.validator import validate


def _make_scenario(**overrides) -> Scenario:
    defaults = dict(
        id="test_scenario",
        title="Test",
        prompt="Test prompt",
        datasets=("DeviceProcessEvents",),
        difficulty=Difficulty.BEGINNER,
    )
    defaults.update(overrides)
    return Scenario(**defaults)


def test_correct_query_passes_result_match():
    scenario = _make_scenario(
        result_match=ResultMatchCriterion(
            reference_query="DeviceProcessEvents | where FileName == 'rundll32.exe' | project DeviceName"
        )
    )
    result = validate(scenario, "DeviceProcessEvents | where FileName == 'rundll32.exe' | project DeviceName")
    assert result.correct is True


def test_row_order_does_not_matter_by_default():
    scenario = _make_scenario(
        result_match=ResultMatchCriterion(
            reference_query="DeviceProcessEvents | where FileName == 'certutil.exe' or FileName == 'mshta.exe' "
            "| project DeviceName | sort by DeviceName asc"
        )
    )
    # Same rows, different (unsorted) order - should still pass since ordered=False.
    result = validate(
        scenario,
        "DeviceProcessEvents | where FileName == 'mshta.exe' or FileName == 'certutil.exe' | project DeviceName",
    )
    assert result.correct is True


def test_wrong_query_fails_result_match_with_expected_result_attached():
    scenario = _make_scenario(
        result_match=ResultMatchCriterion(
            reference_query="DeviceProcessEvents | where FileName == 'rundll32.exe' | project DeviceName"
        )
    )
    result = validate(scenario, "DeviceProcessEvents | where FileName == 'notepad.exe' | project DeviceName")
    assert result.correct is False
    assert result.expected_result is not None


def test_query_syntax_error_fails_gracefully_with_message():
    scenario = _make_scenario(
        result_match=ResultMatchCriterion(reference_query="DeviceProcessEvents | take 1")
    )
    result = validate(scenario, "DeviceProcessEvents | bogusop 1")
    assert result.correct is False
    assert "bogusop" in result.message
    assert result.user_result is None


def test_required_usage_failure_still_attaches_the_users_actual_result():
    # The query itself is valid and runs fine - it just doesn't use the
    # required technique. The caller (e.g. the API layer) still needs the
    # user's own result table to show them, not just the rejection message.
    scenario = _make_scenario(required_usage=RequiredUsageCriterion(required_operators=("SummarizeStage",)))
    result = validate(scenario, "DeviceProcessEvents | where FileName == 'rundll32.exe'")
    assert result.correct is False
    assert result.user_result is not None
    assert len(result.user_result) == 1


def test_required_usage_rejects_missing_operator():
    scenario = _make_scenario(
        required_usage=RequiredUsageCriterion(required_operators=("SummarizeStage",))
    )
    result = validate(scenario, "DeviceProcessEvents | where FileName == 'rundll32.exe'")
    assert result.correct is False
    assert "Summarize" in result.message


def test_required_usage_rejects_missing_column():
    scenario = _make_scenario(required_usage=RequiredUsageCriterion(required_columns=("AccountName",)))
    result = validate(scenario, "DeviceProcessEvents | where FileName == 'rundll32.exe'")
    assert result.correct is False
    assert "AccountName" in result.message


def test_required_usage_accepts_correct_technique():
    scenario = _make_scenario(
        required_usage=RequiredUsageCriterion(required_operators=("SummarizeStage",), required_columns=("DeviceName",))
    )
    result = validate(scenario, "DeviceProcessEvents | summarize count() by DeviceName")
    assert result.correct is True


def test_required_usage_column_check_reaches_inside_join_subquery():
    scenario = _make_scenario(
        datasets=("DeviceProcessEvents", "DeviceLogonEvents"),
        required_usage=RequiredUsageCriterion(required_operators=("JoinStage",), required_columns=("LogonType",)),
    )
    result = validate(
        scenario,
        "DeviceProcessEvents | join kind=inner (DeviceLogonEvents | where LogonType == 'RemoteInteractive') "
        "on DeviceName, AccountName",
    )
    assert result.correct is True


def test_both_criteria_pass_together_when_query_is_fully_correct():
    scenario = _make_scenario(
        result_match=ResultMatchCriterion(reference_query="DeviceProcessEvents | summarize count() by DeviceName"),
        required_usage=RequiredUsageCriterion(required_operators=("SummarizeStage",)),
    )
    result = validate(scenario, "DeviceProcessEvents | summarize count() by DeviceName")
    assert result.correct is True


def test_right_technique_but_wrong_result_still_fails():
    scenario = _make_scenario(
        result_match=ResultMatchCriterion(reference_query="DeviceProcessEvents | summarize count() by DeviceName"),
        required_usage=RequiredUsageCriterion(required_operators=("SummarizeStage",)),
    )
    # Uses summarize (satisfies required_usage) but aggregates the wrong thing.
    result = validate(scenario, "DeviceProcessEvents | summarize sum(ProcessId) by DeviceName")
    assert result.correct is False
