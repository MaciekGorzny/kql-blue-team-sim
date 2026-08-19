"""Synthetic dataset mimicking a simplified Microsoft Defender for Identity
`IdentityDirectoryEvents` table: Active Directory administrative/replication
events, plus a deliberately injected DCSync anomaly - a directory
replication request originating from a device that is not a real domain
controller.

Generation is fully deterministic (no `random` module involved), matching the
convention in `device_process_events.py`/`device_logon_events.py`.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from core.kql_engine.ast_nodes import KqlType

from .schema import ColumnSchema, TableSchema

SCHEMA = TableSchema(
    name="IdentityDirectoryEvents",
    columns=[
        ColumnSchema("Timestamp", KqlType.DATETIME, "Czas zdarzenia w katalogu (UTC)."),
        ColumnSchema("AccountName", KqlType.STRING, "Konto, które wykonało akcję."),
        ColumnSchema("TargetAccountDisplayName", KqlType.STRING, "Konto/obiekt, którego akcja dotyczyła."),
        ColumnSchema("DeviceName", KqlType.STRING, "Urządzenie źródłowe akcji."),
        ColumnSchema(
            "ActionType",
            KqlType.STRING,
            "Np. 'Directory Services replication', 'Group Membership Changed', 'User Account Created'.",
        ),
        ColumnSchema("Application", KqlType.STRING, "Zwykle 'Active Directory'."),
    ],
)

_BASE_TIME = datetime(2026, 8, 10, 8, 0, 0, tzinfo=timezone.utc)

# T1003.006 (DCSync) - a directory-replication request from WIN-CLIENT10, not
# from a real domain controller. Legitimate replication only ever originates
# from DC01 (or another DC) - a workstation issuing this request is a
# definitive compromise indicator, not just a suspicious pattern.
_ANOMALIES: list[dict[str, Any]] = [
    {
        "Timestamp": _BASE_TIME + timedelta(hours=19, minutes=20),
        "AccountName": "hkrawczyk",
        "TargetAccountDisplayName": "krbtgt",
        "DeviceName": "WIN-CLIENT10",
        "ActionType": "Directory Services replication",
        "Application": "Active Directory",
    },
]


def _benign_rows(count: int) -> list[dict[str, Any]]:
    action_types = ["Group Membership Changed", "User Account Created", "Password Reset"]
    rows = []
    for i in range(count):
        rows.append(
            {
                "Timestamp": _BASE_TIME + timedelta(minutes=i * 14),
                "AccountName": "asystem",
                "TargetAccountDisplayName": f"user{i:02d}",
                "DeviceName": "DC01",
                "ActionType": action_types[i % len(action_types)],
                "Application": "Active Directory",
            }
        )
    return rows


def _legitimate_replication() -> list[dict[str, Any]]:
    # Real inter-DC replication, always from DC01 - the contrast that makes
    # `DeviceName != 'DC01'` a meaningful filter rather than a redundant one.
    return [
        {
            "Timestamp": _BASE_TIME + timedelta(hours=i * 6),
            "AccountName": "DC01$",
            "TargetAccountDisplayName": "(all domain objects)",
            "DeviceName": "DC01",
            "ActionType": "Directory Services replication",
            "Application": "Active Directory",
        }
        for i in range(4)
    ]


def _build_rows() -> list[dict[str, Any]]:
    rows = _benign_rows(30) + _legitimate_replication() + _ANOMALIES
    rows.sort(key=lambda r: r["Timestamp"])
    return rows


ROWS: list[dict[str, Any]] = _build_rows()
