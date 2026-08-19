"""JSON API routes - deliberately independent of the server-rendered pages,
so a future frontend (e.g. a React rewrite, per the original brief) could use
these endpoints without any change to the engine/scenarios layer.
"""
from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel

from core.kql_engine import KqlError, run_query
from core.scenarios import all_tables, validate
from core.scenarios.importer import ScenarioImportError, ScenarioNotDeletableError, delete_scenario, import_scenario

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
    get_scenario_or_404,
    get_scenario_with_neighbors,
    scenario_to_dict,
    scenario_to_summary_dict,
)

router = APIRouter(prefix="/api")

MAX_IMPORT_BYTES = 2 * 1024 * 1024


class RunRequest(BaseModel):
    query: str


class RunResponse(BaseModel):
    correct: bool
    message: str
    columns: list[str] = []
    rows: list[dict[str, Any]] = []
    error: str | None = None


class ScenarioSummary(BaseModel):
    id: str
    title: str
    difficulty: str
    mitre_techniques: list[str] = []
    is_imported: bool = False


class ScenarioDetail(BaseModel):
    id: str
    title: str
    prompt: str
    datasets: list[str]
    difficulty: str
    mitre_techniques: list[str] = []
    hint: str | None = None
    source_url: str | None = None
    sc200_area: str | None = None
    prev_id: str | None = None
    next_id: str | None = None
    is_imported: bool = False


class ImportResponse(BaseModel):
    scenario: ScenarioDetail


class SolutionResponse(BaseModel):
    reference_query: str | None = None
    columns: list[str] = []
    rows: list[dict[str, Any]] = []
    message: str | None = None


class QueryResponse(BaseModel):
    columns: list[str] = []
    rows: list[dict[str, Any]] = []
    error: str | None = None


class TableInfo(BaseModel):
    name: str
    row_count: int


class LessonSummary(BaseModel):
    id: str
    title: str


class LessonDetail(BaseModel):
    id: str
    title: str
    description: str
    example_query: str
    example_explanation: str


class IncidentSummary(BaseModel):
    id: str
    title: str
    summary: str
    step_count: int


class IncidentStepSummary(BaseModel):
    step_number: int
    kind: str = "investigation"
    narrative: str
    # "investigation" fields
    scenario_id: str | None = None
    scenario_title: str | None = None
    difficulty: str | None = None
    mitre_techniques: list[str] = []
    # "action" fields
    title: str | None = None
    actions: list[str] = []


class IncidentDetail(BaseModel):
    id: str
    title: str
    summary: str
    steps: list[IncidentStepSummary]


def _serialize_value(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


def _serialize_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{key: _serialize_value(v) for key, v in row.items()} for row in rows]


@router.get("/scenarios", response_model=list[ScenarioSummary])
def list_scenarios() -> list[ScenarioSummary]:
    return [ScenarioSummary(**scenario_to_summary_dict(s)) for s in get_all_scenarios()]


@router.get("/tables", response_model=list[TableInfo])
def list_tables() -> list[TableInfo]:
    """Every table currently queryable in the shared log pool - lets the
    free-query sandbox show what's available without hardcoding table names
    in the frontend."""
    return [TableInfo(name=name, row_count=len(rows)) for name, rows in sorted(all_tables().items())]


@router.post("/query", response_model=QueryResponse)
def run_free_query(body: RunRequest) -> QueryResponse:
    """Runs a query against the full shared log pool with no scenario/grading
    attached - the free-query sandbox's "Uruchom"."""
    try:
        rows = run_query(body.query, all_tables())
    except KqlError as e:
        return QueryResponse(error=str(e))
    columns = list(rows[0].keys()) if rows else []
    return QueryResponse(columns=columns, rows=_serialize_rows(rows))


@router.get("/lessons", response_model=list[LessonSummary])
def list_lessons() -> list[LessonSummary]:
    return [LessonSummary(**lesson_to_summary_dict(lesson)) for lesson in get_all_lessons()]


@router.get("/lessons/{lesson_id}", response_model=LessonDetail)
def get_lesson_detail(lesson_id: str) -> LessonDetail:
    lesson = get_lesson_or_404(lesson_id)
    return LessonDetail(**lesson_to_dict(lesson))


@router.get("/incidents", response_model=list[IncidentSummary])
def list_incidents() -> list[IncidentSummary]:
    return [IncidentSummary(**incident_to_summary_dict(i)) for i in get_all_incidents()]


@router.get("/incidents/{incident_id}", response_model=IncidentDetail)
def get_incident_detail(incident_id: str) -> IncidentDetail:
    incident = get_incident_or_404(incident_id)
    return IncidentDetail(**incident_to_dict(incident))


@router.get("/incidents/{incident_id}/steps/{step_number}")
def get_incident_step_detail(incident_id: str, step_number: int) -> dict[str, Any]:
    # No fixed response_model here: an "investigation" step returns full
    # scenario-detail fields, an "action" step returns title/actions instead
    # - see app/incident_registry.py's get_incident_step_or_404 docstring.
    return get_incident_step_or_404(incident_id, step_number)


@router.get("/scenarios/{scenario_id}", response_model=ScenarioDetail)
def get_scenario_detail(scenario_id: str) -> ScenarioDetail:
    scenario, prev_id, next_id = get_scenario_with_neighbors(scenario_id)
    return ScenarioDetail(**scenario_to_dict(scenario, prev_id, next_id))


@router.post("/scenarios/import", response_model=ImportResponse, status_code=201)
async def import_scenario_endpoint(request: Request) -> ImportResponse:
    raw = await request.body()
    if len(raw) > MAX_IMPORT_BYTES:
        raise HTTPException(
            status_code=413, detail=f"Plik jest za duży (limit {MAX_IMPORT_BYTES // 1024} KB)."
        )
    try:
        data = json.loads(raw.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        raise HTTPException(status_code=400, detail=f"Nieprawidłowy JSON: {e}") from e
    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail="Oczekiwano obiektu JSON z ćwiczeniem.")

    existing_ids = {s.id for s in get_all_scenarios()}
    try:
        scenario = import_scenario(data, existing_ids=existing_ids)
    except ScenarioImportError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e

    _, prev_id, next_id = get_scenario_with_neighbors(scenario.id)
    return ImportResponse(scenario=ScenarioDetail(**scenario_to_dict(scenario, prev_id, next_id)))


@router.delete("/scenarios/{scenario_id}", status_code=204, response_class=Response)
def delete_scenario_endpoint(scenario_id: str) -> Response:
    # 404 first, so deleting an id that never existed reads as "not found"
    # rather than "not deletable".
    get_scenario_or_404(scenario_id)
    try:
        delete_scenario(scenario_id)
    except ScenarioNotDeletableError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return Response(status_code=204)


@router.get("/scenarios/{scenario_id}/solution", response_model=SolutionResponse)
def get_scenario_solution(scenario_id: str) -> SolutionResponse:
    scenario = get_scenario_or_404(scenario_id)
    if scenario.result_match is None:
        # Technique-only (required_usage) scenarios have no single canonical
        # query to reveal - there's no "the" solution, just a requirement.
        return SolutionResponse(
            message="To zadanie nie ma jednego wzorcowego zapytania - sprawdzana jest tylko użyta technika."
        )

    reference_query = scenario.result_match.reference_query
    # Reuses validate() rather than calling run_query directly, so "the
    # solution" is computed the exact same way (same live table pool) as
    # what a trainee's own submission gets compared against - it can never
    # drift from what "correct" actually means right now.
    result = validate(scenario, reference_query)
    rows = result.user_result or []
    columns = list(rows[0].keys()) if rows else []
    return SolutionResponse(reference_query=reference_query, columns=columns, rows=_serialize_rows(rows))


@router.post("/scenarios/{scenario_id}/run", response_model=RunResponse)
def run_scenario_query(scenario_id: str, body: RunRequest) -> RunResponse:
    scenario = get_scenario_or_404(scenario_id)
    result = validate(scenario, body.query)

    if result.user_result is None:
        # The query itself failed to parse/execute - `message` already
        # carries the caret-style detail (see core.kql_engine.errors), so
        # there's no result table to show, only the error.
        return RunResponse(correct=False, message=result.message, error=result.message)

    rows = result.user_result
    columns = list(rows[0].keys()) if rows else []
    return RunResponse(
        correct=result.correct,
        message=result.message,
        columns=columns,
        rows=_serialize_rows(rows),
    )
