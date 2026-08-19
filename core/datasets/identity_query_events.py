"""Synthetic dataset mimicking a simplified Microsoft Defender for Identity
`IdentityQueryEvents` table: LDAP/SAMR directory queries against on-prem
Active Directory, plus one deliberately injected reconnaissance anomaly
(SPN enumeration - the recon step of a Kerberoasting attack).

Generation is fully deterministic (no `random` module involved), matching the
convention in `device_process_events.py`/`device_logon_events.py`.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from core.kql_engine.ast_nodes import KqlType

from .schema import ColumnSchema, TableSchema

SCHEMA = TableSchema(
    name="IdentityQueryEvents",
    columns=[
        ColumnSchema("Timestamp", KqlType.DATETIME, "Czas zapytania do katalogu (UTC)."),
        ColumnSchema("AccountName", KqlType.STRING, "Konto, które wykonało zapytanie."),
        ColumnSchema("DeviceName", KqlType.STRING, "Urządzenie źródłowe, z którego wysłano zapytanie."),
        ColumnSchema("Protocol", KqlType.STRING, "'LDAP' lub 'SAMR'."),
        ColumnSchema("Query", KqlType.STRING, "Treść zapytania/filtra."),
        ColumnSchema("ActionType", KqlType.STRING, "Np. 'LDAP query', 'SAM Name lookup'."),
    ],
)

_BASE_TIME = datetime(2026, 8, 10, 8, 0, 0, tzinfo=timezone.utc)
_ACCOUNTS = ["jkowalski", "anowak", "mwisniewski", "asystem"]

# T1087.002 - LDAP query enumerating every account with a Service Principal
# Name set - the classic recon step before Kerberoasting. A regular helpdesk
# account has no legitimate reason to run this query.
_ANOMALIES: list[dict[str, Any]] = [
    {
        "Timestamp": _BASE_TIME + timedelta(hours=19),
        "AccountName": "hkrawczyk",
        "DeviceName": "WIN-CLIENT10",
        "Protocol": "LDAP",
        "Query": "(&(objectClass=user)(servicePrincipalName=*))",
        "ActionType": "LDAP query",
    },
]


def _benign_rows(count: int) -> list[dict[str, Any]]:
    rows = []
    for i in range(count):
        account = _ACCOUNTS[i % len(_ACCOUNTS)]
        rows.append(
            {
                "Timestamp": _BASE_TIME + timedelta(minutes=i * 6),
                "AccountName": account,
                "DeviceName": "WIN-CLIENT0" + str(1 + i % 3),
                "Protocol": "LDAP",
                "Query": f"(sAMAccountName={account})",
                "ActionType": "SAM Name lookup",
            }
        )
    return rows


def _build_rows() -> list[dict[str, Any]]:
    rows = _benign_rows(50) + _ANOMALIES
    rows.sort(key=lambda r: r["Timestamp"])
    return rows


ROWS: list[dict[str, Any]] = _build_rows()
