"""Tests for core.scenarios.loader."""
import json
from datetime import timezone
from pathlib import Path

import pytest

from core.scenarios import load_all_scenarios
from core.scenarios.loader import ScenarioLoadError, load_scenario_file


def _write(tmp_path: Path, **overrides) -> Path:
    data = {
        "id": "custom_ds_scenario",
        "title": "t",
        "prompt": "p",
        "datasets": ["ImportedTable"],
        "difficulty": "beginner",
        "custom_datasets": [
            {
                "name": "ImportedTable",
                "columns": [
                    {"name": "Timestamp", "type": "datetime"},
                    {"name": "FileName", "type": "string"},
                ],
                "rows": [{"Timestamp": "2026-08-10T08:00:00Z", "FileName": "evil.exe"}],
            }
        ],
        "validation": {"result_match": {"reference_query": "ImportedTable | take 1"}},
    }
    data.update(overrides)
    path = tmp_path / "scenario.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_load_all_scenarios_finds_thirty_three_scenarios():
    scenarios = load_all_scenarios()
    assert len(scenarios) == 33


def test_source_url_is_parsed_when_present(tmp_path: Path):
    scenario = load_scenario_file(_write(tmp_path, source_url="https://example.com/writeup.html"))
    assert scenario.source_url == "https://example.com/writeup.html"


def test_source_url_defaults_to_none(tmp_path: Path):
    scenario = load_scenario_file(_write(tmp_path))
    assert scenario.source_url is None


def test_sc200_area_is_parsed_when_present(tmp_path: Path):
    scenario = load_scenario_file(_write(tmp_path, sc200_area="Microsoft Entra ID"))
    assert scenario.sc200_area == "Microsoft Entra ID"


def test_sc200_area_defaults_to_none(tmp_path: Path):
    scenario = load_scenario_file(_write(tmp_path))
    assert scenario.sc200_area is None


def test_scenarios_are_sorted_by_filename():
    scenarios = load_all_scenarios()
    ids = [s.id for s in scenarios]
    assert ids == sorted(ids)


def test_malformed_json_raises_scenario_load_error(tmp_path: Path):
    bad_file = tmp_path / "bad.json"
    bad_file.write_text("{not valid json", encoding="utf-8")
    with pytest.raises(ScenarioLoadError):
        load_scenario_file(bad_file)


def test_missing_required_field_raises_scenario_load_error(tmp_path: Path):
    bad_file = tmp_path / "bad.json"
    bad_file.write_text('{"id": "x", "title": "y"}', encoding="utf-8")
    with pytest.raises(ScenarioLoadError):
        load_scenario_file(bad_file)


def test_invalid_difficulty_raises_scenario_load_error(tmp_path: Path):
    bad_file = tmp_path / "bad.json"
    bad_file.write_text(
        """
        {
          "id": "x", "title": "y", "prompt": "z",
          "datasets": ["DeviceProcessEvents"],
          "difficulty": "expert",
          "validation": {"result_match": {"reference_query": "T | take 1"}}
        }
        """,
        encoding="utf-8",
    )
    with pytest.raises(ScenarioLoadError):
        load_scenario_file(bad_file)


def test_custom_dataset_datetime_coercion(tmp_path: Path):
    scenario = load_scenario_file(_write(tmp_path))
    (custom_ds,) = scenario.custom_datasets
    row = custom_ds.rows[0]
    assert row["Timestamp"].tzinfo is timezone.utc
    assert row["FileName"] == "evil.exe"


def test_custom_dataset_missing_row_value_becomes_none(tmp_path: Path):
    scenario = load_scenario_file(
        _write(
            tmp_path,
            custom_datasets=[
                {
                    "name": "ImportedTable",
                    "columns": [
                        {"name": "Timestamp", "type": "datetime"},
                        {"name": "FileName", "type": "string"},
                    ],
                    "rows": [{"Timestamp": "2026-08-10T08:00:00Z"}],
                }
            ],
        )
    )
    (custom_ds,) = scenario.custom_datasets
    assert custom_ds.rows[0]["FileName"] is None


def test_custom_dataset_unknown_column_in_row_raises(tmp_path: Path):
    with pytest.raises(ScenarioLoadError):
        load_scenario_file(
            _write(
                tmp_path,
                custom_datasets=[
                    {
                        "name": "ImportedTable",
                        "columns": [{"name": "Timestamp", "type": "datetime"}],
                        "rows": [{"Timestamp": "2026-08-10T08:00:00Z", "Bogus": "x"}],
                    }
                ],
            )
        )


def test_custom_dataset_unknown_type_name_raises(tmp_path: Path):
    with pytest.raises(ScenarioLoadError):
        load_scenario_file(
            _write(
                tmp_path,
                custom_datasets=[
                    {"name": "ImportedTable", "columns": [{"name": "X", "type": "not_a_type"}], "rows": []}
                ],
            )
        )


def test_custom_dataset_bad_bool_value_raises(tmp_path: Path):
    with pytest.raises(ScenarioLoadError):
        load_scenario_file(
            _write(
                tmp_path,
                custom_datasets=[
                    {
                        "name": "ImportedTable",
                        "columns": [{"name": "Flag", "type": "bool"}],
                        "rows": [{"Flag": "maybe"}],
                    }
                ],
            )
        )


def test_scenario_id_with_invalid_characters_raises(tmp_path: Path):
    with pytest.raises(ScenarioLoadError):
        load_scenario_file(_write(tmp_path, id="../../etc/passwd"))


def test_scenario_without_any_validation_criterion_raises(tmp_path: Path):
    bad_file = tmp_path / "bad.json"
    bad_file.write_text(
        """
        {
          "id": "x", "title": "y", "prompt": "z",
          "datasets": ["DeviceProcessEvents"],
          "difficulty": "beginner",
          "validation": {}
        }
        """,
        encoding="utf-8",
    )
    with pytest.raises(ScenarioLoadError):
        load_scenario_file(bad_file)
