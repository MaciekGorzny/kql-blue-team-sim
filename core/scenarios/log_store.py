"""Scenario directory scanning + the merged, always-fresh log table pool.

Kept as its own leaf module (rather than living in `__init__.py` or
`importer.py`) specifically to avoid a circular import: `importer.py` needs to
call into this module for its import-time smoke test, and this module owns
`IMPORTED_DIR`. Everything here only depends on `.loader`/`.schema`/
`core.datasets`, never on `.validator`, `.importer`, or the package `__init__`.

`IMPORTED_DIR` must always be referenced as `log_store.IMPORTED_DIR` (attribute
lookup) elsewhere, never `from .log_store import IMPORTED_DIR` - that keeps a
single patchable source of truth so tests can
`monkeypatch.setattr(log_store, "IMPORTED_DIR", tmp_path)` and have every
consumer (`load_all_scenarios`, `all_tables`, the importer's write step) see it
consistently.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from core.datasets import DATASETS

from .loader import load_scenarios_from_dir
from .schema import CustomDataset, Scenario

Row = dict[str, Any]

KQL_BASICS_DIR = Path(__file__).parent / "kql_basics"
IMPORTED_DIR = Path(__file__).parent / "imported"


def load_all_scenarios() -> list[Scenario]:
    """Loads every scenario: the built-in pack (in conventional numbered
    order) followed by any imported scenarios."""
    return load_scenarios_from_dir(KQL_BASICS_DIR) + load_scenarios_from_dir(IMPORTED_DIR)


def is_imported(scenario_id: str) -> bool:
    """Whether `scenario_id` refers to an imported scenario (as opposed to a
    built-in one) - built-ins live in `KQL_BASICS_DIR` and are never
    deletable, imports live in `IMPORTED_DIR` and are."""
    return imported_path(scenario_id).is_file()


def imported_path(scenario_id: str) -> Path:
    return IMPORTED_DIR / f"{scenario_id}.json"


def merge_custom_datasets(tables: dict[str, list[Row]], custom_datasets: tuple[CustomDataset, ...]) -> dict[str, list[Row]]:
    """Layers `custom_datasets` onto a copy of `tables`, concatenating rows
    when a name already exists - this is the whole "logs accumulate across
    imports" mechanism: two scenarios that each contribute rows to a
    same-named table end up sharing one growing table, not two isolated ones."""
    merged = {name: list(rows) for name, rows in tables.items()}
    for cd in custom_datasets:
        merged[cd.name] = merged.get(cd.name, []) + list(cd.rows)
    return merged


def all_tables() -> dict[str, list[Row]]:
    """Every table any query can touch right now: the built-in datasets plus
    every loaded scenario's custom_datasets, merged by name. Recomputed on
    every call (no caching) - same freshness philosophy as
    `load_all_scenarios`/`scenario_registry`, and cheap at this data size."""
    tables: dict[str, list[Row]] = {name: list(rows) for name, rows in DATASETS.items()}
    for scenario in load_all_scenarios():
        tables = merge_custom_datasets(tables, scenario.custom_datasets)
    return tables
