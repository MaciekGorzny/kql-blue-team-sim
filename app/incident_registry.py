"""Thin incident lookup helpers, mirroring app/lesson_registry.py.

Composes with app/scenario_registry.py to resolve each step's `scenario_id`
into full scenario detail - an incident carries no scenario data of its own,
only ids + narrative framing text.
"""
from __future__ import annotations

from typing import Any

from fastapi import HTTPException

from core.incidents import Incident, load_all_incidents

from . import scenario_registry


def get_all_incidents() -> list[Incident]:
    return load_all_incidents()


def get_incident_or_404(incident_id: str) -> Incident:
    for incident in load_all_incidents():
        if incident.id == incident_id:
            return incident
    raise HTTPException(status_code=404, detail=f"Nieznany scenariusz '{incident_id}'.")


def incident_to_summary_dict(incident: Incident) -> dict[str, Any]:
    return {
        "id": incident.id,
        "title": incident.title,
        "summary": incident.summary,
        "step_count": len(incident.steps),
    }


def incident_to_dict(incident: Incident) -> dict[str, Any]:
    steps = []
    for i, step in enumerate(incident.steps, start=1):
        if step.kind == "action":
            steps.append(
                {
                    "step_number": i,
                    "kind": "action",
                    "title": step.title,
                    "narrative": step.narrative,
                    "actions": list(step.actions),
                }
            )
        else:
            scenario = scenario_registry.get_scenario_or_404(step.scenario_id)
            steps.append(
                {
                    "step_number": i,
                    "kind": "investigation",
                    "scenario_id": scenario.id,
                    "scenario_title": scenario.title,
                    "difficulty": scenario.difficulty.value,
                    "mitre_techniques": list(scenario.mitre_techniques),
                    "narrative": step.narrative,
                }
            )
    return {
        "id": incident.id,
        "title": incident.title,
        "summary": incident.summary,
        "steps": steps,
    }


def _step_context(incident: Incident, step_number: int) -> dict[str, Any]:
    step_count = len(incident.steps)
    step = incident.steps[step_number - 1]
    return {
        "step": step,
        "incident": {
            "id": incident.id,
            "title": incident.title,
            "step_number": step_number,
            "step_count": step_count,
            "narrative": step.narrative,
            "prev_step": step_number - 1 if step_number > 1 else None,
            "next_step": step_number + 1 if step_number < step_count else None,
        },
    }


def get_incident_step_or_404(incident_id: str, step_number: int) -> dict[str, Any]:
    """Resolves one step into the shape both the `/incidents/{id}/steps/{n}`
    page route and the matching API route return, so it's defined exactly
    once. An "investigation" step returns a merged scenario-detail +
    `incident` context dict (same shape as before this function grew a
    second step kind); an "action" step returns no scenario fields at all -
    just its own title/actions plus the same `incident` context."""
    incident = get_incident_or_404(incident_id)
    step_count = len(incident.steps)
    if not 1 <= step_number <= step_count:
        raise HTTPException(
            status_code=404,
            detail=f"Scenariusz '{incident_id}' nie ma kroku {step_number} (dostępne: 1-{step_count}).",
        )

    ctx = _step_context(incident, step_number)
    step = ctx["step"]

    if step.kind == "action":
        return {
            "kind": "action",
            "id": f"{incident.id}:step:{step_number}",
            "title": step.title,
            "actions": list(step.actions),
            "incident": ctx["incident"],
        }

    scenario = scenario_registry.get_scenario_or_404(step.scenario_id)
    return {
        "kind": "investigation",
        **scenario_registry.scenario_to_dict(scenario),
        "incident": ctx["incident"],
    }
