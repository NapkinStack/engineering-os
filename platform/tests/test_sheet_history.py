"""D214 (#384): the sheet lives in the description, which author and verifier both edit. A row explored
at one commit, its Commit cell later moved to another with the same evidence, was never explored
again: pr-check says so, from the rows the records of the pull request's commits hold. Run by
platform/tests/run.sh."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from test_attest import IDENTITY, PASSING
from test_pull_request import USER_FACING, change, git, sheet

from napkinstack import attest, cli

GIVEN = "Given the form, when it is submitted, then the page confirms"
OTHER = "Given the form, when a field is empty, then it says which"


@pytest.fixture(autouse=True)
def _identity(monkeypatch):
    for name, value in IDENTITY.items():
        monkeypatch.setenv(name, value)


def _attested(root: Path) -> None:
    answers = root / ".copier-answers.yml"
    data = yaml.safe_load(answers.read_text(encoding="utf-8")) if answers.exists() else {}
    answers.write_text(yaml.safe_dump({**(data or {}), "checks": "attested"}), encoding="utf-8")


def _body(root: Path, name: str, *rows: tuple[str, ...], confirmed: bool = False) -> Path:
    path = root.parent / f"body-{name}.md"
    path.write_text("Deliverable: D1\n\n" + sheet(*rows, confirmed=confirmed), encoding="utf-8")
    return path


def _pr_check(root: Path, base: str, head: str, body: Path, monkeypatch, capsys) -> tuple[int, str]:
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    monkeypatch.setenv("PR_BODY", body.read_text(encoding="utf-8"))
    monkeypatch.setenv("PR_HEAD_SHA", head)
    monkeypatch.setenv("PR_LABELS", "")
    code = cli.main(["pr-check", "--root", str(root), "--base", base])
    return code, capsys.readouterr().out


@pytest.fixture
def verified_then_fixed(tmp_path, monkeypatch, capsys):
    """S2 explored and S3 automated, both passed by the verifier at `first` and attested; then a fix
    pushed as `second`. Returns (root, base, first, second)."""
    root = tmp_path / "project"
    root.mkdir()
    base, _ = change(root, USER_FACING)
    _attested(root)
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "framed, checks attested")
    first = git(root, "rev-parse", "HEAD")
    monkeypatch.setattr(attest, "CHECKS", PASSING)
    verified = _body(root, "first", ("S2", GIVEN, "explored", "passed", "https://ci.example/shot/2", first[:7]),
                     ("S3", OTHER, "automated", "passed", "the CI run's trace", first[:7]))
    attest.run(root, base, verified, "")
    code, out = _pr_check(root, base, first, verified, monkeypatch, capsys)
    assert code == 0, out  # the honest state: both verified at the head they name
    (root / "modules/login/src/page.txt").write_text("page, fixed\n", encoding="utf-8")
    git(root, "commit", "-q", "-am", "a fix")
    return root, base, first, git(root, "rev-parse", "HEAD")


def _after(root, base, second, body, monkeypatch, capsys) -> tuple[int, str]:
    attest.run(root, base, body, "")
    return _pr_check(root, base, second, body, monkeypatch, capsys)


def test_an_explored_row_moved_to_an_untested_head_is_said(verified_then_fixed, monkeypatch, capsys):
    root, base, first, second = verified_then_fixed
    moved = _body(root, "moved", ("S2", GIVEN, "explored", "passed", "https://ci.example/shot/2", second[:7]),
                  ("S3", OTHER, "automated", "passed", "the CI run's trace", second[:7]))
    code, out = _after(root, base, second, moved, monkeypatch, capsys)
    assert code == 1 and "compliant." not in out, out
    assert f"[T4] scenario S2: its Commit cell moved from {first[:7]} to {second[:7]}, its evidence unchanged" in out
    assert "scenario S3" not in out, "an automated row may move: CI, or the head's record, ran it"


def test_an_explored_row_run_again_with_its_new_evidence_stands(verified_then_fixed, monkeypatch, capsys):
    root, base, _, second = verified_then_fixed
    again = _body(root, "again", ("S2", GIVEN, "explored", "passed", "https://ci.example/shot/9", second[:7]),
                  ("S3", OTHER, "automated", "passed", "the CI run's trace", second[:7]))
    code, out = _after(root, base, second, again, monkeypatch, capsys)
    assert code == 0, out


def test_an_explored_row_confirmed_at_the_head_stands(verified_then_fixed, monkeypatch, capsys):
    root, base, first, second = verified_then_fixed
    confirmed = _body(root, "confirmed",
                      ("S2", GIVEN, "explored", "passed", "https://ci.example/shot/2", first[:7],
                       f"{second[:7]} — one fix under src/, not on this path"),
                      ("S3", OTHER, "automated", "passed", "the CI run's trace", second[:7], "—"), confirmed=True)
    code, out = _after(root, base, second, confirmed, monkeypatch, capsys)
    assert code == 0, out


def test_a_row_a_record_held_and_gone_from_the_sheet_is_said(verified_then_fixed, monkeypatch, capsys):
    root, base, _, second = verified_then_fixed
    fewer = _body(root, "fewer", ("S2", GIVEN, "explored", "passed", "https://ci.example/shot/9", second[:7]))
    code, out = _after(root, base, second, fewer, monkeypatch, capsys)
    assert code == 0, out
    assert "WARNING [T5] scenario(s) S3 were in the sheet a record of this pull request read" in out


def test_a_row_moved_to_a_commit_with_the_same_files_stands(verified_then_fixed, monkeypatch, capsys):
    """D93: a commit whose files are the verified one's is that commit — a revert of the fix."""
    root, base, first, _ = verified_then_fixed
    git(root, "revert", "--no-edit", "HEAD")
    reverted = git(root, "rev-parse", "HEAD")
    back = _body(root, "back", ("S2", GIVEN, "explored", "passed", "https://ci.example/shot/2", reverted[:7]),
                 ("S3", OTHER, "automated", "passed", "the CI run's trace", reverted[:7]))
    code, out = _after(root, base, reverted, back, monkeypatch, capsys)
    assert code == 0, out


def test_a_sheet_without_its_number_column_is_said_never_crashes(verified_then_fixed, monkeypatch, capsys):
    root, base, _, second = verified_then_fixed
    body = root.parent / "body-nonumber.md"
    body.write_text("Deliverable: D1\n\n## Test sheet\n\nVerifier: session verifier-7\n\n"
                    "| Given · when · then | Kind | Result | Evidence | Commit |\n|---|---|---|---|---|\n"
                    f"| {GIVEN} | explored | passed | https://ci.example/shot/2 | {second[:7]} |\n", encoding="utf-8")
    code, out = _pr_check(root, base, second, body, monkeypatch, capsys)
    assert code == 1 and "[T2] Test sheet: columns missing: #" in out, out
