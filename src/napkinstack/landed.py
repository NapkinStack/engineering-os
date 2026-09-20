"""
What reached the default branch (PDR-0006).

Rule:
  W1  a commit on the default branch arrived through a pull request

This is a record, not a barrier. Where the forge can refuse — a ruleset requiring a pull
request — nothing reaches the default branch any other way, and this says so. Where it
cannot, because the repository's plan does not allow it, a commit pushed straight to the
branch is the one thing nobody would otherwise be told about. A record that fires late is
worth more than a silence.

It says nothing about what predates it: the commit that created the repository, and
everything the repository already held when the record arrived, are not reported. A record
that greets a project by failing on its own arrival teaches people to ignore it.

The forge is read with a token supplied by the run (GH_TOKEN, otherwise GITHUB_TOKEN), which
needs no write access of any kind: the project's automation token stays read-only (G10).
Without a token, or when the span cannot be read, nothing is claimed.

Usage :  nstack landed [--root ROOT] [--span BEFORE..AFTER]
Output:  0 when every commit of the span arrived through a pull request, or when nothing
         could be verified; 1 when one did not.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import yaml

from napkinstack.doctor import GitHub, NotVerified
from napkinstack.project import ANSWERS

# The workflow that runs this record in a generated project. Its own arrival is what the
# record treats as its beginning; platform/tests/run.sh checks the two names match.
RECORD = ".github/workflows/commits-on-main.yml"
EMPTY = "0" * 40


def _git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=root, capture_output=True, text=True)


def _commits(root: Path, span: str) -> list[str] | None:
    """The commits of the span, newest first; None when the span cannot be read."""
    before, _, after = span.partition("..")
    if not after or before in ("", EMPTY):
        after, before = (after or before), ""          # a branch's first push has no before
    read = (_git(root, "rev-list", f"{before}..{after}") if before
            else _git(root, "rev-list", "-1", after))
    return None if read.returncode else read.stdout.split()


def _beginning(root: Path) -> str | None:
    """The commit that brought the record into the repository, if it is there."""
    read = _git(root, "log", "--diff-filter=A", "--format=%H", "--", RECORD)
    return read.stdout.split()[-1] if read.returncode == 0 and read.stdout.split() else None


def _exempt(root: Path, commit: str, beginning: str | None) -> str | None:
    """Why this commit is not recorded, or None when it is to be checked."""
    if _git(root, "rev-parse", "--verify", "--quiet", f"{commit}^").returncode:
        return "the first commit of the repository"
    if beginning and _git(root, "merge-base", "--is-ancestor", commit, beginning).returncode == 0:
        return "older than the record itself"
    return None


def _described(root: Path, commit: str) -> str:
    return _git(root, "show", "-s", "--format=%h (%an, %ad)", "--date=short", commit).stdout.strip()


def run(root: Path, span: str, forge: GitHub | None) -> int:
    commits = _commits(root, span)
    if commits is None:
        print(f"[W1] the commits of '{span}' cannot be read: not verified.\n"
              "      Action: fetch the history (fetch-depth: 0), or pass an existing range.")
        return 0
    if forge is None:
        print("[W1] no token (GH_TOKEN or GITHUB_TOKEN): how each commit arrived is not verified.\n"
              "      Action: supply a token with read access to the repository's pull requests.")
        return 0
    beginning = _beginning(root)
    outside, checked = [], 0
    for commit in commits:
        why = _exempt(root, commit, beginning)
        if why:
            print(f"Commit {_described(root, commit)}: not recorded, {why}.")
            continue
        try:
            pulls = forge.get(f"/commits/{commit}/pulls")
        except NotVerified as reason:
            print(f"[W1] commit {commit[:12]}: not verified. Reason: {reason}")
            continue
        checked += 1
        if pulls:
            print(f"Commit {_described(root, commit)}: arrived through a pull request.")
        else:
            outside.append(commit)
    for commit in outside:
        print(f"FAIL [W1] commit {_described(root, commit)} reached this branch outside a pull "
              "request.\n      This run records it; it does not refuse it — on this repository "
              "nothing could.\n      Action: read the commit. If it was not meant to land this "
              "way, revert it through a pull request.")
    if outside:
        return 1
    if checked:
        print(f"Every commit of this push arrived through a pull request ({checked} checked).")
    return 0


def from_environment(root: Path) -> GitHub | None:
    """The forge, read-only, from the project's own answers and the run's token."""
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not token:
        return None
    answers = yaml.safe_load((root / ANSWERS).read_text(encoding="utf-8")) or {}
    return GitHub(str(answers.get("github_repo")), token,
                  os.environ.get("GITHUB_API_URL") or "https://api.github.com")
