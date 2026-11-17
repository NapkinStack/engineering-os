"""D226 (#376): PyPI's simple index can lag its JSON API by minutes after a release. An update
pull request opened in that window failed in CI on `install-engine.sh` — "no version of
napkinstack==X.Y.Z" — and a person had to re-run the jobs: an agent's App cannot. The script
tries again, said, for a few minutes, then fails as before; any other failure fails at once.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "skeleton" / ".nstack" / "install-engine.sh"
MISSING = ("  × No solution found when resolving dependencies:\n"
           "  ╰─▶ Because there is no version of napkinstack==0.31.0 and you require napkinstack==0.31.0, "
           "we can conclude that your requirements are unsatisfiable.")


def _run(tmp_path: Path, failures: int, said: str = MISSING) -> tuple[subprocess.CompletedProcess, list[str], int]:
    """The script, with a `uv` that fails `failures` times saying `said`, and a `sleep` that only
    counts: no test waits."""
    bin_ = tmp_path / "bin"
    bin_.mkdir()
    (bin_ / "uv").write_text(f"""#!/usr/bin/env bash
echo "$*" >> "{tmp_path}/uv.calls"
n=$(wc -l < "{tmp_path}/uv.calls")
if [ "$n" -le {failures} ]; then printf '%s\\n' "{said}" >&2; exit 1; fi
echo "Installed 1 executable: nstack"
""", encoding="utf-8")
    (bin_ / "sleep").write_text(f'#!/usr/bin/env bash\necho "$1" >> "{tmp_path}/sleep.calls"\n', encoding="utf-8")
    for tool in ("uv", "sleep"):
        (bin_ / tool).chmod(0o755)
    project = tmp_path / "project"
    project.mkdir()
    (project / ".copier-answers.yml").write_text("_commit: v0.31.0\n_src_path: gh:NapkinStack/engineering-os\n",
                                                 encoding="utf-8")
    result = subprocess.run(["bash", str(SCRIPT)], cwd=project, capture_output=True, text=True,
                            env={**os.environ, "PATH": f"{bin_}:{os.environ['PATH']}", "TMPDIR": str(tmp_path)}, timeout=60)
    calls = (tmp_path / "uv.calls").read_text(encoding="utf-8").splitlines()
    sleeps = (tmp_path / "sleep.calls").read_text(encoding="utf-8").split() if (tmp_path / "sleep.calls").exists() else []
    return result, calls, sum(int(second) for second in sleeps)


def test_a_version_the_index_does_not_list_yet_is_installed_once_it_does(tmp_path):
    result, calls, waited = _run(tmp_path, failures=2)
    assert result.returncode == 0, result.stdout + result.stderr
    assert len(calls) == 3 and all("napkinstack==0.31.0" in call and "--refresh-package napkinstack" in call
                                   for call in calls), calls
    assert "not listed yet" in result.stdout and "attempt 1" in result.stdout, result.stdout
    assert waited == 60, waited
    assert not list(tmp_path.glob("tmp.*")), "nothing left behind"


def test_a_version_never_listed_fails_as_before_after_a_bounded_wait(tmp_path):
    result, calls, waited = _run(tmp_path, failures=99)
    assert result.returncode == 1
    assert "FAIL [nstack] napkinstack 0.31.0 could not be installed from PyPI" in result.stdout, result.stdout
    assert len(calls) == 6 and waited == 30 * 5, (calls, waited)  # no wait after the last attempt


CONFLICT = ("  × No solution found when resolving dependencies:\n  ╰─▶ Because the current Python version (3.10) does "
            "not satisfy Python>=3.12 and napkinstack==0.31.0 depends on Python>=3.12, we can conclude that "
            "napkinstack==0.31.0 cannot be used.")


@pytest.mark.parametrize("said", ["error: Failed to fetch: connection refused", CONFLICT],
                         ids=["the network", "a resolution that never changes"])
def test_any_other_failure_fails_at_once(tmp_path, said):
    result, calls, waited = _run(tmp_path, failures=99, said=said)
    assert result.returncode == 1 and len(calls) == 1 and waited == 0, (calls, waited)
    assert said.splitlines()[-1].strip() in result.stderr, "uv's own words are kept"
