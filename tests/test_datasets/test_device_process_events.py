"""Tests for the synthetic DeviceProcessEvents dataset."""
from core.datasets import device_process_events as dpe


def test_row_count_is_in_the_tens_to_hundreds_range():
    assert 50 <= len(dpe.ROWS) <= 500


def test_every_row_has_exactly_the_schema_columns():
    expected_columns = {c.name for c in dpe.SCHEMA.columns}
    for row in dpe.ROWS:
        assert set(row.keys()) == expected_columns


def test_generation_is_deterministic():
    assert dpe._build_rows() == dpe._build_rows()


def test_rows_are_sorted_by_timestamp():
    timestamps = [r["Timestamp"] for r in dpe.ROWS]
    assert timestamps == sorted(timestamps)


def test_contains_exactly_one_rundll32_anomaly():
    matches = [r for r in dpe.ROWS if r["FileName"] == "rundll32.exe"]
    assert len(matches) == 1
    assert "Public" in matches[0]["ProcessCommandLine"]


def test_contains_exactly_one_encoded_powershell_anomaly():
    matches = [r for r in dpe.ROWS if r["FileName"] == "powershell.exe" and "-enc" in r["ProcessCommandLine"]]
    assert len(matches) == 1


def test_contains_office_spawning_lolbin_anomalies():
    matches = [
        r
        for r in dpe.ROWS
        if r["InitiatingProcessFileName"] in ("WINWORD.EXE", "OUTLOOK.EXE")
        and r["FileName"] in ("cmd.exe", "powershell.exe")
    ]
    assert len(matches) == 2


def test_contains_exactly_one_psexec_anomaly():
    matches = [r for r in dpe.ROWS if r["FileName"] == "PSEXESVC.exe"]
    assert len(matches) == 1
    assert matches[0]["DeviceName"] == "WIN-SRV02"
    assert matches[0]["AccountName"] == "administrator"


def test_contains_exactly_one_dll_sideload_anomaly():
    matches = [r for r in dpe.ROWS if r["FileName"] == "hpreader.exe"]
    assert len(matches) == 1
    assert "Downloads" in matches[0]["FolderPath"]


def test_contains_exactly_one_fake_invoice_installer_anomaly():
    matches = [r for r in dpe.ROWS if r["FileName"] == "Faktura_Zalegla_Setup.exe"]
    assert len(matches) == 1
    assert matches[0]["AccountName"] == "jkowalski"


def test_contains_ransomware_chain_anomalies_on_win_srv02():
    chain_filenames = {r["FileName"] for r in dpe._RANSOMWARE_CHAIN}
    assert chain_filenames == {
        "net.exe",
        "powershell.exe",
        "vssadmin.exe",
        "schtasks.exe",
        "servertool.exe",
        "cmd.exe",
    }
    assert all(r["DeviceName"] == "WIN-SRV02" for r in dpe._RANSOMWARE_CHAIN)
    assert all(r["AccountName"] == "administrator" for r in dpe._RANSOMWARE_CHAIN)


def test_contains_exactly_one_backdoor_admin_account_anomaly():
    matches = [r for r in dpe.ROWS if r["FileName"] == "net.exe" and "germania" in r["ProcessCommandLine"]]
    assert len(matches) == 1


def test_contains_exactly_one_rmm_spawned_downloader_anomaly():
    matches = [
        r
        for r in dpe.ROWS
        if r["FileName"] == "powershell.exe" and r["InitiatingProcessFileName"] == "RemotePCService.exe"
    ]
    assert len(matches) == 1
    assert "DownloadString" in matches[0]["ProcessCommandLine"]


def test_contains_exactly_one_ping_delay_self_delete_anomaly():
    matches = [
        r
        for r in dpe.ROWS
        if r["FileName"] == "cmd.exe" and "ping" in r["ProcessCommandLine"] and "127.0.0.1" in r["ProcessCommandLine"]
    ]
    assert len(matches) == 1
    assert "/F" in matches[0]["ProcessCommandLine"] and "/Q" in matches[0]["ProcessCommandLine"]


def test_contains_gotoresolve_rmm_abuse_chain_on_win_client04():
    chain_filenames = {r["FileName"] for r in dpe._GOTORESOLVE_CHAIN}
    assert chain_filenames == {
        "wscript.exe",
        "msiexec.exe",
        "GoToResolveUnattended.exe",
        "GoToResolveLoggerProcess.exe",
        "GoToResolveTools64.exe",
    }
    assert all(r["DeviceName"] == "WIN-CLIENT04" for r in dpe._GOTORESOLVE_CHAIN)


def test_contains_exactly_one_clickfix_attempt_anomaly():
    matches = [r for r in dpe.ROWS if r["FileName"] == "powershell.exe" and r["InitiatingProcessFileName"] == "explorer.exe"]
    assert len(matches) == 1
    assert matches[0]["DeviceName"] == "WIN-CLIENT05"
    assert "DownloadString" in matches[0]["ProcessCommandLine"]


def test_all_device_and_account_values_are_from_the_known_pools():
    # A handful of one-off anomaly narratives (GoToResolve RMM abuse,
    # ClickFix) introduce their own dedicated device/account, deliberately
    # kept out of the benign-rotation pools (_DEVICES/_ACCOUNTS) so they
    # don't dilute those incidents' otherwise-clean single-anomaly matches.
    extra_devices = {"WIN-CLIENT04", "WIN-CLIENT05", "WIN-CLIENT06", "WIN-CLIENT09"}
    extra_accounts = {"pkowalczyk", "mzielinska", "SYSTEM", "tgorski", "kwojcik"}
    devices = {r["DeviceName"] for r in dpe.ROWS}
    accounts = {r["AccountName"] for r in dpe.ROWS}
    assert devices <= set(dpe._DEVICES) | extra_devices
    assert accounts <= set(dpe._ACCOUNTS) | extra_accounts
