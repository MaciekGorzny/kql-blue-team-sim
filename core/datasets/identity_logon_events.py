"""Synthetic dataset mimicking a simplified Microsoft Defender for Identity
`IdentityLogonEvents` table: Kerberos/NTLM authentications against on-prem
Active Directory, plus a deliberately injected Kerberoasting anomaly - a
burst of Kerberos service-ticket (TGS) requests for many distinct service
accounts from the same source account/device in a short window.

Generation is fully deterministic (no `random` module involved), matching the
convention in `device_process_events.py`/`device_logon_events.py`.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from core.kql_engine.ast_nodes import KqlType

from .schema import ColumnSchema, TableSchema

SCHEMA = TableSchema(
    name="IdentityLogonEvents",
    columns=[
        ColumnSchema("Timestamp", KqlType.DATETIME, "Czas zdarzenia logowania (UTC)."),
        ColumnSchema("AccountName", KqlType.STRING, "Konto uwierzytelniające się."),
        ColumnSchema("DeviceName", KqlType.STRING, "Urządzenie źródłowe (klient)."),
        ColumnSchema("TargetDeviceName", KqlType.STRING, "Serwer/zasób docelowy (np. kontroler domeny)."),
        ColumnSchema(
            "TargetAccountName",
            KqlType.STRING,
            "Dla żądań biletu Kerberos (TGS) - konto usługi, którego bilet zażądano. Puste dla zwykłych logowań.",
        ),
        ColumnSchema("Protocol", KqlType.STRING, "'Kerberos' lub 'NTLM'."),
        ColumnSchema("ActionType", KqlType.STRING, "'LogonSuccess' lub 'LogonFailed'."),
        ColumnSchema("FailureReason", KqlType.STRING, "Puste przy sukcesie, inaczej np. 'BadPassword'."),
    ],
)

_BASE_TIME = datetime(2026, 8, 10, 8, 0, 0, tzinfo=timezone.utc)
_ACCOUNTS = ["jkowalski", "anowak", "mwisniewski", "asystem"]
_DEVICES = ["WIN-CLIENT01", "WIN-CLIENT02", "WIN-CLIENT03"]

# T1558.003 (Kerberoasting) - hkrawczyk requests TGS tickets for six distinct
# service accounts within minutes, straight after the SPN-enumeration
# reconnaissance anomaly in identity_query_events.py. Real Kerberoasting
# cracks the tickets offline afterwards (not modeled here - out of scope for
# log-based hunting).
_KERBEROASTING_BURST: list[dict[str, Any]] = [
    {
        "Timestamp": _BASE_TIME + timedelta(hours=19, minutes=5, seconds=i * 20),
        "AccountName": "hkrawczyk",
        "DeviceName": "WIN-CLIENT10",
        "TargetDeviceName": "DC01",
        "TargetAccountName": target,
        "Protocol": "Kerberos",
        "ActionType": "LogonSuccess",
        "FailureReason": "",
    }
    for i, target in enumerate(
        ["svc-sql", "svc-backup", "svc-web", "svc-print", "svc-exchange", "svc-reporting"]
    )
]

_ANOMALIES = _KERBEROASTING_BURST


def _benign_rows(count: int) -> list[dict[str, Any]]:
    rows = []
    for i in range(count):
        account = _ACCOUNTS[i % len(_ACCOUNTS)]
        device = _DEVICES[i % len(_DEVICES)]
        protocol = "Kerberos" if i % 2 == 0 else "NTLM"
        rows.append(
            {
                "Timestamp": _BASE_TIME + timedelta(minutes=i * 7),
                "AccountName": account,
                "DeviceName": device,
                "TargetDeviceName": "DC01",
                "TargetAccountName": "",
                "Protocol": protocol,
                "ActionType": "LogonSuccess",
                "FailureReason": "",
            }
        )
    return rows


def _build_rows() -> list[dict[str, Any]]:
    rows = _benign_rows(70) + _ANOMALIES
    rows.sort(key=lambda r: r["Timestamp"])
    return rows


ROWS: list[dict[str, Any]] = _build_rows()
