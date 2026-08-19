"""Synthetic dataset mimicking a simplified Microsoft Entra ID (Azure AD)
`SigninLogs` table: routine cloud sign-ins plus two distinct anomalies - a
password-spray-style burst of failures followed by a suspicious success, and
a separate AiTM-style token-replay sign-in from an unusual location - for
scenarios to detect.

Deliberate simplification: in the real table, `Location` is just a 2-letter
country code, and city-level detail lives in a separate `LocationDetails`
column (`dynamic`, not modeled here - this engine keeps rows flat). Here
`Location` holds a "City, Country" string instead, since city-level color
("Amsterdam, NL" vs. just "NL") makes scenario narratives much more concrete
without changing the querying experience for the columns this app does model.

Generation is fully deterministic (no `random` module involved), matching the
convention in `device_process_events.py`/`device_logon_events.py`.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from core.kql_engine.ast_nodes import KqlType

from .schema import ColumnSchema, TableSchema

SCHEMA = TableSchema(
    name="SigninLogs",
    columns=[
        ColumnSchema("TimeGenerated", KqlType.DATETIME, "Czas zdarzenia logowania (UTC)."),
        ColumnSchema("UserPrincipalName", KqlType.STRING, "UPN konta w Entra ID."),
        ColumnSchema("IPAddress", KqlType.STRING, "Adres IP źródłowy żądania logowania."),
        ColumnSchema("Location", KqlType.STRING, "Lokalizacja geo (miasto, kraj) na podstawie IP."),
        ColumnSchema("AppDisplayName", KqlType.STRING, "Aplikacja, do której nastąpiło logowanie."),
        ColumnSchema(
            "ResultType", KqlType.STRING, "Kod wyniku logowania - '0' oznacza sukces, inne kody to błędy."
        ),
        ColumnSchema("ResultDescription", KqlType.STRING, "Opis wyniku logowania."),
        ColumnSchema("ConditionalAccessStatus", KqlType.STRING, "'success', 'failure' lub 'notApplied'."),
    ],
)

_BASE_TIME = datetime(2026, 8, 10, 8, 0, 0, tzinfo=timezone.utc)
_UPNS = [
    "jkowalski@contoso.com",
    "anowak@contoso.com",
    "mwisniewski@contoso.com",
    "asystem@contoso.com",
    "administrator@contoso.com",
]
_APPS = ["Office 365 Exchange Online", "Microsoft Teams", "SharePoint Online", "OneDrive SyncEngine"]

def _password_spray_burst() -> list[dict[str, Any]]:
    # Reuses the same C2 IP already seen in device_process_events.py's
    # anomalous command lines (and device_network_events.py's outbound
    # connections) - the attacker tries the stolen credentials against the
    # cloud tenant too, shortly after the on-prem encoded-PowerShell anomaly
    # for the same account.
    rows = []
    start = _BASE_TIME + timedelta(hours=2, minutes=30)
    for i in range(6):
        rows.append(
            {
                "TimeGenerated": start + timedelta(seconds=i * 20),
                "UserPrincipalName": "anowak@contoso.com",
                "IPAddress": "185.220.101.5",
                "Location": "Kyiv, UA",
                "AppDisplayName": "Office 365 Exchange Online",
                "ResultType": "50126",
                "ResultDescription": "Error validating credentials due to invalid username or password.",
                "ConditionalAccessStatus": "notApplied",
            }
        )
    rows.append(
        {
            "TimeGenerated": start + timedelta(seconds=140),
            "UserPrincipalName": "anowak@contoso.com",
            "IPAddress": "185.220.101.5",
            "Location": "Kyiv, UA",
            "AppDisplayName": "Office 365 Exchange Online",
            "ResultType": "0",
            "ResultDescription": "Success",
            "ConditionalAccessStatus": "success",
        }
    )
    return rows


def _aitm_token_replay() -> list[dict[str, Any]]:
    # T1550.001: a stolen session token (AiTM proxy / cookie theft) reused
    # from Amsterdam minutes after jkowalski's own legitimate Warsaw sign-in -
    # ResultType "0"/ConditionalAccessStatus "success" throughout, since the
    # replayed token already carries a satisfied MFA claim.
    return [
        {
            "TimeGenerated": _BASE_TIME + timedelta(hours=3, minutes=12),
            "UserPrincipalName": "jkowalski@contoso.com",
            "IPAddress": "45.83.64.12",
            "Location": "Amsterdam, NL",
            "AppDisplayName": "Office 365 Exchange Online",
            "ResultType": "0",
            "ResultDescription": "Success",
            "ConditionalAccessStatus": "success",
        }
    ]


def _device_code_registration() -> list[dict[str, Any]]:
    # T1528/T1098.005: mwisniewski completes a device-code phishing flow
    # (see email_events.py's "dokończ logowanie kodem" lure, ~15 min
    # earlier) - the attacker relays the code and registers their own
    # session/device. AppDisplayName is the real Entra broker app name seen
    # in device-code flows, distinct from every app in _APPS, so it's a
    # clean pivot on its own (no need to filter by location/account).
    # Same attacker geography as _aitm_token_replay's Amsterdam IP.
    return [
        {
            "TimeGenerated": _BASE_TIME + timedelta(hours=4, minutes=15),
            "UserPrincipalName": "mwisniewski@contoso.com",
            "IPAddress": "45.83.64.19",
            "Location": "Amsterdam, NL",
            "AppDisplayName": "Microsoft Authentication Broker",
            "ResultType": "0",
            "ResultDescription": "Success",
            "ConditionalAccessStatus": "success",
        }
    ]


def _meta_phishing_relay_signin() -> list[dict[str, Any]]:
    # T1566.002/T1078.004: THREAT-023-style brand-impersonation phishing -
    # credentials and a real-time-relayed MFA code let the attacker sign in
    # as the shared mailbox account, ~20 min after the phishing email in
    # email_events.py. ResultType "0"/success, since the relayed code
    # already carries a satisfied MFA claim (same shape as _aitm_token_replay).
    return [
        {
            "TimeGenerated": _BASE_TIME + timedelta(hours=18, minutes=20),
            "UserPrincipalName": "biuro@contoso.com",
            "IPAddress": "102.89.44.7",
            "Location": "Lagos, NG",
            "AppDisplayName": "Office 365 Exchange Online",
            "ResultType": "0",
            "ResultDescription": "Success",
            "ConditionalAccessStatus": "success",
        }
    ]


_ANOMALIES = (
    _password_spray_burst()
    + _aitm_token_replay()
    + _device_code_registration()
    + _meta_phishing_relay_signin()
)


def _benign_rows(count: int) -> list[dict[str, Any]]:
    rows = []
    for i in range(count):
        upn = _UPNS[i % len(_UPNS)]
        app = _APPS[(i // len(_UPNS)) % len(_APPS)]
        rows.append(
            {
                "TimeGenerated": _BASE_TIME + timedelta(minutes=i * 9),
                "UserPrincipalName": upn,
                "IPAddress": "10.20.0." + str(10 + i % 40),
                "Location": "Warszawa, PL",
                "AppDisplayName": app,
                "ResultType": "0",
                "ResultDescription": "Success",
                "ConditionalAccessStatus": "success",
            }
        )
    return rows


def _build_rows() -> list[dict[str, Any]]:
    rows = _benign_rows(70) + _ANOMALIES
    rows.sort(key=lambda r: r["TimeGenerated"])
    return rows


ROWS: list[dict[str, Any]] = _build_rows()
