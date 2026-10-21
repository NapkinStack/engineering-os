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
             'BASE="$NSTACK_BASE" bash .nstack/check-modules.sh'),)),
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
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    url = _git(root, "remote", "get-url", _remote(root) or "origin", check=False).stdout.strip()
    from napkinstack.doctor import ON_GITHUB  # the doctor's reading of a GitHub remote

    found = ON_GITHUB.search(url)
    if not token or not found:
        return "not shown on a forge (no GitHub remote, or no token)"
    api = os.environ.get("GITHUB_API_URL", "https://api.github.com").rstrip("/")
    body = json.dumps({"state": "success" if passed == total else "failure", "context": CONTEXT,
                       "description": f"attested: {passed} of {total}"}).encode()
    request = urllib.request.Request(f"{api}/repos/{found.group(1)}/statuses/{commit}", data=body, method="POST",
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


NOREPLY = re.compile(r"@users\.noreply\.github\.com$", re.I)


def _identity(root: Path, base: str) -> tuple[str, str]:
    """Who the record will name, as git would sign a commit made here — and its address."""
    ident = _git(root, "var", "GIT_COMMITTER_IDENT", check=False).stdout.strip()
    who = ident.rsplit(" ", 2)[0] if ident.count(" ") >= 2 else ident
    found = re.search(r"<([^>]*)>", who)
    return who, (found[1] if found else "").lower()


def _shown(root: Path, base: str) -> set[str]:
    """The addresses the project's history already shows, up to its base: a record never adds one."""
    log = _git(root, "log", "-n", "1000", "--format=%ae%n%ce", base, check=False)
    return {line.strip().lower() for line in log.stdout.splitlines() if line.strip()}


def run(root: Path, base: str, body_file: Path | None, labels: str, accept_identity: bool = False) -> int:
    print(provenance.judged_by(root), flush=True)
    who, address = _identity(root, base)
    if not accept_identity and not NOREPLY.search(address) and address not in _shown(root, base):
        # A record travels with the notes to the remote: it never publishes an address the project
        # does not already show — a fresh clone falls back on a workstation's personal identity (#235).
        print(f"FAIL [attest] the record would name {who}, an identity this project's history does not "
              f"show — it travels with the notes to {_remote(root) or 'the remote'}.\n"
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
    env = dict(os.environ, PR_LABELS=labels)
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
    record = {"record": RECORD, "commit": commit,
              "at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="microseconds"),
              "engine": engine, "published": origin is None, "by": who, "session": _session(root, commit),
              "base": base, "checks": results, "evidence": evidence_of(root, commit)}
    remote = fetch(root)
    before = _git(root, "notes", f"--ref={NOTES}", "show", commit, check=False)
    lines = (before.stdout.rstrip("\n") + "\n" if before.returncode == 0 and before.stdout.strip() else "")
    lines += json.dumps(record, separators=(",", ":"), ensure_ascii=False) + "\n"
    subprocess.run(["git", "notes", f"--ref={NOTES}", "add", "--force", "--file=-", commit], cwd=root,
                   input=lines, text=True, capture_output=True, check=True)
    passed = sum(1 for result in results if result["passed"])
    where = "local only: no remote"
    if remote is not None:
        pushed = _git(root, "push", "--quiet", remote, f"refs/notes/{NOTES}", check=False)
        where = f"pushed to {remote}" if pushed.returncode == 0 else f"NOT pushed to {remote}: {pushed.stderr.strip()}"
    print(f"Record of {commit[:12]}: attested: {passed} of {len(results)}; {where}; {_show(root, commit, passed, len(results))}.")
    return 0 if passed == len(results) else 1
