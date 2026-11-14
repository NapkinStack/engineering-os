"""No test asks the real registry or the real forge: `nstack doctor` reads the first for a newer
version (D91), the second for where an unpublished pin stands. No test waits on the machine's
end-to-end lock either: a real run of another project holds it for minutes, and a test that took it
hung the suite (D217) — each test has a runtime folder of its own."""

import pytest


@pytest.fixture(autouse=True)
def _no_registry(monkeypatch):
    monkeypatch.setenv("NSTACK_REGISTRY_URL", "http://127.0.0.1:9")
    monkeypatch.setenv("GITHUB_API_URL", "http://127.0.0.1:9")


@pytest.fixture(autouse=True)
def _own_runtime(monkeypatch, tmp_path_factory):
    runtime = tmp_path_factory.mktemp("runtime")
    runtime.chmod(0o700)
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(runtime))
