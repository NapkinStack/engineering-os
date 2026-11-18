"""D232 (#420): the pre-push hook ran whatever `nstack` the workstation had. A project updated to
v0.30.0 declared `evidence.sealed`; every agent still on 0.29.0 had its push refused with
"M12 unknown key 'sealed'" — an older engine judging a newer project, refusing what the project's
version defines and able to pass what it refuses. Each agent put a shim on PATH to get through.

The hook now judges only with an engine at the project's version or ahead of it; one behind is
refused before any check, naming both versions and the command that installs the right one. The
hook is a project file: it holds for a workstation whose engine predates this fix.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "skeleton" / ".pre-commit-config.yaml"


def _entry() -> str:
    for repo in yaml.safe_load(CONFIG.read_text(encoding="utf-8"))["repos"]:
        for hook in repo["hooks"]:
            if hook["id"] == "nstack-fitness":
                return hook["entry"]
    raise AssertionError("no nstack-fitness hook")


def _push(tmp_path: Path, engine: str | None, commit: str, branch: str = "refs/heads/d1-work") \
        -> tuple[subprocess.CompletedProcess, list[str]]:
    """The hook's entry run as pre-commit runs it, in a project recording `commit`, with an
    `nstack` that answers `--version` as `engine` and logs every check it is asked for."""
    bin_ = tmp_path / "bin"
    bin_.mkdir()
    if engine is not None:
        (bin_ / "nstack").write_text(f"""#!/bin/sh
if [ "$1" = --version ]; then echo "{engine}"; exit 0; fi
echo "$1" >> "{tmp_path}/checks"
""", encoding="utf-8")
        (bin_ / "nstack").chmod(0o755)
    project = tmp_path / "project"
    (project / ".nstack").mkdir(parents=True)
    for script in (ROOT / "skeleton" / ".nstack").glob("*.sh"):
        (project / ".nstack" / script.name).write_bytes(script.read_bytes())
    (project / ".copier-answers.yml").write_text(f"_commit: {commit}\n_src_path: gh:NapkinStack/engineering-os\n",
                                                 encoding="utf-8")
    path = f"{bin_}:/usr/bin:/bin"
    result = subprocess.run(["sh", "-c", _entry()], cwd=project, capture_output=True, text=True,
                            env={**os.environ, "PATH": path, "PRE_COMMIT_REMOTE_BRANCH": branch}, timeout=60)
    checks = (tmp_path / "checks").read_text(encoding="utf-8").split() if (tmp_path / "checks").exists() else []
    return result, checks


@pytest.mark.parametrize("engine, commit", [
    ("nstack 0.29.0", "v0.30.0"),
    ("nstack 0.30.0", "v0.30.1"),                                       # behind by a patch
    ("nstack 0.29.0", "'v0.30.0'"),                                     # quoted, as Copier may write it
    ("nstack 0.29.0", "v0.30.0\r"),                                     # a file saved with CRLF
    ("nstack 0.29.0", "v0.30.0-3-g1a2b3c4"),                            # a pin past v0.30.0: behind it too
])
def test_an_engine_behind_the_project_is_refused_before_judging(tmp_path, engine, commit):
    result, checks = _push(tmp_path, engine, commit)
    said = result.stdout + result.stderr
    assert result.returncode == 1, said
    assert checks == [], "an engine behind the project judged it"
    assert engine in said and f"the project is on {commit.strip(chr(39)).strip()}." in said, said
    assert "Action: bash .nstack/install-engine.sh" in said, said


@pytest.mark.parametrize("engine, commit", [
    ("nstack 0.30.0", "v0.30.0"),                                       # level
    ("nstack 0.31.0", "v0.30.0"),                                       # ahead: an update starts there
    ("nstack 0.30.10", "v0.30.9"),                                      # compared as numbers, not text
    ("nstack 0.31.0", "v0.30.5"),                                       # a higher minor, a lower patch
    ("nstack 1.0.0", "v0.30.0"),                                        # a higher major
    ("nstack 0.31.0 — UNPUBLISHED: a local checkout at v0.30.0-8-gbc5eda3", "v0.31.0"),
    ("nstack 0.30.0", "v0.30.0-3-g1a2b3c4"),                            # at a pin's base: every run says the pin
])
def test_an_engine_level_with_the_project_or_ahead_judges(tmp_path, engine, commit):
    result, checks = _push(tmp_path, engine, commit)
    assert result.returncode == 0, result.stdout + result.stderr
    assert checks == ["manifests", "boundaries", "plan", "hygiene"], checks


def test_a_failed_check_still_refuses_the_push(tmp_path):
    result, _ = _push(tmp_path, "nstack 0.30.0", "v0.30.0")
    assert result.returncode == 0
    fails = tmp_path / "fails"
    fails.mkdir()
    (fails / "bin").mkdir()
    (fails / "bin" / "nstack").write_text('#!/bin/sh\n[ "$1" = --version ] && echo "nstack 0.30.0" && exit 0\n'
                                          '[ "$1" = plan ] && exit 1\nexit 0\n', encoding="utf-8")
    (fails / "bin" / "nstack").chmod(0o755)
    refused = subprocess.run(["sh", "-c", _entry()], cwd=tmp_path / "project", capture_output=True, text=True,
                             env={**os.environ, "PATH": f"{fails / 'bin'}:/usr/bin:/bin"}, timeout=60)
    assert refused.returncode == 1, refused.stdout + refused.stderr


def test_a_project_without_answers_is_judged_without_noise(tmp_path):
    result, checks = _push(tmp_path, "nstack 0.29.0", "v0.30.0")
    assert checks == ["manifests", "boundaries", "plan", "hygiene"] or result.returncode == 1
    (tmp_path / "checks").unlink(missing_ok=True)
    (tmp_path / "project" / ".copier-answers.yml").unlink()
    again = subprocess.run(["sh", "-c", _entry()], cwd=tmp_path / "project", capture_output=True, text=True,
                           env={**os.environ, "PATH": f"{tmp_path / 'bin'}:/usr/bin:/bin"}, timeout=60)
    assert again.returncode == 0 and again.stderr == "", again.stderr


def test_a_workstation_without_nstack_lets_ci_judge(tmp_path):
    result, checks = _push(tmp_path, None, "v0.30.0")
    assert result.returncode == 0 and "CI judges" in result.stdout, result.stdout + result.stderr


@pytest.mark.parametrize("branch, judged", [
    ("refs/heads/nstack/hold/03-the-window/D1", False),   # a hold's event: metadata only (#427)
    ("refs/notes/nstack/checks", False),                  # an attested record
    ("refs/heads/nstack/hold-not-a-hold", True),
    ("refs/heads/main", True),
])
def test_a_hold_s_event_is_pushed_without_judging_the_project(tmp_path, branch, judged):
    """#427: the default branch red, the hook refused every push, a hold's event included —
    `nstack unclaim` could not give a deliverable back. An event moves no file of the project."""
    result, checks = _push(tmp_path, "nstack 0.29.0", "v0.30.0", branch)
    if judged:
        assert result.returncode == 1 and checks == [], result.stdout
    else:
        assert result.returncode == 0 and checks == [], result.stdout + result.stderr
        assert "nstack's own record" in result.stdout
