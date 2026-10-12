"""
Creating and updating a project (PDR-0001), through Copier (ADR-0001).

Copier is driven by its API, never in "unsafe" mode. Its refusals arrive before any
change and are translated into messages naming the rule, the place and the action (P6).

An update starts from a committed state on the default branch and lays the target version,
merged with the project's adaptations, on the branch nstack/update-<version>. A conflict is never
committed: it stays marked in the file for the team, and both the check-merge-conflict
hook and CI reject any remaining marker.
"""

from __future__ import annotations

import os
import re
import subprocess
import tempfile
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


def release_notes(source: str, previous: str, current: str) -> str:
    """Where to read what a version changes, before taking it. The published package carries
    the engine and not the skeleton, so comparing two releases of it cannot show what an update
    merges (D63): the notes are the only channel, and the command that brings the change names
    them (D62).

    It names the whole distance travelled, never the target alone (D66). One `nstack update`
    can cross several versions, and the change that conflicts with the project's own files may
    come from any of them: a release page holds one version and cannot answer for the others.
    The CHANGELOG at the tag holds them all."""
    found = GITHUB.match(source.strip())
    if found:
        return (f"https://github.com/{found['repo']}/blob/{current}/CHANGELOG.md"
                f" — every section above {previous}")
    return f"CHANGELOG.md, every section above {previous}, in {source}"


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
                f"refused.\n{action}check --source; NapkinStack never enables those features.")
    if text.startswith("Validation error for question '"):
        question, _, detail = text.removeprefix("Validation error for question '").partition("': ")
        return (f"FAIL [{command}] Answer rejected for {question}: {detail.strip()}\n"
                f"{action}run again with a valid value.")
    if text.startswith("Destination repository is dirty"):
        return (f"FAIL [{command}] Working tree modified in {where}: an update starts from a "
                f"committed state.\n{action}commit or stash (git stash), then run again.")
    if match := DOWNGRADE.search(text):
        # The action is a command, not a description of one: an install pinned to an exact
        # version is not moved by `uv tool upgrade`, which is what a reader tries first.
        return (f"FAIL [{command}] Target version {match[2]} older than the project version ({match[1]}): "
                f"no going back.\n{action}move this workstation forward first — "
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
    print("  3. Check the workstation and GitHub, read-only: nstack doctor (token: see .nstack/handbook/INSTALL.md)")
    return 0


def _default_branch(root: Path) -> str | None:
    """The branch an update starts from: the remote's default, else the `main` that `init`
    creates. None when neither can be read — then nothing is refused on a guess."""
    remote = _git(root, "symbolic-ref", "--quiet", "--short", "refs/remotes/origin/HEAD")
    if remote.returncode == 0 and "/" in remote.stdout.strip():
        return remote.stdout.strip().split("/", 1)[1]
    if _git(root, "rev-parse", "--verify", "--quiet", "refs/heads/main").returncode == 0:
        return "main"
    return None


# Where the framework's files went when they were gathered under one folder (PDR-0012). A
# rename in a template is a deletion and an addition to the tool that merges it: what a project
# had adapted in the old place is dropped with the old file, without a conflict and without a
# word. Found on the pilot, which had added one line to a page that moved.
MOVED_FOLDERS = {"playbooks/": ".nstack/playbooks/", "docs/os/": ".nstack/handbook/"}
MOVED_FILES = {
    "docs/project/README.md": ".nstack/handbook/project.md",
    "docs/tooling-profile.md": ".nstack/tooling-profile.md",
    "docs/adr/_TEMPLATE.md": ".nstack/forms/adr.md",
    "docs/pdr/_TEMPLATE.md": ".nstack/forms/pdr.md",
    "docs/project/_CHARTER_TEMPLATE.md": ".nstack/forms/charter.md",
    "docs/project/_DISCOVERY_TEMPLATE.md": ".nstack/forms/discovery.md",
    "docs/project/cycles/_TEMPLATE.md": ".nstack/forms/cycle.md",
    "docs/project/rules/_TEMPLATE.md": ".nstack/forms/rules.md",
}


def _moved(path: str) -> str | None:
    if path in MOVED_FILES:
        return MOVED_FILES[path]
    return next((new + path[len(old):] for old, new in MOVED_FOLDERS.items() if path.startswith(old)), None)


def _carry(root: Path, base: str, previous: str) -> tuple[list[str], list[str]]:
    """After an update that moved files: each one the project had adapted in its old place is
    merged — the project's change against what the framework wrote there — into its new place.
    Returns what was carried and what conflicted, as "old -> new". Nothing is carried, and the
    older skeleton is not even fetched, when no file of the project sat in an old place."""
    import copier

    held = [path for path in _git(root, "ls-tree", "-r", "--name-only", "-z", base).stdout.split("\0")
            if path and _moved(path) and (root / _moved(path)).is_file() and not (root / path).exists()]
    if not held:
        return [], []
    answers = yaml.safe_load(_git(root, "show", f"{base}:{ANSWERS}").stdout) or {}
    data = {key: value for key, value in answers.items() if not key.startswith("_")}
    carried: list[str] = []
    conflicted: list[str] = []
    with tempfile.TemporaryDirectory() as scratch:
        before = Path(scratch) / "before"  # the skeleton as the project received it last
        copier.run_copy(str(answers.get("_src_path")), before, data=data, vcs_ref=previous,
                        quiet=True, unsafe=False, defaults=True)
        for path in held:
            mine = _git(root, "show", f"{base}:{path}").stdout
            theirs = before / path
            if not theirs.is_file() or theirs.read_text(encoding="utf-8", errors="replace") == mine:
                continue  # never adapted: the new file is already the right one
            own = Path(scratch) / "mine"
            own.write_text(mine, encoding="utf-8")
            new = root / _moved(path)
            merged = subprocess.run(["git", "merge-file", "-p", "-L", "the framework's new version",
                                     "-L", "the framework's old version", "-L", "the project's adaptation",
                                     str(new), str(theirs), str(own)], capture_output=True, text=True)
            if merged.returncode < 0 or merged.returncode > 127:
                continue  # the merge itself failed: the new file is left as the framework wrote it
            new.write_text(merged.stdout, encoding="utf-8")
            (conflicted if merged.returncode else carried).append(f"{path} -> {_moved(path)}")
    return carried, conflicted


OLD_ADDRESS = re.compile(r"(?<![\w./-])(?:" + "|".join(
    [re.escape(path) for path in MOVED_FILES] + [re.escape(folder) + r"[\w./-]*" for folder in MOVED_FOLDERS]) + ")")
LINK = re.compile(r"(\]\()([^)\s#]+)")


def _readdress(root: Path) -> list[str]:
    """What the project wrote about the pages that moved, in files no update touches — its
    front page, its decisions, a module's manifest — is rewritten to their new addresses: a
    path named from the root, and a relative link, resolved from the file that holds it. Only
    an address that was the framework's is changed, and only when its new place exists.
    Returns the files rewritten."""
    rewritten: list[str] = []
    tracked = [path for path in _git(root, "ls-files", "-z").stdout.split("\0") if path]
    for name in tracked:
        if name.startswith((".nstack/", ".git/")) or name == ANSWERS:
            continue
        file = root / name
        try:
            text = file.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue

        def link(match: re.Match) -> str:
            target = match[2]
            if "://" in target or target.startswith(("/", "mailto:")):
                return match[0]
            old = os.path.normpath(os.path.join(os.path.dirname(name), target)).replace(os.sep, "/")
            new = _moved(old) or (_moved(old + "/") if target.endswith("/") else None)
            if not new or not (root / new).exists():
                return match[0]
            return match[1] + os.path.relpath(new, os.path.dirname(name) or ".").replace(os.sep, "/")

        def address(match: re.Match) -> str:
            new = _moved(match[0])
            return new if new and (root / new).exists() else match[0]

        changed = OLD_ADDRESS.sub(address, LINK.sub(link, text))
        # A link whose text was the old file's bare name — [`_TEMPLATE.md`](./_TEMPLATE.md) —
        # would keep a label naming a file that no longer exists.
        changed = re.sub(r"\[`_TEMPLATE\.md`\]\(([^)\s]*\.nstack/forms/(\w+)\.md)\)", r"[`.nstack/forms/\2.md`](\1)", changed)
        if changed != text:
            file.write_text(changed, encoding="utf-8")
            rewritten.append(name)
    return rewritten


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
    # D74: the update branch is created where HEAD stands. From a feature branch it carries that
    # branch's commits, and the pull request that should hold the framework alone does not.
    default, current_branch = _default_branch(root), _git(root, "branch", "--show-current").stdout.strip()
    if default and current_branch != default:
        where = current_branch or "a detached HEAD"
        print(f"FAIL [update] {where} is checked out, not {default}: the update branch would "
              f"carry its commits.\n      Action: git switch {default}, then run again.")
        return 1
    base = _git(root, "rev-parse", "HEAD").stdout.strip()
    try:
        copier.run_update(root, vcs_ref=ref, overwrite=True, skip_answered=True, defaults=True,
                          conflict="inline", quiet=True, unsafe=False)
        carried, moved_conflicts = _carry(root, base, previous)
        # Only a project that crosses the move: one already in the new layout holds no file
        # in an old place, and its own files are not read.
        crossed = any(_moved(path) for path in _git(root, "ls-tree", "-r", "--name-only", "-z", base).stdout.split("\0") if path)
        readdressed = _readdress(root) if crossed else []
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
    conflicts += [pair.split(" -> ")[1] for pair in moved_conflicts]
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
    if carried:
        print("The framework's files moved, and what the project had adapted in them moved with it:")
        for pair in carried:
            print(f"  - {pair}")
    if readdressed:
        print("The project's own files named pages that moved: old addresses rewritten, to review in the "
              "pull request, in:")
        for name in readdressed:
            print(f"  - {name}")
    print(f"What {previous} -> {current} changes, engine and project apart: "
          f"{release_notes(str(_answers(root).get('_src_path') or ''), previous, current)}")
    print(f"\nNext step: git push -u origin {branch}, then open the PR; CI validates it.")
    return 0
