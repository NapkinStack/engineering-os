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
        # An unpublished version is recorded as git describes it, vX.Y.Z-N-g<commit>: a
        # description, not a name the forge knows. The commit inside it is one (D86).
        described = re.fullmatch(r".+-\d+-g([0-9a-f]{7,40})", current)
        at = described[1] if described else current
        return (f"https://github.com/{found['repo']}/blob/{at}/CHANGELOG.md"
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


FORGES = ("github", "gitlab", "forgejo", "gitea", "other", "none")
OWNERSHIP = (Path(".github") / "CODEOWNERS", Path("CODEOWNERS"), Path("docs") / "CODEOWNERS")


def answer(root: Path, key: str):
    """One answer of the project's answers file; None without the file or the answer."""
    return _answers(root).get(key) if (root / ANSWERS).is_file() else None


def forge(root: Path) -> str:
    """The project's forge, as its answers file says it (PDR-0018): GitHub where it says none."""
    value = answer(root, "forge")
    return str(value) if value in FORGES else "github"


def ownership(root: Path) -> Path:
    """The ownership file the forge reads: the first that exists, else where this forge's goes."""
    found = next((root / path for path in OWNERSHIP if (root / path).is_file()), None)
    if found is not None:
        return found
    return root / (OWNERSHIP[0] if forge(root) == "github" else OWNERSHIP[1])


def settle_checks(root: Path, given: dict) -> None:
    """A forge chosen at Copier's prompt is unknown before the copy: off GitHub, where no CI is
    shipped, `checks` is attested unless the caller gave it (PDR-0018)."""
    path = root / ANSWERS
    if "checks" in given or not path.is_file() or forge(root) == "github":
        return
    text = path.read_text(encoding="utf-8")
    path.write_text(re.sub(r"^checks: forge$", "checks: attested", text, flags=re.M), encoding="utf-8")


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
    if "github_repo" in data:
        data.setdefault("forge", "github")  # a GitHub repository named: the forge needs no asking
    named = data.get("forge", "github")
    if named in ("github", "none") and data.get("repository"):
        print(f"FAIL [init] --repository names a repository at another forge, and this project's forge is "
              f"{named}.\n      Action: " + ("give --github-repo instead." if named == "github" else "leave it out: "
              "with no forge there is no repository but this folder."))
        return 1
    if named != "github" and data.get("github_repo"):
        print(f"FAIL [init] github_repo is GitHub's answer, and this project's forge is {named}.\n"
              "      Action: give its repository at that forge with --repository, or choose --forge github.")
        return 1
    # Not asked at init (Copier would ask): a project on GitHub starts on its CI; elsewhere no CI
    # is shipped, and its checks are attested (PDR-0018) — settled after the copy when the forge
    # was asked by Copier itself.
    data.setdefault("checks", "forge" if named == "github" else "attested")
    data.setdefault("hold_days", 7)  # a hold goes stale after a week without work (ADR-0007)
    try:
        copier.run_copy(source, destination, data=data, vcs_ref=ref, quiet=True, unsafe=False)
    except (CopierError, ValueError, OSError) as exc:
        print(_explain(exc, "init", destination, source, ref))
        return 1

    settle_checks(destination, given=data)
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
    named = str(created.get("forge") or "github")
    if named == "github":
        print(f"  2. Create the GitHub repository {created.get('github_repo')}, push main to it, then apply "
              "these settings:")
        for _, setting, _ in CHECKLIST:
            print(f"     - [ ] {setting}")
        print("  3. Check the workstation and GitHub, read-only: nstack doctor (token: see .nstack/handbook/INSTALL.md)")
        return 0
    where = (f"Create the repository {created.get('repository')} at {named}, push main to it"
             if named != "none" else "No forge: the repository is this folder")
    print(f"  2. {where}. No CI is shipped for {named}: a change's checks are attested where the team "
          "works — nstack attest — and the repository is unguarded: nothing at the forge refuses a merge "
          "(.nstack/handbook/07-governance.md).")
    print("  3. Check the workstation, read-only: nstack doctor")
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


# The contracts module left the skeleton: it is created by the first contract (PDR-0012). A
# project that already holds a contract must keep the module the skeleton gave it — the merge
# would otherwise take its manifest and its owner from under the contracts the project wrote.
CONTRACTS_SCAFFOLD = {"contracts/AGENTS.md", "contracts/MANIFEST.yaml", "contracts/README.md",
                      "contracts/docs/runbook.md", "contracts/tests/.gitkeep", "contracts/.gitkeep"}


def _keep_contracts(root: Path, base: str) -> bool:
    """Restores the contracts module's own files, and its line among the code owners, when the
    project held anything in `contracts/` beyond what the skeleton had put there. True when
    something was restored."""
    held = [path for path in _git(root, "ls-tree", "-r", "--name-only", "-z", base, "--", "contracts").stdout.split("\0") if path]
    if not any(path not in CONTRACTS_SCAFFOLD for path in held):
        return False
    lost = [path for path in held if path in CONTRACTS_SCAFFOLD and not (root / path).exists()]
    for path in lost:
        _git(root, "checkout", base, "--", path)
    owners = root / ".github" / "CODEOWNERS"
    before = [line for line in _git(root, "show", f"{base}:.github/CODEOWNERS").stdout.splitlines()
              if line.split()[:1] == ["/contracts/"]]
    if before and owners.is_file():
        content = owners.read_text(encoding="utf-8")
        if not any(line.split()[:1] == ["/contracts/"] for line in content.splitlines()):
            owners.write_text(content.rstrip("\n") + "\n\n# Contracts: the most critical boundary in the "
                              f"system, never orphaned.\n{before[0]}\n", encoding="utf-8")
            return True
    return bool(lost)


OLD_ADDRESS = re.compile(r"(?<![\w./-])(?:" + "|".join(
    [re.escape(path) for path in MOVED_FILES] + [re.escape(folder) + r"[\w./-]*" for folder in MOVED_FOLDERS]) + ")")
LINK = re.compile(r"(\]\()([^)\s#]+)")


def _readdress(root: Path) -> tuple[list[str], list[str]]:
    """What the project wrote about the pages that moved, in files no update touches — its
    front page, its decisions, a module's manifest — is rewritten to their new addresses: a
    path named from the root, and a relative link, resolved from the file that holds it. Only
    an address that was the framework's is changed, and only when its new place exists.
    A module's code is left as written and named (D88): changing it changes that module, and
    the update's pull request would owe what a change of every such module owes.
    Returns the files rewritten, and the files left."""
    from napkinstack.fitness.manifests import find_manifests, is_description

    modules = [manifest.parent.relative_to(root).as_posix() + "/" for manifest in find_manifests(root)]
    rewritten: list[str] = []
    left: list[str] = []
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
        if changed == text:
            continue
        if any(name.startswith(folder) and not is_description(name[len(folder):]) for folder in modules):
            left.append(name)
            continue
        file.write_text(changed, encoding="utf-8")
        rewritten.append(name)
    return rewritten, left


def update(root: Path, ref: str, session: str | None = None) -> int:
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
        # Before the addresses: a contracts module the merge took away is no module, and its
        # contracts would be rewritten as if they were nobody's.
        contracts_kept = _keep_contracts(root, base)
        readdressed, left = _readdress(root) if crossed else ([], [])
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
    # An agent's update carries the kernel's trailer, as every commit it makes (D135).
    message = f"NapkinStack {previous} -> {current}" + (f"\n\nAgent-Session: {session}" if session else "")
    for args in (("add", "--all"), ("commit", "--quiet", "--message", message)):
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
    if contracts_kept:
        print("contracts/ kept: the skeleton no longer creates that module, and this project holds a "
              "contract in it — its manifest, its owner and its pages stay.")
    if readdressed:
        print("The project's own files named pages that moved: old addresses rewritten, to review in the "
              "pull request, in:")
        for name in readdressed:
            print(f"  - {name}")
    if left:
        print("A module's code is its owner's: an old address is left as written, for a pull request of "
              "that module, in:")
        for name in left:
            print(f"  - {name}")
    print(f"What {previous} -> {current} changes, engine and project apart: "
          f"{release_notes(str(_answers(root).get('_src_path') or ''), previous, current)}")
    print(f"\n{next_step(root, branch)}")
    return 0


def next_step(root: Path, branch: str) -> str:
    """Who checks the update's branch: the forge's CI on GitHub with `checks: forge`; elsewhere a
    record made on this workstation (ADR-0010 §9)."""
    if forge(root) == "github" and answer(root, "checks") != "attested":
        return f"Next step: git push -u origin {branch}, then open the PR; CI validates it."
    if forge(root) == "none":
        return f"Next step: nstack attest on {branch}, then merge it as the project merges its changes."
    return f"Next step: nstack attest on {branch}, then git push -u origin {branch} and open the pull request."
