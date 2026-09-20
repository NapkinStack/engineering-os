"""
What reached the default branch (PDR-0006, rule W1). The record says what nothing could
refuse; it never refuses. Every case proves the rule fails (P5) and names itself (P6).
Run by platform/tests/run.sh.
"""

from __future__ import annotations

import os
import subprocess

from napkinstack import landed

IDENTITY = {"GIT_AUTHOR_NAME": "test", "GIT_AUTHOR_EMAIL": "test@example.invalid",
            "GIT_COMMITTER_NAME": "test", "GIT_COMMITTER_EMAIL": "test@example.invalid"}


def git(root, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=root, env={**os.environ, **IDENTITY}, check=True,
                          capture_output=True, text=True).stdout.strip()


class Forge:
    """The pull requests the forge reports for a commit, by sha."""

    def __init__(self, pulls: dict[str, list]) -> None:
        self.pulls = pulls

    def get(self, path: str, missing: bool = False):
        return self.pulls.get(path.removeprefix("/commits/").removesuffix("/pulls"), [])


def repository(root, record: bool = True) -> tuple[str, str]:
    """A project whose record arrived in the second commit; returns (first, record) shas."""
    git(root, "init", "-q", "--initial-branch=main")
    (root / "README.md").write_text("project\n", encoding="utf-8")
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "first")
    first = git(root, "rev-parse", "HEAD")
    if record:
        workflow = root / landed.RECORD
        workflow.parent.mkdir(parents=True, exist_ok=True)
        workflow.write_text("name: Commits on main\n", encoding="utf-8")
        git(root, "add", "-A")
        git(root, "commit", "-q", "-m", "the record arrives")
    return first, git(root, "rev-parse", "HEAD")


def commit(root, message: str) -> str:
    (root / "src.txt").write_text(message, encoding="utf-8")
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", message)
    return git(root, "rev-parse", "HEAD")


def test_a_commit_that_arrived_outside_a_pull_request_is_recorded(tmp_path, capsys):
    _, base = repository(tmp_path)
    head = commit(tmp_path, "straight to main")
    assert landed.run(tmp_path, f"{base}..{head}", Forge({})) == 1
    output = capsys.readouterr().out
    assert "FAIL [W1]" in output and head[:7] in output, output
    assert "records" in output and "refuse" in output, output


def test_a_commit_that_arrived_through_a_pull_request_passes(tmp_path, capsys):
    _, base = repository(tmp_path)
    head = commit(tmp_path, "through a pull request")
    assert landed.run(tmp_path, f"{base}..{head}", Forge({head: [{"number": 7}]})) == 0
    assert "arrived through a pull request" in capsys.readouterr().out


def test_the_record_says_nothing_about_what_predates_it(tmp_path, capsys):
    """PDR-0006: a record that fails on the commit that installed it teaches people to ignore it."""
    first, record = repository(tmp_path)
    assert landed.run(tmp_path, f"{first}..{record}", Forge({})) == 0
    assert "older than the record" in capsys.readouterr().out


def test_the_first_commit_of_a_repository_is_not_recorded(tmp_path, capsys):
    first, _ = repository(tmp_path, record=False)
    assert landed.run(tmp_path, first, Forge({})) == 0


def test_without_a_forge_nothing_is_claimed(tmp_path, capsys):
    _, base = repository(tmp_path)
    head = commit(tmp_path, "straight to main")
    assert landed.run(tmp_path, f"{base}..{head}", None) == 0
    assert "not verified" in capsys.readouterr().out


def test_a_span_whose_commits_cannot_be_read(tmp_path, capsys):
    repository(tmp_path)
    assert landed.run(tmp_path, "nope..nothing", Forge({})) == 0
    assert "not verified" in capsys.readouterr().out
