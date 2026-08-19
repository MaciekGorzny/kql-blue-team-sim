"""Small runnable example - not part of the test suite. Shows the full
scenario training flow: prompt -> wrong attempt -> feedback -> correct
attempt -> feedback.

Run from the repo root with:  python -m examples.run_scenario_demo
"""
from __future__ import annotations

from core.scenarios import load_all_scenarios, validate

if __name__ == "__main__":
    scenario = next(s for s in load_all_scenarios() if s.id == "002_encoded_powershell")

    print(f"=== {scenario.title} ({scenario.difficulty.value}) ===")
    print(scenario.prompt)
    if scenario.mitre_techniques:
        print("MITRE ATT&CK:", ", ".join(scenario.mitre_techniques))
    print()

    wrong_query = "DeviceProcessEvents | where FileName == 'powershell.exe' and CommandLine has '-enc'"
    print("Próba 1 (błędna nazwa kolumny):")
    print(" ", wrong_query)
    result = validate(scenario, wrong_query)
    print(" ->", "OK" if result.correct else "BŁĄD:", result.message)
    print()

    correct_query = (
        "DeviceProcessEvents | where FileName == 'powershell.exe' and ProcessCommandLine contains '-enc' "
        "| project DeviceName, AccountName, ProcessCommandLine"
    )
    print("Próba 2:")
    print(" ", correct_query)
    result = validate(scenario, correct_query)
    print(" ->", "OK:" if result.correct else "BŁĄD:", result.message)
    if result.correct:
        for row in result.user_result:
            print("   ", row)
