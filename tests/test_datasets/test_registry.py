"""Tests for the dataset registry (core.datasets.get_tables)."""
import pytest

from core.datasets import get_tables


def test_get_tables_returns_requested_datasets():
    tables = get_tables("DeviceProcessEvents")
    assert set(tables.keys()) == {"DeviceProcessEvents"}
    assert len(tables["DeviceProcessEvents"]) > 0


def test_get_tables_multiple_datasets():
    tables = get_tables("DeviceProcessEvents", "DeviceLogonEvents")
    assert set(tables.keys()) == {"DeviceProcessEvents", "DeviceLogonEvents"}


def test_get_tables_includes_all_new_sentinel_style_tables():
    names = ["SigninLogs", "DeviceNetworkEvents", "EmailEvents", "DeviceFileEvents", "OfficeActivity"]
    tables = get_tables(*names)
    assert set(tables.keys()) == set(names)
    assert all(len(rows) > 0 for rows in tables.values())


def test_get_tables_includes_all_identity_mdi_tables():
    names = ["IdentityLogonEvents", "IdentityQueryEvents", "IdentityDirectoryEvents"]
    tables = get_tables(*names)
    assert set(tables.keys()) == set(names)
    assert all(len(rows) > 0 for rows in tables.values())


def test_get_tables_unknown_dataset_raises_helpful_error():
    with pytest.raises(KeyError) as exc_info:
        get_tables("NoSuchTable")
    assert "DeviceProcessEvents" in str(exc_info.value)
