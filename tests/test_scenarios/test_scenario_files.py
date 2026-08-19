"""Safety net for the on-disk scenario files: every scenario's own reference
query must validate as a *correct* answer to itself, and every scenario must
reference only datasets that actually exist. This catches a broken/rotted
scenario file immediately instead of a trainee hitting it first.
"""
from core.datasets import DATASETS
from core.scenarios import load_all_scenarios
from core.scenarios.validator import validate


def test_every_scenario_references_existing_datasets():
    for scenario in load_all_scenarios():
        custom_names = {cd.name for cd in scenario.custom_datasets}
        for dataset_name in scenario.datasets:
            assert dataset_name in DATASETS or dataset_name in custom_names, (
                f"{scenario.id}: unknown dataset '{dataset_name}'"
            )


def test_every_scenario_has_non_empty_prompt_and_title():
    for scenario in load_all_scenarios():
        assert scenario.title.strip()
        assert scenario.prompt.strip()


def test_every_scenarios_reference_query_validates_as_correct():
    for scenario in load_all_scenarios():
        if scenario.result_match is None:
            continue
        result = validate(scenario, scenario.result_match.reference_query)
        assert result.correct, f"{scenario.id}: its own reference_query did not validate as correct: {result.message}"


def test_scenarios_span_multiple_difficulties():
    difficulties = {s.difficulty for s in load_all_scenarios()}
    assert len(difficulties) >= 2


def test_hardest_scenario_requires_summarize_and_join():
    scenarios = {s.id: s for s in load_all_scenarios()}
    advanced = scenarios["007_lateral_movement_join"]
    assert advanced.required_usage is not None
    assert "JoinStage" in advanced.required_usage.required_operators
    assert "SummarizeStage" in advanced.required_usage.required_operators
