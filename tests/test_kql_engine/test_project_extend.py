"""End-to-end tests for the `project` and `extend` operators."""
from core.kql_engine import run_query


def test_project_selects_and_renames(tables):
    result = run_query("DeviceProcessEvents | project Name = FileName, Device = DeviceName", tables)
    assert set(result[0].keys()) == {"Name", "Device"}
    assert result[0]["Name"] == "cmd.exe"


def test_project_computed_column_references_earlier_column(tables):
    result = run_query(
        "DeviceProcessEvents | project Upper = toupper(FileName), IsCmd = Upper == 'CMD.EXE'", tables
    )
    assert result[0]["IsCmd"] is True


def test_extend_keeps_existing_columns(tables):
    result = run_query("DeviceProcessEvents | extend IsCmd = FileName == 'cmd.exe'", tables)
    assert "FileName" in result[0]
    assert "IsCmd" in result[0]


def test_extend_can_reference_earlier_extend_column(tables):
    result = run_query(
        "DeviceProcessEvents | extend Upper = toupper(FileName), IsCmdUpper = Upper == 'CMD.EXE'", tables
    )
    assert result[0]["IsCmdUpper"] is True
