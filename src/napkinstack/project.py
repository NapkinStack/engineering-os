"""
Creating and updating a project (PDR-0001), through Copier (ADR-0001).

Copier is driven by its API, never in "unsafe" mode. Its refusals arrive before any
change and are translated into messages naming the rule, the place and the action (P6).

An update starts from a committed state and lays the target version, merged with the
project's adaptations, on the branch nstack/update-<version>. A conflict is never
committed: it stays marked in the file for the team, and both the check-merge-conflict
hook and CI reject any remaining marker.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import yaml

from napkinstack import __version__

SOURCE = "https://github.com/NapkinStack/engineering-os.git"
ANSWERS = ".copier-answers.yml"
DOWNGRADE = re.compile(r"You are downgrading from (\S+) to (\S+)\.")
# The forms of a GitHub source Copier records, from which a release page can be named.
GITHUB = re.compile(r"^(?:https://github\.com/|git@github\.com:|gh:)(?P<repo>[^/]+/[^/]+?)(?:\.git)?/?$")


def default_ref() -> str:
    """The skeleton of the engine version: they move up together (PDR-0001 R2)."""
    return f"v{__version__}"


def release_notes(source: str, ref: str) -> str:
    """Where to read what a version changes, before taking it. The published package carries
    the engine and not the skeleton, so comparing two releases of it cannot show what an update
    merges (D63): the notes are the only channel, and the command that brings the change names
    them (D62)."""
    found = GITHUB.match(source.strip())
    if found:
        return f"https://github.com/{found['repo']}/releases/tag/{ref}"
    return f"CHANGELOG.md, section {ref}, in {source}"


def _git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=root, capture_output=True, text=True)


def _answers(root: Path) -> dict:
    return yaml.safe_load((root / ANSWERS).read_text(encoding="utf-8")) or {}


def _explain(exc: Exception, command: str, where: Path, source: str, ref: str) -> str:
    """Translates a Copier refusal (P6)."""
    from copier.errors import UnsafeTemplateError

    text = str(exc).strip()
    action = "      Action: "
    if isinstance(exc, UnsafeTemplateError):
        return (f"FAIL [{command}] Template {source} runs code ({text.splitlines()[0]}): "
                f"refused (ADR-0001).\n{action}check --source; NapkinStack never enables those features.")
    if text.startswith("Validation error for question '"):
        question, _, detail = text.removeprefix("Validation error for question '").partition("': ")
        return (f"FAIL [{command}] Answer rejected for {question}: {detail.strip()}\n"
                f"{action}run again with a valid value.")
    if text.startswith("Destination repository is dirty"):
        return (f"FAIL [{command}] Working tree modified in {where}: an update starts from a "
                f"committed state (PDR-0001).\n{action}commit or stash (git stash), then run again.")
    if match := DOWNGRADE.search(text):
        # The action is a command, not a description of one: an install pinned to an exact
        # version is not moved by `uv tool upgrade`, which is what a reader tries first.
        return (f"FAIL [{command}] Target version {match[2]} older than the project version ({match[1]}): "
                f"no going back (PDR-0001).\n{action}move this workstation forward first — "
                'uv tool install "napkinstack@latest" --with-executables-from pre-commit — '
                f"or pin the version you want, {match[1]} or newer.")
    if text.startswith("Updating is only supported in git-tracked subprojects"):
        return (f"FAIL [{command}] {where} is not a git repository: the merge relies on "
                f"history.\n{action}git init, commit, then run again.")
    if text.startswith("Cannot update: version from last update not detected"):
        return (f"FAIL [{command}] The project does not come from a published version (_commit in {ANSWERS}): "
                f"no merge base.\n{action}create the project from a vX.Y.Z tag.")
    # An OSError carrying an errno is the filesystem answering, not the template being out of
    # reach: a full disk, a read-only path, a directory an interrupted run left behind. Calling
    # it "unreachable" sends the reader to --source, --ref and the network, none of which can
    # help (D65). The OSErrors Copier raises for a template it could not read carry no errno.
    if isinstance(exc, OSError) and exc.errno:
        return (f"FAIL [{command}] {command} stopped on a local filesystem error: {text}\n"
                f"{action}read the error above and fix what it names \u2014 space, permissions, or "
                "something left behind by an interrupted run. The template and the network are "
                "not in question.")
    if isinstance(exc, OSError) or text == "Local template must be a directory.":
        lines = [line.split("|", 1)[-1].strip() for line in text.splitlines() if line.strip()]
        # git writes the cause on an `error:` line and the outcome on a `fatal:` one; keeping
        # the last line alone drops the only one that says what happened (D54).
        detail = " — ".join(line for line in lines if line.startswith(("error:", "fatal:"))) or lines[-1]
        # A git `error:` line means git refused something local, and git has already named it:
        # a file of the template's uncommitted state, which Copier copies into its clone, or
        # anything else it could not open. The action points at that line rather than guessing
        # which of the two it was (D55).
        local = ("git named what it could not handle above: fix that file, or, when the "
                 "template's working tree is uncommitted, commit or stash it — Copier copies it "
                 "as it is.")
        remote = "check --source and --ref (a vX.Y.Z tag), and network access."
        return (f"FAIL [{command}] Template {source} at version {ref} unreachable: {detail}\n"
                + action + (local if detail.startswith("error:") else remote))
    return f"FAIL [{command}] Copier: {text}"


def init(destination: Path, answers: dict[str, str | None], source: str, ref: str) -> int:
    import copier
    from copier.errors import CopierError

    from napkinstack.doctor import CHECKLIST

    destination = destination.resolve()
    if destination.exists() and not destination.is_dir():
        print(f"FAIL [init] {destination} is a file, not a folder: nstack init creates a new "
              "project.\n      Action: pick a folder that is missing or empty.")
        return 1
    # Naming what fills the folder: it is usually hidden — an editor's, an agent's — and a
    # reader told only "not empty" goes hunting for it (D56).
    entries = sorted(entry.name for entry in destination.iterdir()) if destination.exists() else []
    if entries:
        listed = ", ".join(entries[:4]) + (f", and {len(entries) - 4} more" if len(entries) > 4 else "")
        print(f"FAIL [init] {destination} is not empty: it holds {listed}.\n"
              "      Action: pick a folder that is missing or empty, or create the project in a "
              f"folder inside it — nstack init {destination}/<project>.")
        return 1
    data = {question: value for question, value in answers.items() if value is not None}
    try:
        copier.run_copy(source, destination, data=data, vcs_ref=ref, quiet=True, unsafe=False)
    except (CopierError, ValueError, OSError) as exc:
        print(_explain(exc, "init", destination, source, ref))
        return 1

    created = _answers(destination)
    version = created.get("_commit", ref)
    for args in (("init", "--quiet", "--initial-branch=main"), ("add", "--all"),
                 ("commit", "--quiet", "--message", f"Project created, NapkinStack {version}")):
        result = _git(destination, *args)
        if result.returncode:
            print(f"FAIL [init] Project generated in {destination}, but `git {args[0]}` failed:\n"
                  f"      {result.stderr.strip()}\n"
                  "      Action: fix it (identity: git config user.name and user.email), "
                  "then git add --all && git commit.")
            return 1

    print(f"Project created in {destination}, NapkinStack {version}, initial commit on main.")
    print("\nNext steps:")
    print(f"  1. cd {destination} && pre-commit install")
    print(f"  2. Create the GitHub repository {created.get('github_repo')}, push main to it, then apply "
          "these settings:")
    for _, setting, _ in CHECKLIST:
        print(f"     - [ ] {setting}")
    print("  3. Check the workstation and GitHub, read-only: nstack doctor (token: see the README)")
    return 0


def update(root: Path, ref: str) -> int:
    import copier
    from copier.errors import CopierError

    if not (root / ANSWERS).is_file():
        print(f"FAIL [update] {ANSWERS} not found in {root}: this folder is not a project "
              "created by nstack init.\n      Action: run the command at the project root, "
              "or pass --root.")
        return 1
    previous = str(_answers(root).get("_commit"))
    if previous == ref:
        print(f"Already up to date: NapkinStack {ref}.")
        return 0
    branch = f"nstack/update-{ref}"
    if _git(root, "rev-parse", "--verify", "--quiet", f"refs/heads/{branch}").returncode == 0:
        print(f"FAIL [update] Branch {branch} already exists in {root}.\n"
              "      Action: merge it or delete it (git branch -D), then run again.")
        return 1
    try:
        copier.run_update(root, vcs_ref=ref, overwrite=True, skip_answered=True, defaults=True,
                          conflict="inline", quiet=True, unsafe=False)
    except (CopierError, ValueError, OSError) as exc:
        print(_explain(exc, "update", root, str(_answers(root).get("_src_path")), ref))
        return 1

    if not _git(root, "status", "--porcelain").stdout.strip():
        print(f"Already up to date: nothing changes between NapkinStack {previous} and {ref}.")
        return 0
    current = str(_answers(root).get("_commit"))
    switch = _git(root, "switch", "--create", branch)
    if switch.returncode:
        print(f"FAIL [update] Branch {branch} could not be created: {switch.stderr.strip()}\n"
              "      Action: the changes stay in the working tree; create the branch "
              "by hand, then commit.")
        return 1
    conflicts = [path for path in _git(root, "diff", "--name-only", "-z", "--diff-filter=U").stdout.split("\0") if path]
    if conflicts:
        print(f"FAIL [update] NapkinStack {previous} -> {current}: conflicts with the project's "
              f"adaptations, marked on branch {branch} in:")
        for path in conflicts:
            print(f"  - {path}")
        print("      Action: in each file, keep the right version between <<<<<<< and >>>>>>>, "
              "then git add --all && git commit.\n      The check-merge-conflict hook and CI "
              "reject any remaining marker.")
        return 1
    for args in (("add", "--all"), ("commit", "--quiet", "--message", f"NapkinStack {previous} -> {current}")):
        result = _git(root, *args)
        if result.returncode:
            print(f"FAIL [update] Update laid on {branch}, but `git {args[0]}` failed:\n"
                  f"      {(result.stdout + result.stderr).strip()}\n"
                  "      Action: fix it, then git add --all && git commit.")
            return 1

    print(f"Branch {branch}: NapkinStack {previous} -> {current}, merged with the project's "
          "adaptations.")
    print(f"What {current} changes, engine and project apart: "
          f"{release_notes(str(_answers(root).get('_src_path') or ''), current)}")
    print(f"\nNext step: git push -u origin {branch}, then open the PR; CI validates it.")
    return 0
