"""Tests for core.scenarios.noise."""
from __future__ import annotations

import random
from datetime import datetime, timezone

from core.scenarios import noise


def _dataset(rows: list[dict]) -> dict:
    return {
        "name": "ImportedProcessEvents",
        "columns": [
            {"name": "Timestamp", "type": "datetime"},
            {"name": "FileName", "type": "string"},
        ],
        "rows": rows,
    }


def test_pad_dataset_rows_reaches_target_when_diversity_allows():
    # 20 distinct row contents, cap=3 (default) -> capacity is 20*2=40,
    # comfortably above the target of 50-20=30 needed, so target_rows is
    # actually reachable here.
    rows = [{"Timestamp": "2026-08-10T08:00:00Z", "FileName": f"f{i}.exe"} for i in range(20)]
    dataset = _dataset(rows)
    padded = noise.pad_dataset_rows(dataset, target_rows=50, rng=random.Random(0))
    assert len(padded["rows"]) == 50


def test_pad_dataset_rows_stops_short_of_target_when_diversity_is_low():
    # Only 2 distinct row contents and the default cap of 3 -> at most
    # (3-1)*2 = 4 rows can be safely added, so target_rows=50 is
    # unreachable and padding stops at 6 rather than over-representing
    # either row.
    dataset = _dataset(
        [
            {"Timestamp": "2026-08-10T08:00:00Z", "FileName": "chrome.exe"},
            {"Timestamp": "2026-08-10T09:00:00Z", "FileName": "evil.exe"},
        ]
    )
    padded = noise.pad_dataset_rows(dataset, target_rows=50, rng=random.Random(0))
    assert len(padded["rows"]) == 6
    counts: dict[str, int] = {}
    for row in padded["rows"]:
        counts[row["FileName"]] = counts.get(row["FileName"], 0) + 1
    assert counts == {"chrome.exe": 3, "evil.exe": 3}


def test_pad_dataset_rows_no_op_when_already_at_target():
    rows = [{"Timestamp": "2026-08-10T08:00:00Z", "FileName": f"f{i}.exe"} for i in range(10)]
    dataset = _dataset(rows)
    padded = noise.pad_dataset_rows(dataset, target_rows=10, rng=random.Random(0))
    assert len(padded["rows"]) == 10


def test_pad_dataset_rows_never_invents_new_non_datetime_values():
    dataset = _dataset(
        [
            {"Timestamp": "2026-08-10T08:00:00Z", "FileName": "chrome.exe"},
            {"Timestamp": "2026-08-10T09:00:00Z", "FileName": "evil.exe"},
        ]
    )
    padded = noise.pad_dataset_rows(dataset, target_rows=40, rng=random.Random(1))
    filenames = {row["FileName"] for row in padded["rows"]}
    assert filenames == {"chrome.exe", "evil.exe"}


def test_pad_dataset_rows_jitters_timestamps_within_original_span():
    dataset = _dataset(
        [
            {"Timestamp": "2026-08-10T08:00:00Z", "FileName": "chrome.exe"},
            {"Timestamp": "2026-08-10T09:00:00Z", "FileName": "chrome.exe"},
        ]
    )
    padded = noise.pad_dataset_rows(dataset, target_rows=30, rng=random.Random(2))
    lo = datetime(2026, 8, 10, 8, 0, 0, tzinfo=timezone.utc)
    hi = datetime(2026, 8, 10, 9, 0, 0, tzinfo=timezone.utc)
    for row in padded["rows"]:
        ts = datetime.fromisoformat(row["Timestamp"].replace("Z", "+00:00"))
        assert lo <= ts <= hi


def test_pad_dataset_rows_caps_duplicates_of_a_single_row_content():
    # 10 distinct row contents, cap=3 -> capped capacity is 20 extra rows,
    # comfortably above the 10 extra needed to reach target_rows=20, so the
    # cap is satisfiable here without falling short (see the
    # low-diversity test above for the case where it isn't).
    rows = [{"Timestamp": "2026-08-10T08:00:00Z", "FileName": f"f{i}.exe"} for i in range(10)]
    dataset = _dataset(rows)
    padded = noise.pad_dataset_rows(dataset, target_rows=20, rng=random.Random(3), max_occurrences_per_row=3)
    counts: dict[str, int] = {}
    for row in padded["rows"]:
        counts[row["FileName"]] = counts.get(row["FileName"], 0) + 1
    assert len(padded["rows"]) == 20
    assert all(count <= 3 for count in counts.values())


def test_pad_scenario_data_is_deterministic_for_same_id():
    data = {
        "id": "sample",
        "custom_datasets": [
            _dataset(
                [
                    {"Timestamp": "2026-08-10T08:00:00Z", "FileName": "chrome.exe"},
                    {"Timestamp": "2026-08-10T09:00:00Z", "FileName": "evil.exe"},
                ]
            )
        ],
    }
    first = noise.pad_scenario_data(data, target_rows=20)
    second = noise.pad_scenario_data(data, target_rows=20)
    assert first == second


def test_pad_scenario_data_no_op_without_custom_datasets():
    data = {"id": "x", "datasets": ["DeviceProcessEvents"]}
    assert noise.pad_scenario_data(data) is data
