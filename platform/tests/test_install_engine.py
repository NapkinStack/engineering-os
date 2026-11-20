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


def _run(tmp_path: Path, failures: int, said: str = MISSING,
         commit: str = "v0.31.0") -> tuple[subprocess.CompletedProcess, list[str], int]:
    """The script, with a `uv` that fails `failures` times saying `said`, and a `sleep` that only
    counts: no test waits. `uv tool dir --bin` names the test's own tool bin folder."""
    bin_ = tmp_path / "bin"
    bin_.mkdir()
    (tmp_path / "tools-bin").mkdir(exist_ok=True)
    (bin_ / "uv").write_text(f"""#!/usr/bin/env bash
if [ "$*" = "tool dir --bin" ]; then echo "{tmp_path}/tools-bin"; exit 0; fi
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
    (project / ".copier-answers.yml").write_text(f"_commit: {commit}\n_src_path: gh:NapkinStack/engineering-os\n",
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



# --- D249 (#453): an executable uv does not own ------------------------------------------------

EXISTS = "error: Executable already exists: pre-commit (use `--force` to overwrite)"


@pytest.mark.parametrize("commit", ["v0.31.0", "v0.31.0-4-gabc1234"], ids=["published", "from sources"])
def test_the_engine_s_own_pre_commit_left_dangling_is_taken_back(tmp_path, commit):
    """uv removed the former engine, then refused its own pre-commit's link, now pointing nowhere:
    the script installs again with --force, and says so."""
    (tmp_path / "tools-bin").mkdir()
    (tmp_path / "tools-bin" / "pre-commit").symlink_to(tmp_path / "removed-tool" / "bin" / "pre-commit")
    result, calls, _ = _run(tmp_path, failures=1, said=EXISTS, commit=commit)
    assert result.returncode == 0, result.stdout + result.stderr
    assert len(calls) == 2 and calls[0] == calls[1] and not any("--force" in call for call in calls), calls
    assert "pre-commit pointed at an engine uv removed" in result.stdout, result.stdout
    assert not (tmp_path / "tools-bin" / "pre-commit").is_symlink(), "the link pointing nowhere is deleted"


def test_another_tool_s_pre_commit_is_never_overwritten(tmp_path):
    (tmp_path / "tools-bin").mkdir()
    (tmp_path / "other-tool").mkdir()
    (tmp_path / "other-tool" / "pre-commit").write_text("#!/bin/sh\n", encoding="utf-8")
    (tmp_path / "tools-bin" / "pre-commit").symlink_to(tmp_path / "other-tool" / "pre-commit")
    result, calls, _ = _run(tmp_path, failures=1, said=EXISTS)
    assert result.returncode == 1 and len(calls) == 1, calls
    assert "pre-commit already belongs to another installation" in result.stdout, result.stdout
    assert "--force" in result.stdout and "not published" not in result.stdout, result.stdout
    assert (tmp_path / "tools-bin" / "pre-commit").exists(), "another installation's link is never touched"


def test_the_command_named_for_a_commit_runs_as_printed(tmp_path):
    """The engine from a commit: its requirement holds spaces, quoted in the command said."""
    (tmp_path / "tools-bin").mkdir()
    (tmp_path / "other").write_text("#!/bin/sh\n", encoding="utf-8")
    (tmp_path / "tools-bin" / "pre-commit").symlink_to(tmp_path / "other")
    result, _, _ = _run(tmp_path, failures=1, said=EXISTS, commit="v0.31.0-4-gabc1234")
    assert result.returncode == 1
    assert "uv tool install napkinstack\\ @\\ git+https://github.com/NapkinStack/engineering-os@abc1234 " in result.stdout, \
        result.stdout


def test_a_failure_that_is_not_a_missing_version_is_never_said_unpublished(tmp_path):
    result, _, _ = _run(tmp_path, failures=99, said="error: Failed to fetch: connection refused")
    assert "not published" not in result.stdout and "uv said why, above" in result.stdout, result.stdout
