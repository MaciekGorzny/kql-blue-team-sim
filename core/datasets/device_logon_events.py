"""Synthetic dataset mimicking a simplified Microsoft Defender for Endpoint
`DeviceLogonEvents` table. Exists mainly to be `join`-ed against
`DeviceProcessEvents` in scenarios (e.g. lateral movement: process activity
on a host shortly after a remote interactive logon).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from core.kql_engine.ast_nodes import KqlType

from .schema import ColumnSchema, TableSchema

SCHEMA = TableSchema(
    name="DeviceLogonEvents",
    columns=[
        ColumnSchema("Timestamp", KqlType.DATETIME, "Czas zdarzenia logowania (UTC)."),
        ColumnSchema("DeviceName", KqlType.STRING, "Nazwa hosta."),
        ColumnSchema("ActionType", KqlType.STRING, "'LogonSuccess' lub 'LogonFailed'."),
        ColumnSchema(
            "LogonType", KqlType.STRING, "Np. 'Interactive', 'RemoteInteractive', 'Network', 'Service'."
        ),
        ColumnSchema("AccountName", KqlType.STRING, "Konto, które się logowało."),
        ColumnSchema("RemoteIP", KqlType.STRING, "Adres IP źródłowy dla logowań zdalnych, '-' dla lokalnych."),
        ColumnSchema("IsLocalAdmin", KqlType.BOOL, "Czy konto ma lokalne uprawnienia administratora."),
    ],
)

_BASE_TIME = datetime(2026, 8, 10, 8, 0, 0, tzinfo=timezone.utc)
_DEVICES = ["WIN-CLIENT01", "WIN-CLIENT02", "WIN-CLIENT03", "WIN-SRV01", "WIN-SRV02"]
_ACCOUNTS = ["jkowalski", "anowak", "mwisniewski", "asystem", "administrator"]

# T1021.002 / T1570: a remote interactive logon onto WIN-SRV02 by
# 'administrator' shortly before the PsExec anomaly in device_process_events.py.
_ANOMALIES: list[dict[str, Any]] = [
    {
        "Timestamp": _BASE_TIME + timedelta(hours=5, minutes=55),
        "DeviceName": "WIN-SRV02",
        "ActionType": "LogonSuccess",
        "LogonType": "RemoteInteractive",
        "AccountName": "administrator",
        "RemoteIP": "185.220.101.5",
        "IsLocalAdmin": True,
    },
]


def _benign_rows(count: int) -> list[dict[str, Any]]:
    rows = []
    for i in range(count):
        device = _DEVICES[i % len(_DEVICES)]
        account = _ACCOUNTS[(i // len(_DEVICES)) % len(_ACCOUNTS)]
        rows.append(
            {
                "Timestamp": _BASE_TIME + timedelta(minutes=i * 11),
                "DeviceName": device,
                "ActionType": "LogonSuccess",
                "LogonType": "Interactive",
                "AccountName": account,
                "RemoteIP": "-",
                "IsLocalAdmin": account == "administrator",
            }
        )
    return rows


def _build_rows() -> list[dict[str, Any]]:
    rows = _benign_rows(40) + _ANOMALIES
    rows.sort(key=lambda r: r["Timestamp"])
    return rows


ROWS: list[dict[str, Any]] = _build_rows()
