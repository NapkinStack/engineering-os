"""
Fitness function 5 — What a shared repository must not carry.

A tracked file is read by everyone who clones the repository, and by their agents. A path
rooted in one person's home directory is wrong for all of them: it does not exist on their
machine, and it publishes the layout — often the locale — of the machine it was written on.
Found in M9 (D27): a plan told its reader to change into the French name of the author's
desktop folder, four times, once inside a block meant to be copy-pasted.

Rules:
  H1  no path rooted in a personal home directory, in any tracked text file

Refused: the home of a named user, on any of the three systems, and a tilde followed by a
real folder. Accepted, because they are true on every machine: a tilde followed by a
dot-directory (`~/.config`, `~/.cache`, `~/.ssh` — tooling is documented legitimately), a
tilde inside an address, the repository's placeholders (`<workspace>`), environment
variables, and the home of an image's own user — `node`, `vscode`, `runner`, `codespace`,
`gitpod`, `jovyan` — which is the same wherever the image runs (D41).

The patterns are written so that this file, the rule's tests and any document describing
the rule are not findings of it: a placeholder or a concatenation never matches. That is
deliberate — there is no way to mark a line as allowed, so no file can exempt itself.

Files out of the rule's subject are named here rather than configurable. .copier-answers.yml
is written by Copier, which forbids editing it by hand (ADR-0001): the template source it
records is a fact about how the project was generated, not a sentence a reader can act on.
A container or a runner's definition — a Dockerfile, a compose file, .devcontainer/, the
workflows — describes a machine that is the same for everyone, not one person's (D41).

Usage :  nstack hygiene [--root ROOT]
Output:  0 when no tracked file carries such a path; 1 otherwise.
A root that is not a git repository is out of scope: the check reads the tracked files.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

GENERATED = {"copier-answers.yml", ".copier-answers.yml"}
MACHINES = re.compile(r"(^|/)(Dockerfile[^/]*|[^/]*\.dockerfile|(docker-)?compose[^/]*\.ya?ml)$"
                      r"|(^|/)\.devcontainer/|^\.github/workflows/")
IMAGE_USERS = r"(?:node|vscode|runner|codespace|gitpod|jovyan)(?![A-Za-z0-9_.-])"
SEGMENT = r"[A-Za-z0-9_.-]+"
HOME_PATH = re.compile(
    rf"(?:/home/(?!{IMAGE_USERS}){SEGMENT}|/Users/{SEGMENT}|[A-Za-z]:\\Users\\{SEGMENT}"
    r"|(?<![\w/:])~(?=/[A-Za-z0-9]))"
    r"[^\s'\"`,;)\]]*"
)
ACTION = ("write what the step needs: a path relative to the repository, a placeholder such "
          "as <idea-file>, or a variable the reader sets")


def tracked_files(root: Path) -> list[Path] | None:
    """The tracked files, or None when the root is not a git repository."""
    try:
        listed = subprocess.run(["git", "ls-files", "-z"], cwd=root, check=True,
                                capture_output=True)
    except (OSError, subprocess.CalledProcessError):
        return None
    names = listed.stdout.decode("utf-8", "surrogateescape").split("\0")
    return [root / name for name in names if name]


def run(root: Path) -> int:
    files = tracked_files(root)
    if files is None:
        print(f"Hygiene: not applicable, {root} is not a git repository.")
        return 0

    failures: list[str] = []
    read = 0
    for path in files:
        if path.name in GENERATED or MACHINES.search(path.relative_to(root).as_posix()):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue  # binary, or listed by git and no longer on disk
        read += 1
        for number, line in enumerate(text.splitlines(), start=1):
            found = HOME_PATH.search(line)
            if found:
                failures.append(f"[H1] {path.relative_to(root)}:{number}\n"
                                f"      '{found.group()}' is a path in someone's home "
                                f"directory — {ACTION}")

    print(f"Hygiene: {read} tracked text file(s) read.")
    for failure in failures:
        print(f"  FAIL {failure}")
    if failures:
        print(f"\n{len(failures)} violation(s). A tracked file is read on every machine "
              "but the one it was written on.")
        return 1
    print("Hygiene: compliant.")
    return 0
