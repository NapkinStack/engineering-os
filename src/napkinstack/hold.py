"""
Who holds a deliverable (PDR-0015, ADR-0007).

A hold is a branch `nstack/hold/<cycle>/<id>` whose empty commits are its events — claim, renew,
take-over, release — each naming the person accountable and the agent's session as trailers.
The shared remote takes the first of two claims and refuses the second, which does not descend
from it: the refusal is git's, on any forge. A hold is never merged; its work is on branches
`d<n>-…`, whose newest commit says when it was last worked on.

Usage :  nstack claim D<n> [--session S] [--person P] [--take-over]
         nstack unclaim D<n> [--session S] [--person P]
Output:  0 when the hold is taken, renewed or released; 1 when refused — saying who holds it.
"""

from __future__ import annotations

import datetime
import os
import re
import subprocess
import time
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from napkinstack.attest import _remote
from napkinstack.fitness import plan
from napkinstack.project import ANSWERS

PREFIX = "nstack/hold"
MIRROR = "refs/nstack-remote"  # what the remote holds, as last fetched: holds, and work branches
LIMIT = 7  # days without work before a hold is stale, unless the project's answer hold_days says otherwise
DAY = 86400
TAKEABLE = {"ready", "in-progress"}


@dataclass
class Hold:
    tip: str | None = None
    event: str | None = None  # the last one; None when the deliverable was never held
    person: str = ""
    sessions: list[str] = field(default_factory=list)
    since: int = 0
    worked: int = 0  # the newest of its last event and its work branches' tips

    @property
    def held(self) -> bool:
        return self.event not in (None, "release")


def _git(root: Path, *args: str, check: bool = False, stdin: str | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, check=check, input=stdin)


def remote(root: Path) -> str | None:
    return _remote(root)


class Unreachable(Exception):
    """The remote could not be read: nothing about its holds is known."""


def fetch(root: Path, again: bool = False) -> str | None:
    """Brings the remote's holds, work branches and default branch in, as they are now; returns
    the remote's name. `again`: the read after a refused push, which must see the hold that won."""
    name = remote(root)
    if name is not None:
        got = _git(root, "fetch", "--quiet", "--prune", "--no-tags", name, f"+HEAD:{MIRROR}/base",
                   f"+refs/heads/{PREFIX}/*:{MIRROR}/hold/*", f"+refs/heads/d*:{MIRROR}/work/d*")
        if got.returncode != 0:
            raise Unreachable(got.stderr.strip())
    return name


def _hold_ref(root: Path, cycle: str, ident: str) -> str:
    return f"{MIRROR}/hold/{cycle}/{ident}" if remote(root) else f"refs/heads/{PREFIX}/{cycle}/{ident}"


def _work_refs(root: Path, ident: str) -> str:
    return f"{MIRROR}/work/{ident.lower()}-*" if remote(root) else f"refs/heads/{ident.lower()}-*"


def _names(person: str) -> set[str]:
    """What a person is called: a handle without its @, or a git identity's name, email and
    email's local part."""
    found = re.fullmatch(r"\s*(.*?)\s*<([^>]*)>\s*", person)
    names = {found[1], found[2], found[2].split("@")[0]} if found else {person.strip().lstrip("@")}
    return {name.lower() for name in names if name}


def same(one: str, other: str) -> bool:
    """One person, whether named by a handle (@alice) or by git (Alice <alice@example.org>). Said,
    not proven: whoever may push may name anyone, as an attested record."""
    return bool(_names(one) & _names(other))


def read(root: Path, cycle: str, ident: str) -> Hold:
    """The hold as its events say, oldest first; its last work from the deliverable's branches."""
    found = Hold()
    ref = _hold_ref(root, cycle, ident)
    log = _git(root, "log", "--reverse", "--format=%H%x1f%ct%x1f"
               "%(trailers:key=Hold-Event,valueonly,separator=)%x1f"
               "%(trailers:key=Hold-Person,valueonly,separator=)%x1f"
               "%(trailers:key=Agent-Session,valueonly,separator=)%x1e", ref)
    if log.returncode != 0:
        return found
    for entry in filter(str.strip, log.stdout.split("\x1e")):
        sha, at, event, person, session = (part.strip() for part in entry.split("\x1f"))
        found.tip, found.event = sha, event
        if event in ("claim", "take-over"):
            found.person, found.sessions, found.since = person, [], int(at)
        if event in ("claim", "take-over", "renew") and session and session not in found.sessions:
            found.sessions.append(session)
        found.worked = int(at)
    tips = _git(root, "for-each-ref", "--format=%(committerdate:unix)", _work_refs(root, ident)).stdout.split()
    found.worked = max([found.worked, *map(int, tips)])
    return found


def limit(root: Path) -> int:
    try:
        answers = yaml.safe_load((root / ANSWERS).read_text(encoding="utf-8")) or {}
        return int(answers.get("hold_days", LIMIT))
    except (OSError, yaml.YAMLError, TypeError, ValueError):
        return LIMIT


def when(at: int) -> str:
    return datetime.datetime.fromtimestamp(at, datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def said(found: Hold) -> str:
    sessions = f", session {', '.join(found.sessions)}" if found.sessions else ""
    return f"held by {found.person}{sessions}, since {when(found.since)}, last worked on {when(found.worked)}"


def _deliverable(root: Path, ident: str) -> tuple[str, str] | str:
    """The accepted cycle's name and the deliverable's title, or why it cannot be taken."""
    cycle = plan.accepted_cycle(root)
    if cycle is None:
        return ("no accepted cycle: a deliverable is taken from the cycle in progress.\n"
                "      Action: the decider accepts a cycle (.nstack/playbooks/framing.md).")
    path, data = cycle
    items = {str(item.get("id")): item for item in data.get("deliverables") or [] if isinstance(item, dict)}
    if ident not in items:
        return (f"{ident} is not in {path.stem}.\n      Action: name one of {', '.join(items) or 'its deliverables'}.")
    state = items[ident].get("state")
    if state not in TAKEABLE:
        return (f"{ident} is '{state}': work starts on a ready deliverable (definition of ready).\n"
                "      Action: take a ready one — nstack plan lists them.")
    return path.stem, str(items[ident].get("title") or ident)


def _person(root: Path, given: str | None) -> str:
    if given:
        return given
    ident = _git(root, "var", "GIT_AUTHOR_IDENT").stdout.strip()
    return ident.rsplit(" ", 2)[0] if ident.count(" ") >= 2 else ident


def _event(root: Path, parent: str | None, ident: str, event: str, person: str, session: str | None,
           previous: Hold | None = None) -> str:
    trailers = [f"Hold-Event: {event}", f"Hold-Person: {person}"]
    if session:
        trailers.append(f"Agent-Session: {session}")
    if previous is not None:
        sessions = f" ({', '.join(previous.sessions)})" if previous.sessions else ""
        trailers.append(f"Hold-Previous: {previous.person}{sessions}")
    trailers.append(f"Hold-Id: {os.urandom(4).hex()}")  # two runs in one second are two claims
    message = f"Hold {ident}: {event}\n\n" + "\n".join(trailers) + "\n"
    tree = _git(root, "mktree", stdin="", check=True).stdout.strip()
    parents = ["-p", parent] if parent else []
    return _git(root, "commit-tree", tree, *parents, stdin=message, check=True).stdout.strip()


def _record(root: Path, name: str | None, cycle: str, ident: str, sha: str) -> tuple[bool, str]:
    """Pushes the event; never forced, so a hold that moved meanwhile refuses it."""
    branch = f"{PREFIX}/{cycle}/{ident}"
    if name is None:
        _git(root, "update-ref", f"refs/heads/{branch}", sha, check=True)
        return True, "local only: no remote, nobody else sees it"
    pushed = _git(root, "push", "--quiet", name, f"{sha}:refs/heads/{branch}")
    if pushed.returncode != 0:
        return False, pushed.stderr.strip()
    _git(root, "update-ref", f"{MIRROR}/hold/{cycle}/{ident}", sha, check=True)
    return True, f"pushed to {name}"


def slug(title: str) -> str:
    """A branch name from a title: its first words, never a word cut."""
    plain = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode()
    words = re.sub(r"[^a-z0-9]+", " ", plain.lower()).split()
    kept = []
    for word in words:
        if kept and len("-".join([*kept, word])) > 40:
            break
        kept.append(word)
    return "-".join(kept)[:40] or "work"


def _work_branch(root: Path, name: str | None, ident: str, title: str, session: str | None) -> str:
    """The deliverable's first work branch, from the default branch, unless it exists."""
    branch = f"{ident.lower()}-{slug(title)}"
    if _git(root, "rev-parse", "--verify", "--quiet", f"refs/heads/{branch}").returncode == 0 or (
            name and _git(root, "rev-parse", "--verify", "--quiet", f"{MIRROR}/work/{branch}").returncode == 0):
        return f"work continues on {branch}, which exists: nothing of it is touched"
    base = f"{MIRROR}/base" if name else "refs/heads/main"
    if _git(root, "rev-parse", "--verify", "--quiet", base).returncode != 0:
        return "no work branch created: the default branch cannot be read.\n      Next: create d<n>-… yourself."
    tree = _git(root, "rev-parse", f"{base}^{{tree}}", check=True).stdout.strip()
    message = f"Start {ident} — {title}\n" + (f"\nAgent-Session: {session}\n" if session else "")
    start = _git(root, "commit-tree", tree, "-p", base, stdin=message, check=True).stdout.strip()
    _git(root, "branch", branch, start, check=True)
    if name:
        pushed = _git(root, "push", "--quiet", name, f"{branch}:refs/heads/{branch}")
        if pushed.returncode != 0:
            return (f"work branch {branch} created here, NOT pushed: {pushed.stderr.strip()}\n"
                    f"      Next: git push -u {name} {branch}")
        _git(root, "update-ref", f"{MIRROR}/work/{branch}", start)
    return f"work branch {branch} created.\n      Next: git switch {branch}"


def claim(root: Path, ident: str, session: str | None = None, person: str | None = None,
          take_over: bool = False) -> int:
    found = _deliverable(root, ident)
    if isinstance(found, str):
        print(f"FAIL [hold] {found}")
        return 1
    cycle, title = found
    person = _person(root, person)
    if any(not value.isprintable() for value in (person, session or "")):
        print("FAIL [hold] a person or a session holds a line break or a control character: it would "
              "write the record's lines.\n      Action: name them on one line.")
        return 1
    try:
        name = fetch(root)
    except Unreachable as error:
        print(f"FAIL [hold] the remote cannot be read: nothing is known of {ident}'s hold.\n"
              f"      {error}\n      Action: check the network and the remote, then again.")
        return 1
    current = read(root, cycle, ident)
    days = limit(root)
    stale_at = current.worked + days * DAY
    previous = None
    if not current.held:
        event = "claim"
    elif same(current.person, person):
        event = "renew"
    elif take_over and time.time() >= stale_at:
        event, previous = "take-over", current
    elif take_over:
        print(f"FAIL [hold] {ident} is {said(current)}: it is not stale — work on it is younger than "
              f"{days} days (hold_days).\n      It will be stale from {when(stale_at)}, if nobody works on it.")
        return 1
    else:
        stale = time.time() >= stale_at
        again = " ".join(["nstack claim", ident, "--take-over", *(["--person", person] if person else []),
                          *(["--session", session] if session else [])])
        print(f"FAIL [hold] {ident} is {said(current)}" + (f" — stale, no work for {days} days." if stale else ".")
              + (f"\n      Action: {again} — recorded, with its previous holder."
                 if stale else "\n      Action: take another ready deliverable — nstack plan lists them; "
                               "or ask its holder to give it back (nstack unclaim)."))
        return 1
    sha = _event(root, current.tip, ident, event, person, session, previous)
    ok, where = _record(root, name, cycle, ident, sha)
    if not ok:
        try:
            fetch(root, again=True)
        except Unreachable:
            pass
        winner = read(root, cycle, ident)
        if winner.tip != current.tip:
            print(f"FAIL [hold] {ident} was taken first: "
                  f"{said(winner) if winner.held else 'given back meanwhile'}.\n"
                  "      Action: take another ready deliverable — nstack plan lists them; or run again.")
        else:
            print(f"FAIL [hold] {ident}: the remote refused the hold.\n      {where}")
        return 1
    done = {"claim": "taken", "renew": "renewed", "take-over": f"taken over from {previous.person if previous else ''}"}
    print(f"{ident} {done[event]}: held by {person}" + (f", session {session}" if session else "") + f"; {where}.")
    if event != "renew":
        print(_work_branch(root, name, ident, title, session))
    return 0


def release(root: Path, ident: str, session: str | None = None, person: str | None = None) -> int:
    cycle = plan.accepted_cycle(root)
    if cycle is None:
        print("FAIL [hold] no accepted cycle: there is no hold to release.")
        return 1
    stem = cycle[0].stem
    person = _person(root, person)
    if any(not value.isprintable() for value in (person, session or "")):
        print("FAIL [hold] a person or a session holds a line break or a control character.\n"
              "      Action: name them on one line.")
        return 1
    try:
        name = fetch(root)
    except Unreachable as error:
        print(f"FAIL [hold] the remote cannot be read.\n      {error}\n      Action: check it, then again.")
        return 1
    current = read(root, stem, ident)
    if not current.held:
        print(f"FAIL [hold] {ident} is not held: nothing to release.")
        return 1
    charter = plan.read_front_matter(root / plan.CHARTER)[0] if (root / plan.CHARTER).is_file() else None
    decider = str((charter or {}).get("decider") or "")
    stale = time.time() >= current.worked + limit(root) * DAY
    if not (same(current.person, person) or (decider and same(decider, person)) or stale):
        print(f"FAIL [hold] {ident} is {said(current)}: only its holder or the decider ({decider or 'none named'}) "
              "releases a hold that is not stale.\n      Action: ask them.")
        return 1
    sha = _event(root, current.tip, ident, "release", person, session)
    ok, where = _record(root, name, stem, ident, sha)
    if not ok:
        print(f"FAIL [hold] {ident}'s hold moved meanwhile: {where}\n      Action: run nstack plan, then again.")
        return 1
    print(f"{ident} released by {person}; {where}. Its branches are kept.")
    return 0
