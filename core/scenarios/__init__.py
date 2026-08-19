"""Public entry point for the scenarios layer.

Typical usage:

    from core.scenarios import load_all_scenarios, validate

    scenarios = load_all_scenarios()
    result = validate(scenarios[0], "DeviceProcessEvents | where FileName == 'rundll32.exe'")
"""
from __future__ import annotations

from . import importer, log_store, noise
from .loader import ScenarioLoadError, load_scenario_file, load_scenarios_from_dir, parse_scenario
from .log_store import KQL_BASICS_DIR, all_tables, load_all_scenarios
from .schema import CustomColumn, CustomDataset, Difficulty, RequiredUsageCriterion, ResultMatchCriterion, Scenario
from .validator import ValidationResult, validate

__all__ = [
    "load_all_scenarios",
    "load_scenario_file",
    "load_scenarios_from_dir",
    "parse_scenario",
    "all_tables",
    "validate",
    "ValidationResult",
    "Scenario",
    "Difficulty",
    "ResultMatchCriterion",
    "RequiredUsageCriterion",
    "CustomColumn",
    "CustomDataset",
    "ScenarioLoadError",
    "KQL_BASICS_DIR",
    "importer",
    "log_store",
    "noise",
]
