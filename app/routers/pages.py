"""HTML page routes (server-rendered via Jinja2).

Independent of the JSON API in api.py - the pages' own JS (static/app.js)
calls the API via fetch() to run queries and switch scenarios without a full
page reload.
"""
from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse

from ..incident_registry import (
    get_all_incidents,
    get_incident_or_404,
    get_incident_step_or_404,
    incident_to_dict,
    incident_to_summary_dict,
)
from ..lesson_registry import get_all_lessons, get_lesson_or_404, lesson_to_dict, lesson_to_summary_dict
from ..scenario_registry import (
    get_all_scenarios,
    get_scenario_with_neighbors,
    scenario_to_dict,
    scenario_to_summary_dict,
)
from ..templating import templates

router = APIRouter()

# Must match the SANDBOX_ID constant in app/static/app.js - the pseudo id the
# frontend uses to tell "free-query sandbox" apart from a real scenario id.
SANDBOX_ID = "__sandbox__"

# Must match LESSON_ID_PREFIX in app/static/app.js - prefixing a lesson's own
# id lets the frontend tell "which lesson" apart from a scenario id or the
# sandbox id purely from the id string's shape.
LESSON_ID_PREFIX = "lesson:"

# Must match INCIDENT_ID_PREFIX in app/static/app.js - used only for an
# incident *overview* page's pseudo id. A step page's id is the real
# scenario id it grades against (see incident_step() below), not prefixed.
INCIDENT_ID_PREFIX = "incident:"


def _json_script(data: object) -> str:
    """Serializes `data` for embedding inside a `<script type="application/json">`
    tag. `ensure_ascii=False` keeps Polish diacritics literal in the page
    source; escaping "<" prevents a literal "</script>" inside a string value
    (e.g. a scenario's prompt or hint) from closing the tag early."""
    return json.dumps(data, ensure_ascii=False).replace("<", "\\u003c")


def _lessons_json() -> str:
    """Embedded on every shell page load (not just /lessons/*), same as
    scenarios_json - the sidebar's "Lekcje" section is always populated
    regardless of which route rendered the shell."""
    return _json_script([lesson_to_summary_dict(lesson) for lesson in get_all_lessons()])


def _incidents_json() -> str:
    """Embedded on every shell page load, same as lessons_json - the
    sidebar's "Scenariusze" section is always populated regardless of which
    route rendered the shell."""
    return _json_script([incident_to_summary_dict(incident) for incident in get_all_incidents()])


@router.get("/")
def index() -> RedirectResponse:
    return RedirectResponse(url="/scenarios")


@router.get("/scenarios")
def scenario_list() -> RedirectResponse:
    scenarios = get_all_scenarios()
    if not scenarios:
        raise HTTPException(status_code=500, detail="Brak zdefiniowanych ćwiczeń.")
    return RedirectResponse(url=f"/scenarios/{scenarios[0].id}")


@router.get("/sandbox")
def sandbox(request: Request):
    scenarios = get_all_scenarios()
    return templates.TemplateResponse(
        request,
        "scenario_shell.html",
        {
            "page_title": "Wolne zapytania",
            "scenarios_json": _json_script([scenario_to_summary_dict(s) for s in scenarios]),
            "lessons_json": _lessons_json(),
            "incidents_json": _incidents_json(),
            "scenario_json": _json_script({"id": SANDBOX_ID}),
        },
    )


@router.get("/lessons/{lesson_id}")
def lesson_detail(request: Request, lesson_id: str):
    lesson = get_lesson_or_404(lesson_id)
    scenarios = get_all_scenarios()
    # Not a real Scenario, so the initial blob only carries the prefixed
    # pseudo id (for currentScenarioId/sidebar-active tracking) plus the full
    # lesson payload nested under "lesson" - app.js's init() reads
    # initial.lesson directly instead of treating `initial` itself as
    # scenario-shaped, unlike the scenario_detail/sandbox routes below.
    initial = {"id": f"{LESSON_ID_PREFIX}{lesson.id}", "lesson": lesson_to_dict(lesson)}
    return templates.TemplateResponse(
        request,
        "scenario_shell.html",
        {
            "page_title": lesson.title,
            "scenarios_json": _json_script([scenario_to_summary_dict(s) for s in scenarios]),
            "lessons_json": _lessons_json(),
            "incidents_json": _incidents_json(),
            "scenario_json": _json_script(initial),
        },
    )


@router.get("/scenarios/{scenario_id}")
def scenario_detail(request: Request, scenario_id: str):
    scenario, prev_id, next_id = get_scenario_with_neighbors(scenario_id)
    scenarios = get_all_scenarios()
    return templates.TemplateResponse(
        request,
        "scenario_shell.html",
        {
            "page_title": scenario.title,
            "scenarios_json": _json_script([scenario_to_summary_dict(s) for s in scenarios]),
            "lessons_json": _lessons_json(),
            "incidents_json": _incidents_json(),
            "scenario_json": _json_script(scenario_to_dict(scenario, prev_id, next_id)),
        },
    )


@router.get("/incidents/{incident_id}")
def incident_overview(request: Request, incident_id: str):
    incident = get_incident_or_404(incident_id)
    scenarios = get_all_scenarios()
    initial = {"id": f"{INCIDENT_ID_PREFIX}{incident.id}", "incident": incident_to_dict(incident)}
    return templates.TemplateResponse(
        request,
        "scenario_shell.html",
        {
            "page_title": incident.title,
            "scenarios_json": _json_script([scenario_to_summary_dict(s) for s in scenarios]),
            "lessons_json": _lessons_json(),
            "incidents_json": _incidents_json(),
            "scenario_json": _json_script(initial),
        },
    )


@router.get("/incidents/{incident_id}/steps/{step_number}")
def incident_step(request: Request, incident_id: str, step_number: int):
    data = get_incident_step_or_404(incident_id, step_number)
    scenarios = get_all_scenarios()
    return templates.TemplateResponse(
        request,
        "scenario_shell.html",
        {
            "page_title": f"{data['title']} ({data['incident']['title']}, krok {step_number})",
            "scenarios_json": _json_script([scenario_to_summary_dict(s) for s in scenarios]),
            "lessons_json": _lessons_json(),
            "incidents_json": _incidents_json(),
            "scenario_json": _json_script(data),
        },
    )
