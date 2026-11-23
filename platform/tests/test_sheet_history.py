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


def _removed(body: Path, line: str) -> Path:
    body.write_text(body.read_text(encoding="utf-8") + f"\n{line}\n", encoding="utf-8")
    return body


def test_a_row_whose_removal_is_said_with_its_reason_is_not_said_again(verified_then_fixed, monkeypatch, capsys):
    """#485: the removal said under the sheet, in the form the warning names, clears it."""
    root, base, _, second = verified_then_fixed
    fewer = _removed(_body(root, "said", ("S2", GIVEN, "explored", "passed", "https://ci.example/shot/9", second[:7])),
                     "Removed: S3 — the page it read is no longer changed; S2 holds it")
    code, out = _after(root, base, second, fewer, monkeypatch, capsys)
    assert code == 0 and "[T5]" not in out, out


@pytest.mark.parametrize("line", ["Removed: S3", "Removed: S4 — another scenario", "S3 left the sheet with the move"])
def test_a_removal_without_its_reason_or_its_form_is_still_said(verified_then_fixed, monkeypatch, capsys, line):
    root, base, _, second = verified_then_fixed
    fewer = _removed(_body(root, "unsaid", ("S2", GIVEN, "explored", "passed", "https://ci.example/shot/9", second[:7])),
                     line)
    code, out = _after(root, base, second, fewer, monkeypatch, capsys)
    assert "WARNING [T5] scenario(s) S3 were in the sheet" in out and "Removed: <ids> — <why>" in out, out


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


def test_an_explored_row_put_back_after_a_record_held_it_moved_stands(verified_then_fixed, monkeypatch, capsys):
    """#444: a record at the head held S2 moved to it; T4's own Action, the original commit put back
    and the head confirmed, then passes — the row was explored at `first`, whatever a record held since."""
    root, base, first, second = verified_then_fixed
    moved = _body(root, "moved", ("S2", GIVEN, "explored", "passed", "https://ci.example/shot/2", second[:7]),
                  ("S3", OTHER, "automated", "passed", "the CI run's trace", second[:7]))
    code, out = _after(root, base, second, moved, monkeypatch, capsys)
    assert code == 1 and f"puts {first[:7]} back" in out, out
    back = _body(root, "put-back",
                 ("S2", GIVEN, "explored", "passed", "https://ci.example/shot/2", first[:7],
                  f"{second[:7]} — one fix under src/, not on this path"),
                 ("S3", OTHER, "automated", "passed", "the CI run's trace", second[:7], "—"), confirmed=True)
    code, out = _after(root, base, second, back, monkeypatch, capsys)
    assert code == 0, out
    later = _body(root, "later", ("S2", GIVEN, "explored", "passed", "https://ci.example/shot/2", second[:7]),
                  ("S3", OTHER, "automated", "passed", "the CI run's trace", second[:7]))
    code, out = _pr_check(root, base, second, later, monkeypatch, capsys)
    assert code == 1 and f"moved from {first[:7]} to {second[:7]}" in out, "moved again, it is said against the first"



def test_an_explored_row_put_back_to_an_ancestor_no_record_held_stands(tmp_path, monkeypatch, capsys):
    """#460: explored at `first`, moved to `second` before any record held it there, recorded at
    `second`; set back to `first` with the head confirmed, it claims less — it stands. Moved to a
    commit after the recorded one, it is still said."""
    root = tmp_path / "project"
    root.mkdir()
    base, _ = change(root, USER_FACING)
    _attested(root)
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "framed, checks attested")
    first = git(root, "rev-parse", "HEAD")
    monkeypatch.setattr(attest, "CHECKS", PASSING)
    (root / "modules/login/src/page.txt").write_text("page, fixed\n", encoding="utf-8")
    git(root, "commit", "-q", "-am", "a fix")
    second = git(root, "rev-parse", "HEAD")
    moved = _body(root, "moved", ("S2", GIVEN, "explored", "passed", "https://ci.example/shot/2", second[:7]),
                  ("S3", OTHER, "automated", "passed", "the CI run's trace", second[:7]))
    attest.run(root, base, moved, "")  # the first record of S2 holds it at `second`
    (root / "modules/login/src/page.txt").write_text("page, fixed again\n", encoding="utf-8")
    git(root, "commit", "-q", "-am", "another fix")
    head = git(root, "rev-parse", "HEAD")
    back = _body(root, "back",
                 ("S2", GIVEN, "explored", "passed", "https://ci.example/shot/2", first[:7],
                  f"{head[:7]} — two fixes under src/, not on this path"),
                 ("S3", OTHER, "automated", "passed", "the CI run's trace", head[:7], "—"), confirmed=True)
    code, out = _after(root, base, head, back, monkeypatch, capsys)
    assert code == 0, out
    later = _body(root, "later", ("S2", GIVEN, "explored", "passed", "https://ci.example/shot/2", head[:7]),
                  ("S3", OTHER, "automated", "passed", "the CI run's trace", head[:7]))
    code, out = _pr_check(root, base, head, later, monkeypatch, capsys)
    assert code == 1 and f"moved from {second[:7]} to {head[:7]}" in out, "moved forward, it is still said"


def test_a_stacked_branch_never_reads_the_sheet_of_the_pull_request_it_started_on(tmp_path, monkeypatch, capsys):
    """#508 (D274): B started on A's branch, and A was squash-merged; A's commits stay in B's range, their
    records holding A's sheet. T5 and T4's history read only the records made for this pull request —
    known by its branch here, with no forge."""
    root = tmp_path / "project"
    root.mkdir()
    base, _ = change(root, USER_FACING)
    _attested(root)
    git(root, "checkout", "-q", "-b", "d1-html")
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "A: the HTML export")
    a = git(root, "rev-parse", "HEAD")
    monkeypatch.setattr(attest, "CHECKS", PASSING)
    attest.run(root, base, _body(root, "a", ("X1", GIVEN, "automated", "passed", "the CI run's trace", a[:7])), "")
    git(root, "checkout", "-q", "-b", "d1-docx")
    (root / "modules/login/src/page.txt").write_text("page, as a document\n", encoding="utf-8")
    git(root, "commit", "-q", "-am", "B: the DOCX export")
    b = git(root, "rev-parse", "HEAD")
    own = _body(root, "b", ("W1", OTHER, "automated", "passed", "the CI run's trace", b[:7]))
    code, out = _after(root, base, b, own, monkeypatch, capsys)
    assert code == 0 and "[T5]" not in out, out
    gone = _body(root, "b-fewer", ("W2", GIVEN, "automated", "passed", "the CI run's trace", b[:7]))
    code, out = _after(root, base, b, gone, monkeypatch, capsys)
    assert "WARNING [T5] scenario(s) W1 were in the sheet" in out, "its own records are still read"


def test_a_record_names_the_pull_request_the_forge_gave_and_the_history_keeps_to_it(tmp_path, monkeypatch, capsys):
    """#508 (D274): where the forge names the pull request, the record keeps its number, and the history
    reads the records of that number only — whatever branch each was made on."""
    from napkinstack import pull_request

    root = tmp_path / "project"
    root.mkdir()
    base, _ = change(root, USER_FACING)
    _attested(root)
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "A's work")
    a = git(root, "rev-parse", "HEAD")
    monkeypatch.setattr(attest, "CHECKS", PASSING)
    monkeypatch.setattr(pull_request, "_pull_labels", lambda root, head: (21, set()))
    attest.run(root, base, _body(root, "a", ("X1", GIVEN, "automated", "passed", "the CI run's trace", a[:7])), "")
    (root / "modules/login/src/page.txt").write_text("page, as a document\n", encoding="utf-8")
    git(root, "commit", "-q", "-am", "B's work, on the same branch")
    b = git(root, "rev-parse", "HEAD")
    monkeypatch.setattr(pull_request, "_pull_labels", lambda root, head: (50, set()))
    code, out = _after(root, base, b, _body(root, "b", ("W1", OTHER, "automated", "passed", "the CI run's trace", b[:7])),
                       monkeypatch, capsys)
    assert code == 0 and "[T5]" not in out, out


def test_ci_names_the_pull_request_by_its_event_and_reads_a_record_naming_none(tmp_path, monkeypatch, capsys):
    """D274's verifier: in the forge's run the event names the pull request — its number, its branch —;
    a record of another number or another branch is not read, and one naming nothing still is."""
    from napkinstack import pull_request

    root = tmp_path / "project"
    root.mkdir()
    change(root, USER_FACING)
    git(root, "commit", "-q", "--allow-empty", "-m", "head")
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setenv("GITHUB_REF", "refs/pull/50/merge")
    monkeypatch.setenv("GITHUB_HEAD_REF", "d1-docx")
    this = pull_request.this_pull(root, git(root, "rev-parse", "HEAD"))
    assert this == {"number": 50, "branch": "d1-docx"}
    assert not pull_request.same_pull({"number": 21, "branch": "d1-docx"}, this)
    assert not pull_request.same_pull({"branch": "d1-html"}, this)
    assert pull_request.same_pull({"branch": "d1-docx"}, this) and pull_request.same_pull(None, this)
    assert pull_request.same_pull({}, this)


def test_a_verifier_s_branch_named_after_the_pull_request_s_tracks_it(tmp_path):
    """D274's verifier: a verifier checks out the pull request's branch under a name of its own; the
    branch it tracks is the one its record names."""
    from napkinstack import pull_request

    origin = tmp_path / "origin"
    origin.mkdir()
    git(origin, "init", "-q", "--initial-branch=d1-docx")
    git(origin, "commit", "-q", "--allow-empty", "-m", "B")
    verifier = tmp_path / "verifier"
    git(tmp_path, "clone", "-q", str(origin), str(verifier))
    git(verifier, "switch", "-q", "-c", "check-50", "--track", "origin/d1-docx")
    assert pull_request.this_pull(verifier, git(verifier, "rev-parse", "HEAD")) == {"branch": "d1-docx"}
    git(verifier, "checkout", "-q", "--detach")
    assert pull_request.this_pull(verifier, git(verifier, "rev-parse", "HEAD")) == {}
