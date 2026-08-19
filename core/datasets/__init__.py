"""Registry of available datasets, keyed by table name.

Adding a new dataset = add one module in this package exposing a
module-level `SCHEMA` (TableSchema) and `ROWS` (list[dict]), then add it to
`_MODULES` below. Nothing in the KQL engine or scenarios layer needs to
change.
"""
from __future__ import annotations

from typing import Any

from . import (
    device_file_events,
    device_logon_events,
    device_network_events,
    device_process_events,
    email_events,
    identity_directory_events,
    identity_logon_events,
    identity_query_events,
    office_activity,
    signin_logs,
)
from .schema import TableSchema

_MODULES = [
    device_process_events,
    device_logon_events,
    device_network_events,
    device_file_events,
    email_events,
    signin_logs,
    office_activity,
    identity_logon_events,
    identity_query_events,
    identity_directory_events,
]

DATASETS: dict[str, list[dict[str, Any]]] = {m.SCHEMA.name: m.ROWS for m in _MODULES}
SCHEMAS: dict[str, TableSchema] = {m.SCHEMA.name: m.SCHEMA for m in _MODULES}


def get_tables(*names: str) -> dict[str, list[dict[str, Any]]]:
    """Returns a `{table_name: rows}` dict for the given dataset names, ready
    to pass to `core.kql_engine.run_query`."""
    result: dict[str, list[dict[str, Any]]] = {}
    for name in names:
        if name not in DATASETS:
            available = ", ".join(sorted(DATASETS)) or "(brak)"
            raise KeyError(f"Nieznany dataset '{name}'. Dostępne: {available}.")
        result[name] = DATASETS[name]
    return result
