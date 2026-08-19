"""Synthetic dataset mimicking a simplified Microsoft 365 unified audit log
`OfficeActivity` table: routine Exchange/SharePoint activity plus a hidden
inbox-forwarding rule created on the already-compromised account (see
`signin_logs.py`'s password-spray/impossible-travel anomaly) - classic BEC
persistence.

Generation is fully deterministic (no `random` module involved), matching the
convention in `device_process_events.py`/`device_logon_events.py`.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from core.kql_engine.ast_nodes import KqlType

from .schema import ColumnSchema, TableSchema

SCHEMA = TableSchema(
    name="OfficeActivity",
    columns=[
        ColumnSchema("TimeGenerated", KqlType.DATETIME, "Czas zdarzenia (UTC)."),
        ColumnSchema("UserId", KqlType.STRING, "UPN konta, które wykonało operację."),
        ColumnSchema(
            "Operation",
            KqlType.STRING,
            "Np. 'MailItemsAccessed', 'FileAccessed', 'New-InboxRule', 'FileDownloaded'.",
        ),
        ColumnSchema("OfficeWorkload", KqlType.STRING, "'Exchange' lub 'SharePoint'."),
        ColumnSchema("ClientIP", KqlType.STRING, "Adres IP źródłowy żądania."),
        ColumnSchema("ResultStatus", KqlType.STRING, "'Succeeded' lub 'Failed'."),
    ],
)

_BASE_TIME = datetime(2026, 8, 10, 8, 0, 0, tzinfo=timezone.utc)
_UPNS = [
    "jkowalski@contoso.com",
    "anowak@contoso.com",
    "mwisniewski@contoso.com",
    "asystem@contoso.com",
]
_OPERATIONS: list[tuple[str, str]] = [
    ("MailItemsAccessed", "Exchange"),
    ("FileAccessed", "SharePoint"),
    ("FileDownloaded", "SharePoint"),
    ("MailItemsAccessed", "Exchange"),
]

# Continues the cloud-account-compromise thread from signin_logs.py's
# password-spray/impossible-travel anomaly - same account, same suspicious
# IP, a few minutes after the successful sign-in there.
_ANOMALIES: list[dict[str, Any]] = [
    {
        "TimeGenerated": _BASE_TIME + timedelta(hours=2, minutes=35),
        "UserId": "anowak@contoso.com",
        "Operation": "New-InboxRule",
        "OfficeWorkload": "Exchange",
        "ClientIP": "185.220.101.5",
        "ResultStatus": "Succeeded",
    },
]


def _benign_rows(count: int) -> list[dict[str, Any]]:
    rows = []
    for i in range(count):
        upn = _UPNS[i % len(_UPNS)]
        operation, workload = _OPERATIONS[i % len(_OPERATIONS)]
        rows.append(
            {
                "TimeGenerated": _BASE_TIME + timedelta(minutes=i * 8),
                "UserId": upn,
                "Operation": operation,
                "OfficeWorkload": workload,
                "ClientIP": "10.20.0." + str(10 + i % 40),
                "ResultStatus": "Succeeded",
            }
        )
    return rows


def _build_rows() -> list[dict[str, Any]]:
    rows = _benign_rows(60) + _ANOMALIES
    rows.sort(key=lambda r: r["TimeGenerated"])
    return rows


ROWS: list[dict[str, Any]] = _build_rows()
