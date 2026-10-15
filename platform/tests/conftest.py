"""No test asks the real registry or the real forge: `nstack doctor` reads the first for a newer
version (D91), the second for where an unpublished pin stands."""

import pytest


@pytest.fixture(autouse=True)
def _no_registry(monkeypatch):
    monkeypatch.setenv("NSTACK_REGISTRY_URL", "http://127.0.0.1:9")
    monkeypatch.setenv("GITHUB_API_URL", "http://127.0.0.1:9")
