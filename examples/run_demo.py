"""Small runnable example - not part of the test suite. Shows the engine
working end-to-end without needing to know pytest.

Run from the repo root with:  python -m examples.run_demo
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from core.kql_engine import run_query

_NOW = datetime(2026, 8, 17, 12, 0, 0, tzinfo=timezone.utc)

DEVICE_PROCESS_EVENTS = [
    {
        "TimeGenerated": _NOW - timedelta(minutes=5),
        "DeviceName": "WIN-CLIENT01",
        "FileName": "cmd.exe",
        "CommandLine": "cmd.exe /c whoami",
        "AccountName": "jkowalski",
        "ProcessId": 4321,
    },
    {
        "TimeGenerated": _NOW - timedelta(minutes=3),
        "DeviceName": "WIN-CLIENT01",
        "FileName": "powershell.exe",
        "CommandLine": "powershell.exe -enc SGVsbG8=",
        "AccountName": "jkowalski",
        "ProcessId": 4355,
    },
    {
        "TimeGenerated": _NOW - timedelta(minutes=1),
        "DeviceName": "WIN-SRV02",
        "FileName": "notepad.exe",
        "CommandLine": "notepad.exe C:\\report.txt",
        "AccountName": "asystem",
        "ProcessId": 5510,
    },
]

TABLES = {"DeviceProcessEvents": DEVICE_PROCESS_EVENTS}

QUERY = (
    "DeviceProcessEvents "
    "| where FileName == 'powershell.exe' and CommandLine contains '-enc' "
    "| project DeviceName, AccountName, CommandLine"
)


if __name__ == "__main__":
    print("Zapytanie:")
    print(" ", QUERY)
    print()
    print("Wynik:")
    for row in run_query(QUERY, TABLES):
        print(" ", row)
