"""Integration tests for the JSON API (/api/scenarios/*)."""
from __future__ import annotations

import json


def _sample_import_payload(scenario_id: str = "imported_evil_sample") -> dict:
    return {
        "id": scenario_id,
        "title": "Znajdź próbkę malware",
        "prompt": "Znajdź uruchomienie evil.exe w tabeli ImportedProcessEvents.",
        "datasets": ["ImportedProcessEvents"],
        "difficulty": "beginner",
        "custom_datasets": [
            {
                "name": "ImportedProcessEvents",
                "columns": [
                    {"name": "Timestamp", "type": "datetime"},
                    {"name": "DeviceName", "type": "string"},
                    {"name": "FileName", "type": "string"},
                ],
                "rows": [
                    {"Timestamp": "2026-08-10T08:00:00Z", "DeviceName": "WIN-CLIENT01", "FileName": "chrome.exe"},
                    {"Timestamp": "2026-08-10T09:00:00Z", "DeviceName": "WIN-CLIENT02", "FileName": "evil.exe"},
                ],
            }
        ],
        "validation": {
            "result_match": {
                "reference_query": "ImportedProcessEvents | where FileName == 'evil.exe' | project DeviceName"
            }
        },
    }


def test_correct_reference_query_is_accepted(client):
    response = client.post(
        "/api/scenarios/001_find_lolbin_rundll32/run",
        json={"query": "DeviceProcessEvents | where FileName == 'rundll32.exe' | project DeviceName, AccountName, ProcessCommandLine"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["correct"] is True
    assert data["error"] is None
    assert data["columns"] == ["DeviceName", "AccountName", "ProcessCommandLine"]
    assert len(data["rows"]) == 1


def test_wrong_result_is_rejected_but_still_shows_users_own_result(client):
    response = client.post(
        "/api/scenarios/001_find_lolbin_rundll32/run",
        json={"query": "DeviceProcessEvents | where FileName == 'notepad.exe' | project DeviceName"},
    )
    data = response.json()
    assert data["correct"] is False
    assert data["error"] is None
    assert data["columns"] == ["DeviceName"]
    assert len(data["rows"]) > 0


def test_syntax_error_returns_error_field_and_no_rows(client):
    response = client.post(
        "/api/scenarios/001_find_lolbin_rundll32/run",
        json={"query": "DeviceProcessEvents | bogusop 1"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["correct"] is False
    assert data["error"] is not None
    assert "bogusop" in data["error"]
    assert data["columns"] == []
    assert data["rows"] == []


def test_missing_required_technique_shows_users_result_not_a_hard_error(client):
    response = client.post(
        "/api/scenarios/005_count_events_per_device/run",
        json={"query": "DeviceProcessEvents | where DeviceName == 'WIN-CLIENT01'"},
    )
    data = response.json()
    assert data["correct"] is False
    assert data["error"] is None
    assert "operator" in data["message"].lower() or "Summarize" in data["message"]
    assert len(data["rows"]) > 0


def test_datetime_column_serializes_to_iso_string(client):
    response = client.post(
        "/api/scenarios/001_find_lolbin_rundll32/run",
        json={"query": "DeviceProcessEvents | take 1"},
    )
    data = response.json()
    assert "Timestamp" in data["columns"]
    timestamp_value = data["rows"][0]["Timestamp"]
    assert isinstance(timestamp_value, str)
    assert "T" in timestamp_value  # ISO 8601


def test_unknown_scenario_id_is_404(client):
    response = client.post("/api/scenarios/does_not_exist/run", json={"query": "T | take 1"})
    assert response.status_code == 404


def test_list_scenarios_returns_all_summaries(client):
    response = client.get("/api/scenarios")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 7
    assert {"id", "title", "difficulty", "mitre_techniques"} <= data[0].keys()


def test_get_scenario_detail_returns_full_shape_with_neighbors(client):
    response = client.get("/api/scenarios/002_encoded_powershell")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "002_encoded_powershell"
    assert data["prev_id"] == "001_find_lolbin_rundll32"
    assert data["next_id"] == "003_office_spawns_lolbin"


def test_get_scenario_detail_includes_writeup_source_url(client):
    data = client.get("/api/scenarios/018_ping_delay_self_delete").json()
    assert data["source_url"] == "https://maciekgorzny.github.io/security-writeups/hunt-002.html"


def test_hand_authored_scenario_has_no_source_url(client):
    data = client.get("/api/scenarios/001_find_lolbin_rundll32").json()
    assert data["source_url"] is None


def test_get_scenario_detail_includes_sc200_area(client):
    mde = client.get("/api/scenarios/001_find_lolbin_rundll32").json()
    assert mde["sc200_area"] == "Microsoft Defender for Endpoint (MDE)"

    entra = client.get("/api/scenarios/008_password_spray_signin").json()
    assert entra["sc200_area"] == "Microsoft Entra ID"

    mdo = client.get("/api/scenarios/009_malicious_inbox_rule").json()
    assert mdo["sc200_area"] == "Microsoft Defender for Office 365"


def test_get_scenario_detail_first_and_last_have_no_neighbor(client):
    first = client.get("/api/scenarios/001_find_lolbin_rundll32").json()
    assert first["prev_id"] is None
    last = client.get("/api/scenarios/033_dcsync_non_dc_replication").json()
    assert last["next_id"] is None


def test_get_scenario_detail_unknown_id_is_404(client):
    response = client.get("/api/scenarios/does_not_exist")
    assert response.status_code == 404


def test_built_in_scenario_is_not_marked_imported(client):
    data = client.get("/api/scenarios/001_find_lolbin_rundll32").json()
    assert data["is_imported"] is False
    summary = next(s for s in client.get("/api/scenarios").json() if s["id"] == "001_find_lolbin_rundll32")
    assert summary["is_imported"] is False


def test_imported_scenario_is_marked_imported_and_deletable(client):
    client.post(
        "/api/scenarios/import",
        content=json.dumps(_sample_import_payload("delete_flag_demo")),
        headers={"Content-Type": "application/json"},
    )
    data = client.get("/api/scenarios/delete_flag_demo").json()
    assert data["is_imported"] is True


def test_delete_imported_scenario_removes_it_from_the_list(client):
    client.post(
        "/api/scenarios/import",
        content=json.dumps(_sample_import_payload("to_delete")),
        headers={"Content-Type": "application/json"},
    )
    assert any(s["id"] == "to_delete" for s in client.get("/api/scenarios").json())

    response = client.delete("/api/scenarios/to_delete")
    assert response.status_code == 204

    assert not any(s["id"] == "to_delete" for s in client.get("/api/scenarios").json())
    assert client.get("/api/scenarios/to_delete").status_code == 404


def test_delete_built_in_scenario_is_rejected(client):
    response = client.delete("/api/scenarios/001_find_lolbin_rundll32")
    assert response.status_code == 400
    # still there
    assert client.get("/api/scenarios/001_find_lolbin_rundll32").status_code == 200


def test_delete_unknown_scenario_is_404(client):
    response = client.delete("/api/scenarios/does_not_exist")
    assert response.status_code == 404


def test_get_solution_returns_reference_query_and_expected_rows(client):
    response = client.get("/api/scenarios/001_find_lolbin_rundll32/solution")
    assert response.status_code == 200
    data = response.json()
    assert "rundll32.exe" in data["reference_query"]
    assert data["columns"] == ["DeviceName", "AccountName", "ProcessCommandLine"]
    assert len(data["rows"]) == 1


def test_get_solution_matches_what_run_would_grade_against(client):
    solution = client.get("/api/scenarios/001_find_lolbin_rundll32/solution").json()
    run = client.post(
        "/api/scenarios/001_find_lolbin_rundll32/run",
        json={"query": solution["reference_query"]},
    )
    assert run.json()["correct"] is True


def test_get_solution_unknown_id_is_404(client):
    response = client.get("/api/scenarios/does_not_exist/solution")
    assert response.status_code == 404


def test_get_solution_for_required_usage_only_scenario_has_no_reference_query(client, monkeypatch):
    import core.scenarios.schema as schema
    import app.routers.api as api_module

    technique_only = schema.Scenario(
        id="technique_only_demo",
        title="Technique only",
        prompt="Use summarize.",
        datasets=("DeviceProcessEvents",),
        difficulty=schema.Difficulty.BEGINNER,
        required_usage=schema.RequiredUsageCriterion(required_operators=("SummarizeStage",)),
    )

    def fake_get_scenario_or_404(scenario_id: str):
        assert scenario_id == "technique_only_demo"
        return technique_only

    # api.py does `from ..scenario_registry import get_scenario_or_404`, so
    # the patch target must be the name as bound in api.py's own module
    # namespace - patching scenario_registry.get_scenario_or_404 itself
    # wouldn't affect api.py's already-imported reference to it.
    monkeypatch.setattr(api_module, "get_scenario_or_404", fake_get_scenario_or_404)

    response = client.get("/api/scenarios/technique_only_demo/solution")
    assert response.status_code == 200
    data = response.json()
    assert data["reference_query"] is None
    assert data["message"]


def test_import_scenario_success_with_custom_dataset(client):
    response = client.post(
        "/api/scenarios/import",
        content=json.dumps(_sample_import_payload()),
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["scenario"]["id"] == "imported_evil_sample"

    listing = client.get("/api/scenarios").json()
    assert any(s["id"] == "imported_evil_sample" for s in listing)

    run = client.post(
        "/api/scenarios/imported_evil_sample/run",
        json={"query": "ImportedProcessEvents | where FileName == 'evil.exe' | project DeviceName"},
    )
    assert run.json()["correct"] is True


def test_import_scenario_duplicate_id_is_rejected(client):
    payload = _sample_import_payload("dup_scenario")
    first = client.post("/api/scenarios/import", content=json.dumps(payload))
    assert first.status_code == 201
    second = client.post("/api/scenarios/import", content=json.dumps(payload))
    assert second.status_code == 422
    assert "istnieje" in second.json()["detail"]


def test_import_scenario_malformed_json_returns_400(client):
    response = client.post("/api/scenarios/import", content="{not valid json")
    assert response.status_code == 400


def test_import_scenario_missing_required_field_returns_422(client):
    payload = _sample_import_payload("broken_scenario")
    del payload["prompt"]
    response = client.post("/api/scenarios/import", content=json.dumps(payload))
    assert response.status_code == 422


def test_import_scenario_bad_reference_query_returns_422(client):
    # A syntactically broken reference_query fails to even execute, which is
    # what the import-time smoke test actually catches (there's no
    # independent oracle to judge a *semantically* wrong-but-valid query
    # against - see core/scenarios/importer.py).
    payload = _sample_import_payload("bad_ref_scenario")
    payload["validation"]["result_match"]["reference_query"] = "ImportedProcessEvents | bogusop 1"
    response = client.post("/api/scenarios/import", content=json.dumps(payload))
    assert response.status_code == 422


def test_list_tables_includes_every_built_in_table_with_rows(client):
    response = client.get("/api/tables")
    assert response.status_code == 200
    tables = {t["name"]: t["row_count"] for t in response.json()}
    for name in (
        "DeviceProcessEvents",
        "DeviceLogonEvents",
        "SigninLogs",
        "DeviceNetworkEvents",
        "EmailEvents",
        "DeviceFileEvents",
        "OfficeActivity",
        "IdentityLogonEvents",
        "IdentityQueryEvents",
        "IdentityDirectoryEvents",
    ):
        assert tables[name] > 0


def test_list_tables_includes_imported_custom_dataset(client):
    client.post(
        "/api/scenarios/import",
        content=json.dumps(_sample_import_payload("tables_listing_demo")),
        headers={"Content-Type": "application/json"},
    )
    response = client.get("/api/tables")
    tables = {t["name"] for t in response.json()}
    assert "ImportedProcessEvents" in tables


def test_free_query_runs_against_a_new_builtin_table(client):
    response = client.post("/api/query", json={"query": "SigninLogs | where ResultType != '0' | count"})
    assert response.status_code == 200
    data = response.json()
    assert data["error"] is None
    assert data["columns"] == ["Count"]
    assert data["rows"][0]["Count"] == 6


def test_free_query_has_no_correct_or_message_fields(client):
    response = client.post("/api/query", json={"query": "DeviceProcessEvents | take 1"})
    data = response.json()
    assert "correct" not in data
    assert "message" not in data


def test_free_query_syntax_error_returns_error_field(client):
    response = client.post("/api/query", json={"query": "DeviceProcessEvents | bogusop 1"})
    assert response.status_code == 200
    data = response.json()
    assert data["error"] is not None
    assert data["rows"] == []


def test_join_scenario_end_to_end(client):
    response = client.post(
        "/api/scenarios/007_lateral_movement_join/run",
        json={
            "query": (
                "DeviceProcessEvents | join kind=inner "
                "(DeviceLogonEvents | where LogonType == 'RemoteInteractive') on DeviceName, AccountName "
                "| summarize ProcessCount = count() by DeviceName"
            )
        },
    )
    data = response.json()
    assert data["correct"] is True
    # WIN-SRV02/administrator is the only DeviceName+AccountName pair with a
    # RemoteInteractive logon, so this counts every DeviceProcessEvents row
    # for that pair - benign rows plus the PsExec and ransomware-chain
    # anomalies (see device_process_events.py's _RANSOMWARE_CHAIN).
    assert data["rows"] == [{"DeviceName": "WIN-SRV02", "ProcessCount": 12}]


def test_list_lessons_returns_all_summaries(client):
    response = client.get("/api/lessons")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 16
    assert {"id", "title"} <= data[0].keys()
    assert data[0]["id"] == "where"


def test_get_lesson_detail_returns_full_shape(client):
    response = client.get("/api/lessons/summarize")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "summarize"
    assert "summarize" in data["example_query"]
    assert data["description"]
    assert data["example_explanation"]


def test_get_lesson_detail_unknown_id_is_404(client):
    response = client.get("/api/lessons/does_not_exist")
    assert response.status_code == 404


def test_list_incidents_returns_all_summaries(client):
    response = client.get("/api/incidents")
    assert response.status_code == 200
    data = response.json()
    first = next(i for i in data if i["id"] == "01_prinz_eugen_ransomware")
    assert first["step_count"] == 8


def test_get_incident_detail_returns_ordered_resolved_steps(client):
    response = client.get("/api/incidents/01_prinz_eugen_ransomware")
    assert response.status_code == 200
    data = response.json()
    assert len(data["steps"]) == 8
    assert [s["step_number"] for s in data["steps"]] == list(range(1, 9))
    assert [s["kind"] for s in data["steps"]] == [
        "investigation",
        "investigation",
        "action",
        "investigation",
        "investigation",
        "action",
        "investigation",
        "action",
    ]
    assert data["steps"][0]["scenario_id"] == "014_backdoor_admin_account"
    assert data["steps"][0]["scenario_title"]
    assert data["steps"][0]["difficulty"]
    assert data["steps"][0]["narrative"]


def test_get_incident_detail_unknown_id_is_404(client):
    response = client.get("/api/incidents/does_not_exist")
    assert response.status_code == 404


def test_get_incident_step_detail_returns_merged_scenario_and_incident_shape(client):
    response = client.get("/api/incidents/01_prinz_eugen_ransomware/steps/1")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "014_backdoor_admin_account"
    assert data["incident"]["step_number"] == 1
    assert data["incident"]["step_count"] == 8
    assert data["incident"]["prev_step"] is None
    assert data["incident"]["next_step"] == 2


def test_get_incident_step_detail_action_step_shape(client):
    response = client.get("/api/incidents/01_prinz_eugen_ransomware/steps/3")
    assert response.status_code == 200
    data = response.json()
    assert data["kind"] == "action"
    assert data["title"] == "Natychmiastowa izolacja hosta"
    assert len(data["actions"]) == 3
    assert data["incident"]["prev_step"] == 2
    assert data["incident"]["next_step"] == 4


def test_get_incident_step_detail_last_step_has_no_next(client):
    response = client.get("/api/incidents/01_prinz_eugen_ransomware/steps/8")
    assert response.status_code == 200
    data = response.json()
    assert data["kind"] == "action"
    assert data["title"] == "Zamknięcie incydentu"
    assert data["incident"]["prev_step"] == 7
    assert data["incident"]["next_step"] is None


def test_get_incident_step_detail_out_of_range_is_404(client):
    response = client.get("/api/incidents/01_prinz_eugen_ransomware/steps/99")
    assert response.status_code == 404


def test_get_incident_step_detail_unknown_incident_is_404(client):
    response = client.get("/api/incidents/does_not_exist/steps/1")
    assert response.status_code == 404


def test_list_incidents_includes_all_incidents(client):
    response = client.get("/api/incidents")
    data = response.json()
    assert len(data) == 10
    ids = {i["id"] for i in data}
    assert ids == {
        "01_prinz_eugen_ransomware",
        "02_devicecode_phishing_and_containment",
        "03_gotoresolve_rmm_abuse",
        "04_clickfix_blocked_attempt",
        "05_fake_invoice_c2_beacon",
        "06_lummac2_infostealer",
        "07_ta569_driveby_blocked",
        "08_theatercraft_malvertising",
        "09_meta_2fa_relay_phishing",
        "10_ad_kerberoasting_dcsync",
    }


def test_second_incident_overview_mixes_step_kinds(client):
    response = client.get("/api/incidents/02_devicecode_phishing_and_containment")
    assert response.status_code == 200
    data = response.json()
    kinds = [s["kind"] for s in data["steps"]]
    assert kinds == ["investigation", "investigation", "action", "investigation", "action"]
    action_step = data["steps"][2]
    assert action_step["title"] == "Natychmiastowe powstrzymanie"
    assert len(action_step["actions"]) == 3
    assert action_step["scenario_id"] is None


def test_incident_action_step_detail_has_no_scenario_fields(client):
    response = client.get("/api/incidents/02_devicecode_phishing_and_containment/steps/3")
    assert response.status_code == 200
    data = response.json()
    assert data["kind"] == "action"
    assert data["title"] == "Natychmiastowe powstrzymanie"
    assert len(data["actions"]) == 3
    assert "prompt" not in data
    assert "scenario_id" not in data
    assert data["incident"]["step_number"] == 3
    assert data["incident"]["prev_step"] == 2
    assert data["incident"]["next_step"] == 4


def test_incident_investigation_step_detail_has_kind_investigation(client):
    response = client.get("/api/incidents/02_devicecode_phishing_and_containment/steps/1")
    assert response.status_code == 200
    data = response.json()
    assert data["kind"] == "investigation"
    assert data["id"] == "019_devicecode_phishing_email"


def test_second_incident_investigation_steps_still_grade_correctly(client):
    for step_number, scenario_id in [(1, "019_devicecode_phishing_email"), (2, "020_device_code_registration_signin")]:
        step = client.get(f"/api/incidents/02_devicecode_phishing_and_containment/steps/{step_number}").json()
        assert step["id"] == scenario_id
        # No reference_query is exposed via the API directly, so pull it from
        # the solution endpoint the same way a trainee revealing it would.
        solution = client.get(f"/api/scenarios/{scenario_id}/solution").json()
        response = client.post(f"/api/scenarios/{scenario_id}/run", json={"query": solution["reference_query"]})
        assert response.json()["correct"] is True


def _assert_grades_correct(client, scenario_id):
    solution = client.get(f"/api/scenarios/{scenario_id}/solution").json()
    response = client.post(f"/api/scenarios/{scenario_id}/run", json={"query": solution["reference_query"]})
    assert response.json()["correct"] is True


def test_third_incident_investigation_steps_still_grade_correctly(client):
    for step_number, scenario_id in [
        (1, "021_gotoresolve_vbs_dropper"),
        (2, "022_gotoresolve_companyid_pivot"),
    ]:
        step = client.get(f"/api/incidents/03_gotoresolve_rmm_abuse/steps/{step_number}").json()
        assert step["id"] == scenario_id
        _assert_grades_correct(client, scenario_id)

    kinds = [s["kind"] for s in client.get("/api/incidents/03_gotoresolve_rmm_abuse").json()["steps"]]
    assert kinds == ["investigation", "investigation", "action", "action"]


def test_fourth_incident_investigation_step_still_grades_correctly(client):
    step = client.get("/api/incidents/04_clickfix_blocked_attempt/steps/1").json()
    assert step["id"] == "023_clickfix_blocked_powershell"
    _assert_grades_correct(client, "023_clickfix_blocked_powershell")

    kinds = [s["kind"] for s in client.get("/api/incidents/04_clickfix_blocked_attempt").json()["steps"]]
    assert kinds == ["investigation", "action", "action"]


def test_fifth_incident_reuses_existing_scenario_and_grades_correctly(client):
    step = client.get("/api/incidents/05_fake_invoice_c2_beacon/steps/1").json()
    assert step["id"] == "012_fake_invoice_installer_beacon"
    _assert_grades_correct(client, "012_fake_invoice_installer_beacon")

    kinds = [s["kind"] for s in client.get("/api/incidents/05_fake_invoice_c2_beacon").json()["steps"]]
    assert kinds == ["investigation", "action", "action"]


def test_sixth_incident_investigation_steps_still_grade_correctly(client):
    for step_number, scenario_id in [
        (1, "024_lummac2_clickfix_mshta"),
        (2, "025_lummac2_staging_payload"),
    ]:
        step = client.get(f"/api/incidents/06_lummac2_infostealer/steps/{step_number}").json()
        assert step["id"] == scenario_id
        _assert_grades_correct(client, scenario_id)

    kinds = [s["kind"] for s in client.get("/api/incidents/06_lummac2_infostealer").json()["steps"]]
    assert kinds == ["investigation", "investigation", "action", "action"]


def test_seventh_incident_investigation_step_still_grades_correctly(client):
    step = client.get("/api/incidents/07_ta569_driveby_blocked/steps/1").json()
    assert step["id"] == "026_ta569_driveby_c2_beacon"
    _assert_grades_correct(client, "026_ta569_driveby_c2_beacon")

    kinds = [s["kind"] for s in client.get("/api/incidents/07_ta569_driveby_blocked").json()["steps"]]
    assert kinds == ["investigation", "action", "action"]


def test_eighth_incident_investigation_steps_still_grade_correctly(client):
    for step_number, scenario_id in [
        (1, "027_theatercraft_hta_loader"),
        (2, "028_theatercraft_dga_beacon"),
    ]:
        step = client.get(f"/api/incidents/08_theatercraft_malvertising/steps/{step_number}").json()
        assert step["id"] == scenario_id
        _assert_grades_correct(client, scenario_id)

    kinds = [s["kind"] for s in client.get("/api/incidents/08_theatercraft_malvertising").json()["steps"]]
    assert kinds == ["investigation", "investigation", "action", "action"]


def test_ninth_incident_investigation_steps_still_grade_correctly(client):
    for step_number, scenario_id in [
        (1, "029_meta_trademark_phishing_email"),
        (2, "030_meta_phishing_signin_anomaly"),
    ]:
        step = client.get(f"/api/incidents/09_meta_2fa_relay_phishing/steps/{step_number}").json()
        assert step["id"] == scenario_id
        _assert_grades_correct(client, scenario_id)

    kinds = [s["kind"] for s in client.get("/api/incidents/09_meta_2fa_relay_phishing").json()["steps"]]
    assert kinds == ["investigation", "investigation", "action", "action"]


def test_tenth_incident_investigation_steps_still_grade_correctly(client):
    for step_number, scenario_id in [
        (1, "031_kerberoasting_spn_recon"),
        (2, "032_kerberoasting_ticket_burst"),
        (4, "033_dcsync_non_dc_replication"),
    ]:
        step = client.get(f"/api/incidents/10_ad_kerberoasting_dcsync/steps/{step_number}").json()
        assert step["id"] == scenario_id
        _assert_grades_correct(client, scenario_id)

    kinds = [s["kind"] for s in client.get("/api/incidents/10_ad_kerberoasting_dcsync").json()["steps"]]
    assert kinds == ["investigation", "investigation", "action", "investigation", "action"]
