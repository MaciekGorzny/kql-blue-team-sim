"""Imports a scenario JSON produced outside this app (e.g. by an external
malware-sample-analysis tool that generates a scenario + its own IoC-derived
log rows) into the on-disk scenario pack.

Reuses `loader.parse_scenario` (the exact same parser `load_scenario_file`
uses for the built-in scenarios) so an imported scenario is held to the same
shape/validation rules - no forked parsing logic.
"""
from __future__ import annotations

import json
from typing import Any

from . import log_store, noise
from .loader import ScenarioLoadError, parse_scenario
from .schema import Scenario
from .validator import ValidationResult, validate


class ScenarioImportError(Exception):
    """Raised when an uploaded scenario is malformed, collides with an
    existing scenario id, or fails its own reference_query/dataset checks."""


class ScenarioNotDeletableError(Exception):
    """Raised when trying to delete a scenario that isn't an import - the
    built-in pack in kql_basics/ is never deletable."""


def _smoke_test(scenario: Scenario) -> ValidationResult | None:
    """Runs reference_query against the pool this scenario will actually be
    graded against once imported (built-in + every already-loaded scenario +
    this one's own not-yet-persisted custom_datasets rows). Returns None for
    scenarios with no result_match (nothing to self-check against data)."""
    if scenario.result_match is None:
        return None
    tables = log_store.merge_custom_datasets(log_store.all_tables(), scenario.custom_datasets)
    return validate(scenario, scenario.result_match.reference_query, tables=tables)


def import_scenario(data: dict[str, Any], *, existing_ids: set[str]) -> Scenario:
    try:
        scenario = parse_scenario(data)
    except ScenarioLoadError as e:
        raise ScenarioImportError(str(e)) from e

    if scenario.id in existing_ids:
        raise ScenarioImportError(f"Scenariusz o id '{scenario.id}' już istnieje.")

    # A dataset name is valid if it's already in the shared log pool (built-in,
    # or contributed by a previously imported scenario - the pool is meant to
    # grow and be reused across scenarios) or defined by this scenario's own
    # custom_datasets.
    known = set(log_store.all_tables()) | {cd.name for cd in scenario.custom_datasets}
    unknown = set(scenario.datasets) - known
    if unknown:
        raise ScenarioImportError(f"Scenariusz odwołuje się do nieznanych tabel: {sorted(unknown)}.")

    # Running reference_query as if it were the submission is tautological for
    # the result-match comparison itself (it always matches itself) - what
    # this actually catches is reference_query failing to execute at all (bad
    # syntax, unknown column) or, when required_usage is also set,
    # reference_query not meeting its own required-technique check. Same
    # safety net test_scenario_files.py applies to the built-ins.
    result = _smoke_test(scenario)
    if result is not None and not result.correct:
        raise ScenarioImportError(
            f"reference_query scenariusza nie przechodzi własnej walidacji: {result.message}"
        )

    # Best-effort: pad each custom dataset with duplicated/jittered background
    # noise (see noise.py) so a real IoC isn't the only row in its table. A
    # scenario's "correct answer" is always recomputed live from
    # reference_query (never hardcoded - see validator.py), so padding can't
    # make an otherwise-correct query wrong; noise.py's own per-row
    # duplication cap is what keeps padding from diluting the intended lesson
    # (e.g. accidentally pushing another row's count over a threshold too).
    # Re-validating here is a narrower, cheap defensive check against padding
    # causing an outright execution error; if that ever happens, fall back to
    # the unpadded data rather than failing the whole import.
    padded_data = noise.pad_scenario_data(data)
    try:
        padded_scenario = parse_scenario(padded_data)
        padded_result = _smoke_test(padded_scenario)
        if padded_result is None or padded_result.correct:
            data, scenario = padded_data, padded_scenario
    except ScenarioLoadError:
        pass

    log_store.IMPORTED_DIR.mkdir(parents=True, exist_ok=True)
    log_store.imported_path(scenario.id).write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return scenario


def delete_scenario(scenario_id: str) -> None:
    path = log_store.imported_path(scenario_id)
    if not path.is_file():
        raise ScenarioNotDeletableError(
            f"Scenariusz '{scenario_id}' nie jest zaimportowany - nie można go usunąć."
        )
    path.unlink()
