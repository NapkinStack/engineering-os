"""D129, ADR-0006: a project's checks run where the team works, and the run is recorded in git,
bound to its commit. Every case proves its rule fails (P5) and names itself (P6). Run by
platform/tests/run.sh.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest
import yaml

from napkinstack import attest

ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = sorted((ROOT / "skeleton/.github/workflows").glob("*.yml"))
IDENTITY = {"GIT_AUTHOR_NAME": "test", "GIT_AUTHOR_EMAIL": "test@example.invalid",
            "GIT_COMMITTER_NAME": "test", "GIT_COMMITTER_EMAIL": "test@example.invalid"}


def git(root, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=root, env={**os.environ, **IDENTITY}, check=True,
                          capture_output=True, text=True).stdout.strip()


# --- the one list, bound to the workflows -------------------------------------------------

def pull_request_jobs() -> dict[str, list[str]]:
    """Each job a pull request runs, by its name: its `run` steps but the engine's install, which
    a workstation does once."""
    jobs: dict[str, list[str]] = {}
    for path in WORKFLOWS:
        workflow = yaml.safe_load(path.read_text(encoding="utf-8"))
        triggers = workflow.get(True) or workflow.get("on") or {}  # YAML reads a bare `on` as True
        if "pull_request" not in triggers:
            continue
        for job in workflow["jobs"].values():
            runs = [step["run"] for step in job["steps"] if "run" in step and "install-engine" not in step["run"]]
            jobs[job["name"]] = runs
    return jobs


def test_the_list_names_every_job_a_pull_request_runs_and_no_other():
    assert {check.name for check in attest.CHECKS} == set(pull_request_jobs())


@pytest.mark.parametrize("check", attest.CHECKS, ids=lambda check: check.name)
def test_each_check_runs_what_its_job_runs(check):
    runs = pull_request_jobs()[check.name]
    assert len(check.steps) == len(runs), f"{check.name}: {len(runs)} steps in the job"
    for step, run in zip(check.steps, runs):
        assert step.signature in run, f"{check.name}: '{step.signature}' is not what the job runs"


# --- the record ---------------------------------------------------------------------------

def project(root: Path) -> str:
    git(root, "init", "-q", "--initial-branch=main")
    (root / "README.md").write_text("project\n", encoding="utf-8")
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "first\n\nAgent-Session: a-session")
    return git(root, "rev-parse", "HEAD")


PASSING = (attest.Check("Passes", (attest.Step("echo", "say it", "echo all good"),)),)
FAILING = (attest.Check("Passes", (attest.Step("echo", "say it", "echo all good"),)),
           attest.Check("Fails", (attest.Step("false", "refuse", "echo broken >&2; false"),)))


@pytest.fixture(autouse=True)
def _identity(monkeypatch):
    for name, value in IDENTITY.items():
        monkeypatch.setenv(name, value)


def records(root: Path, commit: str) -> list[dict]:
    note = git(root, "notes", f"--ref={attest.NOTES}", "show", commit)
    return [json.loads(line) for line in note.splitlines() if line.strip()]


def test_a_run_is_recorded_on_its_commit_as_one_json_line(tmp_path, monkeypatch, capsys):
    head = project(tmp_path)
    monkeypatch.setattr(attest, "CHECKS", PASSING)
    assert attest.run(tmp_path, "HEAD", None, "") == 0
    [record] = records(tmp_path, head)
    assert record["record"] == "attested-checks/v1" and record["commit"] == head
    assert record["session"] == "a-session" and record["by"] == "test <test@example.invalid>"
    assert [(c["name"], c["passed"]) for c in record["checks"]] == [("Passes", True)]
    assert "all good" in record["checks"][0]["steps"][0]["output"]
    out = capsys.readouterr().out
    assert "attested: 1 of 1" in out and "local only" in out


def test_a_failed_check_is_recorded_failed_and_every_check_still_runs(tmp_path, monkeypatch, capsys):
    head = project(tmp_path)
    monkeypatch.setattr(attest, "CHECKS", tuple(reversed(FAILING)))
    assert attest.run(tmp_path, "HEAD", None, "") == 1
    [record] = records(tmp_path, head)
    assert [(c["name"], c["passed"]) for c in record["checks"]] == [("Fails", False), ("Passes", True)]
    assert "broken" in record["checks"][0]["steps"][0]["output"]
    assert "FAIL [attest] Fails" in capsys.readouterr().out


def test_a_second_run_is_a_second_line_and_the_latest_is_the_record(tmp_path, monkeypatch):
    head = project(tmp_path)
    monkeypatch.setattr(attest, "CHECKS", FAILING)
    attest.run(tmp_path, "HEAD", None, "")
    monkeypatch.setattr(attest, "CHECKS", PASSING)
    attest.run(tmp_path, "HEAD", None, "")
    lines = records(tmp_path, head)
    assert len(lines) == 2
    assert attest.latest(tmp_path, head)["checks"][-1]["passed"] is True


@pytest.mark.parametrize("change", ["modified", "untracked"])
def test_a_tree_with_changes_is_refused_and_nothing_is_written(tmp_path, monkeypatch, capsys, change):
    head = project(tmp_path)
    monkeypatch.setattr(attest, "CHECKS", PASSING)
    target = tmp_path / ("README.md" if change == "modified" else "new.txt")
    target.write_text("changed\n", encoding="utf-8")
    assert attest.run(tmp_path, "HEAD", None, "") == 1
    assert "FAIL [attest] the tree holds changes" in capsys.readouterr().out
    assert attest.latest(tmp_path, head) is None


def test_the_record_travels_with_the_branch_remote_and_merges_with_anothers(tmp_path, monkeypatch, capsys):
    remote = tmp_path / "remote.git"
    subprocess.run(["git", "init", "-q", "--bare", "--initial-branch=main", str(remote)], check=True)
    one, two = tmp_path / "one", tmp_path / "two"
    one.mkdir()
    head = project(one)
    git(one, "remote", "add", "origin", str(remote))
    git(one, "push", "-q", "origin", "main")
    subprocess.run(["git", "clone", "-q", str(remote), str(two)], check=True)
    monkeypatch.setattr(attest, "CHECKS", PASSING)
    assert attest.run(one, "HEAD", None, "") == 0
    assert attest.run(two, "HEAD", None, "") == 0  # a second workstation, the same commit
    assert "pushed to origin" in capsys.readouterr().out
    fresh = tmp_path / "fresh"
    subprocess.run(["git", "clone", "-q", str(remote), str(fresh)], check=True)
    attest.fetch(fresh)
    assert len(records(fresh, head)) == 2


def test_the_output_kept_is_capped_and_its_whole_is_hashed():
    text = "x" * (attest.KEPT * 3)
    kept = attest.capped(text)
    assert len(kept) < attest.KEPT + 200 and "bytes cut" in kept
    assert kept.startswith("x") and kept.endswith("x")


# --- the decider's word, read by pr-check (rules A1, A2) ------------------------------------

from napkinstack import pull_request  # noqa: E402


def change(root: Path, checks: str | None) -> tuple[str, str]:
    """A project whose answers say how its checks are judged; a second commit changes a file."""
    git(root, "init", "-q", "--initial-branch=main")
    answers = {"_commit": "v0.9.6", "project_name": "p"} | ({"checks": checks} if checks else {})
    (root / ".copier-answers.yml").write_text(yaml.safe_dump(answers), encoding="utf-8")
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "base")
    base = git(root, "rev-parse", "HEAD")
    (root / "notes.txt").write_text("a change\n", encoding="utf-8")
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "change\n\nAgent-Session: a-session")
    return base, git(root, "rev-parse", "HEAD")


def judged(root: Path, base: str, monkeypatch, capsys) -> tuple[int, str]:
    monkeypatch.setenv("PR_BODY", "A change.")
    monkeypatch.delenv("PR_HEAD_SHA", raising=False)
    code = pull_request.run(root, base)
    return code, capsys.readouterr().out


@pytest.mark.parametrize("answer", [None, "forge"])
def test_judged_on_the_forge_a_record_is_shown_and_nothing_required(tmp_path, monkeypatch, capsys, answer):
    base, _ = change(tmp_path, answer)
    code, out = judged(tmp_path, base, monkeypatch, capsys)
    assert code == 0 and "Checks          : the forge's CI" in out
    monkeypatch.setattr(attest, "CHECKS", PASSING)
    attest.run(tmp_path, base, None, "")
    code, out = judged(tmp_path, base, monkeypatch, capsys)
    assert code == 0 and "a record of the head: attested 1 of 1 (information)" in out


def test_attested_with_no_record_of_the_head_is_refused(tmp_path, monkeypatch, capsys):
    base, _ = change(tmp_path, "attested")
    code, out = judged(tmp_path, base, monkeypatch, capsys)
    assert code == 1 and "FAIL [A1]" in out and "nstack attest" in out


def test_attested_with_a_record_of_another_commit_is_refused(tmp_path, monkeypatch, capsys):
    base, _ = change(tmp_path, "attested")
    monkeypatch.setattr(attest, "CHECKS", PASSING)
    attest.run(tmp_path, base, None, "")  # recorded on this head
    (tmp_path / "notes.txt").write_text("a later change\n", encoding="utf-8")
    git(tmp_path, "commit", "-q", "-am", "later")  # a new head, with no record
    code, out = judged(tmp_path, base, monkeypatch, capsys)
    assert code == 1 and "FAIL [A1]" in out


def test_attested_with_a_failed_or_incomplete_record_is_refused(tmp_path, monkeypatch, capsys):
    base, _ = change(tmp_path, "attested")
    monkeypatch.setattr(attest, "CHECKS", FAILING)
    attest.run(tmp_path, base, None, "")
    code, out = judged(tmp_path, base, monkeypatch, capsys)
    assert code == 1 and "FAIL [A2]" in out and "Fails" in out
    monkeypatch.setattr(attest, "CHECKS", PASSING)
    attest.run(tmp_path, base, None, "")
    monkeypatch.setattr(attest, "CHECKS", FAILING)  # the list now has a check the record lacks
    code, out = judged(tmp_path, base, monkeypatch, capsys)
    assert code == 1 and "FAIL [A2]" in out and "missing: Fails" in out


def test_attested_with_a_complete_passed_record_is_compliant_and_says_attested(tmp_path, monkeypatch, capsys):
    base, head = change(tmp_path, "attested")
    monkeypatch.setattr(attest, "CHECKS", PASSING)
    attest.run(tmp_path, base, None, "")
    code, out = judged(tmp_path, base, monkeypatch, capsys)
    assert code == 0 and "Checks          : attested on a workstation, by test <test@example.invalid>" in out
    assert "Pull request rules: compliant." in out
