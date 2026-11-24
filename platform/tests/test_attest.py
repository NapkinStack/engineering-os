"""D129, ADR-0006: a project's checks run where the team works, and the run is recorded in git,
bound to its commit. Every case proves its rule fails (P5) and names itself (P6). Run by
platform/tests/run.sh.
"""

from __future__ import annotations

import base64
import json
import os
import signal
import subprocess
import sys
import time
import urllib.error
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


def module(name: str, noise: int, result: str) -> str:
    """A module's log group as check-modules.sh prints it: its commands, the build's noise, its results."""
    return (f"::group::{name}\nCriticality: standard\n-> {name}: cargo test --locked\n"
            + "   Compiling some-crate v1.0.0\n" * noise + f"test result: {result}\ne2e: passed\n::endgroup::\n")


def test_each_module_keeps_its_own_results_when_the_output_is_cut():
    # The third project's record of a contract change: one cut across the whole lost the middle module's results (#295).
    names = ("capture", "platform", "shell", "transcription", "contracts")
    noise = (700, 30, 2000, 700, 60)
    text = "".join(module(name, n, f"ok. {name} passed") for name, n in zip(names, noise))
    text += "Every changed module passed.\n"
    assert len(text.encode()) > attest.KEPT * 1.5
    kept = attest.capped(text)
    assert len(kept.encode()) <= attest.KEPT
    for name in names:
        assert f"::group::{name}\n" in kept and f"-> {name}: cargo test" in kept
        assert f"test result: ok. {name} passed\ne2e: passed\n::endgroup::" in kept
    assert kept.endswith("Every changed module passed.\n")
    assert module("platform", 30, "ok. platform passed") in kept  # a small module, whole
    assert kept.count("bytes cut") == 3


def test_one_large_module_leaves_the_others_whole():
    text = module("small", 10, "ok. small") + module("large", 20000, "ok. large") + module("tiny", 1, "ok. tiny")
    kept = attest.capped(text)
    assert len(kept.encode()) <= attest.KEPT
    assert module("small", 10, "ok. small") in kept and module("tiny", 1, "ok. tiny") in kept
    assert "test result: ok. large" in kept and kept.count("bytes cut") == 1


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


def with_remote(root: Path) -> Path:
    """The project's remote, a bare repository holding its branch — as the forge would."""
    remote = root.parent / f"{root.name}-remote.git"
    git(root.parent, "init", "-q", "--bare", str(remote))
    git(root, "remote", "add", "origin", str(remote))
    git(root, "push", "-q", "origin", "main")
    return remote


def fresh_checkout(root: Path) -> None:
    """CI's checkout: the branch, and none of the notes a workstation holds."""
    git(root, "update-ref", "-d", f"refs/notes/{attest.NOTES}")


def test_in_ci_the_record_is_read_from_the_remote_and_judged(tmp_path, monkeypatch, capsys):
    """#367: on a fourth project, CI said "compliant" for a head nobody had attested — it never read the
    record. Where the remote answers, the record pushed with the notes is the one judged."""
    project = tmp_path / "p"
    project.mkdir()
    base, _ = change(project, "attested")
    with_remote(project)
    monkeypatch.setattr(attest, "CHECKS", PASSING)
    attest.run(project, base, None, "")  # pushes the record with the notes
    fresh_checkout(project)
    code, out = judged(project, base, monkeypatch, capsys, ci=True)
    assert code == 0 and "attested on a workstation, by test <test@example.invalid>" in out, out


def test_in_ci_a_head_with_no_record_on_the_remote_is_refused(tmp_path, monkeypatch, capsys):
    project = tmp_path / "p"
    project.mkdir()
    base, head = change(project, "attested")
    with_remote(project)
    code, out = judged(project, base, monkeypatch, capsys, ci=True)
    assert code == 1 and f"FAIL [A1] no record of the head {head[:7]}" in out, out
    assert "Pull request rules: compliant." not in out


def test_in_ci_a_failed_record_on_the_remote_is_refused(tmp_path, monkeypatch, capsys):
    project = tmp_path / "p"
    project.mkdir()
    base, _ = change(project, "attested")
    with_remote(project)
    monkeypatch.setattr(attest, "CHECKS", FAILING)
    attest.run(project, base, None, "")
    fresh_checkout(project)
    code, out = judged(project, base, monkeypatch, capsys, ci=True)
    assert code == 1 and "FAIL [A2]" in out, out


def test_in_ci_a_record_that_cannot_be_read_is_said_never_called_compliant_silently(tmp_path, monkeypatch, capsys):
    """No remote, or one that refuses: the record is unread — a warning, not a failure, and never the
    silent line that let an unattested head through (#367)."""
    base, _ = change(tmp_path, "attested")
    code, out = judged(tmp_path, base, monkeypatch, capsys, ci=True)
    assert code == 0 and "WARNING [A1] the record of the head is not read here" in out, out
    assert "judged where nstack attest runs" not in out


def test_in_ci_a_remote_that_refuses_is_warned_with_git_s_reason(tmp_path, monkeypatch, capsys):
    project = tmp_path / "p"
    project.mkdir()
    base, _ = change(project, "attested")
    git(project, "remote", "add", "origin", str(tmp_path / "gone.git"))  # a remote that does not answer
    code, out = judged(project, base, monkeypatch, capsys, ci=True)
    assert code == 0 and "WARNING [A1] the record of the head is not read here (origin did not answer: fatal:" in out, out
    assert "FAIL [A1]" not in out


SECRET = base64.b64encode(b"x-access-token:tok123").decode()


def test_the_fetch_authenticates_with_the_job_token_in_the_environment_never_an_argument(monkeypatch, capsys):
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    env = attest.fetch_env("https://github.com/org/repo", "tok123")
    assert env["GIT_CONFIG_COUNT"] == "1"
    assert env["GIT_CONFIG_KEY_0"] == "http.https://github.com/.extraheader"
    assert env["GIT_CONFIG_VALUE_0"] == f"AUTHORIZATION: basic {SECRET}"
    assert f"::add-mask::{SECRET}" in capsys.readouterr().out  # the runner never prints it in clear
    assert attest.fetch_env("https://github.com/org/repo", None) == {}
    assert attest.fetch_env("/some/path.git", "tok123") == {}  # a token goes to GitHub only
    monkeypatch.delenv("GITHUB_ACTIONS")
    assert attest.fetch_env("https://github.com/org/repo", "tok123") == {}  # never on a workstation


class Recorded:
    """git as read_remote calls it: each call's arguments and environment, answered as asked."""

    def __init__(self, answers):
        self.calls, self.answers, self.real = [], answers, subprocess.run

    def __call__(self, args, **kwargs):
        if args[1] not in self.answers:  # the local reads go to git itself
            return self.real(args, **kwargs)
        self.calls.append((args, kwargs.get("env") or {}))
        code, out, err = self.answers[args[1]]
        return subprocess.CompletedProcess(args, code, out, err)


def github_project(root: Path) -> None:
    git(root, "init", "-q", "--initial-branch=main")
    git(root, "remote", "add", "origin", "https://github.com/org/repo.git")


@pytest.mark.parametrize("ci", [True, False])
def test_the_token_reaches_git_in_ci_and_only_there(tmp_path, monkeypatch, ci):
    """On a workstation a token in the environment, perhaps expired, would be sent before the
    remote's own credential and refuse the fetch (#373's verifier)."""
    github_project(tmp_path)
    monkeypatch.setenv("GH_TOKEN", "tok123")
    monkeypatch.setenv("GITHUB_ACTIONS", "true") if ci else monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    recorded = Recorded({"ls-remote": (0, "", "")})
    monkeypatch.setattr(attest.subprocess, "run", recorded)
    assert attest.read_remote(tmp_path) == ("origin", None)
    args, env = recorded.calls[0]
    assert args[1] == "ls-remote" and "tok123" not in " ".join(args) and SECRET not in " ".join(args)
    assert (env.get("GIT_CONFIG_VALUE_0") == f"AUTHORIZATION: basic {SECRET}") is ci


def test_notes_listed_but_not_fetched_are_unread_not_read(tmp_path, monkeypatch):
    github_project(tmp_path)
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    recorded = Recorded({"ls-remote": (0, "abc123\trefs/notes/nstack/checks\n", ""),
                         "fetch": (128, "", "remote: some detail\nfatal: unable to access 'x': refused\nmore\n")})
    monkeypatch.setattr(attest.subprocess, "run", recorded)
    assert attest.read_remote(tmp_path) == ("origin", "origin's notes not fetched: fatal: unable to access 'x': refused")


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


@pytest.mark.parametrize("change", ["a failure", "an engine from a dirty checkout"])
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


def test_in_ci_a_required_local_checks_status_judges_the_record_and_the_run_defers_to_it(tmp_path, monkeypatch, capsys):
    """#399: the record is made after the description's last edit (D214) and travels by notes, which
    start no run: the run before it stayed red. Where the base branch's rules require the record's
    own status, that status — posted by nstack attest with the record — is the record's verdict."""
    project = tmp_path / "p"
    project.mkdir()
    base, _ = change(project, "attested")
    with_remote(project)
    monkeypatch.setattr(pull_request, "status_required", lambda root: True)
    code, out = judged(project, base, monkeypatch, capsys, ci=True)
    assert code == 0 and "FAIL [A1]" not in out, out
    assert f"judged by the required status '{attest.CONTEXT}'" in out, out
    monkeypatch.setattr(attest, "CHECKS", FAILING)
    attest.run(project, base, None, "")
    fresh_checkout(project)
    code, out = judged(project, base, monkeypatch, capsys, ci=True)
    assert code == 0 and "FAIL [A2]" not in out, "a failed record is the status's red, never a run's that stays"
    assert "WARNING [A2] the latest record of the head" in out, "a failed record the status may not show is said"


def test_in_ci_without_the_required_status_a_head_with_no_record_names_both_ways_out(tmp_path, monkeypatch, capsys):
    project = tmp_path / "p"
    project.mkdir()
    base, _ = change(project, "attested")
    with_remote(project)
    monkeypatch.setattr(pull_request, "status_required", lambda root: False)
    code, out = judged(project, base, monkeypatch, capsys, ci=True)
    assert code == 1 and "FAIL [A1]" in out and f"require the status '{attest.CONTEXT}'" in out, out


@pytest.mark.parametrize(("rules", "required"), [
    ([{"type": "required_status_checks", "parameters": {"required_status_checks": [
        {"context": "Test sheet and cycle"}, {"context": attest.CONTEXT}]}}], True),
    ([{"type": "required_status_checks", "parameters": {"required_status_checks": [
        {"context": "Test sheet and cycle"}]}},
      {"type": "pull_request", "parameters": {"required_status_checks": [{"context": attest.CONTEXT}]}}], False),
    (None, False),
])
def test_the_base_branch_s_rules_say_whether_the_status_is_required(tmp_path, monkeypatch, rules, required):
    read = []

    class Answer:
        def __init__(self, request):
            read.append(request.full_url)

        def __enter__(self):
            if rules is None:
                raise urllib.error.URLError("refused")
            return self

        def __exit__(self, *_):
            return False

        def read(self):
            return json.dumps(rules).encode()

    monkeypatch.setattr(pull_request.urllib.request, "urlopen", lambda request, timeout=None: Answer(request))
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setenv("GITHUB_REPOSITORY", "owner/p")
    monkeypatch.setenv("GITHUB_BASE_REF", "release/1")
    monkeypatch.setenv("GH_TOKEN", "t")
    monkeypatch.delenv("GITHUB_API_URL", raising=False)
    assert pull_request.status_required(tmp_path) is required
    assert read == ["https://api.github.com/repos/owner/p/rules/branches/release%2F1?per_page=100"]
    monkeypatch.delenv("GITHUB_ACTIONS")
    assert pull_request.status_required(tmp_path) is False, "a workstation's pr-check reads the record itself"


def test_attest_refuses_a_label_the_pull_request_does_not_carry_and_records_where_labels_came_from(
        tmp_path, monkeypatch, capsys):
    """#368: a record held "justified by label" of a label no pull request carried."""
    from napkinstack import hold

    base, head = change(tmp_path, "attested")
    monkeypatch.setattr(attest, "CHECKS", PASSING)
    monkeypatch.setattr(hold, "_forge", lambda root, name: ("https://api.example", "owner/p", "t"))
    monkeypatch.setattr(hold, "_call", lambda forge, method, path, body=None: [
        {"number": 7, "state": "open", "head": {"sha": head}, "labels": [{"name": "cross-module"}]}])
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    assert attest.run(tmp_path, base, None, "over-budget") == 1
    out = capsys.readouterr().out
    assert "FAIL [attest] pull request #7 carries no label over-budget" in out, out
    assert attest.latest(tmp_path, head) is None, "nothing recorded on a refused label"
    assert attest.run(tmp_path, base, None, None) == 0
    assert attest.latest(tmp_path, head)["labels"] == {"names": ["cross-module"], "from": "read from pull request #7"}



# --- D223: a passed module check is kept while its inputs are unchanged (#406) ----------------

def modular(root: Path) -> str:
    """main holds modules a (consumes b), b and c; branch `work` changes a. Returns main's name."""
    git(root, "init", "-q", "--initial-branch=main")
    for name, consumes in (("a", [{"contract": "b-api", "version": "v1", "module": "b"}]), ("b", []), ("c", [])):
        folder = root / "modules" / name
        folder.mkdir(parents=True)
        (folder / "MANIFEST.yaml").write_text(yaml.safe_dump({"module": {"name": name}, "consumes": consumes}),
                                              encoding="utf-8")
        (folder / "code.py").write_text("x = 1\n", encoding="utf-8")
    for shared in ("contracts", "platform"):
        (root / shared).mkdir()
        (root / shared / "MANIFEST.yaml").write_text(yaml.safe_dump({"module": {"name": shared}}), encoding="utf-8")
        (root / shared / "doc.md").write_text("v1\n", encoding="utf-8")
    (root / "uv.lock").write_text("lock 1\n", encoding="utf-8")
    (root / "docs/project").mkdir(parents=True)
    (root / "docs/project/rules.md").write_text("rule 1\n", encoding="utf-8")
    (root / "docs/project/résumé.md").write_text("résumé 1\n", encoding="utf-8")
    (root / "docs/privacy.md").write_text("paths 1\n", encoding="utf-8")
    (root / ".copier-answers.yml").write_text(yaml.safe_dump({"_commit": "v0.9.6", "checks": "attested"}),
                                              encoding="utf-8")
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "first\n\nAgent-Session: a-session")
    git(root, "switch", "-q", "-c", "work")
    (root / "modules/a/code.py").write_text("x = 2\n", encoding="utf-8")
    git(root, "commit", "-q", "-am", "a moves\n\nAgent-Session: a-session")
    return "main"


def main_moves(root: Path, path: str) -> None:
    """Another change lands on main, and the branch merges main in."""
    git(root, "switch", "-q", "main")
    target = root / path
    target.write_text(target.read_text(encoding="utf-8") + "more\n", encoding="utf-8")
    git(root, "commit", "-q", "-am", f"{path} moves")
    git(root, "switch", "-q", "work")
    git(root, "merge", "-q", "--no-edit", "main")


@pytest.fixture
def counting(tmp_path, monkeypatch):
    root = tmp_path / "p"
    root.mkdir()
    monkeypatch.setattr(attest, "CHECKS", counted(root))
    monkeypatch.setattr(attest.provenance, "engine", lambda: ("0.17.0", None))
    return root


@pytest.mark.parametrize("path", ["modules/c/code.py", "docs/project/rules.md", "docs/project/résumé.md"])
def test_a_merge_in_that_touches_nothing_the_module_reads_keeps_its_check(counting, capsys, path):
    """#441 (D242): the project's records under the root `docs/` are read by no module check; a line
    of a rules document merged on main cost every open pull request its end-to-end runs again."""
    root = counting
    base = modular(root)
    first_head = git(root, "rev-parse", "HEAD")
    assert attest.run(root, base, None, "") == 0 and runs(root) == 1
    main_moves(root, path)
    capsys.readouterr()
    assert attest.run(root, base, None, "") == 0 and runs(root) == 1
    head = git(root, "rev-parse", "HEAD")
    kept = records(root, head)[-1]["checks"][1]
    assert kept["kept_commit"] == first_head and kept["inputs"] == records(root, first_head)[-1]["checks"][1]["inputs"]
    assert f"kept from the run on {first_head[:7]}" in capsys.readouterr().out


@pytest.mark.parametrize("path", ["modules/b/code.py", "uv.lock", "modules/a/code.py", "contracts/doc.md",
                                  "platform/doc.md", "docs/privacy.md"])
def test_a_merge_in_that_touches_what_the_module_reads_runs_it_again(counting, path):
    root = counting
    base = modular(root)
    attest.run(root, base, None, "")
    if path == "modules/a/code.py":  # the module itself moves on the branch
        (root / path).write_text("x = 3\n", encoding="utf-8")
        git(root, "commit", "-q", "-am", "a again")
    else:
        main_moves(root, path)
    attest.run(root, base, None, "")
    assert runs(root) == 2


@pytest.mark.parametrize("bound", ["FRESH_DAYS", "FRESH_COMMITS"])
def test_a_kept_result_expires(counting, monkeypatch, bound):
    root = counting
    base = modular(root)
    attest.run(root, base, None, "")
    main_moves(root, "modules/c/code.py")
    monkeypatch.setattr(attest, bound, 0 if bound == "FRESH_COMMITS" else -1)
    attest.run(root, base, None, "")
    assert runs(root) == 2


def test_a_kept_result_keeps_its_first_run_s_age(counting, monkeypatch):
    """Kept from a kept one, the age is the first run's: keeping never makes a result younger."""
    root = counting
    base = modular(root)
    attest.run(root, base, None, "")
    first = records(root, git(root, "rev-parse", "HEAD"))[-1]["at"]
    main_moves(root, "modules/c/code.py")
    attest.run(root, base, None, "")
    main_moves(root, "README.md" if (root / "README.md").exists() else "modules/c/code.py")
    attest.run(root, base, None, "")
    assert runs(root) == 1
    assert records(root, git(root, "rev-parse", "HEAD"))[-1]["checks"][1]["kept_from"] == first


def test_a_consumes_naming_no_module_is_no_key(counting):
    root = counting
    base = modular(root)
    manifest = root / "modules/a/MANIFEST.yaml"
    manifest.write_text(yaml.safe_dump({"module": {"name": "a"}, "consumes": [{"contract": "z", "version": "v1",
                                                                               "module": "nowhere"}]}), encoding="utf-8")
    git(root, "commit", "-q", "-am", "a consumes from nowhere")
    attest.run(root, base, None, "")
    main_moves(root, "modules/c/code.py")
    attest.run(root, base, None, "")
    assert runs(root) == 2


def test_pr_check_lets_an_automated_row_stand_across_a_merge_in_that_kept_the_module_check(counting, monkeypatch, capsys):
    """D223, end to end: the row was run at the first head; main merged in changed only module c."""
    from napkinstack import pull_request

    root = counting
    base = modular(root)
    first = git(root, "rev-parse", "HEAD")
    attest.run(root, base, None, "")
    main_moves(root, "modules/c/code.py")
    attest.run(root, base, None, "")
    head = git(root, "rev-parse", "HEAD")
    same = pull_request.same_inputs(root, head, base)
    main = git(root, "rev-parse", "main")
    assert same(first[:7]) is None
    assert same(main[:7]) == (f"{main[:7]} has no passing record of its module checks: nstack attest with {main[:7]} checked out, "
                              "and the row stands while what its modules read is unchanged since"), "#491: why, and the cheap path"
    monkeypatch.setattr(attest, "FRESH_DAYS", -1)
    assert "is older than -1 days" in pull_request.same_inputs(root, head, base)(first[:7]), "past the bound, re-run"


def test_t4_s_relief_reads_the_records_the_remote_holds_in_a_fresh_clone(counting, tmp_path):
    """The verifier's finding on #491: read before the head's digest, the row's commit's record was never
    fetched in CI's clone, and T4 said it had none."""
    from napkinstack import pull_request

    root = counting
    base = modular(root)
    first = git(root, "rev-parse", "HEAD")
    attest.run(root, base, None, "")
    main_moves(root, "modules/c/code.py")
    attest.run(root, base, None, "")
    head = git(root, "rev-parse", "HEAD")
    bare = tmp_path / "remote.git"
    subprocess.run(["git", "init", "-q", "--bare", str(bare)], check=True)
    git(root, "remote", "add", "origin", str(bare))
    git(root, "push", "-q", "origin", "main", "work", f"refs/notes/{attest.NOTES}")
    clone = tmp_path / "clone"
    subprocess.run(["git", "clone", "-q", "-b", "work", str(bare), str(clone)], check=True)
    git(clone, "branch", "-q", "main", "origin/main")
    assert pull_request.same_inputs(clone, head, base)(first[:7]) is None


def test_t4_says_when_the_head_has_no_record_yet(counting):
    """#491: pr-check run before the head is attested names that, not a change of inputs."""
    from napkinstack import pull_request

    root = counting
    base = modular(root)
    first = git(root, "rev-parse", "HEAD")
    attest.run(root, base, None, "")
    main_moves(root, "modules/c/code.py")
    head = git(root, "rev-parse", "HEAD")
    assert pull_request.same_inputs(root, head, base)(first[:7]) == (
        f"the head {head[:7]} has no passing record of its module checks yet: nstack attest on it, "
        "and the row stands while what its modules read is unchanged since")



def test_the_forge_s_run_leaves_a_row_waiting_for_the_head_s_record_to_the_required_status(counting, monkeypatch):
    """#495: the forge's run starts at the push, before nstack attest writes the head's record. Where the
    ruleset requires attest's status, T4 does not fail for want of that record, as A1 does not: the row
    waits, it is said, and attest's own run judges it with the digest. A row whose commit has no record
    still fails here: attest at the head would not keep it either."""
    from napkinstack import pull_request

    root = counting
    base = modular(root)
    first = git(root, "rev-parse", "HEAD")
    attest.run(root, base, None, "")
    main_moves(root, "modules/c/code.py")
    head = git(root, "rev-parse", "HEAD")
    main = git(root, "rev-parse", "main")
    said: list[str] = []
    monkeypatch.setattr(pull_request, "status_required", lambda root: True)
    same = pull_request.same_inputs(root, head, base, said.append)
    assert same(first[:7]) is None
    assert same(first[:7]) is None
    assert len(said) == 1 and said[0].startswith(f"[T4] automated rows run at {first[:7]} wait for the record of the "
                                                 f"head {head[:7]}: the required status '{attest.CONTEXT}' judges them"), said
    assert f"Action: nstack attest on the head {head[:7]}" in said[0]
    assert same(main[:7]).startswith(f"{main[:7]} has no passing record of its module checks"), \
        "the row's commit has no record: attest at the head would not keep it"
    monkeypatch.setattr(pull_request, "status_required", lambda root: False)
    assert pull_request.same_inputs(root, head, base)(first[:7]).startswith(f"the head {head[:7]} has no passing record"), \
        "the status not required: the run judges, as before"


def test_a_head_record_without_a_digest_or_attest_s_own_run_never_waits(counting, monkeypatch):
    """D269's verifier: only a head with no record at all waits for one. A record that holds no digest —
    its module checks failed, kept from a voided run — and attest's own run, which makes the record,
    are judged as before."""
    from napkinstack import pull_request

    root = counting
    base = modular(root)
    first = git(root, "rev-parse", "HEAD")
    attest.run(root, base, None, "")
    main_moves(root, "modules/c/code.py")
    head = git(root, "rev-parse", "HEAD")
    monkeypatch.setattr(pull_request, "status_required", lambda root: True)
    monkeypatch.setattr(attest, "latest", lambda root, commit, real=attest.latest: real(root, commit) or
                        ({"checks": [{"name": "Module checks", "passed": False}]} if commit == head else None))
    said: list[str] = []
    assert pull_request.same_inputs(root, head, base, said.append)(first[:7]).startswith(f"the head {head[:7]} has no"), said
    monkeypatch.undo()
    monkeypatch.setattr(attest, "CHECKS", counted(root))
    monkeypatch.setattr(pull_request, "status_required", lambda root: True)
    monkeypatch.setenv("NSTACK_ATTESTING", head)
    monkeypatch.setenv("NSTACK_INPUTS", "")
    assert pull_request.same_inputs(root, head, base, said.append)(first[:7]).startswith(f"the head {head[:7]} has no")
    assert said == []


def test_pr_check_prints_what_t4_s_relief_says(tmp_path, monkeypatch, capsys):
    """D269's verifier: the warning travels from T4's relief to pr-check's output, and fails nothing."""
    base, _ = change(tmp_path, "attested")

    def saying(root, head, base, warn):
        warn("[T4] a row waits")
        return lambda commit: None

    monkeypatch.setattr(pull_request, "same_inputs", saying)
    _, out = judged(tmp_path, base, monkeypatch, capsys)
    assert "WARNING [T4] a row waits" in out, out


def test_a_head_attested_again_never_outlives_the_bound_of_the_run_it_kept(counting, monkeypatch):
    """The verifier's finding on D223: a same-commit keep (D166) carried a result kept by inputs past
    its seven days."""
    root = counting
    base = modular(root)
    attest.run(root, base, None, "")
    main_moves(root, "modules/c/code.py")
    attest.run(root, base, None, "")
    assert runs(root) == 1
    monkeypatch.setattr(attest, "FRESH_DAYS", -1)
    attest.run(root, base, None, "")
    assert runs(root) == 2


def test_a_base_that_changes_the_modules_run_runs_the_check_again(counting):
    root = counting
    base = modular(root)
    attest.run(root, base, None, "")
    attest.run(root, "HEAD~1", None, "")  # same module a; nothing else differs
    assert runs(root) == 1
    (root / "modules/c/code.py").write_text("x = 9\n", encoding="utf-8")
    git(root, "commit", "-q", "-am", "c too")
    attest.run(root, base, None, "")  # modules a and c now: another set
    assert runs(root) == 2


def test_t4_s_relief_reads_attest_s_digest_while_it_makes_the_record_and_only_where_checks_are_attested(
        counting, monkeypatch):
    from napkinstack import pull_request

    root = counting
    base = modular(root)
    first = git(root, "rev-parse", "HEAD")
    attest.run(root, base, None, "")
    digest = records(root, first)[-1]["checks"][1]["inputs"]
    main_moves(root, "modules/c/code.py")
    head = git(root, "rev-parse", "HEAD")
    monkeypatch.setenv("NSTACK_ATTESTING", head)
    monkeypatch.setenv("NSTACK_INPUTS", digest)
    assert pull_request.same_inputs(root, head, base)(first) is None
    monkeypatch.setenv("NSTACK_INPUTS", "0" * 64)
    assert pull_request.same_inputs(root, head, base)(first).startswith(
        f"what its modules read changed between {first} and the head {head[:7]}")
    monkeypatch.setenv("NSTACK_INPUTS", digest)
    (root / ".copier-answers.yml").write_text(yaml.safe_dump({"_commit": "v0.9.6"}), encoding="utf-8")
    assert pull_request.same_inputs(root, head, base)(first) == "", "the forge's CI replays it: nothing to say"


def test_a_dependency_bot_s_head_is_attested_as_it_stands_by_the_project_s_identity(tmp_path, monkeypatch, capsys):
    """#371: on attested checks, a dependency update opened by a bot carries no record, and an agent's
    App cannot ask the bot to rebase. The route: the agent checks the bot's head out as it stands and
    attests it — the record names who ran the checks, never who wrote the commit."""
    project = tmp_path / "p"
    project.mkdir()
    base, _ = change(project, "attested")
    with_remote(project)
    git(project, "checkout", "-q", "-b", "dependabot/pre-commit/x", base)
    (project / ".pre-commit-config.yaml").write_text("repos: []\n", encoding="utf-8")
    git(project, "add", "-A")
    bot = {"GIT_AUTHOR_NAME": "dependabot[bot]", "GIT_AUTHOR_EMAIL": "49699333+dependabot[bot]@users.noreply.github.com",
           "GIT_COMMITTER_NAME": "GitHub", "GIT_COMMITTER_EMAIL": "noreply@github.com"}
    subprocess.run(["git", "commit", "-q", "-m", "Bump the pre-commit group"], cwd=project, check=True,
                   env={**os.environ, **bot})
    head = git(project, "rev-parse", "HEAD")
    git(project, "push", "-q", "origin", "HEAD")
    git(project, "checkout", "-q", "--detach", head)  # as `git fetch origin pull/<n>/head` leaves it
    monkeypatch.setattr(attest, "CHECKS", PASSING)
    assert attest.run(project, base, None, "") == 0, capsys.readouterr().out
    [record] = records(project, head)
    assert record["by"] == "test <test@example.invalid>" and record["commit"] == head
    fresh_checkout(project)
    code, out = judged(project, base, monkeypatch, capsys, ci=True)
    assert code == 0 and "attested on a workstation, by test <test@example.invalid>" in out, out


# --- A failed module check names what failed, and keeps its whole output (D237, #428) ---
# Measured downstream on 2026-11-18: a flaky test failed under `nstack attest`, which said only
# "`cargo test --locked` exited with 101"; run again by hand it passed, and its name was lost.

CARGO = "\n".join([
    "::group::shell",
    "Criticality: standard",
    "-> shell: cargo test --locked",
    *[f"test tests::case_{n} ... ok" for n in range(400)],
    "test tests::flaky_window ... FAILED",
    "failures:",
    "    tests::flaky_window",
    "test result: FAILED. 400 passed; 1 failed; 0 ignored",
    "FAIL [test] module 'shell': `cargo test --locked` exited with 101.",
    "::endgroup::",
    "Module checks failed: shell. Each one's log group above names the verb and its output.",
])


def test_a_failed_module_check_says_its_tool_s_last_lines_and_keeps_its_output(tmp_path, monkeypatch, capsys):
    head = project(tmp_path)
    script = tmp_path.parent / f"{tmp_path.name}-say.txt"  # outside the tree: a record names a clean commit
    script.write_text(CARGO + "\n", encoding="utf-8")
    monkeypatch.setattr(attest, "CHECKS", (attest.Check("Module checks", (
        attest.Step("bash .nstack/check-modules.sh", "Every changed module", f"cat {script}; exit 1"),)),))
    assert attest.run(tmp_path, "HEAD", None, "") == 1
    out = capsys.readouterr().out
    assert "test tests::flaky_window ... FAILED" in out and "test result: FAILED. 400 passed; 1 failed" in out, out
    assert "test tests::case_7 ... ok" not in out, "the whole output printed"
    log = tmp_path / ".git" / "nstack" / "attest" / f"{head[:12]}-module-checks.log"
    assert f"whole output: {log.relative_to(tmp_path)}" in out, out
    assert log.read_text(encoding="utf-8") == CARGO + "\n"
    assert git(tmp_path, "status", "--porcelain") == "", "the log left a change in the tree"


def test_a_passed_check_leaves_no_log(tmp_path, monkeypatch):
    project(tmp_path)
    monkeypatch.setattr(attest, "CHECKS", PASSING)
    assert attest.run(tmp_path, "HEAD", None, "") == 0
    assert not (tmp_path / ".git" / "nstack" / "attest").exists()


def test_each_module_s_failure_says_its_own_tool_lines_and_never_the_engine_s():
    """Its neighbours: a module that passed before says nothing under another's failure, an e2e's
    evidence audit is the engine's, and a nested run's lines are said once."""
    output = "\n".join([
        "::group::calendar", "-> calendar: pytest", "calendar passed line", "::endgroup::",
        "::group::shell", "-> shell: run-scenarios", "scenario login ... FAILED", "summary: 1 failed",
        "Evidence of shell: .evidence/e2e/shell — 3 undeclared (output.txt)",
        "  undeclared: something the engine says",
        "FAIL [e2e] module 'shell': `run-scenarios` exited with 1.",
        "::endgroup::",
    ])
    said = attest.why(output)
    assert said[:2] == ["scenario login ... FAILED", "summary: 1 failed"], said
    assert "calendar passed line" not in said and not any("undeclared" in line for line in said), said
    nested = "\n".join(["-> outer: nstack test inner", "-> inner: cargo test", "test x ... FAILED",
                        "FAIL [test] module 'inner': `cargo test` exited with 101.",
                        "FAIL [test] module 'outer': `nstack test inner` exited with 101."])
    assert attest.why(nested).count("test x ... FAILED") == 1


def test_a_step_that_prints_bytes_not_utf_8_is_recorded(tmp_path, monkeypatch):
    head = project(tmp_path)
    monkeypatch.setattr(attest, "CHECKS", (attest.Check("Bytes", (attest.Step("bytes", "latin", r"printf 'caf\351\n'; exit 1"),)),))
    assert attest.run(tmp_path, "HEAD", None, "") == 1
    assert "caf" in records(tmp_path, head)[0]["checks"][0]["steps"][0]["output"]


# --- A record known unsound is voided, and never kept from (D238, #429) ---
# Measured downstream on 2026-11-18: two attests shared one build folder for half an hour; a later
# attest on the same commit kept the module checks of one of their records, and only an operator's
# memory of --again stood between an unsound record and its reuse.

def test_a_voided_record_is_never_kept_from_on_its_commit(tmp_path, monkeypatch, capsys):
    root = tmp_path / "p"
    root.mkdir()
    head = project(root)
    monkeypatch.setattr(attest, "CHECKS", counted(root))
    monkeypatch.setattr(attest.provenance, "engine", lambda: ("0.17.0", None))
    assert attest.run(root, "HEAD", None, "") == 0 and runs(root) == 1
    capsys.readouterr()
    assert attest.void(root, "HEAD", "two attests shared one build folder") == 0
    out = capsys.readouterr().out
    assert f"Record of {head[:12]}: voided by test <test@example.invalid> — two attests shared one build folder" in out, out
    last = records(root, head)[-1]
    assert last["void"] == "two attests shared one build folder" and last["checks"] == []
    assert attest.run(root, "HEAD", None, "") == 0 and runs(root) == 2, "kept from a voided record"


def test_a_check_kept_by_its_inputs_from_a_voided_commit_runs_again(counting):
    root = counting
    base = modular(root)
    first = git(root, "rev-parse", "HEAD")
    attest.run(root, base, None, "")
    main_moves(root, "modules/c/code.py")
    attest.run(root, base, None, "")  # kept from the first commit's run
    assert runs(root) == 1
    assert attest.void(root, first, "unsound run") == 0
    main_moves(root, "modules/c/code.py")
    attest.run(root, base, None, "")
    assert runs(root) == 2, "a check kept, through another commit's record, from a voided one"


def test_void_needs_a_reason_and_a_record(tmp_path, capsys):
    project(tmp_path)
    assert attest.void(tmp_path, "HEAD", " ") == 1
    assert "FAIL [attest] a void says why" in capsys.readouterr().out
    assert attest.void(tmp_path, "HEAD", "why") == 1
    assert "no record of" in capsys.readouterr().out


def test_pr_check_reads_a_voided_head_as_voided_until_attested_again(tmp_path, monkeypatch, capsys):
    base, head = change(tmp_path, "attested")
    monkeypatch.setattr(attest, "CHECKS", PASSING)
    attest.run(tmp_path, base, None, "")
    attest.void(tmp_path, "HEAD", "shared a build folder")
    code, out = judged(tmp_path, base, monkeypatch, capsys)
    assert code == 1 and f"FAIL [A2] the record of the head {head[:7]} was voided by test <test@example.invalid>" in out, out
    assert "shared a build folder" in out and "nstack attest" in out
    attest.run(tmp_path, base, None, "")
    code, out = judged(tmp_path, base, monkeypatch, capsys)
    assert code == 0, out


def test_a_head_that_kept_a_check_from_a_voided_run_is_refused_and_keeps_it_no_more(counting, monkeypatch, capsys):
    """The verifier's: Y kept X's module check; X voided — pr-check and the next keep both refuse Y's."""
    root = counting
    base = modular(root)  # its answers say checks: attested
    first = git(root, "rev-parse", "HEAD")
    attest.run(root, base, None, "")
    main_moves(root, "modules/c/code.py")
    attest.run(root, base, None, "")  # kept from the first
    head = git(root, "rev-parse", "HEAD")
    assert runs(root) == 1
    assert attest.void(root, first, "shared a build folder", base) == 0
    capsys.readouterr()
    code, out = judged(root, base, monkeypatch, capsys)
    assert code == 1 and f"FAIL [A2] the record of the head {head[:7]} keeps Module checks from a run since voided" in out, out
    attest.run(root, base, None, "", again=False)
    assert runs(root) == 2, "kept again, through its own record, from the voided run"


def test_attesting_a_voided_commit_again_never_brings_its_old_run_back(counting):
    root = counting
    base = modular(root)
    first = git(root, "rev-parse", "HEAD")
    attest.run(root, base, None, "")
    main_moves(root, "modules/c/code.py")
    attest.run(root, base, None, "")  # Y keeps from X
    voided = records(root, first)[0]["at"]
    attest.void(root, first, "unsound", base)
    git(root, "switch", "-q", "--detach", first)
    attest.run(root, base, None, "", again=True)  # X attested again: a sound run of its own
    sound = attest.latest(root, first)["at"]
    git(root, "switch", "-q", "work")
    main_moves(root, "modules/c/code.py")
    attest.run(root, base, None, "")
    kept = attest.latest(root, git(root, "rev-parse", "HEAD"))["checks"][1]
    assert kept["kept_from"] == sound != voided, "Z kept, through Y's record, X's voided run"


def test_a_voided_run_with_a_clock_ahead_stays_voided(tmp_path, monkeypatch):
    root = tmp_path / "p"
    root.mkdir()
    head = project(root)
    monkeypatch.setattr(attest, "CHECKS", counted(root))
    monkeypatch.setattr(attest.provenance, "engine", lambda: ("0.17.0", None))
    attest.run(root, "HEAD", None, "")
    lines = git(root, "notes", f"--ref={attest.NOTES}", "show", head).strip().splitlines()
    ahead = json.loads(lines[-1]) | {"at": "2999-01-01T00:00:00+00:00"}
    git(root, "notes", f"--ref={attest.NOTES}", "add", "-f", "-m", json.dumps(ahead), head)
    assert attest.void(root, "HEAD", "its clock lied") == 0
    assert attest.latest(root, head)["void"] == "its clock lied"
    attest.run(root, "HEAD", None, "")
    assert runs(root) == 2


def test_a_void_never_publishes_an_identity_the_project_does_not_show(tmp_path, monkeypatch, capsys):
    root = tmp_path / "p"
    root.mkdir()
    project(root)
    monkeypatch.setattr(attest, "CHECKS", PASSING)
    attest.run(root, "HEAD", None, "")
    git(root, "remote", "add", "origin", str(tmp_path / "nowhere.git"))
    monkeypatch.setenv("GIT_COMMITTER_EMAIL", "someone@personal.example")
    capsys.readouterr()
    assert attest.void(root, "HEAD", "why", "HEAD") == 1
    assert "FAIL [attest] the void would name" in capsys.readouterr().out


@pytest.mark.parametrize("argv", [["attest", "--reason", "x"], ["attest", "--void", "HEAD"],
                                  ["attest", "--void", "HEAD", "--reason", "x", "--again"]])
def test_void_and_its_reason_go_together_and_with_no_run(argv, capsys):
    from napkinstack import cli
    with pytest.raises(SystemExit):
        cli.main(argv)
    assert "--void and --reason go together" in capsys.readouterr().err


def test_a_run_kept_on_its_commit_from_a_run_voided_meanwhile_is_kept_from_no_more(tmp_path, monkeypatch):
    """The verifier's: another clone, before seeing the void, kept R1 in R2 on the same commit; the
    notes merge, R2 is the latest — the next attest must run, not keep R1 again through R2."""
    root = tmp_path / "p"
    root.mkdir()
    head = project(root)
    monkeypatch.setattr(attest, "CHECKS", counted(root))
    monkeypatch.setattr(attest.provenance, "engine", lambda: ("0.17.0", None))
    attest.run(root, "HEAD", None, "")
    attest.run(root, "HEAD", None, "")  # R2 keeps R1
    r1, r2 = records(root, head)
    void = {"record": attest.RECORD, "commit": head, "at": "2000-01-01T00:00:00+00:00", "by": "x",
            "void": "unsound", "voids": [r1["at"]], "checks": []}  # the other clone's void, R1 only
    lines = git(root, "notes", f"--ref={attest.NOTES}", "show", head).rstrip("\n") + "\n" + json.dumps(void)
    git(root, "notes", f"--ref={attest.NOTES}", "add", "-f", "-m", lines, head)
    assert attest.latest(root, head)["at"] == r2["at"]
    attest.run(root, "HEAD", None, "")
    assert runs(root) == 2, "R1 kept again, through R2"


@pytest.mark.parametrize("path, said", [("modules/b/code.py", "modules/b (1 file)"), ("uv.lock", "uv.lock")])
def test_t4_names_what_its_modules_read_that_changed(counting, path, said):
    """D275: after a merge of main, a row is not kept because what its modules read changed — a module
    it consumes, a shared file —; T4 names what, so nobody digs for it."""
    from napkinstack import pull_request

    root = counting
    base = modular(root)
    first = git(root, "rev-parse", "HEAD")
    attest.run(root, base, None, "")
    main_moves(root, path)
    head = git(root, "rev-parse", "HEAD")
    attest.run(root, base, None, "")
    assert pull_request.same_inputs(root, head, base)(first) == \
        f"what its modules read changed between {first} and the head {head[:7]}: {said}"


def test_t4_says_when_no_file_its_modules_read_differs(counting, monkeypatch):
    """D275: the digest also holds the modules run and who runs them with which engine; none of the
    files differing, T4 says that instead of naming nothing."""
    from napkinstack import pull_request

    root = counting
    base = modular(root)
    first = git(root, "rev-parse", "HEAD")
    attest.run(root, base, None, "")
    git(root, "commit", "-q", "--allow-empty", "-m", "nothing changes")
    head = git(root, "rev-parse", "HEAD")
    monkeypatch.setattr(attest.provenance, "engine", lambda: ("0.18.0", None))
    attest.run(root, base, None, "")
    assert pull_request.same_inputs(root, head, base)(first).endswith(
        " — no file they read differs; the modules run, the engine or who runs it changed")


def test_t4_s_list_counts_folders_leaves_out_what_is_not_read_and_stops_at_five(counting):
    """D275's verifier: a record and a module not read are never named; a folder read whole is counted,
    each other path named, five at most; nothing read differing, that is said; a diff git cannot make
    says nothing rather than a guess."""
    from napkinstack import pull_request

    root = counting
    base = modular(root)
    first = git(root, "rev-parse", "HEAD")
    git(root, "switch", "-q", "main")
    for path in ("docs/project/rules.md", "modules/c/code.py", "modules/b/code.py"):
        (root / path).write_text("moved\n", encoding="utf-8")
    (root / "modules/b/more.py").write_text("y = 2\n", encoding="utf-8")
    for n in range(5):
        (root / f"f{n}.txt").write_text("new\n", encoding="utf-8")
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "main moves")
    git(root, "switch", "-q", "work")
    git(root, "merge", "-q", "--no-edit", "main")
    head = git(root, "rev-parse", "HEAD")
    assert pull_request._what_changed(root, base, first, head) == ": f0.txt, f1.txt, f2.txt, f3.txt, f4.txt, and 1 more"
    git(root, "rm", "-q", "f1.txt", "f2.txt", "f3.txt", "f4.txt")
    git(root, "commit", "-q", "-m", "fewer")
    assert pull_request._what_changed(root, base, first, git(root, "rev-parse", "HEAD")) == \
        ": f0.txt, modules/b (2 files)"
    git(root, "switch", "-q", "main")
    (root / "docs/project/rules.md").write_text("again\n", encoding="utf-8")
    (root / "modules/c/code.py").write_text("again\n", encoding="utf-8")
    git(root, "commit", "-q", "-am", "only what is not read")
    assert pull_request._what_changed(root, base, git(root, "rev-parse", "HEAD~1"), git(root, "rev-parse", "HEAD")) == \
        " — no file they read differs; the modules run, the engine or who runs it changed"
    assert pull_request._what_changed(root, base, first, "0" * 40) == ""


@pytest.mark.parametrize("excluded", [False, True], ids=["as git shows it", "hidden by .git/info/exclude"])
def test_a_tree_an_agent_s_sandbox_masks_is_refused_and_said(tmp_path, monkeypatch, capsys, excluded):
    """#514 (D278): an agent's sandbox puts mount points over protected paths — `.claude/skills`, which
    the commit tracks, among them. The tree is then not the commit: refused whatever git is told to
    ignore, naming the paths and the way out — attest outside the sandbox."""
    import shutil

    head = project(tmp_path)
    skill = tmp_path / ".claude/skills/demo/SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text("a skill\n", encoding="utf-8")
    git(tmp_path, "add", "-A")
    git(tmp_path, "commit", "-q", "-m", "a skill")
    head = git(tmp_path, "rev-parse", "HEAD")
    shutil.rmtree(tmp_path / ".claude/skills")
    mount = tmp_path / ".claude/skills"
    os.mkfifo(mount)  # no regular file: as a sandbox's mount, a device
    if excluded:
        (tmp_path / ".git/info").mkdir(exist_ok=True)
        (tmp_path / ".git/info/exclude").write_text("/.claude/skills\n", encoding="utf-8")
    monkeypatch.setattr(attest, "CHECKS", PASSING)
    assert attest._masked(tmp_path) == [".claude/skills"]
    assert attest.run(tmp_path, "HEAD", None, "") == 1
    out = capsys.readouterr().out
    assert "FAIL [attest] this session cannot read what the commit holds: .claude/skills — " in out, out
    assert "attest outside the sandbox" in out, out
    assert attest.latest(tmp_path, head) is None


def test_a_path_a_sparse_checkout_leaves_out_is_not_masked(tmp_path, monkeypatch):
    """D278: `nstack agent run`'s clone leaves `.claude/skills/` out of its working tree on purpose; a
    mount point over it there is no path the checkout should hold."""
    project(tmp_path)
    skill = tmp_path / ".claude/skills/demo/SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text("a skill\n", encoding="utf-8")
    git(tmp_path, "add", "-A")
    git(tmp_path, "commit", "-q", "-m", "a skill")
    git(tmp_path, "sparse-checkout", "set", "--no-cone", "/*", "!/.claude/skills/")
    assert not skill.exists()
    (tmp_path / ".claude").mkdir(exist_ok=True)
    (tmp_path / ".claude/skills").write_text("mnt", encoding="utf-8")
    assert attest._masked(tmp_path) == []


def test_a_folder_replaced_by_a_file_is_a_change_and_links_are_no_mask(tmp_path, monkeypatch, capsys):
    """D278's verifier: a tracked folder replaced by a file of the person's is an edit, said as one; a
    tracked link, dangling or to what this session cannot read, hides nothing; an untracked mount point
    is named with the way out."""
    import shutil

    project(tmp_path)
    (tmp_path / "pages").mkdir()
    (tmp_path / "pages/a.md").write_text("a\n", encoding="utf-8")
    (tmp_path / "gone").symlink_to("nowhere")
    git(tmp_path, "add", "-A")
    git(tmp_path, "commit", "-q", "-m", "pages and a link")
    assert attest._masked(tmp_path) == []
    shutil.rmtree(tmp_path / "pages")
    (tmp_path / "pages").write_text("x\n", encoding="utf-8")
    assert attest._masked(tmp_path) == []
    monkeypatch.setattr(attest, "CHECKS", PASSING)
    assert attest.run(tmp_path, "HEAD", None, "") == 1
    assert "Action: commit or stash them" in capsys.readouterr().out
    (tmp_path / "pages").unlink()
    git(tmp_path, "checkout", "-q", "--", "pages")
    if os.geteuid() == 0:
        return  # root reads a file of any mode: a sandbox's unreadable mount cannot be made here
    mount = tmp_path / ".bashrc"  # as the sandbox's: a file of 3 bytes this session may not read
    mount.write_text("mnt", encoding="utf-8")
    mount.chmod(0)
    try:
        assert attest.run(tmp_path, "HEAD", None, "") == 1
    finally:
        mount.chmod(0o600)
    out = capsys.readouterr().out
    assert ".bashrc: no file or folder this session reads" in out and "attest outside the sandbox" in out, out


# --- #526: a check runs for minutes, and a run stopped from outside said neither where nor what ----
# Each step's output is captured until it ends: a long module's end-to-end was minutes of silence,
# and a timeout that cut it left `ok` of the check before as the last line, no record, no word.

GROUPED = (attest.Check("Groups", (attest.Step("echo", "Every changed module",
                                               "echo '::group::modules/a'; echo inside; echo '::endgroup::'"),)),)


def test_each_step_and_each_module_is_said_as_it_starts(tmp_path, monkeypatch, capsys):
    project(tmp_path)
    monkeypatch.setattr(attest, "CHECKS", GROUPED)
    assert attest.run(tmp_path, "HEAD", None, "") == 0
    out = capsys.readouterr().out
    started, module, ended = (out.index("run  [attest] Groups — Every changed module"),
                              out.index("run  [attest] Groups — modules/a"), out.index("ok   [attest] Groups"))
    assert started < module < ended, out
    assert "inside" not in out, "a step's output stays its record's, shown on failure only"
    assert records(tmp_path, git(tmp_path, "rev-parse", "HEAD"))[0]["checks"][0]["steps"][0]["output"].count("inside") == 1


def test_the_signal_handlers_are_the_caller_s_again_after_a_run(tmp_path, monkeypatch, capsys):
    project(tmp_path)
    monkeypatch.setattr(attest, "CHECKS", PASSING)
    before = (signal.getsignal(signal.SIGTERM), signal.getsignal(signal.SIGINT))
    assert attest.run(tmp_path, "HEAD", None, "") == 0
    assert (signal.getsignal(signal.SIGTERM), signal.getsignal(signal.SIGINT)) == before


STEPS = {
    "obeys": "echo $$ > {pid}; echo ::group::modules/slow; exec sleep 60",
    "writes in its folder": "echo $$ > {pid}; echo ::group::modules/slow; "
                            "while :; do touch \"$NSTACK_TMP/f$RANDOM\"; done",
    "ignores TERM": "trap '' TERM; echo $$ > {pid}; echo ::group::modules/slow; exec sleep 60",
}


@pytest.mark.parametrize("signal_, code, step", [(signal.SIGTERM, 143, "obeys"), (signal.SIGINT, 130, "obeys"),
                                                 (signal.SIGTERM, 143, "writes in its folder"),
                                                 (signal.SIGTERM, 143, "ignores TERM")])
def test_a_run_stopped_from_outside_says_where_and_writes_no_record(tmp_path, signal_, code, step):
    project(tmp_path)
    pid = tmp_path.parent / f"{tmp_path.name}.pid"
    command = STEPS[step].format(pid=pid)
    script = (
        "import sys; from pathlib import Path; from napkinstack import attest\n"
        "attest.CHECKS = (attest.Check('Slow', (attest.Step('sleep', 'Every changed module',\n"
        f"    {command!r}),)),)\n"
        f"sys.exit(attest.run(Path({str(tmp_path)!r}), 'HEAD', None, ''))\n")
    run = subprocess.Popen([sys.executable, "-c", script], cwd=tmp_path, stdout=subprocess.PIPE,
                           stderr=subprocess.STDOUT, text=True, env={**os.environ, **IDENTITY})
    seen = ""
    while "modules/slow" not in seen:
        line = run.stdout.readline()
        assert line, seen
        seen += line
    run.send_signal(signal_)
    out = seen + run.stdout.read()
    assert run.wait(timeout=30) == code, out
    assert f"STOPPED [attest] Slow — modules/slow: {signal.Signals(signal_).name}; no record written" in out, out
    assert subprocess.run(["git", "notes", f"--ref={attest.NOTES}", "list"], cwd=tmp_path, capture_output=True,
                          text=True).stdout == "", "a stopped run recorded"
    with pytest.raises(ProcessLookupError):
        os.kill(int(pid.read_text()), 0)  # the step it started is ended, not left behind


def test_a_second_signal_while_stopping_changes_nothing(tmp_path):
    """The step ignores TERM: attest waits, then kills it — a second signal meanwhile must not cut that
    short and leave the step behind."""
    project(tmp_path)
    pid = tmp_path.parent / f"{tmp_path.name}.pid"
    command = STEPS["ignores TERM"].format(pid=pid)
    script = (
        "import sys; from pathlib import Path; from napkinstack import attest\n"
        "attest.CHECKS = (attest.Check('Slow', (attest.Step('sleep', 'Every changed module',\n"
        f"    {command!r}),)),)\n"
        f"sys.exit(attest.run(Path({str(tmp_path)!r}), 'HEAD', None, ''))\n")
    run = subprocess.Popen([sys.executable, "-c", script], cwd=tmp_path, stdout=subprocess.PIPE,
                           stderr=subprocess.STDOUT, text=True, env={**os.environ, **IDENTITY})
    seen = ""
    while "modules/slow" not in seen:
        line = run.stdout.readline()
        assert line, seen
        seen += line
    stopped = time.monotonic()
    run.send_signal(signal.SIGTERM)
    time.sleep(1)
    run.send_signal(signal.SIGTERM)
    out = seen + run.stdout.read()
    assert run.wait(timeout=30) == 143, out
    assert time.monotonic() - stopped < 30, "the step was left to run out, not killed"
    assert "Traceback" not in out and "STOPPED [attest] Slow — modules/slow: SIGTERM" in out, out
    with pytest.raises(ProcessLookupError):
        os.kill(int(pid.read_text()), 0)


def test_a_stop_before_the_first_step_names_where_it_was():
    assert attest._Running().where == "before the first check"
