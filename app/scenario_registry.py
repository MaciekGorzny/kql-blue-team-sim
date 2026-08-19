"""Thin scenario lookup helpers shared by the pages and API routers.

Reloads scenarios from disk on every call rather than caching - at 7 tiny
JSON files this costs a fraction of a millisecond, and it means editing a
scenario file takes effect without restarting the server.
"""
from __future__ import annotations

from typing import Any

from fastapi import HTTPException

from core.scenarios import Scenario, load_all_scenarios, log_store


def get_all_scenarios() -> list[Scenario]:
    return load_all_scenarios()


def get_scenario_or_404(scenario_id: str) -> Scenario:
    for scenario in load_all_scenarios():
        if scenario.id == scenario_id:
            return scenario
    raise HTTPException(status_code=404, detail=f"Nieznane ćwiczenie '{scenario_id}'.")


def get_scenario_with_neighbors(scenario_id: str) -> tuple[Scenario, str | None, str | None]:
    """Like `get_scenario_or_404`, but also returns the previous/next scenario
    id (by position in the full list) - one disk load instead of two."""
    scenarios = load_all_scenarios()
    ids = [s.id for s in scenarios]
    try:
        idx = ids.index(scenario_id)
    except ValueError:
        raise HTTPException(status_code=404, detail=f"Nieznane ćwiczenie '{scenario_id}'.") from None
    prev_id = ids[idx - 1] if idx > 0 else None
    next_id = ids[idx + 1] if idx < len(ids) - 1 else None
    return scenarios[idx], prev_id, next_id


def scenario_to_summary_dict(scenario: Scenario) -> dict[str, Any]:
    return {
        "id": scenario.id,
        "title": scenario.title,
        "difficulty": scenario.difficulty.value,
        "mitre_techniques": list(scenario.mitre_techniques),
        "is_imported": log_store.is_imported(scenario.id),
    }


def scenario_to_dict(
    scenario: Scenario, prev_id: str | None = None, next_id: str | None = None
) -> dict[str, Any]:
    return {
        "id": scenario.id,
        "title": scenario.title,
        "prompt": scenario.prompt,
        "datasets": list(scenario.datasets),
        "difficulty": scenario.difficulty.value,
        "mitre_techniques": list(scenario.mitre_techniques),
        "hint": scenario.hint,
        "source_url": scenario.source_url,
        "sc200_area": scenario.sc200_area,
        "prev_id": prev_id,
        "next_id": next_id,
        "is_imported": log_store.is_imported(scenario.id),
    }
