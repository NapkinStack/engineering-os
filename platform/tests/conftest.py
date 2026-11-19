"""No test asks the real registry, the real forge or the person's gh login: `nstack doctor` reads the first for a newer
version (D91), the second for where an unpublished pin stands. No test waits on the machine's
end-to-end lock either: a real run of another project holds it for minutes, and a test that took it
hung the suite (D217) — each test has a runtime folder of its own. Nor does a test see the day
change under it (D235): the engine's clock is held at the day the run started."""

import datetime
import types

import pytest

# The tests compute their dates once, when their module loads (TODAY, and the parameters built
# from it); the engine reads the clock at each call. A run crossing midnight had them a day apart:
# seven tests of test_plan.py failed for a date, never for a rule.
RUN_DAY = datetime.date.today()


class _RunDay(datetime.date):
    @classmethod
    def today(cls) -> datetime.date:
        return RUN_DAY


HELD = types.SimpleNamespace(**{**{name: getattr(datetime, name) for name in dir(datetime)
                                   if not name.startswith("__")}, "date": _RunDay})


@pytest.fixture(autouse=True)
def _no_registry(monkeypatch):
    monkeypatch.setenv("NSTACK_REGISTRY_URL", "http://127.0.0.1:9")
    monkeypatch.setenv("GITHUB_API_URL", "http://127.0.0.1:9")
    from napkinstack import settings  # nor the person's own gh login (D244)
    monkeypatch.setattr(settings, "_gh_token", lambda: None)


@pytest.fixture(autouse=True)
def _own_runtime(monkeypatch, tmp_path_factory):
    runtime = tmp_path_factory.mktemp("runtime")
    runtime.chmod(0o700)
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(runtime))


@pytest.fixture(autouse=True)
def _run_day(monkeypatch):
    from napkinstack import pull_request
    from napkinstack.fitness import manifests, plan
    for module in (plan, manifests, pull_request):
        monkeypatch.setattr(module, "datetime", HELD)
