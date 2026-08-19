"""Suite-wide fixtures."""
from __future__ import annotations

import pytest

from core.scenarios import log_store


@pytest.fixture(autouse=True)
def isolated_imported_scenarios(tmp_path, monkeypatch):
    """Every test gets its own empty core.scenarios.log_store.IMPORTED_DIR by
    default, so tests never read from (or pollute) the real
    core/scenarios/imported/ directory and stay hermetic regardless of what's
    been imported locally through the running dev server."""
    monkeypatch.setattr(log_store, "IMPORTED_DIR", tmp_path / "imported")
