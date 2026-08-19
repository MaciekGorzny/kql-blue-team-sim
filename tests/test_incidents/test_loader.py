"""Tests for core.incidents.loader."""
import json
from pathlib import Path

import pytest

from core.incidents import load_all_incidents
from core.incidents.loader import IncidentLoadError, load_incident_file


def test_load_all_incidents_finds_nine_incidents():
    incidents = load_all_incidents()
    assert len(incidents) == 9


def test_incidents_are_sorted_by_filename():
    incidents = load_all_incidents()
    ids = [incident.id for incident in incidents]
    assert ids == [
        "01_prinz_eugen_ransomware",
        "02_devicecode_phishing_and_containment",
        "03_gotoresolve_rmm_abuse",
        "04_clickfix_blocked_attempt",
        "05_fake_invoice_c2_beacon",
        "06_lummac2_infostealer",
        "07_ta569_driveby_blocked",
        "08_theatercraft_malvertising",
        "09_meta_2fa_relay_phishing",
    ]


def test_every_incident_has_non_empty_fields():
    for incident in load_all_incidents():
        assert incident.title.strip()
        assert incident.summary.strip()
        assert incident.steps
        for step in incident.steps:
            assert step.narrative.strip()
            if step.kind == "investigation":
                assert step.scenario_id.strip()
            else:
                assert step.title.strip()
                assert step.actions


def test_second_incident_mixes_investigation_and_action_steps():
    incidents = load_all_incidents()
    incident = next(i for i in incidents if i.id == "02_devicecode_phishing_and_containment")
    kinds = [step.kind for step in incident.steps]
    assert kinds == ["investigation", "investigation", "action", "investigation", "action"]


def test_first_incident_now_also_mixes_investigation_and_action_steps():
    incidents = load_all_incidents()
    incident = next(i for i in incidents if i.id == "01_prinz_eugen_ransomware")
    kinds = [step.kind for step in incident.steps]
    assert kinds == [
        "investigation",
        "investigation",
        "action",
        "investigation",
        "investigation",
        "action",
        "investigation",
        "action",
    ]


def test_malformed_json_raises_incident_load_error(tmp_path: Path):
    bad_file = tmp_path / "bad.json"
    bad_file.write_text("{not valid json", encoding="utf-8")
    with pytest.raises(IncidentLoadError):
        load_incident_file(bad_file)


def test_missing_required_field_raises_incident_load_error(tmp_path: Path):
    bad_file = tmp_path / "bad.json"
    bad_file.write_text(json.dumps({"id": "x", "title": "y"}), encoding="utf-8")
    with pytest.raises(IncidentLoadError):
        load_incident_file(bad_file)


def test_step_missing_narrative_raises_incident_load_error(tmp_path: Path):
    bad_file = tmp_path / "bad.json"
    bad_file.write_text(
        json.dumps(
            {
                "id": "x",
                "title": "y",
                "summary": "z",
                "steps": [{"scenario_id": "001_find_lolbin_rundll32"}],
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(IncidentLoadError):
        load_incident_file(bad_file)


def test_incident_with_no_steps_raises_incident_load_error(tmp_path: Path):
    bad_file = tmp_path / "bad.json"
    bad_file.write_text(
        json.dumps({"id": "x", "title": "y", "summary": "z", "steps": []}), encoding="utf-8"
    )
    with pytest.raises(IncidentLoadError):
        load_incident_file(bad_file)


def test_action_step_parses_correctly(tmp_path: Path):
    good_file = tmp_path / "good.json"
    good_file.write_text(
        json.dumps(
            {
                "id": "x",
                "title": "y",
                "summary": "z",
                "steps": [
                    {
                        "kind": "action",
                        "title": "Zablokuj konto",
                        "narrative": "...",
                        "actions": ["Zablokuj logowanie.", "Odwołaj sesje."],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    incident = load_incident_file(good_file)
    step = incident.steps[0]
    assert step.kind == "action"
    assert step.title == "Zablokuj konto"
    assert step.actions == ("Zablokuj logowanie.", "Odwołaj sesje.")
    assert step.scenario_id is None


def test_action_step_missing_title_raises_incident_load_error(tmp_path: Path):
    bad_file = tmp_path / "bad.json"
    bad_file.write_text(
        json.dumps(
            {
                "id": "x",
                "title": "y",
                "summary": "z",
                "steps": [{"kind": "action", "narrative": "...", "actions": ["a"]}],
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(IncidentLoadError):
        load_incident_file(bad_file)


def test_action_step_with_no_actions_raises_incident_load_error(tmp_path: Path):
    bad_file = tmp_path / "bad.json"
    bad_file.write_text(
        json.dumps(
            {
                "id": "x",
                "title": "y",
                "summary": "z",
                "steps": [{"kind": "action", "title": "t", "narrative": "...", "actions": []}],
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(IncidentLoadError):
        load_incident_file(bad_file)


def test_investigation_step_missing_scenario_id_raises_incident_load_error(tmp_path: Path):
    bad_file = tmp_path / "bad.json"
    bad_file.write_text(
        json.dumps(
            {
                "id": "x",
                "title": "y",
                "summary": "z",
                "steps": [{"narrative": "..."}],
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(IncidentLoadError):
        load_incident_file(bad_file)
