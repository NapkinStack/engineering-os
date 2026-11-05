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
    """The pull requests the forge reports for a commit, by sha, and the record's last run that
    succeeded, when there is one."""

    def __init__(self, pulls: dict[str, list], recorded: str | None = None, merged: dict[int, str] | None = None,
                 referenced: dict[int, list[str]] | None = None, padding: int = 0) -> None:
        self.pulls, self.recorded, self.merged = pulls, recorded, merged or {}
        self.referenced, self.padding = referenced or {}, padding

    def get(self, path: str, missing: bool = False):
        if path.startswith("/actions/workflows/"):
            return {"workflow_runs": [{"head_sha": self.recorded}] if self.recorded else []}
        if path.startswith("/issues/"):  # a pull request's events, by number: its merged event, or 404
            number = int(path.split("/")[2])
            if number not in self.merged:
                return None
            # A direct push whose subject says (#N) leaves a referenced event naming it: only `merged` proves.
            events = [{"event": "referenced", "commit_id": sha} for sha in self.referenced.get(number, [])]
            events += [{"event": "labeled", "commit_id": None}] * self.padding
            events += [{"event": "merged", "commit_id": self.merged[number]}, {"event": "closed", "commit_id": None}]
            page = int(path.split("page=")[-1]) if "&page=" in path else 1
            return events[(page - 1) * 100:page * 100]
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


def test_a_merge_whose_link_the_forge_lost_is_read_from_the_pull_request_it_names(tmp_path, capsys):
    """#356: the forge answered no pull request for a squash merge of #645 — its commit→pull request
    link lost —, and W1 failed on it at every later push. The pull request the subject names says
    which commit it merged: when it is this one, the commit arrived through it."""
    _, base = repository(tmp_path)
    head = commit(tmp_path, "PDR-0006: the product is named Kitokey (#645)")
    assert landed.run(tmp_path, f"{base}..{head}", Forge({}, merged={645: head})) == 0, capsys.readouterr().out
    assert "arrived through pull request #645, which merged it" in capsys.readouterr().out


def test_a_subject_naming_a_pull_request_that_did_not_merge_it_is_still_recorded(tmp_path, capsys):
    """Anyone may write `(#645)`; only the forge says what #645 merged. Another commit, or no such
    pull request, and the commit is recorded as before."""
    _, base = repository(tmp_path)
    other = commit(tmp_path, "the real merge (#645)")
    head = commit(tmp_path, "straight to main (#645)")
    assert landed.run(tmp_path, f"{other}..{head}", Forge({}, merged={645: other})) == 1
    assert "FAIL [W1]" in capsys.readouterr().out
    assert landed.run(tmp_path, f"{other}..{head}", Forge({})) == 1
    assert "FAIL [W1]" in capsys.readouterr().out


def test_only_the_merged_event_proves_and_it_is_read_past_the_first_page(tmp_path, capsys):
    """A direct push naming #645 leaves a referenced event with its own commit: recorded. A pull request with
    more events than one page holds its merged event further on: read there."""
    _, base = repository(tmp_path)
    merge = commit(tmp_path, "the real merge (#645)")
    head = commit(tmp_path, "straight to main (#645)")
    assert landed.run(tmp_path, f"{merge}..{head}", Forge({}, merged={645: merge}, referenced={645: [head]})) == 1
    assert "FAIL [W1]" in capsys.readouterr().out
    assert landed.run(tmp_path, f"{base}..{merge}", Forge({}, merged={645: merge}, padding=250)) == 0
    assert "through pull request #645" in capsys.readouterr().out


def test_a_merge_commit_s_subject_names_its_pull_request_and_only_at_its_end_a_squash_s(tmp_path, capsys):
    _, base = repository(tmp_path)
    merge = commit(tmp_path, "Merge pull request #12 from acme/branch")
    assert landed.run(tmp_path, f"{base}..{merge}", Forge({}, merged={12: merge})) == 0
    capsys.readouterr()
    head = commit(tmp_path, "revert (#12) by hand")
    assert landed.run(tmp_path, f"{merge}..{head}", Forge({}, merged={12: head})) == 1


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


def test_a_push_whose_run_never_started_is_read_by_the_next_one(tmp_path, capsys):
    """Measured on 2026-10-14: an organisation's minutes ran out, no job started, and the ranges
    of those pushes were never read again. The record reads from the last commit it recorded."""
    _, record = repository(tmp_path)
    missed = commit(tmp_path, "pushed while no run could start")
    head = commit(tmp_path, "through a pull request, once runs start again")
    assert landed.run(tmp_path, f"{missed}..{head}", Forge({head: [{"number": 8}]}, recorded=record)) == 1
    output = capsys.readouterr().out
    assert "FAIL [W1]" in output and missed[:7] in output, output
    assert "since the last commit it recorded" in output, output


def test_a_record_that_never_succeeded_reads_the_push_alone(tmp_path, capsys):
    """What predates the record's first success stays unread, as PDR-0006 decides."""
    _, record = repository(tmp_path)
    older = commit(tmp_path, "before any record succeeded")
    head = commit(tmp_path, "through a pull request")
    assert landed.run(tmp_path, f"{older}..{head}", Forge({head: [{"number": 9}]})) == 0
    assert older[:7] not in capsys.readouterr().out
