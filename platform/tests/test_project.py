"""
Copier's refusals, translated (P6): the message names what happened, and the action is one
the reader can carry out (D50, D54). Run by platform/tests/run.sh.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from napkinstack import project

CACHE = """Unexpected exit code: 128
Command line: | /usr/bin/git fetch --tags
Stderr:       | error: cannot open '/c/copier/git/81c2bf.git/FETCH_HEAD': Read-only file system
              | fatal: could not fetch"""
GIT_ADD = """Unexpected exit code: 128
Command line: | /usr/bin/git --git-dir=.git --work-tree=/w add -A
Stderr:       | error: .bash_profile: can only add regular files, symbolic links or git-directories
              | fatal: adding files failed"""


def test_a_git_error_keeps_the_line_that_says_what_happened():
    """D54: `fatal: adding files failed` alone names neither the file nor the cause, and the
    action that followed it — check --source, --ref and the network — could not help."""
    message = project._explain(OSError(GIT_ADD), "init", Path("/w"), ".", "HEAD")
    assert "error: .bash_profile: can only add regular files" in message, message
    assert "fatal: adding files failed" in message, message
    assert "commit or stash" in message, message
    assert "network access" not in message, message


def test_a_local_error_that_is_not_the_working_tree():
    """D55: the action D54 added over-claims. A read-only Copier cache is a git `error:` line
    too, and telling its reader to commit the template's working tree cannot help (P6)."""
    message = project._explain(OSError(CACHE), "init", Path("/w"), ".", "v1.0.0")
    assert "Read-only file system" in message, message
    assert "git named what it could not handle above" in message, message


def test_init_names_what_makes_the_folder_full(tmp_path, capsys):
    """D56: "pick a folder that is missing or empty" sends the reader hunting, and what fills
    the folder is usually hidden files an editor or an agent left. Found on the pilot, at the
    framework's very first gesture."""
    (tmp_path / ".vscode").mkdir()
    (tmp_path / ".mcp.json").write_text("{}\n", encoding="utf-8")
    assert project.init(tmp_path, {}, "unused", "v1.0.0") == 1
    output = capsys.readouterr().out
    assert ".mcp.json" in output and ".vscode" in output, output
    assert str(tmp_path) in output, output


@pytest.mark.parametrize(("source", "expected"), [
    ("https://github.com/NapkinStack/engineering-os.git",
     "https://github.com/NapkinStack/engineering-os/releases/tag/v1.2.3"),
    ("https://github.com/NapkinStack/engineering-os",
     "https://github.com/NapkinStack/engineering-os/releases/tag/v1.2.3"),
    ("gh:NapkinStack/engineering-os",
     "https://github.com/NapkinStack/engineering-os/releases/tag/v1.2.3"),
    ("https://gitlab.com/acme/os.git", "CHANGELOG.md, section v1.2.3, in https://gitlab.com/acme/os.git"),
    ("/srv/checkouts/framework", "CHANGELOG.md, section v1.2.3, in /srv/checkouts/framework"),
])
def test_update_says_where_the_notes_are(source, expected):
    """D62: an update is offered for review, and nothing says what it changes. The published
    package does not carry the skeleton, so the artefacts cannot answer either (D63)."""
    assert project.release_notes(source, "v1.2.3") == expected


def test_a_single_line_error_is_unchanged():
    """The neighbour: with nothing to prefer, the last line still carries the message."""
    message = project._explain(OSError("Could not resolve host: github.com"), "init",
                               Path("/w"), "gh:acme/x", "v1.0.0")
    assert "Could not resolve host: github.com" in message, message
    assert "check --source and --ref" in message, message
