"""Loads Scenario objects from JSON files on disk.

One scenario = one JSON file. See schema.py for the on-disk JSON shape.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.kql_engine.ast_nodes import KqlType

from .schema import (
    CustomColumn,
    CustomDataset,
    Difficulty,
    RequiredUsageCriterion,
    ResultMatchCriterion,
    Scenario,
)


class ScenarioLoadError(Exception):
    """Raised when a scenario JSON file is missing required fields, malformed,
    or has an invalid value (e.g. unknown difficulty)."""


def _coerce_datetime(value: Any) -> datetime:
    if not isinstance(value, str):
        raise ValueError(f"oczekiwano tekstu ISO-8601, otrzymano {value!r}")
    text = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        dt = datetime.fromisoformat(text)
    except ValueError as e:
        raise ValueError(f"nieprawidłowa data/czas ISO-8601: {value!r} ({e})") from e
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


def _coerce_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str) and value.lower() in ("true", "false"):
        return value.lower() == "true"
    raise ValueError(f"oczekiwano wartości logicznej, otrzymano {value!r}")


_COERCERS = {
    KqlType.DATETIME: _coerce_datetime,
    KqlType.LONG: lambda v: int(v),
    KqlType.REAL: lambda v: float(v),
    KqlType.BOOL: _coerce_bool,
    KqlType.STRING: lambda v: v if isinstance(v, str) else str(v),
    KqlType.DYNAMIC: lambda v: v,
    KqlType.NULL: lambda v: v,
    KqlType.TIMESPAN: lambda v: v,
}


def _parse_custom_dataset(data: dict[str, Any], source: str) -> CustomDataset:
    try:
        name = data["name"]
        columns = []
        for col in data["columns"]:
            type_name = col["type"]
            try:
                kql_type = KqlType[str(type_name).upper()]
            except KeyError as e:
                raise ScenarioLoadError(
                    f"{source}: nieznany typ kolumny '{type_name}' w custom_datasets['{name}']."
                ) from e
            columns.append(CustomColumn(col["name"], kql_type, col.get("description", "")))
    except KeyError as e:
        raise ScenarioLoadError(f"{source}: custom_datasets - brakuje wymaganego pola {e}.") from e

    by_type = {c.name: c.kql_type for c in columns}

    rows: list[dict[str, Any]] = []
    for i, raw_row in enumerate(data.get("rows", [])):
        unknown = set(raw_row) - set(by_type)
        if unknown:
            raise ScenarioLoadError(
                f"{source}: wiersz {i} datasetu '{name}' ma nieznane kolumny: {sorted(unknown)}."
            )
        row: dict[str, Any] = {}
        for col_name, kql_type in by_type.items():
            value = raw_row.get(col_name)
            if value is None:
                row[col_name] = None
                continue
            try:
                row[col_name] = _COERCERS[kql_type](value)
            except (ValueError, TypeError) as e:
                raise ScenarioLoadError(
                    f"{source}: wiersz {i}, kolumna '{col_name}' datasetu '{name}': {e}"
                ) from e
        rows.append(row)

    return CustomDataset(name=name, columns=tuple(columns), rows=tuple(rows))


def load_scenario_file(path: Path) -> Scenario:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ScenarioLoadError(f"{path}: nieprawidłowy JSON ({e}).") from e
    return parse_scenario(data, source=str(path))


def load_scenarios_from_dir(directory: Path) -> list[Scenario]:
    """Loads every `*.json` file in `directory`, sorted by filename (scenario
    files are conventionally numbered, e.g. `001_...json`, to control the
    order they're presented in)."""
    return [load_scenario_file(p) for p in sorted(directory.glob("*.json"))]


def parse_scenario(data: dict[str, Any], source: str = "<uploaded>") -> Scenario:
    try:
        validation = data["validation"]

        result_match = None
        if "result_match" in validation:
            rm = validation["result_match"]
            result_match = ResultMatchCriterion(
                reference_query=rm["reference_query"], ordered=rm.get("ordered", False)
            )

        required_usage = None
        if "required_usage" in validation:
            ru = validation["required_usage"]
            required_usage = RequiredUsageCriterion(
                required_operators=tuple(ru.get("required_operators", [])),
                required_columns=tuple(ru.get("required_columns", [])),
            )

        custom_datasets = tuple(
            _parse_custom_dataset(cd, source) for cd in data.get("custom_datasets", [])
        )

        return Scenario(
            id=data["id"],
            title=data["title"],
            prompt=data["prompt"],
            datasets=tuple(data["datasets"]),
            difficulty=Difficulty(data["difficulty"]),
            mitre_techniques=tuple(data.get("mitre_techniques", [])),
            hint=data.get("hint"),
            source_url=data.get("source_url"),
            sc200_area=data.get("sc200_area"),
            result_match=result_match,
            required_usage=required_usage,
            custom_datasets=custom_datasets,
        )
    except KeyError as e:
        raise ScenarioLoadError(f"{source}: brakuje wymaganego pola {e}.") from e
    except ValueError as e:
        raise ScenarioLoadError(f"{source}: {e}") from e
