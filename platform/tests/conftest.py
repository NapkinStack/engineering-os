"""No test asks the real registry: `nstack doctor` reads it for a newer version (D91)."""

import pytest


@pytest.fixture(autouse=True)
def _no_registry(monkeypatch):
    monkeypatch.setenv("NSTACK_REGISTRY_URL", "http://127.0.0.1:9")
