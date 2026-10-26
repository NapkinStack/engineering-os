"""
Checks run where the team works, recorded in git (PDR-0013, ADR-0006).

When the forge cannot run a pull request's checks, the team runs them on a workstation: this
command runs every check the project's CI runs — from one list, bound to the workflows by a
test — on a clean tree at a commit, and appends the run to that commit's note under
`refs/notes/nstack/checks`, one JSON line per run. The note travels with the branch's remote
and is merged line by line; the latest line for a commit is its record. On GitHub, with a token
that may write statuses, the run is also shown as `nstack / local checks` — a name no CI job
has. A record is *attested*, never *checked*: it makes a claim traceable, not true.

Usage :  nstack attest [--root ROOT] [--base BASE] [--body-file FILE] [--labels a,b] [--accept-identity]
Output:  0 when every check passed, 1 otherwise — the record is written either way.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from napkinstack import provenance

NOTES = "nstack/checks"
RECORD = "attested-checks/v1"
CONTEXT = "nstack / local checks"
KEPT = 64 * 1024  # bytes of a step's output kept in the record; the whole is hashed


@dataclass(frozen=True)
class Step:
    signature: str  # what the job's own `run` holds: the test binding the list to the workflows reads it
    label: str
    command: str  # bash, at the root; NSTACK_BASE, NSTACK_BODY, NSTACK_TMP and PR_LABELS are set


@dataclass(frozen=True)
class Check:
    name: str  # the CI job's name
    steps: tuple[Step, ...]
    kept: bool = False  # reads only the tree and the base: a pass on the same commit, base and engine stands (#275)


# The project's CI, job by job, as a workstation runs it (skeleton/.github/workflows/). A job or a
# step in one place and not the other fails platform/tests/test_attest.py.
CHECKS: tuple[Check, ...] = (
    Check("Fitness functions", (
        Step("nstack fitness", "Manifests, boundaries, skills, plan, hygiene", "nstack fitness --root ."),)),
    Check("PR scope and review budget", (
        Step("nstack pr-scope", "One PR = one module", 'nstack pr-scope --root . --base "$NSTACK_BASE"'),)),
    Check("Hooks and secrets", (
        Step("pre-commit run --all-files", "Hooks on every file",
             "SKIP=gitleaks pre-commit run --all-files --show-diff-on-failure"),
        Step("pre-commit run gitleaks-history", "Secrets in the whole git history",
             "pre-commit run gitleaks-history --hook-stage manual --all-files"),
        Step("pre-commit run no-session-link", "No private session link in a message",
             '{ cat "$NSTACK_BODY"; git log --format=%B "$NSTACK_BASE..HEAD"; } > "$NSTACK_TMP/said.txt" '
             '&& pre-commit run no-session-link --hook-stage commit-msg --commit-msg-filename "$NSTACK_TMP/said.txt"'),
    )),
    Check("Test sheet and cycle", (
        Step("nstack pr-check", "Test sheet and cycle",
             'nstack pr-check --root . --base "$NSTACK_BASE" --body-file "$NSTACK_BODY"'),)),
    Check("Module checks", (
        Step("bash .nstack/check-modules.sh", "Every changed module",
             'BASE="$NSTACK_BASE" bash .nstack/check-modules.sh'),), kept=True),
)


def _git(root: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, check=check)


def capped(text: str) -> str:
    """A step's output as the record keeps it: whole up to KEPT bytes, else its head and its tail."""
    data = text.encode("utf-8", "replace")
    if len(data) <= KEPT:
        return text
    half = KEPT // 2
    cut = len(data) - KEPT
    return (data[:half].decode("utf-8", "ignore") + f"\n[… {cut} bytes cut …]\n"
            + data[-half:].decode("utf-8", "ignore"))


def unplaced(value, root: Path):
    """What a record keeps, said nowhere on the machine that attested: the checkout's root as
    `<root>`, the home folder as `~` (#277). The notes are pushed, and public with the repository;
    a path names a person and their folders. Strings inside lists and mappings too."""
    if isinstance(value, str):
        for folder, said in ((root.resolve(), "<root>"), (root.absolute(), "<root>"),
                             (Path.home().resolve(), "~"), (Path.home(), "~")):
            if str(folder) not in ("", "/"):  # a whole folder only: never a neighbour, never inside a longer path
                value = re.sub(r"(?<![\w.-])" + re.escape(str(folder)) + r"(?=$|[/\s'\"`)\]}>:,;])", said, value)
        return value
    if isinstance(value, list):
        return [unplaced(item, root) for item in value]
    if isinstance(value, dict):
        return {key: unplaced(item, root) for key, item in value.items()}
    return value


def latest(root: Path, commit: str) -> dict | None:
    """The record of a commit: the latest run its note holds, or None."""
    shown = _git(root, "notes", f"--ref={NOTES}", "show", commit, check=False)
    if shown.returncode != 0:
        return None
    runs = []
    for line in shown.stdout.splitlines():
        try:
            run = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(run, dict) and run.get("record") == RECORD and run.get("commit") == commit:
            runs.append(run)
    return max(runs, key=lambda run: str(run.get("at", "")), default=None)


def _remote(root: Path) -> str | None:
    """The branch's remote, else `origin`, else none."""
    branch = _git(root, "symbolic-ref", "--quiet", "--short", "HEAD", check=False).stdout.strip()
    if branch:
        named = _git(root, "config", f"branch.{branch}.remote", check=False).stdout.strip()
        if named:
            return named
    remotes = _git(root, "remote", check=False).stdout.split()
    return "origin" if "origin" in remotes else None


def fetch(root: Path) -> str | None:
    """Brings the remote's notes in, merged line by line with ours; returns the remote's name."""
    remote = _remote(root)
    if remote is None:
        return None
    theirs = f"refs/notes/nstack-remote/{NOTES.split('/')[-1]}"
    got = _git(root, "fetch", "--quiet", remote, f"+refs/notes/{NOTES}:{theirs}", check=False)
    if got.returncode == 0:
        _git(root, "notes", f"--ref={NOTES}", "merge", "--quiet", "--strategy=cat_sort_uniq", theirs, check=False)
    return remote


def _session(root: Path, commit: str) -> str | None:
    trailers = _git(root, "log", "-1", "--format=%(trailers:key=Agent-Session,valueonly)", commit).stdout
    return trailers.strip().splitlines()[0] if trailers.strip() else None


def _show(root: Path, commit: str, passed: int, total: int) -> str:
    """The forge's display, when there is one and a token: never a judgement, a view of the record."""
    from napkinstack import hold  # the one reading of the project's GitHub

    forge = hold._forge(root, _remote(root) or "origin")
    if forge is None:
        return hold.unshown(root)
    api, repo, token = forge
    body = json.dumps({"state": "success" if passed == total else "failure", "context": CONTEXT,
                       "description": f"attested: {passed} of {total}"}).encode()
    request = urllib.request.Request(f"{api}/repos/{repo}/statuses/{commit}", data=body, method="POST",
                                     headers={"Accept": "application/vnd.github+json",
                                              "Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(request, timeout=10):
            return f"shown on GitHub as '{CONTEXT}'"
    except (OSError, ValueError) as error:
        return f"not shown on GitHub ({error})"


def evidence_of(root: Path, commit: str) -> list[dict]:
    """The audits of the end-to-end runs made on this commit (ADR-0009): each module's folder,
    relative to the project — never a path naming a person's home in notes pushed."""
    found = []
    for path in sorted(root.rglob(".evidence/e2e/audit.json")):
        try:
            audit = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(audit, dict) and audit.get("commit") == commit:
            kept = {key: value for key, value in audit.items() if key not in ("commit", "module")}
            # A log line may carry a path or a name: ten at most travel in notes pushed to a remote.
            undeclared = kept.get("undeclared") if isinstance(kept.get("undeclared"), list) else []
            kept.update(undeclared=undeclared[:10], undeclared_count=len(undeclared))
            found.append({"module": audit.get("module"), "folder": path.parent.relative_to(root).as_posix(), "audit": kept})
    return found


# GitHub's noreply address, whole: never a personal address dressed in its suffix.
NOREPLY = re.compile(r"(?:\d+\+)?[a-z0-9-]+(?:\[bot\])?@users\.noreply\.github\.com", re.I)


def _identity(root: Path) -> tuple[str, str]:
    """Who the record will name, as git would sign a commit made here — and its address."""
    ident = _git(root, "var", "GIT_COMMITTER_IDENT", check=False).stdout.strip()
    who = ident.rsplit(" ", 2)[0] if ident.count(" ") >= 2 else ident
    found = re.search(r"<([^>]*)>", who)
    return who, (found[1] if found else "").lower()


def _shown(root: Path, base: str) -> set[str]:
    """The addresses the project's history already shows, up to its base: a record never adds one."""
    log = _git(root, "log", "--format=%ae%n%ce", base, check=False)
    return {line.strip().lower() for line in log.stdout.splitlines() if line.strip()}


REASON = 8  # lines of a failed step shown when it says no FAIL line of its own


def why(output: str) -> list[str]:
    """A failed step's reason: its FAIL lines and the indented lines under each (the action), or,
    when it says none, its last lines — a check that failed says why without its whole output (#244)."""
    lines = output.splitlines()
    said, under = [], False
    for line in lines:
        if line.startswith("FAIL"):
            said.append(line)
            under = True
        elif under and line.startswith(" "):
            said.append(line)
        else:
            under = False
    return said or [line for line in lines if line.strip()][-REASON:]


def _kept(previous: dict | None, check: Check, engine: str, origin: str | None, base_commit: str | None) -> dict | None:
    """The check as the commit's record last passed it, when nothing it read can differ: the same
    commit, the same base commit, the same engine — published, or a checkout with no change of its
    own. A sheet filled in between changes the description, which this check never reads (#275)."""
    if not check.kept or previous is None or base_commit is None or "-dirty" in (origin or ""):
        return None
    if (previous.get("engine"), previous.get("origin"), previous.get("published"), previous.get("base_commit")) != (
            engine, origin, origin is None, base_commit):
        return None
    found = next((c for c in previous.get("checks") or [] if isinstance(c, dict) and c.get("name") == check.name), None)
    return {**found, "kept_from": found.get("kept_from") or previous.get("at")} if found and found.get("passed") is True else None


def run(root: Path, base: str, body_file: Path | None, labels: str | None, accept_identity: bool = False,
        again: bool = False) -> int:
    print(provenance.judged_by(root), flush=True)
    who, address = _identity(root)
    remote = _remote(root)
    if remote is not None and not accept_identity and not NOREPLY.fullmatch(address):
        if _git(root, "rev-parse", "--verify", "--quiet", f"{base}^{{commit}}", check=False).returncode != 0:
            print(f"FAIL [attest] base '{base}' not found: the identities the project already shows cannot be "
                  f"read, and the record would travel to {remote}.\n"
                  "      Action: fetch the base (git fetch), or pass --base with a commit of the shared history.")
            return 1
    # No remote: nothing travels — the record stays in this repository, whoever ran it.
    if remote is not None and not accept_identity and not NOREPLY.fullmatch(address) and address not in _shown(root, base):
        # A record travels with the notes to the remote: it never publishes an address the project
        # does not already show — a fresh clone falls back on a workstation's personal identity (#235).
        print(f"FAIL [attest] the record would name {who or 'no one'}, an identity this project's history does not "
              f"show — it travels with the notes to {remote}.\n"
              "      Action: set this checkout's identity to the one the project works under "
              "(git config user.name / user.email), or, for a first record of your own, "
              "nstack attest --accept-identity.")
        return 1
    if _git(root, "status", "--porcelain", "--untracked-files=normal").stdout.strip():
        print("FAIL [attest] the tree holds changes: a record names one commit, and this tree is none.\n"
              "      Action: commit or stash them, then run nstack attest again.")
        return 1
    commit = _git(root, "rev-parse", "HEAD").stdout.strip()
    engine, origin = provenance.engine()
    base_commit = _git(root, "rev-parse", "--verify", "--quiet", f"{base}^{{commit}}", check=False).stdout.strip() or None
    previous = None if again else latest(root, commit)
    # The option, else PR_LABELS as the caller set it: one way for attest and pr-check (D147).
    env = dict(os.environ, PR_LABELS=os.environ.get("PR_LABELS", "") if labels is None else labels)
    # The engine that runs this command runs the checks: its folder first on the path.
    env["PATH"] = os.pathsep.join([str(Path(sys.argv[0]).resolve().parent), env.get("PATH", "")])
    results = []
    with tempfile.TemporaryDirectory() as tmp:
        body = body_file or Path(tmp, "body.md")
        if body_file is None:
            body.write_text("", encoding="utf-8")
        # NSTACK_ATTESTING: pr-check, run as one of the checks, judges the pull request's rules
        # without asking for the record this run is making (A1, A2) — found rehearsing v0.10.0.
        env.update(NSTACK_BASE=base, NSTACK_BODY=str(Path(body).resolve()), NSTACK_TMP=tmp,
                   NSTACK_ATTESTING=commit)
        for check in CHECKS:
            kept = _kept(previous, check, engine, origin, base_commit)
            if kept is not None:
                results.append(kept)
                print(f"ok   [attest] {check.name}: kept from the record of {kept['kept_from']} — same commit, base "
                      "and engine (nstack attest --again runs it)", flush=True)
                continue
            steps = []
            for step in check.steps:
                done = subprocess.run(["bash", "-c", step.command], cwd=root, env=env,
                                      stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
                steps.append({"label": step.label, "command": step.command, "exit": done.returncode,
                              "output": capped(done.stdout),
                              "sha256": hashlib.sha256(done.stdout.encode("utf-8", "replace")).hexdigest()})
            passed = all(step["exit"] == 0 for step in steps)
            results.append({"name": check.name, "passed": passed, "steps": steps})
            failed = "; ".join(f"{s['label']} exited {s['exit']}" for s in steps if s["exit"])
            print(f"FAIL [attest] {check.name}: {failed}" if failed else f"ok   [attest] {check.name}", flush=True)
            for step in steps:
                if step["exit"]:
                    print("\n".join(f"       {line}" for line in why(step["output"])), flush=True)
    record = {"record": RECORD, "commit": commit,
              "at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="microseconds"),
              "engine": engine, "origin": origin, "published": origin is None, "by": who, "session": _session(root, commit),
              "base": base, "base_commit": base_commit, "checks": results, "evidence": evidence_of(root, commit)}
    remote = fetch(root)
    before = _git(root, "notes", f"--ref={NOTES}", "show", commit, check=False)
    lines = (before.stdout.rstrip("\n") + "\n" if before.returncode == 0 and before.stdout.strip() else "")
    lines += json.dumps(unplaced(record, root), separators=(",", ":"), ensure_ascii=False) + "\n"
    subprocess.run(["git", "notes", f"--ref={NOTES}", "add", "--force", "--file=-", commit], cwd=root,
                   input=lines, text=True, capture_output=True, check=True)
    passed = sum(1 for result in results if result["passed"])
    where = "local only: no remote"
    if remote is not None:
        pushed = _git(root, "push", "--quiet", remote, f"refs/notes/{NOTES}", check=False)
        where = f"pushed to {remote}" if pushed.returncode == 0 else f"NOT pushed to {remote}: {pushed.stderr.strip()}"
    print(f"Record of {commit[:12]}: attested: {passed} of {len(results)}; {where}; {_show(root, commit, passed, len(results))}.")
    return 0 if passed == len(results) else 1
