"""D153: an update says what holds its working tree, and starts from wherever the default branch's
tip is checked out (#261). The third project's checkout held one untracked file its decider keeps
there: the update said "Working tree modified", named nothing, and its action, `git stash`, leaves
an untracked file in place. The clean way round, a worktree detached at the default branch's tip,
was refused as "a detached HEAD". And Copier's "Make sure Git >= 2.24" read as a broken
workstation on git 2.56.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from napkinstack import project

ROOT = Path(__file__).resolve().parents[2]
IDENTITY = {"GIT_AUTHOR_NAME": "test", "GIT_AUTHOR_EMAIL": "test@example.invalid",
            "GIT_COMMITTER_NAME": "test", "GIT_COMMITTER_EMAIL": "test@example.invalid"}


@pytest.fixture(autouse=True)
def _identity(monkeypatch):
    for name, value in IDENTITY.items():
        monkeypatch.setenv(name, value)


def git(root: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=root, check=True, capture_output=True, text=True).stdout.strip()


@pytest.fixture
def old(tmp_path) -> Path:
    destination = tmp_path / "old"
    answers = {"project_name": "Demo", "github_repo": "acme/demo", "owner_team": "acme/platform"}
    assert project.init(destination, answers, str(ROOT), "v0.15.1") == 0
    return destination


def branches(root: Path) -> list[str]:
    return git(root, "for-each-ref", "--format=%(refname:short)", "refs/heads/nstack/").split()


def test_an_untracked_file_is_named_and_given_an_action_that_moves_it(old, capsys):
    (old / "chosen").write_text("the decider's\n", encoding="utf-8")
    capsys.readouterr()
    assert project.update(old, "HEAD") == 1
    out = capsys.readouterr().out
    assert "untracked" in out and "chosen" in out and "git stash -u" in out, out
    assert "git worktree add --detach" in out, out
    assert (old / "chosen").is_file() and branches(old) == []


def test_a_modified_file_is_named(old, capsys):
    with (old / "README.md").open("a", encoding="utf-8") as readme:
        readme.write("local change\n")
    capsys.readouterr()
    assert project.update(old, "HEAD") == 1
    out = capsys.readouterr().out
    assert "FAIL [update] Working tree modified" in out and "README.md" in out, out
    assert branches(old) == []


def test_a_worktree_detached_at_the_default_branch_s_tip_is_updated(old, tmp_path, capsys):
    (old / "chosen").write_text("the decider's\n", encoding="utf-8")
    clean = tmp_path / "clean"
    git(old, "worktree", "add", "--detach", str(clean), "main")
    capsys.readouterr()
    assert project.update(clean, "HEAD") == 0, capsys.readouterr().out
    assert git(clean, "branch", "--show-current") == "nstack/update-HEAD"


def test_a_detached_head_elsewhere_is_still_refused(old, tmp_path, capsys):
    git(old, "commit", "-q", "--allow-empty", "-m", "a second commit")
    elsewhere = tmp_path / "elsewhere"
    git(old, "worktree", "add", "--detach", str(elsewhere), "main~1")
    git(elsewhere, "commit", "-q", "--allow-empty", "-m", "a commit of its own")
    capsys.readouterr()
    assert project.update(elsewhere, "HEAD") == 1
    assert "a detached HEAD is checked out, not main" in capsys.readouterr().out


def test_copier_s_old_git_warning_is_not_shown(old, capfd):
    capfd.readouterr()
    project.update(old, "HEAD")
    seen = capfd.readouterr()
    assert "Make sure Git >= 2.24" not in seen.out + seen.err
