"""D129, ADR-0006: a project's checks run where the team works, and the run is recorded in git,
bound to its commit. Every case proves its rule fails (P5) and names itself (P6). Run by
platform/tests/run.sh.
"""

from __future__ import annotations

import base64
import json
import os
import subprocess
import sys
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


def test_a_merge_in_that_touches_nothing_the_module_reads_keeps_its_check(counting, capsys):
    root = counting
    base = modular(root)
    first_head = git(root, "rev-parse", "HEAD")
    assert attest.run(root, base, None, "") == 0 and runs(root) == 1
    main_moves(root, "modules/c/code.py")
    capsys.readouterr()
    assert attest.run(root, base, None, "") == 0 and runs(root) == 1
    head = git(root, "rev-parse", "HEAD")
    kept = records(root, head)[-1]["checks"][1]
    assert kept["kept_commit"] == first_head and kept["inputs"] == records(root, first_head)[-1]["checks"][1]["inputs"]
    assert f"kept from the run on {first_head[:7]}" in capsys.readouterr().out


@pytest.mark.parametrize("path", ["modules/b/code.py", "uv.lock", "modules/a/code.py", "contracts/doc.md",
                                  "platform/doc.md"])
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
    assert same(first[:7]) and not same(git(root, "rev-parse", "main"))
    monkeypatch.setattr(attest, "FRESH_DAYS", -1)
    assert not pull_request.same_inputs(root, head, base)(first[:7]), "past the bound, the row is re-run"



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
    assert pull_request.same_inputs(root, head, base)(first)
    monkeypatch.setenv("NSTACK_INPUTS", "0" * 64)
    assert not pull_request.same_inputs(root, head, base)(first)
    monkeypatch.setenv("NSTACK_INPUTS", digest)
    (root / ".copier-answers.yml").write_text(yaml.safe_dump({"_commit": "v0.9.6"}), encoding="utf-8")
    assert not pull_request.same_inputs(root, head, base)(first), "the forge's CI replays it"
