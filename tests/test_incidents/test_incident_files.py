"""Safety net for the on-disk incident files: every step's scenario_id must
resolve to a real scenario. Catches a typo'd or renamed scenario id
immediately instead of a trainee hitting a 404 mid-walkthrough."""
from core.incidents import load_all_incidents
from core.scenarios import load_all_scenarios


def test_every_incident_step_scenario_id_resolves_to_a_real_scenario():
    known_ids = {s.id for s in load_all_scenarios()}
    for incident in load_all_incidents():
        for step in incident.steps:
            if step.kind != "investigation":
                continue
            assert step.scenario_id in known_ids, (
                f"{incident.id}: step scenario_id '{step.scenario_id}' does not match any scenario"
            )
