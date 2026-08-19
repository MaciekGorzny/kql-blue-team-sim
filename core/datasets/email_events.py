"""Synthetic dataset mimicking a simplified Microsoft Defender for Office 365
`EmailEvents` table: routine business mail plus the two phishing emails that
kick off the incident already told across `device_process_events.py`'s
anomalies (the encoded-PowerShell click and the `faktura_2026.docm` macro).

Generation is fully deterministic (no `random` module involved), matching the
convention in `device_process_events.py`/`device_logon_events.py`.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from core.kql_engine.ast_nodes import KqlType

from .schema import ColumnSchema, TableSchema

SCHEMA = TableSchema(
    name="EmailEvents",
    columns=[
        ColumnSchema("Timestamp", KqlType.DATETIME, "Czas doręczenia wiadomości (UTC)."),
        ColumnSchema("SenderFromAddress", KqlType.STRING, "Adres nadawcy."),
        ColumnSchema("RecipientEmailAddress", KqlType.STRING, "Adres odbiorcy."),
        ColumnSchema("Subject", KqlType.STRING, "Temat wiadomości."),
        ColumnSchema("ThreatTypes", KqlType.STRING, "'None' lub 'Phish'."),
        ColumnSchema("DeliveryAction", KqlType.STRING, "'Delivered', 'Junked' lub 'Blocked'."),
        ColumnSchema("AttachmentCount", KqlType.LONG, "Liczba załączników."),
        ColumnSchema("UrlCount", KqlType.LONG, "Liczba linków w treści."),
    ],
)

_BASE_TIME = datetime(2026, 8, 10, 8, 0, 0, tzinfo=timezone.utc)
_INTERNAL_ACCOUNTS = ["jkowalski", "anowak", "mwisniewski", "asystem"]
_EXTERNAL_SENDERS = [
    "dostawy@partner-firma.example",
    "no-reply@newsletter.example",
    "hr@contoso.com",
    "faktury@ksiegowosc-zewn.example",
]
_SUBJECTS = [
    "Harmonogram spotkania - sierpień",
    "Newsletter tygodniowy",
    "Aktualizacja polityki urlopowej",
    "Potwierdzenie dostawy",
]

# The first two phishing emails are referenced in device_process_events.py's
# anomaly comments as the entry point for that incident - both bypass
# filtering (DeliveryAction="Delivered" despite ThreatTypes="Phish"), timed
# shortly before the recipient's own process-execution anomaly. The third is
# a separate incident: a device-code-phishing lure (see signin_logs.py's
# device-code registration anomaly).
_ANOMALIES: list[dict[str, Any]] = [
    {
        # precedes WIN-CLIENT02 / anowak's encoded-powershell anomaly (+2h13m)
        "Timestamp": _BASE_TIME + timedelta(hours=2, minutes=0),
        "SenderFromAddress": "zamowienia@dostawca-zewn.example",
        "RecipientEmailAddress": "anowak@contoso.com",
        "Subject": "Pilne: potwierdzenie zamówienia - kliknij aby zobaczyć",
        "ThreatTypes": "Phish",
        "DeliveryAction": "Delivered",
        "AttachmentCount": 0,
        "UrlCount": 1,
    },
    {
        # precedes WIN-CLIENT01 / jkowalski's WINWORD macro anomaly (+3h5m)
        "Timestamp": _BASE_TIME + timedelta(hours=2, minutes=50),
        "SenderFromAddress": "faktury@ksiegowosc-zewn.example",
        "RecipientEmailAddress": "jkowalski@contoso.com",
        "Subject": "faktura_2026.docm - prosimy o pilną płatność",
        "ThreatTypes": "Phish",
        "DeliveryAction": "Delivered",
        "AttachmentCount": 1,
        "UrlCount": 0,
    },
    {
        # A separate incident: a device-code-phishing lure (T1566.002) to
        # mwisniewski, precedes the device-code registration sign-in
        # anomaly in signin_logs.py by ~15 minutes.
        "Timestamp": _BASE_TIME + timedelta(hours=4, minutes=0),
        "SenderFromAddress": "no-reply@teams-meetings-support.example",
        "RecipientEmailAddress": "mwisniewski@contoso.com",
        "Subject": "Twoje zaproszenie do spotkania wygasło - dokończ logowanie kodem",
        "ThreatTypes": "Phish",
        "DeliveryAction": "Delivered",
        "AttachmentCount": 0,
        "UrlCount": 1,
    },
    {
        # THREAT-023-style brand-impersonation phishing (T1566.002) to a
        # shared mailbox, precedes the anomalous sign-in anomaly in
        # signin_logs.py by ~20 minutes.
        "Timestamp": _BASE_TIME + timedelta(hours=18, minutes=0),
        "SenderFromAddress": "MetaCopyrightTeam@raisnagar.org",
        "RecipientEmailAddress": "biuro@contoso.com",
        "Subject": "Final Notice: Resolve Trademark Violations to Avoid Account Restrictions",
        "ThreatTypes": "Phish",
        "DeliveryAction": "Delivered",
        "AttachmentCount": 0,
        "UrlCount": 1,
    },
]


def _benign_rows(count: int) -> list[dict[str, Any]]:
    rows = []
    for i in range(count):
        recipient = _INTERNAL_ACCOUNTS[i % len(_INTERNAL_ACCOUNTS)]
        sender = _EXTERNAL_SENDERS[(i // len(_INTERNAL_ACCOUNTS)) % len(_EXTERNAL_SENDERS)]
        subject = _SUBJECTS[i % len(_SUBJECTS)]
        rows.append(
            {
                "Timestamp": _BASE_TIME + timedelta(minutes=i * 7),
                "SenderFromAddress": sender,
                "RecipientEmailAddress": f"{recipient}@contoso.com",
                "Subject": subject,
                "ThreatTypes": "None",
                "DeliveryAction": "Delivered",
                "AttachmentCount": i % 2,
                "UrlCount": (i + 1) % 3,
            }
        )
    return rows


def _build_rows() -> list[dict[str, Any]]:
    rows = _benign_rows(60) + _ANOMALIES
    rows.sort(key=lambda r: r["Timestamp"])
    return rows


ROWS: list[dict[str, Any]] = _build_rows()
