"""D129, ADR-0006: a project's checks run where the team works, and the run is recorded in git,
bound to its commit. Every case proves its rule fails (P5) and names itself (P6). Run by
platform/tests/run.sh.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
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


def judged(root: Path, base: str, monkeypatch, capsys, ci: bool = False) -> tuple[int, str]:
    # The tests themselves run under GitHub Actions in CI: where they run is set, never inherited.
    if ci:
        monkeypatch.setenv("GITHUB_ACTIONS", "true")
    else:
        monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
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


def test_in_ci_an_attested_project_is_not_judged_on_a_record_ci_cannot_fetch(tmp_path, monkeypatch, capsys):
    base, _ = change(tmp_path, "attested")
    code, out = judged(tmp_path, base, monkeypatch, capsys, ci=True)
    assert code == 0 and "attested — judged where nstack attest runs, not in CI" in out


def test_attest_judges_the_pull_request_rules_without_asking_for_the_record_it_is_making(tmp_path, monkeypatch, capsys):
    """Found rehearsing v0.10.0 on the third project: `attest` runs pr-check, which in an attested
    project asked for a record of the head — the one being made. A1 failed inside attest, so
    no record ever passed."""
    base, head = change(tmp_path, "attested")
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    monkeypatch.setenv("PR_BODY", "A change.")
    calls = (attest.Check("Test sheet and cycle", (attest.Step(
        "nstack pr-check", "Test sheet and cycle",
        f'"{sys.executable}" -c "import sys; from napkinstack import pull_request; '
        f'sys.exit(pull_request.run(__import__(\'pathlib\').Path(\'.\'), \'{base}\'))"'),)),)
    monkeypatch.setattr(attest, "CHECKS", calls)
    assert attest.run(tmp_path, base, None, "") == 0, capsys.readouterr().out
    code, out = judged(tmp_path, base, monkeypatch, capsys)
    assert code == 0 and "attested on a workstation" in out


# --- #235: a record never publishes an identity the project does not already show ------------

def shared(root):
    """A remote the record would travel to."""
    git(root, "remote", "add", "origin", str(root))


def stranger(monkeypatch, email="someone@personal.example"):
    monkeypatch.setenv("GIT_COMMITTER_NAME", "Someone")
    monkeypatch.setenv("GIT_COMMITTER_EMAIL", email)


def test_an_identity_the_project_s_history_does_not_show_is_refused_before_any_check(tmp_path, monkeypatch, capsys):
    project(tmp_path)
    shared(tmp_path)
    monkeypatch.setattr(attest, "CHECKS", PASSING)
    stranger(monkeypatch)
    assert attest.run(tmp_path, "HEAD", None, "") == 1
    out = capsys.readouterr().out
    assert "FAIL [attest]" in out and "someone@personal.example" in out and "--accept-identity" in out
    assert "ok   [attest]" not in out  # nothing ran
    shown = subprocess.run(["git", "notes", "--ref=nstack/checks", "show", "HEAD"], cwd=tmp_path, capture_output=True)
    assert shown.returncode != 0  # no record written


def test_a_noreply_address_is_always_accepted(tmp_path, monkeypatch):
    project(tmp_path)
    shared(tmp_path)
    monkeypatch.setattr(attest, "CHECKS", PASSING)
    stranger(monkeypatch, "12345+someone@users.noreply.github.com")
    assert attest.run(tmp_path, "HEAD", None, "") == 0


def test_a_new_contributor_records_once_they_accept_their_identity(tmp_path, monkeypatch):
    project(tmp_path)
    shared(tmp_path)
    monkeypatch.setattr(attest, "CHECKS", PASSING)
    stranger(monkeypatch)
    assert attest.run(tmp_path, "HEAD", None, "", accept_identity=True) == 0
    assert records(tmp_path, git(tmp_path, "rev-parse", "HEAD"))[-1]["by"] == "Someone <someone@personal.example>"


def test_with_no_remote_nothing_travels_and_the_sole_committer_is_never_refused(tmp_path, monkeypatch):
    project(tmp_path)
    monkeypatch.setattr(attest, "CHECKS", PASSING)
    assert attest.run(tmp_path, "origin/main", None, "") == 0


def test_a_base_that_does_not_resolve_is_named_never_an_identity_blamed(tmp_path, monkeypatch, capsys):
    project(tmp_path)
    git(tmp_path, "remote", "add", "origin", str(tmp_path / "nowhere.git"))
    monkeypatch.setattr(attest, "CHECKS", PASSING)
    assert attest.run(tmp_path, "origin/main", None, "") == 1
    out = capsys.readouterr().out
    assert "origin/main" in out and "not found" in out and "history does not show" not in out


@pytest.mark.parametrize("address", ["me@personal.example@users.noreply.github.com",
                                     "x@users.noreply.github.com.evil.org"])
def test_a_personal_address_dressed_as_noreply_is_refused(tmp_path, monkeypatch, address):
    project(tmp_path)
    shared(tmp_path)
    monkeypatch.setattr(attest, "CHECKS", PASSING)
    stranger(monkeypatch, address)
    assert attest.run(tmp_path, "HEAD", None, "") == 1


# --- D162: a record keeps no path of the machine that attested (#277) ------------------------

def test_a_record_keeps_no_path_of_the_machine_that_attested(tmp_path, monkeypatch):
    home = tmp_path / "home" / "someone"
    root = home / "work" / "project"
    root.mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))
    (root / ".gitignore").write_text(".evidence/\n", encoding="utf-8")
    head = project(root)
    (root / ".evidence/e2e").mkdir(parents=True)
    (root / ".evidence/e2e/audit.json").write_text(json.dumps(
        {"commit": head, "module": "m", "undeclared": [f"{root}/log.jsonl: WARN at {home}/.cache"]}), encoding="utf-8")
    monkeypatch.setattr(attest, "CHECKS", (attest.Check("Paths", (attest.Step(
        "echo", "say paths", f'echo "Compiling c ($PWD/modules/m)"; echo "ls: {home}/.local/state"; echo "{home}x"; '
        f'echo "/srv{home}/data {root}~bak"'),)),))
    attest.run(root, "HEAD", None, "")
    [record] = records(root, head)
    output = record["checks"][0]["steps"][0]["output"]
    assert "Compiling c (<root>/modules/m)" in output and "ls: ~/.local/state" in output
    assert f"{home}x" in output  # a folder whose name only starts like the home is another folder
    neighbour = "/".join(["~", "work", "project~bak"])
    assert f"/srv{home}/data {neighbour}" in output  # inside a longer path: not the home; a neighbour: not the root
    assert record["evidence"][0]["audit"]["undeclared"] == ["<root>/log.jsonl: WARN at ~/.cache"]
    assert str(home) not in json.dumps(record).replace(f"{home}x", "").replace(f"/srv{home}/data", "")
# --- D166: a passed module check is kept for the same commit, base and engine (#275) ----------

def counted(root: Path) -> tuple[attest.Check, ...]:
    return (attest.Check("Passes", (attest.Step("echo", "say it", "echo all good"),)),
            attest.Check("Module checks", (attest.Step("count", "count runs", f"echo run >> {root}/../runs"),), kept=True))


def runs(root: Path) -> int:
    return (root.parent / "runs").read_text().count("run") if (root.parent / "runs").exists() else 0


def test_a_passed_module_check_is_kept_for_the_same_commit_base_and_engine(tmp_path, monkeypatch, capsys):
    root = tmp_path / "p"
    root.mkdir()
    head = project(root)
    monkeypatch.setattr(attest, "CHECKS", counted(root))
    monkeypatch.setattr(attest.provenance, "engine", lambda: ("0.17.0", None))
    assert attest.run(root, "HEAD", None, "") == 0 and runs(root) == 1
    first = records(root, head)[0]["at"]
    capsys.readouterr()
    assert attest.run(root, "HEAD", None, "") == 0 and runs(root) == 1
    kept = records(root, head)[-1]["checks"][1]
    assert kept["passed"] and kept["kept_from"] == first, kept
    assert f"ok   [attest] Module checks: kept from the record of {first}" in capsys.readouterr().out
    assert attest.run(root, "HEAD", None, "", again=True) == 0 and runs(root) == 2
    monkeypatch.setattr(attest.provenance, "engine", lambda: ("0.17.1", None))
    assert attest.run(root, "HEAD", None, "") == 0 and runs(root) == 3


@pytest.mark.parametrize("change", ["the base", "a failure", "an engine from a dirty checkout"])
def test_a_module_check_runs_again_when_anything_it_read_may_differ(tmp_path, monkeypatch, change):
    root = tmp_path / "p"
    root.mkdir()
    project(root)
    git(root, "commit", "-q", "--allow-empty", "-m", "second\n\nAgent-Session: a-session")
    monkeypatch.setattr(attest, "CHECKS", counted(root))
    origin = "a local checkout at v0.17.0-dirty" if change.startswith("an engine") else None
    monkeypatch.setattr(attest.provenance, "engine", lambda: ("0.17.0", origin))
    if change == "a failure":
        monkeypatch.setattr(attest, "CHECKS", (attest.Check("Module checks", (attest.Step(
            "count", "count runs", f"echo run >> {root}/../runs; false"),), kept=True),))
    attest.run(root, "HEAD~1", None, "")
    attest.run(root, "HEAD" if change == "the base" else "HEAD~1", None, "")
    assert runs(root) == 2


@pytest.mark.parametrize("origin", ["an archive, not the registry", "a local checkout at an unknown commit"])
def test_an_engine_no_commit_names_never_keeps_a_check(tmp_path, monkeypatch, origin):
    root = tmp_path / "p"
    root.mkdir()
    project(root)
    monkeypatch.setattr(attest, "CHECKS", counted(root))
    monkeypatch.setattr(attest.provenance, "engine", lambda: ("0.17.0", origin))
    attest.run(root, "HEAD", None, "")
    attest.run(root, "HEAD", None, "")
    assert runs(root) == 2


def test_a_check_another_person_passed_is_run_again_and_its_evidence_kept_with_a_kept_check(tmp_path, monkeypatch):
    root = tmp_path / "p"
    root.mkdir()
    head = project(root)
    monkeypatch.setattr(attest, "CHECKS", counted(root))
    monkeypatch.setattr(attest.provenance, "engine", lambda: ("0.17.0", "a local checkout at v0.17.0-1-g792e41a"))
    (root / ".git/info/exclude").write_text(".evidence/\n", encoding="utf-8")
    (root / ".evidence/e2e").mkdir(parents=True)
    audit = root / ".evidence/e2e/audit.json"
    audit.write_text(json.dumps({"commit": head, "module": "m", "verdict": "passed"}), encoding="utf-8")
    attest.run(root, "HEAD", None, "")
    audit.unlink()
    attest.run(root, "HEAD", None, "")
    assert runs(root) == 1 and records(root, head)[-1]["evidence"][0]["module"] == "m"
    monkeypatch.setenv("GIT_COMMITTER_NAME", "other")
    monkeypatch.setenv("GIT_COMMITTER_EMAIL", "other@example.invalid")
    attest.run(root, "HEAD", None, "")
    assert runs(root) == 2


def test_a_malformed_record_is_never_kept_from(tmp_path, monkeypatch):
    root = tmp_path / "p"
    root.mkdir()
    head = project(root)
    monkeypatch.setattr(attest, "CHECKS", counted(root))
    monkeypatch.setattr(attest.provenance, "engine", lambda: ("0.17.0", None))
    attest.run(root, "HEAD", None, "")
    bad = {**records(root, head)[-1], "checks": 7, "at": "9999"}
    git(root, "notes", f"--ref={attest.NOTES}", "append", "-m", json.dumps(bad), head)
    assert attest.run(root, "HEAD", None, "") == 0 and runs(root) == 2


def test_an_engine_installed_from_a_path_under_the_home_keeps_its_check(tmp_path, monkeypatch):
    home = tmp_path / "home"
    root = home / "p"
    root.mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))
    project(root)
    monkeypatch.setattr(attest, "CHECKS", counted(root))
    monkeypatch.setattr(attest.provenance, "engine", lambda: ("0.17.0", f"file://{home}/engine@0123456789ab"))
    attest.run(root, "HEAD", None, "")
    attest.run(root, "HEAD", None, "")
    assert runs(root) == 1
