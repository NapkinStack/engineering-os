"""
Pull request rules read from the description (PDR-0003, PDR-0002): every rule proves it
fails (P5) and names itself (P6). Run by platform/tests/run.sh.
"""

from __future__ import annotations

import datetime
import os
import subprocess

import pytest
import yaml

from napkinstack import cli
from test_guardrails import VALID, degrade, write_module
from test_plan import CHARTER, cycle, deliverable, framed

IDENTITY = {"GIT_AUTHOR_NAME": "test", "GIT_AUTHOR_EMAIL": "test@example.invalid",
            "GIT_COMMITTER_NAME": "test", "GIT_COMMITTER_EMAIL": "test@example.invalid"}
USER_FACING = degrade(module__user_facing=True)
HIGH = degrade(module__criticality="high")
PROTOTYPE_FACING = degrade(module__criticality="prototype", module__user_facing=True)
CRITICAL = degrade(module__criticality="critical", docs__runbook="docs/runbook.md")


def git(root, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=root, env={**os.environ, **IDENTITY}, check=True,
                          capture_output=True, text=True).stdout.strip()


def change(root, manifest=VALID, frame: bool = True) -> tuple[str, str]:
    """A repository whose second commit changes the module `login`; returns (base, head).
    `frame`: an accepted charter and cycle, whose deliverable D1 is ready."""
    git(root, "init", "-q", "--initial-branch=main")
    git(root, "commit", "-q", "--allow-empty", "-m", "base")
    base = git(root, "rev-parse", "HEAD")
    write_module(root, "login", manifest, {"src/page.txt": "page\n"})
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "change")
    if frame:
        framed(root)
    return base, git(root, "rev-parse", "HEAD")


def sheet(*rows: tuple[str, ...], verifier: str = "session verifier-7 — ran the sheet before the diff",
          confirmed: bool = False) -> str:
    columns = "| # | Given · when · then | Kind | Result | Evidence | Commit |"
    if confirmed:  # the optional column of T4: present in the template, read only when needed
        columns = columns + " Confirmed |"
    lines = ["## Test sheet", "", f"Verifier: {verifier}", "",
             columns, "|" + "---|" * (columns.count("|") - 1)]
    return "\n".join([*lines, *(f"| {' | '.join(row)} |" for row in rows), "", "## Summary", ""])


def check(root, base: str, head: str, body: str, monkeypatch, labels: str = "",
          deliverable_line: str | None = "Deliverable: D1") -> int:
    text = body.replace("{head}", head[:7])
    monkeypatch.setenv("PR_BODY", f"{deliverable_line}\n\n{text}" if deliverable_line else text)
    monkeypatch.setenv("PR_HEAD_SHA", head)
    monkeypatch.setenv("PR_LABELS", labels)
    return cli.main(["pr-check", "--root", str(root), "--base", base])


PASSED = ("S1", "Given an account, when the password is valid, then the dashboard", "automated",
          "passed", "https://ci.example/run/1", "{head}")
OLD = "1111111"  # a commit that is not the head: the evidence was produced before the last fix
EXPLORED_OLD = ("S2", "Given the form, when it is submitted, then the page confirms",
                "explored", "passed", "https://ci.example/shot/2", OLD)
AUTOMATED_OLD = ("S3", "Given a user, when they sign in, then the session opens",
                 "automated", "passed", "https://ci.example/run/3", OLD)
HUMAN = ("S8", "Given a real mailbox, when a reset is asked, then the email arrives",
         "human only — no test mailbox", "not verified", "—", "—")
TEMPLATE = ("S1", "<Given …, when …, then …>", "<automated · explored · human only — reason>",
            "<passed · failed · not verified>", "<link>", "<commit>")

SHEET_CASES = {
    "T1 user-facing module without a sheet": (USER_FACING, "No sheet here.", "FAIL [T1] Test sheet missing", 1),
    "T1 high criticality without a sheet": (HIGH, "", "(criticality high)", 1),
    "T1 the template's row only": (USER_FACING, sheet(TEMPLATE), "FAIL [T1]", 1),
    "T1 a standard module needs none": (VALID, "", "Test sheet      : not required", 0),
    # The matrix of 05-workflow.md §7: at `prototype` the sheet is never required, and that is
    # what the value buys. A throwaway a user sees costs no verifier (M11a).
    "T1 a user-facing prototype needs none": (PROTOTYPE_FACING, "", "Test sheet      : not required", 0),
    # P6 on a threshold: the refusal says what the value below would have changed, so that
    # the reader can judge the declaration instead of only obeying it.
    "T1 the refusal names the value below": (HIGH, "", "at standard it would be required only", 1),
    "T2 no verifier": (USER_FACING, sheet(PASSED, verifier="<@handle, or session and the agent session's identifier>"),
                       "FAIL [T2] Test sheet: no verifier", 1),
    "T2 a verifier named in prose only (D32)": (USER_FACING, sheet(PASSED, verifier="a fresh agent session"),
                                               "FAIL [T2] Test sheet: the verifier is not named", 1),
    "T2 'session' inside a sentence names no session": (
        USER_FACING, sheet(PASSED, verifier="a session other than the author's"),
        "FAIL [T2] Test sheet: the verifier is not named", 1),
    "T2 a handle inside a sentence is a name": (USER_FACING, sheet(PASSED, verifier="@dana — ran it on staging"),
                                                "Pull request rules: compliant.", 0),
    "T2 missing column": (USER_FACING, "## Test sheet\n\nVerifier: x\n\n| # | Kind | Result |\n|---|---|---|\n| S1 | explored | passed |\n",
                          "FAIL [T2] Test sheet: columns missing", 1),
    "T2 unknown kind": (USER_FACING, sheet(("S1", "Given x", "guessed", "passed", "link", "{head}")), "FAIL [T2] scenario S1: kind", 1),
    "T2 unknown result": (USER_FACING, sheet(("S1", "Given x", "explored", "ok", "link", "{head}")), "FAIL [T2] scenario S1: result", 1),
    "T3 passed without evidence": (USER_FACING, sheet(("S1", "Given x", "explored", "passed", "—", "{head}")), "FAIL [T3] scenario S1", 1),
    # T4 stops being a ratchet. An explored scenario keeps the commit its evidence was produced
    # on, and the sheet confirms at the head: one line instead of a full round (D71).
    "T4 an explored scenario confirmed at the head passes": (
        USER_FACING, sheet((*EXPLORED_OLD, "{head} — only modules/login/src/page.txt changed since"),
                           confirmed=True), "Pull request rules: compliant.", 0),
    "T4 an explored scenario with no confirmation is refused": (
        USER_FACING, sheet(EXPLORED_OLD), "add the head commit in a Confirmed column", 1),
    # At `critical` nothing stands in for a re-run. That is the rerun_at_head row of the matrix,
    # and the first thing the top value has ever cost that `high` does not.
    "T4 at criticality critical a confirmation does not stand in": (
        CRITICAL, sheet((*EXPLORED_OLD, "{head} — nothing that touches it"), confirmed=True),
        "At criticality critical every scenario is re-run at the head", 1),
    # An automated scenario is cheap to re-run and CI re-runs it anyway: no relief for it.
    "T4 an automated scenario is re-run, never confirmed": (
        USER_FACING, sheet((*AUTOMATED_OLD, "{head} — nothing that touches it"), confirmed=True),
        "run them again on the head commit", 1),
    "T5 failed": (USER_FACING, sheet(("S1", "Given x", "explored", "**failed** — the button is hidden", "link", "{head}")),
                  "FAIL [T5] scenario S1: failed", 1),
    "T5 not verified": (USER_FACING, sheet(("S1", "Given x", "automated", "not verified", "—", "—")),
                        "FAIL [T5] scenario S1: not verified", 1),
    "compliant, human only listed apart": (USER_FACING, sheet(PASSED, HUMAN),
                                           "For the approver, human only: S8 — no test mailbox", 0),
}


def test_a_fix_costs_a_confirmation_not_a_round(tmp_path, capsys, monkeypatch):
    """D71, measured on the pilot: six scenarios, three blockers fixed after the first
    verification, and T4 called the whole sheet stale each time — six rounds on one read-only
    module, three of whose eleven defects were introduced by the late rounds themselves.

    The same sheet now passes with one confirmation: the automated scenarios are replayed by CI at
    the head, the three explored by hand keep the commit their evidence was produced on and are
    confirmed on the head. And the refusal, when a confirmation is missing, names that scenario
    alone — not the five that are fine."""
    base, head = change(tmp_path, USER_FACING)
    explored = [(f"S{n}", f"Given step {n}, when it runs, then the page shows it", "explored",
                 "passed", f"https://ci.example/shot/{n}", OLD) for n in (1, 2, 3)]
    automated = [(f"S{n}", f"Given step {n}, when it runs, then the log says so", "automated",
                  "passed", f"https://ci.example/run/{n}", "{head}") for n in (4, 5, 6)]
    confirmation = "{head} — three fixes under src/, none inside this scenario's path"
    whole = sheet(*[(*row, confirmation) for row in explored], *[(*row, "") for row in automated],
                  confirmed=True)
    assert check(tmp_path, base, head, whole, monkeypatch) == 0, capsys.readouterr().out
    assert "compliant" in capsys.readouterr().out

    one_missing = sheet((*explored[0], ""), *[(*row, confirmation) for row in explored[1:]],
                        *[(*row, "") for row in automated], confirmed=True)
    assert check(tmp_path, base, head, one_missing, monkeypatch) == 1
    output = capsys.readouterr().out
    assert "not confirmed on it: S1." in output, output
    assert "S2" not in output.split("not confirmed on it:")[1], output


@pytest.mark.parametrize(("manifest", "body", "expected", "code"), SHEET_CASES.values(), ids=SHEET_CASES.keys())
def test_test_sheet(tmp_path, capsys, monkeypatch, manifest, body, expected, code):
    base, head = change(tmp_path, manifest)
    result = check(tmp_path, base, head, body, monkeypatch)
    output = capsys.readouterr().out
    assert expected in output, output
    assert result == code, output


AGENT = "330339777+napkinstack-agent[bot]@users.noreply.github.com"
AUTHORSHIP = {
    "the pull request's author": ({}, "", "@alice", "alice", "FAIL [T2] Test sheet: the verifier @alice is an author", 1),
    "a commit's author": ({"GIT_AUTHOR_EMAIL": "123+bob@users.noreply.github.com"}, "", "@bob", "alice",
                          "the verifier @bob is an author", 1),
    "a co-author": ({}, "Co-authored-by: Carol <7+carol@users.noreply.github.com>", "@Carol", "alice",
                    "the verifier @carol is an author", 1),
    "the App, named as a person": ({"GIT_AUTHOR_EMAIL": AGENT}, "Agent-Session: author-1", "@napkinstack-agent",
                                   "alice", "the verifier @napkinstack-agent is an author", 1),
    "the App, named as a bot": ({"GIT_AUTHOR_EMAIL": AGENT}, "Agent-Session: author-1", "@napkinstack-agent[bot]",
                                "alice", "the verifier @napkinstack-agent is an author", 1),
    "one author among the names": ({}, "", "@dana, then @alice", "alice", "the verifier @alice is an author", 1),
    "the session, with a full stop (D40)": ({"GIT_AUTHOR_EMAIL": AGENT}, "Agent-Session: author-1", "session author-1.",
                                            "alice", "the verifier, session author-1, wrote commits", 1),
    "the session, in capitals (D40)": ({"GIT_AUTHOR_EMAIL": AGENT}, "Agent-Session: author-1", "session AUTHOR-1",
                                       "alice", "the verifier, session author-1, wrote commits", 1),
    "the session that wrote it": ({"GIT_AUTHOR_EMAIL": AGENT}, "Agent-Session: author-1", "session author-1",
                                  "napkinstack-agent[bot]", "the verifier, session author-1, wrote commits", 1),
    "an agent commit naming no session": ({"GIT_AUTHOR_EMAIL": AGENT}, "", "session verifier-7",
                                          "napkinstack-agent[bot]", "an agent's commits name no session", 1),
    "another session: compliant": ({"GIT_AUTHOR_EMAIL": AGENT}, "Agent-Session: author-1", "session verifier-7",
                                   "napkinstack-agent[bot]", "Pull request rules: compliant.", 0),
    "another person: compliant": ({"GIT_AUTHOR_EMAIL": AGENT}, "Agent-Session: author-1", "@dana",
                                  "napkinstack-agent[bot]", "Pull request rules: compliant.", 0),
}


@pytest.mark.parametrize(("identity", "trailer", "verifier", "opener", "expected", "code"),
                         AUTHORSHIP.values(), ids=AUTHORSHIP.keys())
def test_the_verifier_is_not_an_author(tmp_path, capsys, monkeypatch, identity, trailer, verifier, opener,
                                       expected, code):
    """D32: T2 compares the verifier with the change's authors, people and sessions."""
    base, _ = change(tmp_path, USER_FACING)
    (tmp_path / "modules" / "login" / "src" / "page.txt").write_text("page, fixed\n", encoding="utf-8")
    git(tmp_path, "add", "-A")
    subprocess.run(["git", "commit", "-q", "-m", "fix", *(["-m", trailer] if trailer else [])], cwd=tmp_path,
                   env={**os.environ, **IDENTITY, **identity}, check=True)
    head = git(tmp_path, "rev-parse", "HEAD")
    monkeypatch.setenv("PR_AUTHOR", opener)
    result = check(tmp_path, base, head, sheet(PASSED, verifier=verifier), monkeypatch)
    output = capsys.readouterr().out
    assert expected in output, output
    assert result == code, output


def test_the_authors_are_the_commits_the_pull_request_brings(tmp_path, capsys, monkeypatch):
    """CI checks out a merge commit, and updating a branch merges the base in: neither is the
    change's author, and the base's own commits are not either."""
    agent = {**os.environ, **IDENTITY, "GIT_AUTHOR_EMAIL": AGENT, "GIT_COMMITTER_EMAIL": AGENT}
    base, _ = change(tmp_path, USER_FACING)
    git(tmp_path, "checkout", "-q", "-b", "feature")
    (tmp_path / "modules" / "login" / "src" / "page.txt").write_text("page, fixed\n", encoding="utf-8")
    git(tmp_path, "add", "-A")
    subprocess.run(["git", "commit", "-q", "-m", "fix", "-m", "Agent-Session: author-1"], cwd=tmp_path,
                   env=agent, check=True)
    git(tmp_path, "checkout", "-q", "main")
    (tmp_path / "NOTES.md").write_text("on main\n", encoding="utf-8")
    git(tmp_path, "add", "-A")
    subprocess.run(["git", "commit", "-q", "-m", "main moves on"], cwd=tmp_path, env=agent, check=True)
    git(tmp_path, "checkout", "-q", "feature")
    subprocess.run(["git", "merge", "-q", "--no-edit", "main"], cwd=tmp_path, env=agent, check=True)
    head = git(tmp_path, "rev-parse", "HEAD")
    monkeypatch.setenv("PR_AUTHOR", "napkinstack-agent[bot]")
    result = check(tmp_path, "main", head, sheet(PASSED, verifier="session verifier-7"), monkeypatch)
    output = capsys.readouterr().out
    assert "Pull request rules: compliant." in output and result == 0, output


def test_a_file_moved_out_of_a_user_facing_module(tmp_path, capsys, monkeypatch):
    """D38: git reports the rename under its new name; the module it left changes too."""
    base, _ = change(tmp_path, USER_FACING)
    write_module(tmp_path, "other", degrade(module__name="other"))
    git(tmp_path, "add", "-A")
    git(tmp_path, "commit", "-q", "-m", "another module")
    base = git(tmp_path, "rev-parse", "HEAD")
    git(tmp_path, "mv", "modules/login/src/page.txt", "modules/other/page.txt")
    git(tmp_path, "commit", "-q", "-m", "move")
    head = git(tmp_path, "rev-parse", "HEAD")
    assert check(tmp_path, base, head, "No sheet.", monkeypatch) == 1
    assert "modules/login (criticality standard, user-facing)" in capsys.readouterr().out


def test_a_short_row_is_a_finding_not_a_crash(tmp_path, capsys, monkeypatch):
    """D40: a row missing its last cells is read as empty ones."""
    base, head = change(tmp_path, USER_FACING)
    body = "## Test sheet\n\nVerifier: @dana\n\n| # | Given · when · then | Kind | Result | Evidence | Commit |\n" \
           "|---|---|---|---|---|---|\n| S1 | Given x, when y, then z | automated | passed |\n"
    assert check(tmp_path, base, head, body, monkeypatch) == 1
    assert "FAIL [T3] scenario S1: passed without evidence" in capsys.readouterr().out


def test_pr_check_on_an_unknown_base(tmp_path, capsys, monkeypatch):
    base, head = change(tmp_path, USER_FACING)
    assert check(tmp_path, "nope", head, "", monkeypatch) == 1
    assert "FAIL [pr-check] base 'nope' not found" in capsys.readouterr().out


def test_without_a_description_nothing_is_checked(tmp_path, capsys, monkeypatch):
    base, _ = change(tmp_path, USER_FACING)
    monkeypatch.delenv("PR_BODY", raising=False)
    assert cli.main(["pr-check", "--root", str(tmp_path), "--base", base]) == 0
    assert "not checked" in capsys.readouterr().out


def test_description_from_a_file(tmp_path, capsys, monkeypatch):
    base, head = change(tmp_path, USER_FACING)
    body = tmp_path.parent / f"{tmp_path.name}-body.md"
    body.write_text("Deliverable: D1\n\n" + sheet(PASSED).replace("{head}", head[:7]), encoding="utf-8")
    monkeypatch.delenv("PR_BODY", raising=False)
    monkeypatch.setenv("PR_HEAD_SHA", head)
    assert cli.main(["pr-check", "--root", str(tmp_path), "--base", base, "--body-file", str(body)]) == 0, \
        capsys.readouterr().out


def revise(root, edits: dict[str, str | None], manifest=VALID) -> tuple[str, str]:
    """The module `login` in the base commit; the head commit applies `edits` inside it —
    path to new content, None to delete, "." for the whole module. Returns (base, head).
    Not framed: a change counted as delivery work fails K1."""
    git(root, "init", "-q", "--initial-branch=main")
    folder = write_module(root, "login", manifest,
                          {"src/page.txt": "page\n", "docs/runbook.md": "run\n", "src/.gitkeep": ""})
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "base")
    base = git(root, "rev-parse", "HEAD")
    for path, content in edits.items():
        target = folder / path
        if content is None:
            git(root, "rm", "-rq", str(target.relative_to(root)))
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "change")
    return base, git(root, "rev-parse", "HEAD")


ENVELOPE = {"MANIFEST.yaml": yaml.safe_dump(degrade(USER_FACING, module__responsibility="Signs in.")),
            "AGENTS.md": "y\n", "README.md": "y\n", "docs/runbook.md": "y\n", "docs/adr/0001-x.md": "y\n"}
MODULE_CASES = {
    "the envelope only: no sheet, no cycle": (USER_FACING, ENVELOPE, "Modules touched : 0", 0),
    "an empty placeholder: no change": (HIGH, {"src/.gitkeep": None, "tests/.gitkeep": ""}, "Modules touched : 0", 0),
    "a source file: a change": (USER_FACING, {"src/page.txt": "new\n"}, "FAIL [T1]", 1),
    "the stricter of base and head": (USER_FACING, {"MANIFEST.yaml": yaml.safe_dump(VALID), "src/page.txt": "new\n"},
                                      "modules/login (criticality standard, user-facing)", 1),
    "a deleted module: a change": (USER_FACING, {".": None}, "FAIL [T1] Test sheet missing", 1),
}


@pytest.mark.parametrize(("manifest", "edits", "expected", "code"), MODULE_CASES.values(), ids=MODULE_CASES.keys())
def test_what_changes_a_module(tmp_path, capsys, monkeypatch, manifest, edits, expected, code):
    """A module changes when its behaviour may: not its manifest, AGENTS.md, README.md,
    docs/ or an empty placeholder (D24, PDR-0003 and PDR-0002 clarifications)."""
    base, head = revise(tmp_path, edits, manifest)
    result = check(tmp_path, base, head, "", monkeypatch, deliverable_line=None)
    output = capsys.readouterr().out
    assert expected in output, output
    assert result == code, output


def test_a_framework_update_is_neither_delivery_nor_a_sheet(tmp_path, capsys, monkeypatch):
    """D24: `nstack update` migrates the skeleton's `contracts` module, criticality high."""
    git(tmp_path, "init", "-q", "--initial-branch=main")
    contracts = tmp_path / "contracts"
    (contracts / "tests").mkdir(parents=True)
    (contracts / "README.md").write_text("contracts\n", encoding="utf-8")
    (contracts / "MANIFEST.yaml").write_text(yaml.safe_dump(degrade(HIGH, module__user_facing=None)), encoding="utf-8")
    git(tmp_path, "add", "-A")
    git(tmp_path, "commit", "-q", "-m", "NapkinStack v0.2.0")
    base = git(tmp_path, "rev-parse", "HEAD")
    (contracts / "MANIFEST.yaml").write_text(yaml.safe_dump(HIGH), encoding="utf-8")
    (contracts / "README.md").write_text("contracts, updated\n", encoding="utf-8")
    (contracts / "tests" / ".gitkeep").write_text("", encoding="utf-8")
    git(tmp_path, "add", "-A")
    git(tmp_path, "commit", "-q", "-m", "NapkinStack v0.2.0 -> v0.3.0")
    result = check(tmp_path, base, git(tmp_path, "rev-parse", "HEAD"), "", monkeypatch, deliverable_line=None)
    output = capsys.readouterr().out
    assert "Pull request rules: compliant." in output, output
    assert result == 0, output


BROKEN = cycle(start=datetime.date.today() - datetime.timedelta(days=22))  # ended yesterday
CYCLE_CASES = {
    "K1 not framed": (None, "", "", "FAIL [K1] the project is not framed: no accepted charter", 1),
    "K1 between two cycles names the cycle (D47)": (lambda r: framed(r, cycles={}), "Deliverable: D1", "",
                                                    "FAIL [K1] no accepted cycle", 1),
    "K1 charter proposed": (lambda r: framed(r, {**CHARTER, "status": "proposed"}), "Deliverable: D1", "", "FAIL [K1]", 1),
    "K2 circuit breaker": (lambda r: framed(r, cycles={"01-first.md": BROKEN}), "Deliverable: D1", "",
                           "FAIL [K2] circuit breaker: 01-first.md ended on", 1),
    "K3 no deliverable named": (framed, "", "", "FAIL [K3] no deliverable named", 1),
    "K3 deliverable outside the cycle": (framed, "Deliverable: D9", "", "FAIL [K3] deliverable D9 is not in 01-first.md", 1),
    "K3 deliverable not ready": (lambda r: framed(r, cycles={"01-first.md": cycle(deliverables=[
        deliverable(state="proposed", acceptance=None)])}), "Deliverable: D1", "", "FAIL [K3] deliverable D1 is 'proposed'", 1),
    "K4 label without justification": (None, "", "out-of-cycle", "FAIL [K4] label out-of-cycle without its justification", 1),
    "out of cycle, justified": (None, "Out of cycle: a production incident", "bug,out-of-cycle", "Pull request rules: compliant.", 0),
    "in the cycle": (framed, "Deliverable: D1", "", "Pull request rules: compliant.", 0),
}


@pytest.mark.parametrize(("prepare", "body", "labels", "expected", "code"), CYCLE_CASES.values(), ids=CYCLE_CASES.keys())
def test_cycle(tmp_path, capsys, monkeypatch, prepare, body, labels, expected, code):
    base, head = change(tmp_path, frame=False)
    if prepare:
        prepare(tmp_path)
    result = check(tmp_path, base, head, body, monkeypatch, labels, deliverable_line=None)
    output = capsys.readouterr().out
    assert expected in output, output
    assert result == code, output


def test_cycle_rules_spare_work_outside_the_modules(tmp_path, capsys, monkeypatch):
    """Delivery work only: framing documents, updates and CI changes (PDR-0002, clarification)."""
    git(tmp_path, "init", "-q", "--initial-branch=main")
    git(tmp_path, "commit", "-q", "--allow-empty", "-m", "base")
    base = git(tmp_path, "rev-parse", "HEAD")
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "notes.md").write_text("notes\n", encoding="utf-8")
    git(tmp_path, "add", "-A")
    git(tmp_path, "commit", "-q", "-m", "docs")
    assert check(tmp_path, base, git(tmp_path, "rev-parse", "HEAD"), "", monkeypatch, deliverable_line=None) == 0, \
        capsys.readouterr().out
