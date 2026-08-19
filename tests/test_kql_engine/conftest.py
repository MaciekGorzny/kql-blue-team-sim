"""Shared pytest fixtures: minimal in-memory tables mimicking a Sentinel/
Defender schema, used across engine tests."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest


@pytest.fixture
def process_events() -> list[dict]:
    now = datetime(2026, 8, 17, 12, 0, 0, tzinfo=timezone.utc)
    return [
        {
            "TimeGenerated": now - timedelta(minutes=5),
            "DeviceName": "WIN-CLIENT01",
            "FileName": "cmd.exe",
            "CommandLine": "cmd.exe /c whoami",
            "AccountName": "jkowalski",
            "ProcessId": 4321,
        },
        {
            "TimeGenerated": now - timedelta(minutes=3),
            "DeviceName": "WIN-CLIENT01",
            "FileName": "powershell.exe",
            "CommandLine": "powershell.exe -enc SGVsbG8=",
            "AccountName": "jkowalski",
            "ProcessId": 4355,
        },
        {
            "TimeGenerated": now - timedelta(minutes=1),
            "DeviceName": "WIN-SRV02",
            "FileName": "notepad.exe",
            "CommandLine": "notepad.exe C:\\report.txt",
            "AccountName": "asystem",
            "ProcessId": 5510,
        },
    ]


@pytest.fixture
def logon_events() -> list[dict]:
    # Deliberately has no entry for WIN-SRV02, to exercise leftouter join
    # null-padding in join tests.
    return [
        {"DeviceName": "WIN-CLIENT01", "AccountName": "jkowalski", "LogonType": "Interactive"},
    ]


@pytest.fixture
def tables(process_events: list[dict], logon_events: list[dict]) -> dict[str, list[dict]]:
    return {"DeviceProcessEvents": process_events, "DeviceLogonEvents": logon_events}
