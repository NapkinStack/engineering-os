"""
Pull request rules read from the description (PDR-0003, PDR-0002): every rule proves it
fails (P5) and names itself (P6). Run by platform/tests/run.sh.
"""

from __future__ import annotations

import os
import subprocess

import pytest

from napkinstack import cli
from test_guardrails import VALID, degrade, write_module

IDENTITY = {"GIT_AUTHOR_NAME": "test", "GIT_AUTHOR_EMAIL": "test@example.invalid",
            "GIT_COMMITTER_NAME": "test", "GIT_COMMITTER_EMAIL": "test@example.invalid"}
USER_FACING = degrade(module__user_facing=True)
HIGH = degrade(module__criticality="high")


def git(root, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=root, env={**os.environ, **IDENTITY}, check=True,
                          capture_output=True, text=True).stdout.strip()


def change(root, manifest=VALID) -> tuple[str, str]:
    """A repository whose second commit changes the module `login`; returns (base, head)."""
    git(root, "init", "-q", "--initial-branch=main")
    git(root, "commit", "-q", "--allow-empty", "-m", "base")
    base = git(root, "rev-parse", "HEAD")
    write_module(root, "login", manifest, {"src/page.txt": "page\n"})
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "change")
    return base, git(root, "rev-parse", "HEAD")


def sheet(*rows: tuple[str, ...], verifier: str = "a fresh agent session") -> str:
    lines = ["## Test sheet", "", f"Verifier: {verifier}", "",
             "| # | Given · when · then | Kind | Result | Evidence | Commit |", "|---|---|---|---|---|---|"]
    return "\n".join([*lines, *(f"| {' | '.join(row)} |" for row in rows), "", "## Summary", ""])


def check(root, base: str, head: str, body: str, monkeypatch, labels: str = "") -> int:
    monkeypatch.setenv("PR_BODY", body.replace("{head}", head[:7]))
    monkeypatch.setenv("PR_HEAD_SHA", head)
    monkeypatch.setenv("PR_LABELS", labels)
    return cli.main(["pr-check", "--root", str(root), "--base", base])


PASSED = ("S1", "Given an account, when the password is valid, then the dashboard", "automated",
          "passed", "https://ci.example/run/1", "{head}")
HUMAN = ("S8", "Given a real mailbox, when a reset is asked, then the email arrives",
         "human only — no test mailbox", "not verified", "—", "—")
TEMPLATE = ("S1", "<Given …, when …, then …>", "<automated · explored · human only — reason>",
            "<passed · failed · not verified>", "<link>", "<commit>")

SHEET_CASES = {
    "T1 user-facing module without a sheet": (USER_FACING, "No sheet here.", "FAIL [T1] Test sheet missing", 1),
    "T1 high criticality without a sheet": (HIGH, "", "(criticality high)", 1),
    "T1 the template's row only": (USER_FACING, sheet(TEMPLATE), "FAIL [T1]", 1),
    "T1 a standard module needs none": (VALID, "", "Test sheet      : not required", 0),
    "T2 no verifier": (USER_FACING, sheet(PASSED, verifier="<agent session or @human>"), "FAIL [T2] Test sheet: no verifier", 1),
    "T2 missing column": (USER_FACING, "## Test sheet\n\nVerifier: x\n\n| # | Kind | Result |\n|---|---|---|\n| S1 | explored | passed |\n",
                          "FAIL [T2] Test sheet: columns missing", 1),
    "T2 unknown kind": (USER_FACING, sheet(("S1", "Given x", "guessed", "passed", "link", "{head}")), "FAIL [T2] scenario S1: kind", 1),
    "T2 unknown result": (USER_FACING, sheet(("S1", "Given x", "explored", "ok", "link", "{head}")), "FAIL [T2] scenario S1: result", 1),
    "T3 passed without evidence": (USER_FACING, sheet(("S1", "Given x", "explored", "passed", "—", "{head}")), "FAIL [T3] scenario S1", 1),
    "T4 verified on another commit": (USER_FACING, sheet(("S1", "Given x", "explored", "passed", "link", "0000000")),
                                      "FAIL [T4] scenarios verified on another commit", 1),
    "T5 failed": (USER_FACING, sheet(("S1", "Given x", "explored", "**failed** — the button is hidden", "link", "{head}")),
                  "FAIL [T5] scenario S1: failed", 1),
    "T5 not verified": (USER_FACING, sheet(("S1", "Given x", "automated", "not verified", "—", "—")),
                        "FAIL [T5] scenario S1: not verified", 1),
    "compliant, human only listed apart": (USER_FACING, sheet(PASSED, HUMAN),
                                           "For the approver, human only: S8 — no test mailbox", 0),
}


@pytest.mark.parametrize(("manifest", "body", "expected", "code"), SHEET_CASES.values(), ids=SHEET_CASES.keys())
def test_test_sheet(tmp_path, capsys, monkeypatch, manifest, body, expected, code):
    base, head = change(tmp_path, manifest)
    result = check(tmp_path, base, head, body, monkeypatch)
    output = capsys.readouterr().out
    assert expected in output, output
    assert result == code, output


def test_without_a_description_nothing_is_checked(tmp_path, capsys, monkeypatch):
    base, _ = change(tmp_path, USER_FACING)
    monkeypatch.delenv("PR_BODY", raising=False)
    assert cli.main(["pr-check", "--root", str(tmp_path), "--base", base]) == 0
    assert "not checked" in capsys.readouterr().out


def test_description_from_a_file(tmp_path, capsys, monkeypatch):
    base, head = change(tmp_path, USER_FACING)
    body = tmp_path.parent / f"{tmp_path.name}-body.md"
    body.write_text(sheet(PASSED).replace("{head}", head[:7]), encoding="utf-8")
    monkeypatch.delenv("PR_BODY", raising=False)
    monkeypatch.setenv("PR_HEAD_SHA", head)
    assert cli.main(["pr-check", "--root", str(tmp_path), "--base", base, "--body-file", str(body)]) == 0, \
        capsys.readouterr().out
