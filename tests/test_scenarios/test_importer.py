"""Tests for core.scenarios.importer.

Isolation from the real core/scenarios/imported/ directory is provided by the
suite-wide autouse fixture in tests/conftest.py.
"""
from __future__ import annotations

import pytest

from core.scenarios import importer, log_store, noise


def _payload(scenario_id: str = "imported_sample") -> dict:
    return {
        "id": scenario_id,
        "title": "Imported",
        "prompt": "Find evil.exe",
        "datasets": ["ImportedProcessEvents"],
        "difficulty": "beginner",
        "custom_datasets": [
            {
                "name": "ImportedProcessEvents",
                "columns": [
                    {"name": "Timestamp", "type": "datetime"},
                    {"name": "FileName", "type": "string"},
                ],
                "rows": [
                    {"Timestamp": "2026-08-10T08:00:00Z", "FileName": "chrome.exe"},
                    {"Timestamp": "2026-08-10T09:00:00Z", "FileName": "evil.exe"},
                ],
            }
        ],
        "validation": {
            "result_match": {"reference_query": "ImportedProcessEvents | where FileName == 'evil.exe'"}
        },
    }


def test_import_scenario_writes_file_and_returns_scenario():
    scenario = importer.import_scenario(_payload(), existing_ids=set())
    assert scenario.id == "imported_sample"
    assert (log_store.IMPORTED_DIR / "imported_sample.json").exists()


def test_import_scenario_rejects_duplicate_id():
    with pytest.raises(importer.ScenarioImportError, match="istnieje"):
        importer.import_scenario(_payload(), existing_ids={"imported_sample"})


def test_import_scenario_rejects_bad_reference_query():
    payload = _payload()
    payload["validation"]["result_match"]["reference_query"] = "ImportedProcessEvents | bogusop 1"
    with pytest.raises(importer.ScenarioImportError):
        importer.import_scenario(payload, existing_ids=set())


def test_import_scenario_rejects_unknown_dataset_name():
    payload = _payload()
    payload["datasets"] = ["NoSuchTable"]
    with pytest.raises(importer.ScenarioImportError):
        importer.import_scenario(payload, existing_ids=set())


def test_import_scenario_with_only_custom_dataset_self_validates():
    scenario = importer.import_scenario(_payload(), existing_ids=set())
    assert scenario.custom_datasets[0].name == "ImportedProcessEvents"
    # Automatically padded with background noise (see noise.py) - the 2
    # uploaded rows aren't the only rows anymore. Only 2 distinct row
    # contents here, so the per-row duplication cap (default 3) - not
    # noise.DEFAULT_TARGET_ROWS - is what actually bounds the result: at
    # most (3-1)*2 = 4 rows can be safely added.
    assert len(scenario.custom_datasets[0].rows) == 6


def test_import_scenario_padding_keeps_original_rows_and_stays_correct():
    scenario = importer.import_scenario(_payload(), existing_ids=set())
    filenames = {row["FileName"] for row in scenario.custom_datasets[0].rows}
    assert filenames == {"chrome.exe", "evil.exe"}

    tables = log_store.merge_custom_datasets(log_store.all_tables(), scenario.custom_datasets)
    from core.scenarios.validator import validate

    result = validate(scenario, "ImportedProcessEvents | where FileName == 'evil.exe'", tables=tables)
    assert result.correct is True


def test_import_scenario_skips_padding_when_dataset_already_large():
    payload = _payload()
    payload["custom_datasets"][0]["rows"] = [
        {"Timestamp": f"2026-08-10T{8 + i % 12:02d}:00:00Z", "FileName": f"f{i}.exe"}
        for i in range(noise.DEFAULT_TARGET_ROWS)
    ]
    payload["validation"]["result_match"]["reference_query"] = (
        "ImportedProcessEvents | where FileName == 'f0.exe'"
    )
    scenario = importer.import_scenario(payload, existing_ids=set())
    assert len(scenario.custom_datasets[0].rows) == noise.DEFAULT_TARGET_ROWS


def test_import_scenario_rejects_malformed_scenario():
    payload = _payload()
    del payload["prompt"]
    with pytest.raises(importer.ScenarioImportError):
        importer.import_scenario(payload, existing_ids=set())


def test_delete_scenario_removes_the_file():
    importer.import_scenario(_payload(), existing_ids=set())
    assert log_store.is_imported("imported_sample")

    importer.delete_scenario("imported_sample")

    assert not log_store.is_imported("imported_sample")
    assert not (log_store.IMPORTED_DIR / "imported_sample.json").exists()


def test_delete_scenario_rejects_built_in_scenario():
    with pytest.raises(importer.ScenarioNotDeletableError):
        importer.delete_scenario("001_find_lolbin_rundll32")


def test_delete_scenario_rejects_unknown_id():
    with pytest.raises(importer.ScenarioNotDeletableError):
        importer.delete_scenario("does_not_exist")


def test_import_scenario_pool_grows_across_imports():
    """Two scenarios that both contribute rows to the same custom table name
    end up sharing one growing table - the deliberate "logs accumulate across
    imports" behavior (see log_store.merge_custom_datasets)."""
    first = _payload("sample_one")
    second = _payload("sample_two")
    second["custom_datasets"][0]["rows"] = [
        {"Timestamp": "2026-08-11T08:00:00Z", "FileName": "malware2.exe"},
    ]
    second["validation"]["result_match"]["reference_query"] = (
        "ImportedProcessEvents | where FileName == 'malware2.exe'"
    )

    importer.import_scenario(first, existing_ids=set())
    importer.import_scenario(second, existing_ids={"sample_one"})

    pooled = log_store.all_tables()["ImportedProcessEvents"]
    filenames = {row["FileName"] for row in pooled}
    assert {"chrome.exe", "evil.exe", "malware2.exe"} <= filenames
