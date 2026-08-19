"""Integration tests for the HTML page routes."""
from __future__ import annotations

import json
import re

def _json_blob(html: str, element_id: str):
    pattern = rf'<script type="application/json" id="{re.escape(element_id)}">(.*?)</script>'
    match = re.search(pattern, html, re.DOTALL)
    assert match, f"no <script type=application/json id={element_id!r}> blob found"
    return json.loads(match.group(1))


def test_index_redirects_to_scenario_list(client):
    response = client.get("/", follow_redirects=False)
    assert response.status_code in (302, 307)
    assert response.headers["location"] == "/scenarios"


def test_scenario_list_redirects_to_first_scenario(client):
    response = client.get("/scenarios", follow_redirects=False)
    assert response.status_code in (302, 307)
    assert response.headers["location"] == "/scenarios/001_find_lolbin_rundll32"


def test_scenario_list_shows_all_scenario_titles(client):
    response = client.get("/scenarios")
    assert response.status_code == 200
    assert "Podejrzany rundll32.exe" in response.text
    assert "Ruch boczny" in response.text


def test_scenario_detail_shows_prompt_and_editor(client):
    response = client.get("/scenarios/001_find_lolbin_rundll32")
    assert response.status_code == 200
    data = _json_blob(response.text, "initial-scenario-data")
    assert data["id"] == "001_find_lolbin_rundll32"
    assert "rundll32.exe" in data["prompt"]


def test_scenario_detail_shows_hint_and_mitre_tag(client):
    response = client.get("/scenarios/002_encoded_powershell")
    assert response.status_code == 200
    data = _json_blob(response.text, "initial-scenario-data")
    assert "T1059.001" in data["mitre_techniques"]
    assert data["hint"]


def test_scenario_detail_unknown_id_is_404(client):
    response = client.get("/scenarios/does_not_exist")
    assert response.status_code == 404


def test_scenario_detail_has_prev_next_navigation(client):
    response = client.get("/scenarios/002_encoded_powershell")
    assert response.status_code == 200
    data = _json_blob(response.text, "initial-scenario-data")
    assert data["prev_id"] == "001_find_lolbin_rundll32"
    assert data["next_id"] == "003_office_spawns_lolbin"


def test_sandbox_page_renders_with_sandbox_id(client):
    response = client.get("/sandbox")
    assert response.status_code == 200
    data = _json_blob(response.text, "initial-scenario-data")
    assert data["id"] == "__sandbox__"
    assert "Wolne zapytania" in response.text


def test_lesson_page_renders_with_prefixed_id(client):
    response = client.get("/lessons/where")
    assert response.status_code == 200
    data = _json_blob(response.text, "initial-scenario-data")
    assert data["id"] == "lesson:where"
    assert data["lesson"]["id"] == "where"
    assert "example_query" in data["lesson"]


def test_lesson_page_unknown_id_is_404(client):
    response = client.get("/lessons/does_not_exist")
    assert response.status_code == 404


def test_lesson_page_lists_all_lessons_in_sidebar_data(client):
    response = client.get("/lessons/where")
    lessons = _json_blob(response.text, "lessons-data")
    assert len(lessons) == 16


def test_incident_overview_page_renders_with_prefixed_id(client):
    response = client.get("/incidents/01_prinz_eugen_ransomware")
    assert response.status_code == 200
    data = _json_blob(response.text, "initial-scenario-data")
    assert data["id"] == "incident:01_prinz_eugen_ransomware"
    assert len(data["incident"]["steps"]) == 8


def test_incident_overview_page_unknown_id_is_404(client):
    response = client.get("/incidents/does_not_exist")
    assert response.status_code == 404


def test_incident_step_page_renders_with_real_scenario_id(client):
    response = client.get("/incidents/01_prinz_eugen_ransomware/steps/2")
    assert response.status_code == 200
    data = _json_blob(response.text, "initial-scenario-data")
    assert data["id"] == "015_rmm_spawns_downloader"
    assert data["incident"]["step_number"] == 2


def test_incident_step_page_out_of_range_is_404(client):
    response = client.get("/incidents/01_prinz_eugen_ransomware/steps/0")
    assert response.status_code == 404


def test_scenario_page_lists_incidents_in_sidebar_data(client):
    response = client.get("/scenarios/001_find_lolbin_rundll32")
    incidents = _json_blob(response.text, "incidents-data")
    assert len(incidents) == 9
    assert {i["id"] for i in incidents} == {
        "01_prinz_eugen_ransomware",
        "02_devicecode_phishing_and_containment",
        "03_gotoresolve_rmm_abuse",
        "04_clickfix_blocked_attempt",
        "05_fake_invoice_c2_beacon",
        "06_lummac2_infostealer",
        "07_ta569_driveby_blocked",
        "08_theatercraft_malvertising",
        "09_meta_2fa_relay_phishing",
    }


def test_incident_action_step_page_renders_for_first_incident(client):
    response = client.get("/incidents/01_prinz_eugen_ransomware/steps/3")
    assert response.status_code == 200
    data = _json_blob(response.text, "initial-scenario-data")
    assert data["kind"] == "action"
    assert data["title"] == "Natychmiastowa izolacja hosta"


def test_incident_action_step_page_renders_with_synthetic_id(client):
    response = client.get("/incidents/02_devicecode_phishing_and_containment/steps/3")
    assert response.status_code == 200
    data = _json_blob(response.text, "initial-scenario-data")
    assert data["kind"] == "action"
    assert data["id"] == "02_devicecode_phishing_and_containment:step:3"
    assert data["title"] == "Natychmiastowe powstrzymanie"
    assert len(data["actions"]) == 3


def test_static_assets_are_served(client):
    css = client.get("/static/style.css")
    assert css.status_code == 200
    js = client.get("/static/app.js")
    assert js.status_code == 200
