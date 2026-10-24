"""D147: the two commands that judge one pull request take its labels one way (#244).

In 0.14.0 `attest` read them from `--labels` alone and set PR_LABELS empty for its checks, while
`pr-check` read PR_LABELS alone and refused `--labels`: a caller passing them as one command
wanted failed the other, and `attest` said a check failed without its reason.
"""

from __future__ import annotations

import pytest

from napkinstack import attest, cli
from test_attest import IDENTITY, git, project, records
from test_pull_request import change, check


@pytest.fixture(autouse=True)
def _identity(monkeypatch):
    for name, value in IDENTITY.items():
        monkeypatch.setenv(name, value)


JUSTIFIED = "Out of cycle: a production incident"


def test_pr_check_takes_the_labels_as_an_option(tmp_path, monkeypatch, capsys):
    base, head = change(tmp_path)
    monkeypatch.setenv("PR_BODY", JUSTIFIED)
    monkeypatch.setenv("PR_HEAD_SHA", head)
    monkeypatch.delenv("PR_LABELS", raising=False)
    code = cli.main(["pr-check", "--root", str(tmp_path), "--base", base, "--labels", "bug,out-of-cycle"])
    out = capsys.readouterr().out
    assert code == 0 and "Pull request rules: compliant." in out, out


def test_pr_check_s_option_wins_over_the_environment(tmp_path, monkeypatch, capsys):
    base, head = change(tmp_path)
    monkeypatch.setenv("PR_BODY", JUSTIFIED)
    monkeypatch.setenv("PR_HEAD_SHA", head)
    monkeypatch.setenv("PR_LABELS", "out-of-cycle")
    assert cli.main(["pr-check", "--root", str(tmp_path), "--base", base, "--labels", ""]) == 1
    assert "FAIL [K3] no deliverable named" in capsys.readouterr().out


def test_pr_check_still_reads_the_environment(tmp_path, monkeypatch, capsys):
    base, head = change(tmp_path)
    assert check(tmp_path, base, head, JUSTIFIED, monkeypatch, "out-of-cycle", deliverable_line=None) == 0, \
        capsys.readouterr().out


LABELS_SEEN = (attest.Check("Labels", (attest.Step("echo", "say them", 'test "$PR_LABELS" = out-of-cycle'),)),)


def test_attest_reads_pr_labels_when_no_option_is_given(tmp_path, monkeypatch, capsys):
    """0.13.0's way, `PR_LABELS=out-of-cycle nstack attest`, recorded 4 of 5 in 0.14.0."""
    head = project(tmp_path)
    monkeypatch.setattr(attest, "CHECKS", LABELS_SEEN)
    monkeypatch.setenv("PR_LABELS", "out-of-cycle")
    assert cli.main(["attest", "--root", str(tmp_path), "--base", "HEAD"]) == 0, capsys.readouterr().out
    assert records(tmp_path, head)[0]["checks"][0]["passed"]


def test_attest_s_option_wins_over_the_environment(tmp_path, monkeypatch, capsys):
    project(tmp_path)
    monkeypatch.setattr(attest, "CHECKS", LABELS_SEEN)
    monkeypatch.setenv("PR_LABELS", "bug")
    assert cli.main(["attest", "--root", str(tmp_path), "--base", "HEAD", "--labels", "out-of-cycle"]) == 0, \
        capsys.readouterr().out


SAYS_WHY = (attest.Check("Test sheet and cycle", (attest.Step("echo", "Test sheet and cycle", (
    "echo 'Project framed — charter accepted.'; "
    "echo 'FAIL [K3] no deliverable named: a change to a module names the cycle s deliverable.'; "
    "echo '      Action: write Deliverable: D<n> in the description.'; "
    "echo 'Pull request rules: 1 failure(s).'; exit 1")),)),)


def test_a_failed_check_says_its_failing_rule(tmp_path, monkeypatch, capsys):
    project(tmp_path)
    monkeypatch.setattr(attest, "CHECKS", SAYS_WHY)
    assert attest.run(tmp_path, "HEAD", None, "") == 1
    out = capsys.readouterr().out
    assert "FAIL [attest] Test sheet and cycle: Test sheet and cycle exited 1" in out
    assert "FAIL [K3] no deliverable named" in out and "Action: write Deliverable" in out, out
    assert "Project framed" not in out, "only the failing lines, not the whole output"


def test_a_failed_check_with_no_fail_line_shows_its_last_lines(tmp_path, monkeypatch, capsys):
    project(tmp_path)
    monkeypatch.setattr(attest, "CHECKS", (attest.Check("Crash", (attest.Step("x", "crash", (
        "for i in 1 2 3 4 5 6 7 8; do echo line$i; done; echo 'Traceback: boom' >&2; exit 2")),)),))
    assert attest.run(tmp_path, "HEAD", None, "") == 1
    out = capsys.readouterr().out
    assert "Traceback: boom" in out and "line1\n" not in out, out
