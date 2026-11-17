"""D227 (#377): where the forge keeps an approval once new commits are pushed — no ruleset on the
plan, or stale approvals not dismissed —, "approved" no longer says the head was read. On a fourth
project two pull requests showed APPROVED on heads their approver had never seen. `nstack pr-check`
reads each reviewer's latest approval and says the ones the head moved past: a warning, never a
failure, since a review starts no run (D218) and a failed check would stay red after the approver
read the head and approved again.
"""

from __future__ import annotations

import pytest

from napkinstack import pull_request
from test_pull_request import PASSED, USER_FACING, Answer, change, check, git, sheet


def _commit(root, message: str) -> str:
    (root / "modules" / "login" / "src" / "page.txt").write_text(f"{message}\n", encoding="utf-8")
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", message)
    return git(root, "rev-parse", "HEAD")


def _said(root, base, head, found) -> list[str]:
    said: list[str] = []
    pull_request.check_approvals(root, base, head, found, said.append)
    return said


def test_an_approval_of_the_head_is_not_said(tmp_path):
    base, head = change(tmp_path, USER_FACING)
    assert _said(tmp_path, base, head, [("dana", head)]) == []


def test_an_approval_the_head_moved_past_is_said_with_who_which_commit_and_what_followed(tmp_path):
    base, approved = change(tmp_path, USER_FACING)
    _commit(tmp_path, "one more")
    head = _commit(tmp_path, "and another")
    said = _said(tmp_path, base, head, [("dana", approved), ("erin", head)])
    assert len(said) == 1, said
    assert said[0].startswith("[R1] @dana approved " + approved[:7]), said
    assert f"not the head {head[:7]}" in said[0] and "2 commit(s) pushed since" in said[0], said
    assert "approves again" in said[0], said


def test_only_the_base_branch_merged_in_since_leaves_the_approval_covering_the_head(tmp_path):
    base, approved = change(tmp_path, USER_FACING)
    git(tmp_path, "checkout", "-q", "-b", "trunk", base)
    (tmp_path / "elsewhere.txt").write_text("main moved\n", encoding="utf-8")
    git(tmp_path, "add", "-A")
    git(tmp_path, "commit", "-q", "-m", "main moved")
    moved = git(tmp_path, "rev-parse", "HEAD")
    git(tmp_path, "checkout", "-q", "-")
    git(tmp_path, "merge", "-q", "--no-edit", "trunk")
    head = git(tmp_path, "rev-parse", "HEAD")
    assert _said(tmp_path, moved, head, [("dana", approved)]) == []


def test_an_approval_of_a_commit_the_branch_no_longer_holds_is_said(tmp_path):
    base, head = change(tmp_path, USER_FACING)
    said = _said(tmp_path, base, head, [("dana", "f" * 40)])
    assert len(said) == 1 and "the branch was rewritten since" in said[0], said


def test_approvals_not_read_are_said_never_judged(tmp_path):
    base, head = change(tmp_path, USER_FACING)
    said = _said(tmp_path, base, head, "token refused (HTTP 401)")
    assert said == ["[R1] whether each approval covers the head is not read: token refused (HTTP 401)."]
    assert _said(tmp_path, base, head, None) == [], "a workstation reads no pull request"


def test_pr_check_warns_and_stays_green_on_github_and_does_not_ask_elsewhere(tmp_path, capsys, monkeypatch):
    base, approved = change(tmp_path, USER_FACING)
    head = _commit(tmp_path, "pushed after the approval")
    monkeypatch.setattr(pull_request, "approvals", lambda root: [("dana", approved)])
    assert check(tmp_path, base, head, sheet(PASSED), monkeypatch) == 0
    out = capsys.readouterr().out
    assert f"WARNING [R1] @dana approved {approved[:7]}" in out, out
    monkeypatch.setattr(pull_request.project, "forge", lambda root: "gitlab")
    monkeypatch.setattr(pull_request, "approvals", lambda root: pytest.fail("read off GitHub"))
    check(tmp_path, base, head, sheet(PASSED), monkeypatch)
    assert "[R1]" not in capsys.readouterr().out


def _reviews(*nodes, total=None):
    return Answer({"data": {"repository": {"pullRequest": {"latestOpinionatedReviews": {
        "totalCount": len(nodes) if total is None else total, "nodes": list(nodes)}}}}})


def test_the_approvals_are_each_reviewer_s_latest_approving_review_and_its_commit(tmp_path, monkeypatch):
    sent = {}

    def answer(request, timeout):
        import json
        sent.update(json.loads(request.data))
        return _reviews({"state": "APPROVED", "author": {"login": "Dana"}, "commit": {"oid": "ABC123"}},
                        {"state": "CHANGES_REQUESTED", "author": {"login": "erin"}, "commit": {"oid": "def456"}},
                        {"state": "APPROVED", "author": None, "commit": {"oid": "fed654"}})

    for name in ("GH_TOKEN", "GITHUB_TOKEN", "PR_NUMBER", "GITHUB_REPOSITORY", "NSTACK_ATTESTING"):
        monkeypatch.delenv(name, raising=False)
    assert pull_request.approvals(tmp_path) is None
    monkeypatch.setenv("PR_NUMBER", "12")
    monkeypatch.setenv("GITHUB_REPOSITORY", "acme/app")
    monkeypatch.setenv("GITHUB_TOKEN", "t0ken")
    monkeypatch.setattr(pull_request.urllib.request, "urlopen", answer)
    assert pull_request.approvals(tmp_path) == [("Dana", "abc123"), ("a deleted account", "fed654")]
    assert "latestOpinionatedReviews" in sent["query"] and "commit { oid }" in sent["query"], sent
    monkeypatch.setattr(pull_request.urllib.request, "urlopen", lambda request, timeout: _reviews(total=101))
    assert pull_request.approvals(tmp_path) == "more reviewers than one page"
    monkeypatch.setenv("NSTACK_ATTESTING", "abc1234")
    assert pull_request.approvals(tmp_path) is None, "attest records the head: the forge's run judges"
