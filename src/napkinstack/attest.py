"""
Checks run where the team works, recorded in git (PDR-0013, ADR-0006).

When the forge cannot run a pull request's checks, the team runs them on a workstation: this
command runs every check the project's CI runs — from one list, bound to the workflows by a
test — on a clean tree at a commit, and appends the run to that commit's note under
`refs/notes/nstack/checks`, one JSON line per run. The note travels with the branch's remote
and is merged line by line; the latest line for a commit is its record. On GitHub, with a token
that may write statuses, the run is also shown as `nstack / local checks` — a name no CI job
has. A passed `Module checks` is kept, not run again, while the digest of what it reads is
unchanged — the modules it runs and those they consume from or assemble, the files outside the
modules, `contracts/` and `platform/` included, the project's records (`docs/project/`, `docs/adr/`,
`docs/pdr/`) left out, the engine and the person — for 7 days and 20 commits of the default branch at most (ADR-0006,
D223). A ruleset that requires that name gates the merge on the record, and the forge's pull
request run leaves the record to it (D221): notes start no run, a status is an event.
A record is *attested*, never *checked*: it makes a claim traceable, not true.

Usage :  nstack attest [--root ROOT] [--base BASE] [--body-file FILE] [--labels a,b] [--accept-identity]
Output:  0 when every check passed, 1 otherwise — the record is written either way.
"""

from __future__ import annotations

import base64
import datetime
import hashlib
import json
import os
import stat
import re
import signal
import subprocess
import sys
import tempfile
import threading
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


MARK = 48  # bytes a cut's mark may take: `[… N bytes cut …]` and its newlines


def _cut(data: bytes, room: int) -> str:
    """Whole up to room bytes, else a quarter of it from the head, the rest from the tail."""
    if len(data) <= room:
        return data.decode("utf-8", "ignore")
    head = max(room - MARK, 0) // 4
    tail = max(room - MARK, 0) - head
    return (data[:head].decode("utf-8", "ignore") + f"\n[… {len(data) - head - tail} bytes cut …]\n"
            + (data[-tail:].decode("utf-8", "ignore") if tail else ""))


def capped(text: str) -> str:
    """A step's output as the record keeps it: whole up to KEPT bytes, else cut log group by log
    group — one per module in Module checks — so that each keeps its commands and its results,
    the room a small one leaves going to the others (#295). No group: one head and one tail."""
    data = text.encode("utf-8", "replace")
    if len(data) <= KEPT:
        return text
    starts = [found.start() for found in re.finditer(rb"^::group::", data, re.M)]
    bounds = [0, *(start for start in starts if start), len(data)]
    parts = [data[start:end] for start, end in zip(bounds, bounds[1:])]
    room, given = KEPT, {}
    for index in sorted(range(len(parts)), key=lambda index: len(parts[index])):
        share = room // (len(parts) - len(given))
        given[index] = min(len(parts[index]), share)
        room -= given[index]
    return "".join(_cut(part, given[index]) for index, part in enumerate(parts))


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


def _lines(root: Path, commit: str) -> list[dict]:
    """The runs and voids a commit's note holds, in no order: notes merge line by line, sorted."""
    shown = _git(root, "notes", f"--ref={NOTES}", "show", commit, check=False)
    found = []
    for line in shown.stdout.splitlines() if shown.returncode == 0 else []:
        try:
            run = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(run, dict) and run.get("record") == RECORD and run.get("commit") == commit:
            found.append(run)
    return found


def voided_runs(root: Path, commit: str) -> set[str]:
    """The runs of a commit a void named, by their time (#429): each void lists the runs the note
    held when it was made, so a clock ahead or a merge of notes never brings one back."""
    return {str(at) for line in _lines(root, commit) if line.get("void") and isinstance(line.get("voids"), list)
            for at in line["voids"]}


def latest(root: Path, commit: str) -> dict | None:
    """The record of a commit: the latest run its note holds that no void named; else its latest
    void, when every run was voided; else None."""
    lines = _lines(root, commit)
    gone = voided_runs(root, commit)
    runs = [line for line in lines if not line.get("void") and str(line.get("at", "")) not in gone]
    voids = [line for line in lines if line.get("void")]
    return max(runs or voids, key=lambda run: str(run.get("at", "")), default=None)


def kept_from_voided(root: Path, check: dict, commit: str) -> bool:
    """Whether a check a record kept comes from a run since voided (#429): its first run, on the
    commit it was kept from, or on this one."""
    first = check.get("kept_from") if isinstance(check, dict) else None
    return bool(first) and str(first) in voided_runs(root, str(check.get("kept_commit") or commit))


def void(root: Path, ref: str, reason: str, base: str = "origin/main", accept_identity: bool = False) -> int:
    """Marks a commit's record as known unsound — a run that shared what it must not, a tool that
    lied (#429): a line of its own in the note naming every run the note holds. None of them is a
    record afterwards, nor kept from, on its commit or through another commit's record (D223), and
    pr-check reads the head unattested until it is attested again. The runs stay in the note:
    evidence is never rewritten."""
    reason = " ".join(reason.split())
    if not reason:
        print("FAIL [attest] a void says why: the next reader of the record is owed the reason.\n"
              '      Action: nstack attest --void <commit> --reason "<what made it unsound>".')
        return 1
    who, refused = _publishable(root, base, accept_identity)
    if refused:
        print(refused.replace("the record would", "the void would"))
        return 1
    commit = _git(root, "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}", check=False).stdout.strip()
    remote, unread = read_remote(root)
    if remote is not None and unread:
        print(f"FAIL [attest] the notes of {remote} are not read ({unread}): a void names every run they hold, "
              "and one unread would stay a record.\n      Action: fix the access, then again.")
        return 1
    runs = [line for line in _lines(root, commit) if not line.get("void")] if commit else []
    if not runs:
        print(f"FAIL [attest] no record of {ref} to void: nothing is kept from a run that was never recorded.\n"
              "      Action: name the commit whose record is unsound (git notes --ref=nstack/checks list).")
        return 1
    line = {"record": RECORD, "commit": commit,
            "at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="microseconds"),
            "by": who, "void": unplaced(reason, root), "voids": sorted(str(run.get("at", "")) for run in runs),
            "checks": []}
    before = _git(root, "notes", f"--ref={NOTES}", "show", commit, check=False).stdout.rstrip("\n")
    subprocess.run(["git", "notes", f"--ref={NOTES}", "add", "--force", "--file=-", commit], cwd=root,
                   input=before + "\n" + json.dumps(line, separators=(",", ":"), ensure_ascii=False) + "\n",
                   text=True, capture_output=True, check=True)
    if not (latest(root, commit) or {}).get("void"):
        print(f"FAIL [attest] the void of {commit[:12]} is written, yet a run stays its record.\n"
              "      Action: report it: git notes --ref=nstack/checks show " + commit[:12])
        return 1
    where, pushed = "local only: no remote", True
    if remote is not None:
        sent = _git(root, "push", "--quiet", remote, f"refs/notes/{NOTES}", check=False)
        pushed = sent.returncode == 0
        where = f"pushed to {remote}" if pushed else f"NOT pushed to {remote}: {sent.stderr.strip()}"
    print(f"Record of {commit[:12]}: voided by {who} — {line['void']}; {where}; {_show(root, commit, 0, 0, line['void'])}.\n"
          + ("      Nothing is kept from it any more; the commit is attested again by nstack attest on it."
             if pushed else "      Action: push again (git push " + str(remote) + " refs/notes/" + NOTES
             + "): until then only this clone knows."))
    return 0 if pushed else 1


def _remote(root: Path) -> str | None:
    """The branch's remote, else `origin`, else none."""
    branch = _git(root, "symbolic-ref", "--quiet", "--short", "HEAD", check=False).stdout.strip()
    if branch:
        named = _git(root, "config", f"branch.{branch}.remote", check=False).stdout.strip()
        if named and named != ".":  # "." tracks a local branch: no remote
            return named
    remotes = _git(root, "remote", check=False).stdout.split()
    return "origin" if "origin" in remotes else None


def fetch_env(url: str, token: str | None) -> dict[str, str]:
    """In GitHub Actions only, the credential a fetch from GitHub carries — in git's environment,
    never in an argument a log shows, and masked for the runner. CI's checkout keeps none
    (`persist-credentials: false`); the job's token reads (#367). Never on a workstation: there the
    remote's own credential answers, and a token in the environment, perhaps expired, would be sent
    before it and refuse the fetch."""
    if os.environ.get("GITHUB_ACTIONS") != "true" or not token or not url.startswith("https://github.com/"):
        return {}
    secret = base64.b64encode(f"x-access-token:{token}".encode()).decode()
    print(f"::add-mask::{secret}", flush=True)  # as actions/checkout does, and hold's own fetch
    return {"GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": "http.https://github.com/.extraheader",
            "GIT_CONFIG_VALUE_0": f"AUTHORIZATION: basic {secret}"}


def _why(stderr: str) -> str:
    """git's reason, in one line: its `fatal:` line when it says one, else its last."""
    lines = [line.strip() for line in stderr.strip().splitlines() if line.strip()]
    fatal = [line for line in lines if line.startswith("fatal:")]
    return (fatal or lines or ["no reason given"])[0 if fatal else -1]


def read_remote(root: Path) -> tuple[str | None, str | None]:
    """Brings the remote's notes in, merged line by line with ours. Returns the remote's name, and
    why its notes were not read — None when they were, or when it holds none."""
    remote = _remote(root)
    if remote is None:
        return None, "no remote"
    url = _git(root, "remote", "get-url", remote, check=False).stdout.strip()
    env = dict(os.environ, **fetch_env(url, os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")))

    def git(*args: str) -> subprocess.CompletedProcess:
        return subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, env=env)

    listed = git("ls-remote", remote, f"refs/notes/{NOTES}")
    if listed.returncode != 0:
        return remote, f"{remote} did not answer: {_why(listed.stderr)}"
    if not listed.stdout.strip():
        return remote, None  # read: the remote holds no record at all
    theirs = f"refs/notes/nstack-remote/{NOTES.split('/')[-1]}"
    got = git("fetch", "--quiet", remote, f"+refs/notes/{NOTES}:{theirs}")
    if got.returncode != 0:
        return remote, f"{remote}'s notes not fetched: {_why(got.stderr)}"
    _git(root, "notes", f"--ref={NOTES}", "merge", "--quiet", "--strategy=cat_sort_uniq", theirs, check=False)
    return remote, None


def fetch(root: Path) -> str | None:
    """Brings the remote's notes in, merged line by line with ours; returns the remote's name."""
    return read_remote(root)[0]


def _session(root: Path, commit: str) -> str | None:
    trailers = _git(root, "log", "-1", "--format=%(trailers:key=Agent-Session,valueonly)", commit).stdout
    return trailers.strip().splitlines()[0] if trailers.strip() else None


def _show(root: Path, commit: str, passed: int, total: int, voided: str | None = None) -> str:
    """The forge's display, when there is one and a token: never a judgement, a view of the record."""
    from napkinstack import hold  # the one reading of the project's GitHub

    forge = hold._forge(root, _remote(root) or "origin")
    if forge is None:
        return hold.unshown(root)
    api, repo, token = forge
    body = json.dumps({"state": "success" if passed == total and voided is None else "failure", "context": CONTEXT,
                       "description": f"voided: {voided}"[:140] if voided is not None
                       else f"attested: {passed} of {total}"}).encode()
    request = urllib.request.Request(f"{api}/repos/{repo}/statuses/{commit}", data=body, method="POST",
                                     headers={"Accept": "application/vnd.github+json",
                                              "Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(request, timeout=10):
            return f"shown on GitHub as '{CONTEXT}'"
    except (OSError, ValueError) as error:
        return (f"not shown on GitHub ({error}) — a ruleset requiring '{CONTEXT}' waits for it: a token that "
                "may write commit statuses — an older agent App gets Commit statuses: write in its "
                "settings, accepted on its installation — then nstack attest again")


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


EXITED = re.compile(r"FAIL \[\w+\] module '[^']+': `.*` exited with \d+\.")


def why(output: str) -> list[str]:
    """A failed step's reason: its FAIL lines and the indented lines under each (the action), or,
    when it says none, its last lines — a check that failed says why without its whole output (#244).
    A module command that exited non-zero says no more than its code: the last lines its own tool
    wrote before it come first — a test runner's summary names the test that failed (#428)."""
    lines = output.splitlines()
    said, under, tool, audit = [], False, [], False
    for line in lines:
        if line.startswith("FAIL"):
            if EXITED.match(line):
                said.extend(tool[-REASON:])
                tool = []
            said.append(line)
            under = True
        elif under and line.startswith(" "):
            said.append(line)
        else:
            under = False
        if line.startswith(("::group::", "-> ")):
            tool, audit = [], False  # a module's own command writes after the engine says it runs it
        elif line.startswith("Evidence of "):
            audit = True  # and before the engine audits its evidence: those lines are the engine's
        elif line.strip() and not audit and not line.startswith(("FAIL", "::")):
            tool.append(line)
    return said or [line for line in lines if line.strip()][-REASON:]


LOG_KEPT = 8 * 1024 * 1024  # bytes of a failed step's output kept in its log, the last ones


def keep_log(root: Path, commit: str, check: str, steps: list[tuple[str, str]]) -> Path:
    """A failed check's whole output, in the clone's git folder — never in the tree, where it would
    leave changes the next attest refuses: the record keeps 64 KiB of it and a FAIL line a few
    lines; a test that fails once and passes again is named here, or nowhere (#428). Its last
    8 MiB when longer; the next failure of the same commit and check replaces it."""
    folder = (root / _git(root, "rev-parse", "--git-path", "nstack/attest").stdout.strip()).resolve()
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{commit[:12]}-{re.sub(r'[^a-z0-9]+', '-', check.lower()).strip('-')}.log"
    text = steps[0][1] if len(steps) == 1 else "".join(f"== {label}\n{output.rstrip(chr(10))}\n" for label, output in steps)
    data = text.encode("utf-8", "replace")
    path.write_bytes(data if len(data) <= LOG_KEPT else data[-LOG_KEPT:])
    return path


# An engine whose code a string names: published, a forge's commit, or a checkout's own commit.
NAMED = re.compile(r".* \(commit [0-9a-f]{7,}\)|.*@[0-9a-f]{7,}|a local checkout at (?!an unknown commit)\S+(?<!-dirty)")


FRESH_DAYS = 7  # a check kept by its inputs, at most this old (ADR-0006, D223)
FRESH_COMMITS = 20  # and the default branch moved by at most this many commits since its run


SHARED_MODULES = ("contracts", "platform")  # read by every module: counted as shared files (D223)
# The project's records — charter, cycles, rules, log; ADRs; PDRs: no module check reads them (D242).
# The rest of the root `docs/` stays an input: a module's end-to-end run may check a page it ships.
RECORDS = ("docs/project/", "docs/adr/", "docs/pdr/")


def inputs(root: Path, base: str, identity: str = "", commit: str = "HEAD") -> str | None:
    """The digest of what `Module checks` reads at `commit`, HEAD by default (ADR-0006 decision 2, D223): the folders of
    the modules it runs, of those they consume from or assemble, every tracked path outside the
    module folders — `contracts/` and `platform/` included, which every module reads — but the
    project's records, `docs/project/`, `docs/adr/` and `docs/pdr/` (D242), and who runs it with which
    engine; git's ids, never hashed by hand. None when it cannot be told: no key."""
    # The scope is the working tree's: the head locally and under nstack attest; on the forge the checkout
    # is the test merge, which can only widen it — conservative (D295). Read at `commit`, a manifest that
    # moved in between is a folder read whole, and so a difference.
    scope = input_scope(root, base)
    if scope is None:
        return None
    names, folders, inside = scope
    lines = [f"ran {' '.join(names)}", f"identity {identity}"]
    for folder in sorted(folders):
        tree = _git(root, "rev-parse", "--verify", "--quiet", f"{commit}:{folder}", check=False).stdout.strip()
        if not tree:
            return None
        lines.append(f"{folder} {tree}")
    # -z: a path git would quote — a record whose name is not ASCII, `résumé.md` — is read as it is.
    listed = _git(root, "ls-tree", "-r", "-z", "--full-tree", commit, check=False)
    if listed.returncode:
        return None
    lines += [line for line in listed.stdout.split("\0")
              if line and not line.split("\t", 1)[-1].startswith((*inside, *RECORDS))]
    return hashlib.sha256("\n".join(lines).encode("utf-8", "surrogateescape")).hexdigest()


def input_scope(root: Path, base: str) -> tuple[list[str], set[str], tuple[str, ...]] | None:
    """What `inputs` hashes: the modules run, the folders read whole — theirs and those they consume
    or assemble —, and the module folders left out, every other tracked path but the records being
    read (D275: T4 names the ones that changed). None when it cannot be told."""
    import yaml

    from napkinstack import modules

    ran = modules.listing(root, base, with_contract_sides=True)
    every = {module["name"]: module["folder"] for module in modules.listing(root) or []}
    if ran is None:
        return None
    folders = {module["folder"] for module in ran}
    for module in ran:
        try:
            data = yaml.safe_load((root / module["folder"] / "MANIFEST.yaml").read_text(encoding="utf-8")) or {}
        except (OSError, yaml.YAMLError):
            return None
        consumes = data.get("consumes") if isinstance(data, dict) else None
        assembles = data.get("assembles") if isinstance(data, dict) else None
        named = [entry.get("module") for entry in consumes if isinstance(entry, dict) and entry.get("module")] \
            if isinstance(consumes, list) else []
        named += [name for name in assembles if isinstance(name, str)] if isinstance(assembles, list) else []
        for name in named:
            if name not in every:
                return None  # a dependency the project does not hold: what it reads is unknown
            folders.add(every[name])
    inside = tuple(f"{folder}/" for folder in every.values() if folder.split("/", 1)[0] not in SHARED_MODULES)
    return sorted(module["name"] for module in ran), folders, inside


def _fresh(root: Path, at: str, run_base: str | None, base_commit: str | None) -> bool:
    """Whether a run kept by its inputs is recent enough (ADR-0006, D223)."""
    try:
        when = datetime.datetime.fromisoformat(at)
    except (TypeError, ValueError):
        return False
    now = datetime.datetime.now(datetime.timezone.utc)
    if when.tzinfo is None or now - when > datetime.timedelta(days=FRESH_DAYS) or when - now > datetime.timedelta(minutes=5):
        return False  # too old, or from a clock ahead: never fresh for longer than the bound
    if not run_base or not base_commit:
        return False
    moved = _git(root, "rev-list", "--count", f"{run_base}..{base_commit}", check=False)
    return moved.returncode == 0 and int(moved.stdout.strip() or 0) <= FRESH_COMMITS


def _by_inputs(root: Path, base: str, digest: str | None, check: Check, engine: str, origin: str | None,
               base_commit: str | None, who: str, said: str | None) -> dict | None:
    """The check as a passed run on this branch's history left it, when what it reads is the same
    — the digest of its inputs, whatever the commit — and the run is fresh (ADR-0006, D223)."""
    if digest is None or not check.kept or base_commit is None or not (origin is None or NAMED.fullmatch(origin)):
        return None
    for commit in _git(root, "rev-list", f"{base_commit}..HEAD", check=False).stdout.split():
        record = latest(root, commit)  # a voided commit's latest line is its void: no check is kept from it
        if record is None or (record.get("engine"), record.get("origin"), record.get("published"),
                              record.get("by")) != (engine, said, origin is None, who):
            continue
        checks = record.get("checks") if isinstance(record.get("checks"), list) else []
        found = next((c for c in checks if isinstance(c, dict) and c.get("name") == check.name), None)
        if not found or found.get("passed") is not True or found.get("inputs") != digest:
            continue
        if kept_from_voided(root, found, commit):
            continue  # kept, through this record, from a run since voided (#429)
        first = str(found.get("kept_from") or record.get("at", ""))
        run_base = found.get("kept_base") or record.get("base_commit")
        if not _fresh(root, first, run_base, base_commit):
            continue
        return {**found, "kept_from": first, "kept_commit": found.get("kept_commit") or commit, "kept_base": run_base}
    return None


def _kept(previous: dict | None, check: Check, engine: str, origin: str | None, base_commit: str | None,
          who: str, said: str | None = None, root: Path | None = None) -> dict | None:
    """The check as the commit's record last passed it, when what it reads is the same: the commit,
    the base commit, the engine — published, or one whose commit names its code — and the person who
    ran it. A sheet filled in between changes the description, which this check never reads (#275).
    Not compared: what the tree's ignored files, the environment or the tools outside it hold."""
    said = origin if said is None else said  # the origin as the record wrote it, its paths unplaced (D162)
    if not check.kept or previous is None or base_commit is None or not (origin is None or NAMED.fullmatch(origin)):
        return None
    if (previous.get("engine"), previous.get("origin"), previous.get("published"), previous.get("base_commit"),
            previous.get("by")) != (engine, said, origin is None, base_commit, who):
        return None
    checks = previous.get("checks") if isinstance(previous.get("checks"), list) else []
    found = next((c for c in checks if isinstance(c, dict) and c.get("name") == check.name), None)
    if not found or found.get("passed") is not True or found.get("kept_commit"):
        return None  # kept by its inputs from another commit: its freshness is _by_inputs' to judge (D223)
    if root is not None and kept_from_voided(root, found, str(previous.get("commit", ""))):
        return None  # kept, on this commit, from a run since voided: a clone that had not seen the void (#429)
    return {**found, "kept_from": found.get("kept_from") or previous.get("at")}


def sheet_of(body: str) -> dict | None:
    """The sheet's rows as this run read them (D214): what each claims — kind, result, commit — and a
    digest of its evidence, never the evidence itself. pr-check compares a later description with
    them: a row whose commit moved and whose evidence did not was never run again."""
    from napkinstack.pull_request import read_sheet  # the one reader of the sheet

    _, _, rows = read_sheet(body)
    found = {row["#"]: {"kind": row.get("kind", "").lower(), "result": row.get("result", "").lower(),
                        "commit": row.get("commit", "").strip().strip("`").lower(),
                        "evidence": hashlib.sha256(row.get("evidence", "").strip().encode()).hexdigest()[:16]}
             for row in rows if row.get("#")}
    return found or None


def _publishable(root: Path, base: str, accept_identity: bool) -> tuple[str, str | None]:
    """Who a line of the notes will name, and why it may not travel: the notes go to the remote, and
    never publish an address the project does not already show (#235) — a run's record, or a void."""
    who, address = _identity(root)
    remote = _remote(root)
    if remote is not None and not accept_identity and not NOREPLY.fullmatch(address):
        if _git(root, "rev-parse", "--verify", "--quiet", f"{base}^{{commit}}", check=False).returncode != 0:
            return who, (f"FAIL [attest] base '{base}' not found: the identities the project already shows cannot "
                         f"be read, and the record would travel to {remote}.\n"
                         "      Action: fetch the base (git fetch), or pass --base with a commit of the shared history.")
    # No remote: nothing travels — the record stays in this repository, whoever ran it.
    if remote is not None and not accept_identity and not NOREPLY.fullmatch(address) and address not in _shown(root, base):
        # A record travels with the notes to the remote: it never publishes an address the project
        # does not already show — a fresh clone falls back on a workstation's personal identity (#235).
        return who, (f"FAIL [attest] the record would name {who or 'no one'}, an identity this project's history "
                     f"does not show — it travels with the notes to {remote}.\n"
                     "      Action: set this checkout's identity to the one the project works under "
                     "(git config user.name / user.email), or, for a first record of your own, "
                     "nstack attest --accept-identity.")
    return who, None


def _masked(root: Path) -> list[str]:
    """The tracked paths this session cannot read — each under the first path that hides it — as an
    agent's sandbox makes them: a mount point over `.claude/skills/`, which git may show as untracked,
    or not at all once it is told to ignore it (#514). A file deleted is a change, said as one."""
    hidden: list[str] = []
    # -t: a path a sparse checkout leaves out (S, skip-worktree) is meant to be absent, as `nstack agent
    # run`'s clone leaves `.claude/skills/` out; only the paths the checkout should hold are judged.
    listed = (entry.split(" ", 1) for entry in _git(root, "ls-files", "-z", "-t").stdout.split("\0") if " " in entry)
    for name in (path for tag, path in listed if tag != "S"):
        try:
            os.lstat(root / name)
            if os.access(root / name, os.R_OK) or (root / name).is_symlink():
                continue
        except FileNotFoundError:
            continue
        except OSError:
            pass  # a parent that is no folder, or none this session may enter
        parts = Path(name).parts
        cover = next((Path(*parts[:n]).as_posix() for n in range(1, len(parts) + 1)
                      if not (root / Path(*parts[:n])).is_dir() or not os.access(root / Path(*parts[:n]), os.R_OK | os.X_OK)),
                     name)
        if _plain(root / cover):
            continue  # a folder replaced by a file of the person's: a change, said as one
        if cover not in hidden:
            hidden.append(cover)
    return hidden


OUTSIDE = ("attest outside the sandbox — the person runs nstack attest in a terminal of their own, outside the "
           "agent's session, or the decider does (.nstack/handbook/INSTALL.md, *Your agent tool's configuration is "
           "still yours*).")


def _plain(path: Path) -> bool:
    """A regular file this session reads: the person's own edit. A sandbox's mount point is none — a
    device, or a path it may not read."""
    try:
        return stat.S_ISREG(os.lstat(path).st_mode) and os.access(path, os.R_OK)
    except OSError:
        return False


def _mount_points(root: Path) -> list[str]:
    """Untracked entries this session cannot read as a file or a folder: a sandbox's mount points (#514)."""
    entries = _git(root, "status", "--porcelain", "-z", "--untracked-files=normal").stdout.split("\0")
    found = [entry[3:].rstrip("/") for entry in entries if entry.startswith("?? ")]
    return [name for name in found if not (root / name).is_dir() and not _plain(root / name)]



class _Stopped(Exception):
    """A signal from outside — a timeout, Ctrl-C, a closed terminal — while the checks run (#526)."""

    def __init__(self, signum: int):
        super().__init__(signum)
        self.signum = signum


class _Running:
    """The step running now, said as it starts: a check runs for minutes with its output captured,
    and a run stopped from outside must say where it was, and that it wrote no record (#526)."""

    STOPS = (signal.SIGTERM, signal.SIGINT)

    def __init__(self) -> None:
        self.where = "before the first check"

    def trap(self) -> dict:
        if threading.current_thread() is not threading.main_thread():
            return {}

        def stop(signum, frame):
            raise _Stopped(signum)

        return {signum: signal.signal(signum, stop) for signum in self.STOPS}

    def untrap(self, trapped: dict) -> None:
        for signum, handler in trapped.items():
            signal.signal(signum, handler)

    def step(self, check: str, step: Step, root: Path, env: dict) -> tuple[int, str]:
        """Runs one step, its output captured whole; says the step, and each module its
        `::group::` line opens, as it starts. Stopped, it ends the step it started before anything
        else unwinds — the temporary folder the step may still write in among them."""
        self.where = f"{check} — {step.label}"
        print(f"run  [attest] {self.where}", flush=True)
        with subprocess.Popen(["bash", "-c", step.command], cwd=root, env=env, stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT, text=True, errors="replace") as process:
            try:
                lines = []
                for line in process.stdout:
                    lines.append(line)
                    if line.startswith("::group::") and line[9:].strip():
                        self.where = f"{check} — {line[9:].strip()}"
                        print(f"run  [attest] {self.where}", flush=True)
                returncode = process.wait()
            except BaseException:
                self.quiet()
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
                raise
        self.where = f"{check} — after {step.label}"
        return returncode, "".join(lines)

    def quiet(self) -> None:
        """A second signal while the first is being answered changes nothing."""
        if threading.current_thread() is threading.main_thread():
            for signum in self.STOPS:
                signal.signal(signum, signal.SIG_IGN)

    def stopped(self, signum: int) -> int:
        self.quiet()
        print(f"STOPPED [attest] {self.where}: {signal.Signals(signum).name}; no record written — "
              "a record holds whole runs only. Run nstack attest again.", flush=True)
        return 128 + signum


def run(root: Path, base: str, body_file: Path | None, labels: str | None, accept_identity: bool = False,
        again: bool = False) -> int:
    print(provenance.judged_by(root), flush=True)
    who, refused = _publishable(root, base, accept_identity)
    if refused:
        print(refused)
        return 1
    if masked := _masked(root):
        shown = ", ".join(masked[:5]) + (f", and {len(masked) - 5} more" if len(masked) > 5 else "")
        print(f"FAIL [attest] this session cannot read what the commit holds: {shown} — mount points an agent's "
              "sandbox puts over the paths it protects. A record made here would not be the commit's.\n"
              f"      Action: {OUTSIDE}")
        return 1
    if _git(root, "status", "--porcelain", "--untracked-files=normal").stdout.strip():
        mounts = _mount_points(root)
        print("FAIL [attest] the tree holds changes: a record names one commit, and this tree is none.\n"
              + (f"      {', '.join(mounts[:5])}{', and more' if len(mounts) > 5 else ''}: no file or folder this "
                 f"session reads — mount points an agent's sandbox puts over the paths it protects.\n      Action: {OUTSIDE}"
                 if mounts else "      Action: commit or stash them, then run nstack attest again."))
        return 1
    commit = _git(root, "rev-parse", "HEAD").stdout.strip()
    engine, origin = provenance.engine()
    base_commit = _git(root, "rev-parse", "--verify", "--quiet", f"{base}^{{commit}}", check=False).stdout.strip() or None
    previous = None if again else latest(root, commit)
    previous = None if previous and previous.get("void") else previous  # a void keeps nothing, evidence included
    # The option, else PR_LABELS as the caller set it: one way for attest and pr-check (D147) — and the
    # pull request's own when the forge answers, a label it does not carry refused (#368).
    from napkinstack.pull_request import labels_for, this_pull

    judged, labels_from, refused = labels_for(root, commit, os.environ.get("PR_LABELS", "") if labels is None else labels)
    if refused:
        print(f"FAIL [attest] {refused}")
        return 1
    print(f"Labels: {', '.join(sorted(judged)) or 'none'} — {labels_from}", flush=True)
    env = dict(os.environ, PR_LABELS=",".join(sorted(judged)))
    # The engine that runs this command runs the checks: its folder first on the path.
    env["PATH"] = os.pathsep.join([str(Path(sys.argv[0]).resolve().parent), env.get("PATH", "")])
    results = []
    running = _Running()
    trapped = running.trap()
    try:
        # The run's own scratch: a child a stopped step left writing in it must not cost the run's word (#526).
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            body = body_file or Path(tmp, "body.md")
            if body_file is None:
                body.write_text("", encoding="utf-8")
            body_text = Path(body).read_text(encoding="utf-8", errors="replace")
            # NSTACK_ATTESTING: pr-check, run as one of the checks, judges the pull request's rules
            # without asking for the record this run is making (A1, A2) — found rehearsing v0.10.0.
            env.update(NSTACK_BASE=base, NSTACK_BODY=str(Path(body).resolve()), NSTACK_TMP=tmp,
                       NSTACK_ATTESTING=commit)
            digest = inputs(root, base, json.dumps([engine, unplaced(origin, root), origin is None, who]))
            env["NSTACK_INPUTS"] = digest or ""  # the head's, for pr-check's T4 while this record is made (D223)
            for check in CHECKS:
                kept = _kept(previous, check, engine, origin, base_commit, who, unplaced(origin, root), root)
                if kept is not None:
                    results.append(kept)
                    print(f"ok   [attest] {check.name}: kept from the record of {kept['kept_from']} — same commit, base "
                          "and engine (nstack attest --again runs it)", flush=True)
                    continue
                kept = None if again else _by_inputs(root, base, digest, check, engine, origin, base_commit, who,
                                                      unplaced(origin, root))
                if kept is not None:
                    results.append(kept)
                    print(f"ok   [attest] {check.name}: kept from the run on {kept['kept_commit'][:7]} at {kept['kept_from']} — "
                          f"same inputs ({digest[:12]}), within {FRESH_DAYS} days and {FRESH_COMMITS} commits of the "
                          "default branch (nstack attest --again runs it)", flush=True)
                    continue
                steps, outputs = [], []
                for step in check.steps:
                    returncode, output = running.step(check.name, step, root, env)
                    steps.append({"label": step.label, "command": step.command, "exit": returncode,
                                  "output": capped(output),
                                  "sha256": hashlib.sha256(output.encode("utf-8", "replace")).hexdigest()})
                    outputs.append(output)
                passed = all(step["exit"] == 0 for step in steps)
                results.append({"name": check.name, "passed": passed, "steps": steps,
                                **({"inputs": digest} if check.kept and digest else {})})
                failed = "; ".join(f"{s['label']} exited {s['exit']}" for s in steps if s["exit"])
                print(f"FAIL [attest] {check.name}: {failed}" if failed else f"ok   [attest] {check.name}", flush=True)
                for step, whole in zip(steps, outputs):
                    if step["exit"]:
                        print("\n".join(f"       {line}" for line in why(whole)), flush=True)
                if failed:
                    try:
                        log = keep_log(root, commit, check.name, [(s["label"], o) for s, o in zip(steps, outputs)])
                    except OSError as error:  # a full or read-only disk never costs the record
                        print(f"       whole output: not kept ({error.strerror})", flush=True)
                    else:
                        shown = log.relative_to(root) if log.is_relative_to(root) else log
                        print(f"       whole output: {shown}", flush=True)
    except _Stopped as stop:
        return running.stopped(stop.signum)
    finally:
        running.untrap(trapped)
    record = {"record": RECORD, "commit": commit,
              "at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="microseconds"),
              "engine": engine, "origin": origin, "published": origin is None, "by": who, "session": _session(root, commit),
              "base": base, "base_commit": base_commit, "checks": results,
              "sheet": sheet_of(body_text), "pull": this_pull(root, commit),
              "labels": {"names": sorted(judged), "from": labels_from},
              # The audits of the run the module checks come from: kept with them, never read again (#275).
              "evidence": (previous.get("evidence") if isinstance(previous.get("evidence"), list) else [])
              if previous and any(r.get("kept_from") for r in results) else evidence_of(root, commit)}
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
