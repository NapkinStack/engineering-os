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
import json
import os
import re
import subprocess
import time
import unicodedata
import urllib.request
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


def _git(root: Path, *args: str, check: bool = False, stdin: str | None = None,
         timeout: int | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, check=check, input=stdin,
                          timeout=timeout,
                          # A remote asking for a password is unreachable, not a wait.
                          env={**os.environ, "GIT_TERMINAL_PROMPT": "0"})


def remote(root: Path) -> str | None:
    return _remote(root)


class Unreachable(Exception):
    """The remote could not be read: nothing about its holds is known."""


def fetch(root: Path, again: bool = False) -> str | None:
    """Brings the remote's holds, work branches and default branch in, as they are now; returns
    the remote's name. `again`: the read after a refused push, which must see the hold that won."""
    name = remote(root)
    if name is not None:
        try:
            got = _git(root, "fetch", "--quiet", "--prune", "--no-tags", name, f"+HEAD:{MIRROR}/base",
                       f"+refs/heads/{PREFIX}/*:{MIRROR}/hold/*", f"+refs/heads/d*:{MIRROR}/work/d*",
                       timeout=60)
        except subprocess.TimeoutExpired:
            raise Unreachable(f"no answer from {name} within a minute") from None
        if got.returncode != 0:
            raise Unreachable(got.stderr.strip().splitlines()[0] if got.stderr.strip() else f"{name} refused the fetch")
    return name


def _hold_ref(root: Path, cycle: str, ident: str) -> str:
    return f"{MIRROR}/hold/{cycle}/{ident}" if remote(root) else f"refs/heads/{PREFIX}/{cycle}/{ident}"


def _work_refs(root: Path, ident: str) -> str:
    return f"{MIRROR}/work/{ident.lower()}-*" if remote(root) else f"refs/heads/{ident.lower()}-*"


NOREPLY = re.compile(r"(?:\d+\+)?(?P<login>[^@]+)@users\.noreply\.github\.com", re.I)


def _names(person: str) -> set[str]:
    """What names a person: a handle without its @, or a git identity's email and its local
    part — a GitHub noreply address naming its account. Never a display name: anyone may carry it."""
    found = re.fullmatch(r"\s*(.*?)\s*<([^>]*)>\s*", person)
    if not found:
        return {person.strip().lstrip("@").lower()} - {""}
    email = found[2].strip().lower()
    noreply = NOREPLY.fullmatch(email)
    return {email, noreply["login"] if noreply else email.split("@")[0]} - {""}


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


def _work_branch(root: Path, name: str | None, ident: str, title: str, session: str | None) -> tuple[str, str | None]:
    """The deliverable's first work branch, from the default branch, unless it exists: what is
    said, and the branch when it was made and pushed."""
    branch = f"{ident.lower()}-{slug(title)}"
    if _git(root, "rev-parse", "--verify", "--quiet", f"refs/heads/{branch}").returncode == 0 or (
            name and _git(root, "rev-parse", "--verify", "--quiet", f"{MIRROR}/work/{branch}").returncode == 0):
        return f"work continues on {branch}, which exists: nothing of it is touched", None
    base = f"{MIRROR}/base" if name else "refs/heads/main"
    if _git(root, "rev-parse", "--verify", "--quiet", base).returncode != 0:
        return "no work branch created: the default branch cannot be read.\n      Next: create d<n>-… yourself.", None
    tree = _git(root, "rev-parse", f"{base}^{{tree}}", check=True).stdout.strip()
    message = f"Start {ident} — {title}\n" + (f"\nAgent-Session: {session}\n" if session else "")
    start = _git(root, "commit-tree", tree, "-p", base, stdin=message, check=True).stdout.strip()
    _git(root, "branch", branch, start, check=True)
    if name:
        pushed = _git(root, "push", "--quiet", name, f"{branch}:refs/heads/{branch}")
        if pushed.returncode != 0:
            return (f"work branch {branch} created here, NOT pushed: {pushed.stderr.strip()}\n"
                    f"      Next: git push -u {name} {branch}"), None
        _git(root, "update-ref", f"{MIRROR}/work/{branch}", start)
    return f"work branch {branch} created.\n      Next: git switch {branch}", branch if name else None


def _forge(root: Path, name: str | None) -> tuple[str, str, str] | None:
    """(API, owner/name, token) when the remote is on GitHub and a token is set; else None. The
    remote's URL as configured, before any rewriting."""
    from napkinstack.doctor import ON_GITHUB

    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    url = _git(root, "config", f"remote.{name}.url").stdout.strip() if name else ""
    found = ON_GITHUB.search(url)
    if not token or not found:
        return None
    return os.environ.get("GITHUB_API_URL", "https://api.github.com").rstrip("/"), found.group(1), token


def _call(forge: tuple[str, str, str], method: str, path: str, body: dict | None = None):
    api, repo, token = forge
    request = urllib.request.Request(f"{api}/repos/{repo}{path}", method=method,
                                     data=json.dumps(body).encode() if body is not None else None,
                                     headers={"Accept": "application/vnd.github+json",
                                              "Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(request, timeout=10) as answer:
        return json.loads(answer.read() or b"null")


def _show(root: Path, name: str | None, ident: str, title: str, person: str, branch: str | None,
          previous: Hold | None) -> str:
    """The hold where people look: a draft pull request from its first work branch; on a take-over,
    a comment on the previous holder's open pull requests. Never a judgement: the hold is git's."""
    forge = _forge(root, name)
    if forge is None:
        return "not shown on a forge (no GitHub remote, or no token)"
    try:
        said = []
        if previous is not None:
            prefix = f"{ident.lower()}-"
            for pull in _call(forge, "GET", "/pulls?state=open&per_page=100") or []:
                if str((pull.get("head") or {}).get("ref", "")).startswith(prefix):
                    _call(forge, "POST", f"/issues/{pull['number']}/comments", {"body": (
                        f"{ident} was taken over by {person} from {previous.person}: nobody had worked on it "
                        f"since {when(previous.worked)}. This branch is kept; the new holder may start from it "
                        "(nstack claim --take-over).")})
                    said.append(f"#{pull['number']} told")
        if branch is not None:
            base = _call(forge, "GET", "").get("default_branch") or "main"
            opened = _call(forge, "POST", "/pulls", {
                "title": f"{ident} — {title}", "head": branch, "base": base, "draft": True,
                "body": (f"Deliverable: {ident}\n\nHeld by {person} (nstack claim). A draft until the work "
                         "is done: its description is completed before it is marked ready for review.")})
            said.append(f"draft pull request {opened.get('html_url')}")
        return "shown on GitHub: " + ", ".join(said) if said else "nothing to show on GitHub"
    except (OSError, ValueError) as error:
        return f"not shown on GitHub ({error})"


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
        made, branch = _work_branch(root, name, ident, title, session)
        print(made)
        print(_show(root, name, ident, title, person, branch, previous) + ".")
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


def show(root: Path) -> int:
    """Who holds what in the accepted cycle, for `nstack plan`: said, never a failure."""
    cycle = plan.accepted_cycle(root)
    if cycle is None:
        return 0
    path, data = cycle
    days = limit(root)
    try:
        name = fetch(root)
    except Unreachable as error:
        print(f"\nHolds in {path.stem}: holds not read — the remote cannot be read.\n      {error}")
        return 0
    lines = []
    for item in data.get("deliverables") or []:
        if not isinstance(item, dict):
            continue
        ident, state = str(item.get("id")), item.get("state")
        found = read(root, path.stem, ident)
        if not found.held and state not in TAKEABLE:
            continue
        if not found.held:
            lines.append(f"  {ident}  free")
        elif state not in TAKEABLE:
            lines.append(f"  {ident}  ended — {state}; was {said(found)}")
        elif time.time() >= found.worked + days * DAY:
            lines.append(f"  {ident}  STALE — {said(found)}: its holder renews (nstack claim {ident}); "
                         f"anyone else may nstack claim {ident} --take-over")
        else:
            lines.append(f"  {ident}  {said(found)}")
    where = f"from {name}" if name else "local only: no remote"
    print(f"\nHolds in {path.stem} ({where}; stale after {days} days without work):")
    print("\n".join(lines) or "  no ready deliverable")
    return 0


def judge(root: Path, ident: str) -> Hold | str | None:
    """The hold of a deliverable of the accepted cycle for `pr-check`: None when nobody holds
    it, the reason when it cannot be read."""
    cycle = plan.accepted_cycle(root)
    if cycle is None:
        return None
    try:
        fetch(root)
    except Unreachable as error:
        return str(error)
    found = read(root, cycle[0].stem, ident)
    return found if found.held else None
