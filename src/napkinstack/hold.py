"""
Who holds a deliverable (PDR-0015, ADR-0007).

A hold is a branch `nstack/hold/<cycle>/<id>` whose empty commits are its events — claim, renew,
take-over, release — each naming the person accountable and the agent's session as trailers.
The shared remote takes the first of two claims and refuses the second, which does not descend
from it: the refusal is git's, on any forge. A hold is never merged; its work is on branches
`d<n>-…`, whose newest commit says when it was last worked on.

Usage :  nstack claim D<n> [--session S] [--person P] [--take-over]
         nstack unclaim D<n> [--session S] [--person P]
         nstack deliver D<n> --held '#12' [--held '2=#13'] [--session S] [--person P]
         nstack deliver --write-states
Output:  0 when the hold is taken, renewed or released; 1 when refused — saying who holds it.

Two sessions of one person are two holders (D181, D185): a session renews only a hold it is on; a
person's other session takes it with --take-over, on that person's word. A person with no session
has nothing to tell apart, and their name answers.

A `deliver` event records a delivery, criterion by criterion (PDR-0022): a rule refuses it with no
merge of the deliverable on the default branch. `delivered` is computed from it and from those
merges, and never written in the cycle file until its closure.
"""

from __future__ import annotations

import base64
import datetime
import json
import os
import re
import subprocess
import time
import unicodedata
import urllib.error
import urllib.parse
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
    criteria: list[str] = field(default_factory=list)  # what a `deliver` event says holds each criterion

    @property
    def held(self) -> bool:
        return self.event not in (None, "release", "deliver")

    @property
    def recorded(self) -> bool:
        """A delivery is on record; whether it still stands is `delivered`'s to say."""
        return self.event == "deliver" and bool(self.criteria)  # with none, no rule ever ran on it


def _git(root: Path, *args: str, check: bool = False, stdin: str | None = None,
         timeout: int | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, errors="replace", check=check, input=stdin,
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
            got = _git(root, *_ci_credential(root, name), "fetch", "--quiet", "--prune", "--no-tags", name, f"+HEAD:{MIRROR}/base",
                       f"+refs/heads/{PREFIX}/*:{MIRROR}/hold/*", f"+refs/heads/d*:{MIRROR}/work/d*",
                       timeout=60)
        except subprocess.TimeoutExpired:
            raise Unreachable(f"no answer from {name} within a minute") from None
        if got.returncode != 0:
            raise Unreachable(got.stderr.strip().splitlines()[0] if got.stderr.strip() else f"{name} refused the fetch")
    return name


def _ci_credential(root: Path, name: str) -> list[str]:
    """In GitHub Actions, the job's token for this one command: the checkout keeps no credential
    (`persist-credentials: false`), and a private repository's holds are read with it (ADR-0008).
    Never on a workstation, and never to another host."""
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    url = _git(root, "config", f"remote.{name}.url").stdout.strip()
    if os.environ.get("GITHUB_ACTIONS") != "true" or not token or not url.startswith("https://github.com/"):
        return []
    secret = base64.b64encode(f"x-access-token:{token}".encode()).decode()
    print(f"::add-mask::{secret}", flush=True)  # never printed in clear by the runner, as actions/checkout does
    return ["-c", f"http.https://github.com/.extraheader=AUTHORIZATION: basic {secret}"]


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
               "%(trailers:key=Agent-Session,valueonly,separator=)%x1f"
               "%(trailers:key=Hold-Criterion,valueonly,separator=%x1d)%x1e", ref)
    if log.returncode != 0:
        return found
    for entry in filter(str.strip, log.stdout.split("\x1e")):
        sha, at, event, person, session, criteria = (part.strip() for part in entry.split("\x1f"))
        found.tip, found.event = sha, event
        if event in ("claim", "take-over", "deliver"):  # a record names who said it, whoever held it
            found.person, found.sessions, found.since = person, [], int(at)
        if event in ("claim", "take-over", "renew", "deliver") and session and session not in found.sessions:
            found.sessions.append(session)
        found.criteria = [one.strip() for one in criteria.split("\x1d") if one.strip()] if event == "deliver" else []
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
    items = {str(item.get("id")): item for item in (data.get("deliverables") if isinstance(data.get("deliverables"), list) else []) if isinstance(item, dict)}
    if ident not in items:
        return (f"{ident} is not in {path.stem}.\n      Action: name one of {', '.join(items) or 'its deliverables'}.")
    state = items[ident].get("state")
    if not plan.one_of(state, TAKEABLE):
        return (f"{ident} is '{state}': work starts on a ready deliverable (definition of ready).\n"
                "      Action: take a ready one — nstack plan lists them.")
    return path.stem, str(items[ident].get("title") or ident)


def _person(root: Path, given: str | None) -> str:
    if given:
        return given
    ident = _git(root, "var", "GIT_AUTHOR_IDENT").stdout.strip()
    return ident.rsplit(" ", 2)[0] if ident.count(" ") >= 2 else ident


def _event(root: Path, parent: str | None, ident: str, event: str, person: str, session: str | None,
           previous: Hold | None = None, criteria: list[str] | None = None) -> str:
    trailers = [f"Hold-Event: {event}", f"Hold-Person: {person}"]
    trailers += [f"Hold-Criterion: {one}" for one in criteria or []]
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


def _started_for_another(root: Path, ref: str, base: str, ident: str, title: str) -> bool:
    """The branch's first commit off the default branch is a start `claim` made for another title."""
    first = _git(root, "log", "--reverse", "--format=%s", f"{base}..{ref}").stdout.splitlines()[:1]
    start = f"Start {ident} — "
    return bool(first) and first[0].startswith(start) and first[0] != start + title


def _work_branch(root: Path, name: str | None, ident: str, title: str, session: str | None,
                 renew: bool = False) -> tuple[str, str | None]:
    """The deliverable's first work branch, from the default branch, unless it exists: what is
    said, and the branch when it was made and pushed. A renewed hold says nothing of a branch that
    exists, and starts none once the cycle's default branch has merged the deliverable."""
    branch = f"{ident.lower()}-{slug(title)}"
    # Any d<n>-… branch is the deliverable's work, as the hold's freshness reads it: the one checked
    # out first, then the remote's, then this checkout's — never a second one beside it (#232).
    # A branch `claim` started for another title of the same id is an earlier cycle's, never this one's.
    current = _git(root, "branch", "--show-current").stdout.strip()
    pattern = f"{ident.lower()}-*"
    base = f"{MIRROR}/base" if name else "refs/heads/main"
    shared = [one for one in (_git(root, "for-each-ref", "--format=%(refname:lstrip=3)", f"{MIRROR}/work/{pattern}").stdout.split()
                              if name else []) if not _started_for_another(root, f"{MIRROR}/work/{one}", base, ident, title)]
    local = [one for one in _git(root, "for-each-ref", "--format=%(refname:short)", f"refs/heads/{pattern}").stdout.split()
             if not _started_for_another(root, f"refs/heads/{one}", base, ident, title)]
    existing = [current] if current in local else shared + [one for one in local if one not in shared]
    if existing and renew:
        return "", None
    if existing:
        found = existing[0]
        if name and found not in shared:
            return (f"work continues on {found}, which exists here only: no other branch is made.\n"
                    f"      Next: git push -u {name} {found} — the hold stays fresh with the remote's work"), None
        return f"work continues on {found}, which exists: no other branch is made", None
    if renew and ident in _read_merges(root, name, plan.accepted_cycle(root)[1]).live:
        return "", None
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
    """(API, owner/name, token) when the project is on GitHub, its remote is there and a token is
    set; else None. The remote's URL as configured, before any rewriting: on github.com, or one
    naming the project's `github_repo` — GitHub Enterprise Server, its API in GITHUB_API_URL. A
    clone of a checkout names neither, and never writes to the project's forge (ADR-0010 §4)."""
    from napkinstack import project
    from napkinstack.doctor import ON_GITHUB

    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not token or not name or project.forge(root) != "github":
        return None
    # As configured, and as git rewrites it (an `insteadOf` alias): github.com in either.
    urls = [_git(root, "config", f"remote.{name}.url").stdout.strip(), _git(root, "remote", "get-url", name).stdout.strip()]
    api = os.environ.get("GITHUB_API_URL")
    for url in urls:
        if found := ON_GITHUB.search(url):
            return (api or "https://api.github.com").rstrip("/"), found.group(1), token
    # A server of the company's own: its API named, and a remote with a host — never a path, a
    # file:// URL nor a public forge — whose path is exactly `github_repo`, as GitHub compares
    # names, without case.
    repo = str(project.answer(root, "github_repo") or "")
    for url in urls if api and repo else []:
        host = SERVER.fullmatch(url)
        if host and (host["host"] or host["scp"]).lower() not in project.KNOWN_HOSTS and host["path"].lower() == repo.lower():
            return api.rstrip("/"), repo, token
    return None


# A remote with a host: scheme://[user@]host[:port]/path, or scp-like user@host:path.
SERVER = re.compile(r"(?:(?:https?|ssh|git)://(?:[^@/]+@)?(?P<host>[^/:]+)(?::\d+)?/|[^/@:]+@(?P<scp>[^/:]+):)"
                    r"(?P<path>[^/]+/[^/]+?)(?:\.git)?/?")


def unshown(root: Path) -> str:
    """Why the forge shows nothing: its name off GitHub, else a remote or a token missing."""
    from napkinstack import project

    name = project.forge(root)
    return f"not shown — forge {name}" if name != "github" else "not shown on a forge (no GitHub remote, or no token)"


class Refused(Exception):
    """The forge did not do what was asked: the reason, as it says it."""


def _call(forge: tuple[str, str, str], method: str, path: str, body: dict | None = None):
    """One call, as doctor makes them; any failure — a status, the network, an answer that is not
    JSON — is Refused, with the forge's own message when it gives one."""
    from napkinstack import __version__
    from napkinstack.doctor import API_VERSION

    api, repo, token = forge
    headers = {"Accept": "application/vnd.github+json", "Authorization": f"Bearer {token}",
               "X-GitHub-Api-Version": API_VERSION, "User-Agent": f"nstack/{__version__}"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(f"{api}/repos/{repo}{path}", method=method, headers=headers,
                                     data=json.dumps(body).encode() if body is not None else None)
    try:
        with urllib.request.urlopen(request, timeout=10) as answer:
            return json.loads(answer.read() or b"null")
    except urllib.error.HTTPError as error:
        try:
            reason = json.loads(error.read() or b"{}").get("message")
        except (ValueError, AttributeError, OSError):
            reason = None
        raise Refused(f"HTTP {error.code}" + (f": {reason}" if reason else f": {error.reason}")) from None
    except Exception as error:  # the network, a cut answer, a page that is not JSON: never past the hold
        raise Refused(str(error) or type(error).__name__) from None


def _open_pulls(root: Path, forge: tuple[str, str, str], ident: str) -> list[int]:
    """The open pull requests from this repository's work branches of the deliverable — asked
    branch by branch, so that a fork's branch of the same name is never one."""
    owner = forge[1].split("/")[0]
    branches = _git(root, "for-each-ref", "--format=%(refname:lstrip=3)", f"{MIRROR}/work/{ident.lower()}-*").stdout.split()
    numbers = []
    for branch in branches:
        answer = _call(forge, "GET", f"/pulls?state=open&head={urllib.parse.quote(f'{owner}:{branch}')}")
        numbers += [pull["number"] for pull in answer if isinstance(pull, dict) and "number" in pull] \
            if isinstance(answer, list) else []
    return numbers


def _show(root: Path, name: str | None, ident: str, title: str, person: str, branch: str | None,
          previous: Hold | None) -> str:
    """The hold where people look: a draft pull request from its first work branch made now; else
    a comment on the open pull requests of its work branches, saying who holds it now. Never a
    judgement: the hold is git's, and stands whatever the forge answers."""
    forge = _forge(root, name)
    if forge is None:
        return unshown(root)
    said: list[str] = []
    try:
        if branch is None:
            since = (f" from {previous.person}, last worked on {when(previous.worked)}"
                     if previous is not None else "")
            for number in _open_pulls(root, forge, ident):
                _call(forge, "POST", f"/issues/{number}/comments", {"body": (
                    f"{ident} is now held by {person}{since} (nstack claim). This branch is kept; its "
                    "work may be carried on from it.")})
                said.append(f"#{number} told")
        else:
            repository = _call(forge, "GET", "")
            base = (repository.get("default_branch") if isinstance(repository, dict) else None) or "main"
            opened = _call(forge, "POST", "/pulls", {
                "title": f"{ident} — {title}", "head": branch, "base": base, "draft": True,
                "body": (f"Deliverable: {ident}\n\nHeld by {person} (nstack claim). A draft until the work "
                         "is done: its description is completed before it is marked ready for review.")})
            said.append(f"draft pull request {opened.get('html_url') if isinstance(opened, dict) else 'opened'}")
    except Refused as error:
        return ("shown on GitHub: " + ", ".join(said) + "; then " if said else "") + f"not shown on GitHub ({error})"
    return "shown on GitHub: " + ", ".join(said) if said else "nothing to show on GitHub: no open pull request of its branches"


def claim(root: Path, ident: str, session: str | None = None, person: str | None = None,
          take_over: bool = False) -> int:
    found = _deliverable(root, ident)
    if isinstance(found, str):
        print(f"FAIL [hold] {found}")
        return 1
    cycle, title = found
    person, session = _person(root, person), (session or "").strip() or None
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
    if _stands(root, name, cycle, ident, current):
        print(f"FAIL [hold] {ident} is already delivered: {_recorded_said(current)}.\n      Action: take another "
              f"ready deliverable — nstack plan lists them; a record found wrong is withdrawn with nstack unclaim {ident}.")
        return 1
    days = limit(root)
    stale_at = current.worked + days * DAY
    previous = None
    mine = same(current.person, person)
    other_session = _another_session(current, session)
    if not current.held:
        event = "claim"
    elif mine and not other_session:
        event = "renew"
    elif take_over and (mine or time.time() >= stale_at):  # a person moves their own hold on their word
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
                               "or ask its holder to give it back (nstack unclaim)."
                               + (f"\n      Another session of the same person holds it: only if that person asks, "
                                  f"{again} — recorded, with the session it leaves." if mine else "")))
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
    left = f"{previous.person}, session {', '.join(previous.sessions)}" if previous and previous.sessions \
        else (previous.person if previous else "")
    done = {"claim": "taken", "renew": "renewed", "take-over": f"taken over from {left}"}
    print(f"{ident} {done[event]}: held by {person}" + (f", session {session}" if session else "") + f"; {where}.")
    if event != "renew":
        made, branch = _work_branch(root, name, ident, title, session)
        print(made)
        print(_show(root, name, ident, title, person, branch, previous) + ".")
    else:
        made, branch = _work_branch(root, name, ident, title, session, renew=True)
        if made:
            print(made)
        if branch:
            print(_show(root, name, ident, title, person, branch, previous) + ".")
    return 0


def _another_session(current: Hold, session: str | None) -> bool:
    """Named, and on none of the hold's events. A person with no session has nothing to tell apart."""
    named = (session or "").strip().casefold()
    return bool(named and current.sessions and named not in {held.casefold() for held in current.sessions})


def _ended(root: Path, ident: str, current: str | None) -> str | None:
    """Where a hold of an ended cycle is still open: a hold lasts its cycle (#280). Nothing it
    guarded can be delivered any more, and a new cycle's hold is a branch of its own."""
    for path in plan.cycle_files(root):
        status = (plan.read_front_matter(path)[0] or {}).get("status")
        if path.stem != current and plan.one_of(status, plan.OUTCOMES) and read(root, path.stem, ident).held:
            return (f"{ident}'s hold ended with {path.stem} ({status}): a hold lasts its cycle, nothing to release. "
                    f"Its branch {PREFIX}/{path.stem}/{ident} is kept, the hold's record.")
    return None


def release(root: Path, ident: str, session: str | None = None, person: str | None = None) -> int:
    cycle = plan.accepted_cycle(root)
    stem = cycle[0].stem if cycle else None
    person, session = _person(root, person), (session or "").strip() or None
    if any(not value.isprintable() for value in (person, session or "")):
        print("FAIL [hold] a person or a session holds a line break or a control character.\n"
              "      Action: name them on one line.")
        return 1
    try:
        name = fetch(root)
    except Unreachable as error:
        print(f"FAIL [hold] the remote cannot be read.\n      {error}\n      Action: check it, then again.")
        return 1
    current = read(root, stem, ident) if stem else Hold()
    if not current.held and not current.recorded:
        ended = _ended(root, ident, stem)
        if ended:
            print(ended)
            return 0
        print(f"FAIL [hold] {ident} is not held: nothing to release." if stem else
              "FAIL [hold] no accepted cycle: there is no hold to release.")
        return 1
    charter = plan.read_front_matter(root / plan.CHARTER)[0] if (root / plan.CHARTER).is_file() else None
    decider = str((charter or {}).get("decider") or "")
    stale = not current.recorded and time.time() >= current.worked + limit(root) * DAY  # a record never goes stale
    is_decider = bool(decider and same(decider, person))
    if current.recorded and not (same(current.person, person) or is_decider):
        print(f"FAIL [hold] {ident} is {_recorded_said(current)}: only who recorded it or the decider "
              f"({decider or 'none named'}) withdraws a record.\n      Action: ask them.")
        return 1
    if not current.recorded and same(current.person, person) and _another_session(current, session) and not stale and not is_decider:
        print(f"FAIL [hold] {ident} is {said(current)}: another session of the same person does not give it "
              f"back.\n      Action: only if that person asks, nstack claim {ident} --take-over --person {person} "
              f"--session {session}.")
        return 1
    if not (same(current.person, person) or is_decider or stale):
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


_fetched: dict[Path, "str | None | Unreachable"] = {}  # what `refresh` just read, for `show` to say


_NOT_READ = object()


def refresh(root: Path) -> int:
    """Brings the holds in before `nstack plan` counts them; what cannot be read `show` says."""
    try:
        _fetched[root] = fetch(root)
    except Unreachable as error:
        _fetched[root] = error
    return 0


def show(root: Path) -> int:
    """Who holds what in the accepted cycle, for `nstack plan`: said, never a failure."""
    just_read = _fetched.pop(root, _NOT_READ)
    cycle = plan.accepted_cycle(root)
    if cycle is None:
        return 0
    path, data = cycle
    days = limit(root)
    try:
        name = fetch(root) if just_read is _NOT_READ else just_read
        if isinstance(name, Unreachable):
            raise name
    except Unreachable as error:
        print(f"\nHolds in {path.stem}: holds not read — the remote cannot be read.\n      {error}")
        return 0
    lines, held, stale = [], 0, 0
    items = data.get("deliverables")
    read_merges = _read_merges(root, name, data)
    merges = read_merges.live
    for item in items if isinstance(items, list) else []:
        if not isinstance(item, dict):
            continue
        ident, state = str(item.get("id")), item.get("state")
        found = read(root, path.stem, ident)
        if found.recorded and plan.one_of(state, TAKEABLE):
            lines.append(f"  {ident}  {_recorded_said(found)}" if _stands(root, name, path.stem, ident, found, read_merges)
                         else f"  {ident}  free — delivered, then a merge it names was reverted: back in work")
            continue
        if not found.held and not plan.one_of(state, TAKEABLE):
            continue
        if not found.held:
            lines.append(f"  {ident}  free")
        elif not plan.one_of(state, TAKEABLE):
            lines.append(f"  {ident}  ended — {state}; was {said(found)}")
        elif time.time() >= found.worked + days * DAY:
            held, stale = held + 1, stale + 1
            lines.append(f"  {ident}  STALE — {said(found)}: its holder renews (nstack claim {ident}); "
                         f"anyone else may nstack claim {ident} --take-over"
                         + (f"; its work is merged: nstack deliver {ident} once its criteria hold" if ident in merges else ""))
        else:
            held += 1
            lines.append(f"  {ident}  {said(found)}")
    where = f"from {name}" if name else "local only: no remote"
    print(f"\nHolds in {path.stem}: {held} held, of which {stale} stale ({where}; stale after {days} days without work):")
    print("\n".join(lines) or "  no ready deliverable")
    merged = [] if _shallow(root) else _merged(path.stem, root, merges, items)
    if merged:
        print("\nMerged, not recorded as delivered — read from commit titles, no approval checked; once every "
              "criterion holds: nstack deliver D<n> --held '#<pull request>':")
        print("\n".join(merged))
    if _shallow(root):
        print("\nA shallow clone: merges not read, so what is merged is not said here.\n      Action: git fetch --unshallow.")
    left = _empty_starts(root, name, items if isinstance(items, list) else [])
    if left:
        print("\nEmpty start branches left — one empty commit each, nothing to lose, and git branch -d refuses them:")
        print("\n".join(left))
    return 0


def _empty_starts(root: Path, name: str | None, items: list) -> list[str]:
    """What to run for each branch `claim` started that its deliverable no longer needs (#316): its
    state moved on, or its work landed from other branches — the default branch names it since —
    or it belongs to another cycle. An id no cycle here knows may be newer than this checkout, and
    is left alone. Only such a branch: the claim's own subject, one empty commit on the default
    branch, here or on the remote."""
    states = {str(item.get("id")).lower(): item.get("state") for item in items if isinstance(item, dict)}
    known = set()
    for path in plan.cycle_files(root):
        listed = (plan.read_front_matter(path)[0] or {}).get("deliverables")
        known |= {str(item.get("id")).lower() for item in (listed if isinstance(listed, list) else []) if isinstance(item, dict)}
    base = f"{MIRROR}/base" if name else "refs/heads/main"
    branches: dict[str, set[str]] = {}
    for where, prefix, strip in (("remote", f"{MIRROR}/work", 3), ("local", "refs/heads", 2)):
        if where == "remote" and not name:
            continue
        shown = _git(root, "for-each-ref", f"--format=%(refname:lstrip={strip})%09%(refname)%09%(subject)", f"{prefix}/d*").stdout
        for line in shown.splitlines():
            branch, ref, subject = (line.split("\t", 2) + ["", ""])[:3]
            ident = branch.split("-")[0]
            if (ident not in known or not subject.startswith(f"Start {ident.upper()} — ")
                    or _git(root, "rev-list", "--count", f"{base}..{ref}").stdout.strip() != "1"
                    or _git(root, "rev-parse", f"{ref}^{{tree}}").stdout != _git(root, "rev-parse", f"{ref}~1^{{tree}}").stdout):
                continue
            if ident in states and plan.one_of(states[ident], TAKEABLE) and not _landed(root, ident, ref, base):
                continue
            if ident not in states and _held_in_a_live_cycle(root, ident.upper()):
                continue
            branches.setdefault(branch, set()).add(where)
    return [f"  {branch}  " + "; ".join(([f"git push {name} --delete {branch}"] if "remote" in places else [])
                                        + ([f"git branch -D {branch}"] if "local" in places else []))
            for branch, places in sorted(branches.items())]


_ID = r"D[1-9][0-9]*"
_TITLED = re.compile(rf"\(({_ID}(?:, *{_ID})*)(?:,[^()]*)?\)(?: *\(#[0-9]+\))?$")  # "… (D47, second of three) (#12)"
_OPENED = re.compile(rf"^({_ID}) [—–-]")
_NAMED = re.compile(rf"^Deliverable:[ \t]*({_ID})\b", re.I | re.M)  # as pr-check K3 reads it
_PULL = re.compile(r"\(#([0-9]+)\)$")
_MERGED = re.compile(r"^Merge pull request #([0-9]+)\b")  # the forge's merge commit: the title is the body's first line
_REVERTS = re.compile(r"^This reverts commit ([0-9a-f]{7,40})", re.M)
_REVERTS_PULL = re.compile(r"^Reverts [\w./-]*#([0-9]+)\s*$", re.M)  # the forge's revert button
_ANSWER = re.compile(r"(?:(?P<criterion>[0-9]+)=)?(?P<answer>#[0-9]+|[0-9a-f]{7,40})")


def _delivers(subject: str, body: str) -> set[str]:
    """The deliverables a commit on the default branch delivers: its title, as a squash leaves it, or
    the `Deliverable:` line a pull request's description keeps. A mention elsewhere names nothing."""
    titled, opened = _TITLED.search(subject), _OPENED.match(subject)
    return ({part.upper() for part in re.findall(_ID, titled[1])} if titled else set()) \
        | ({opened[1].upper()} if opened else set()) | {found.upper() for found in _NAMED.findall(body)}


@dataclass
class Merges:
    """What the default branch's main line says of the deliverables, each change alive or undone."""
    live: dict[str, list[tuple[str, str | None]]] = field(default_factory=dict)  # this cycle's: id to (commit, pull request)
    citable: dict[str, list[tuple[str, str | None]]] = field(default_factory=dict)  # the same, with what reapplied them
    reverted: dict[str, list[tuple[str, str | None]]] = field(default_factory=dict)
    earlier: set[str] = field(default_factory=set)  # alive, merged before the cycle: an id carried over


@dataclass
class _Change:
    sha: str
    pull: str | None
    subject: str
    idents: set[str]
    before: bool  # merged before the cycle started
    alive: bool = True
    also: list[tuple[str, str | None]] = field(default_factory=list)  # the commits that reapplied it
    undid: set[str] = field(default_factory=set)  # the commits that reverted it


def _plain(subject: str) -> str:
    return _PULL.sub("", subject).strip()


def _chain(subject: str) -> tuple[str, str | None, int]:
    """A title's innermost title, that title's pull request, and how many reverts wrap it: `Revert` is
    one, `Reapply` two. Odd, the change is gone; even, it is back."""
    depth, pull = 0, None
    while True:
        found = _PULL.search(subject)
        pull = found[1] if found else None
        subject = _PULL.sub("", subject).strip()
        wrapped = re.fullmatch(r'(Revert|Reapply) "(.*)"', subject, re.S)
        if not wrapped:
            break
        depth, subject = depth + (1 if wrapped[1] == "Revert" else 2), wrapped[2]
    merged = _MERGED.match(subject)
    return subject, merged[1] if merged else pull, depth


def _read_merges(root: Path, name: str | None, data: dict) -> Merges:
    """Every change of the whole main line, whatever its date (`--since` stops at the first older
    commit, and reads the date in the machine's timezone), alive or undone; those since the cycle
    started, in UTC, are its merges (#328), an id carried over answering for its own alone.

    A revert acts on what its body names — `This reverts commit`, `Reverts …#<n>` — and on nothing
    else if it names any, however they end: an unknown commit changes nothing. Otherwise its title
    names one, by number or words. A commit is a merge of what its title names as well as what its
    body reverts. Not read: a revert in words alone, another forge's merge commit."""
    found, start = Merges(), plan.as_date(data.get("start"))
    if start is None:
        return found
    base = f"{MIRROR}/base" if name else "refs/heads/main"
    since = datetime.datetime(start.year, start.month, start.day, tzinfo=datetime.timezone.utc).timestamp()
    changes: list[_Change] = []
    log = _git(root, "log", "--first-parent", "--reverse", "--format=%H%x00%ct%x00%s%x00%b%x01", base).stdout
    for entry in log.split("\x01"):
        fields = entry.strip().split("\0")
        if len(fields) != 4:
            continue
        sha, before, subject, body = fields[0], int(fields[1]) < since, fields[2], fields[3]
        merged = _MERGED.match(subject)
        if merged:  # "Merge pull request #5 from …": a title on the body's first line, unless it is a trailer
            title = body.partition("\n")[0].strip()
            subject = f"#{merged[1]}" if not title or _NAMED.match(title) else f"{title} (#{merged[1]})"
        own = _PULL.search(subject)
        own = own[1] if own else merged[1] if merged else None
        inner, inner_pull, depth = _chain(subject)
        shas, pulls = _REVERTS.findall(body), _REVERTS_PULL.findall(body)
        targets = [change for change in changes if any(change.sha.startswith(one) or
                                                       any(also[0].startswith(one) for also in change.also) or
                                                       any(undid.startswith(one) for undid in change.undid) for one in shas)
                   or change.pull in pulls]
        back = {id(change) for change in targets if any(undid.startswith(one) for undid in change.undid for one in shas)}
        if not depth:
            for change in targets:
                change.alive = id(change) in back
                if not change.alive:
                    change.undid.add(sha)
            if _delivers(subject, body):
                changes.append(_Change(sha, own, _plain(subject), _delivers(subject, body), before))
            continue
        if not shas and not pulls:
            wanted = depth % 2 == 1  # a revert undoes what is alive, a reapply brings back what is not
            for change in reversed(changes):
                if change.alive == wanted and ((change.pull == inner_pull) if inner_pull else (change.subject == _plain(inner))):
                    targets = [change]
                    break
        for change in targets:
            change.alive = depth % 2 == 0
            if change.alive:
                change.also.append((sha, own))
            else:
                change.undid.add(sha)
        if not targets and depth % 2 == 0 and not shas and not pulls:  # reapplied, never seen reverted: a merge
            idents = _delivers(inner, body)
            if idents:
                changes.append(_Change(sha, own, _plain(inner), idents, before))
    for change in changes:
        for ident in change.idents:
            if not change.alive:
                found.reverted.setdefault(ident, []).extend([(change.sha, change.pull), *change.also])
            elif change.before:
                found.earlier.add(ident)
            else:
                found.live.setdefault(ident, []).append((change.sha, change.pull))
                found.citable.setdefault(ident, []).extend([(change.sha, change.pull), *change.also])
    return found


def _merges(root: Path, name: str | None, data: dict) -> dict[str, list[tuple[str, str | None]]]:
    return _read_merges(root, name, data).live


def _merged(cycle: str, root: Path, merges: dict, items) -> list[str]:
    """The open deliverables with merges and no record: what `nstack deliver` is owed."""
    lines = []
    for item in items if isinstance(items, list) else []:
        if isinstance(item, dict) and plan.one_of(item.get("state"), TAKEABLE):
            ident = str(item.get("id")).upper()
            if merges.get(ident) and not read(root, cycle, ident).recorded:
                lines.append(f"  {ident}  {len(merges[ident])} merge" + ("" if len(merges[ident]) == 1 else "s"))
    return lines


def _shallow(root: Path) -> bool:
    return _git(root, "rev-parse", "--is-shallow-repository").stdout.strip() == "true"


def _stands(root: Path, name: str | None, cycle: str, ident: str, found: Hold, merges: Merges | None = None) -> bool:
    """A record stands until a merge it names is seen reverted, or every merge of the deliverable is;
    only what is seen takes it down: a shallow clone, a `start` moved or removed never do."""
    if not found.recorded:
        return False
    if _shallow(root):
        return True
    if merges is None:
        path = next((one for one in plan.cycle_files(root) if one.stem == cycle), None)
        merges = _read_merges(root, name, plan.read_front_matter(path)[0] or {}) if path else Merges()
    ident = ident.upper()
    live, gone = merges.live.get(ident, []), merges.reverted.get(ident, [])
    if not gone:
        return True
    if ident in merges.earlier:
        live = live or [("", None)]
    answers = {answer for one in found.criteria for answer in one.split()[1:]}  # a criterion may name several
    def cited(merge: tuple[str, str | None]) -> bool:
        return any(answer == f"#{merge[1]}" or merge[0].startswith(answer) for answer in answers)
    return bool(live) and not any(cited(merge) for merge in gone)


def delivered(root: Path, path: Path, data: dict) -> set[str]:
    """The cycle's deliverables a record says are delivered, the one answer everything reads
    (PDR-0022): as last fetched, with no network. An unreadable hold is none."""
    items = data.get("deliverables")
    open_ones = [str(item.get("id")) for item in (items if isinstance(items, list) else [])
                 if isinstance(item, dict) and plan.one_of(item.get("state"), TAKEABLE)]
    found = {ident: read(root, path.stem, ident) for ident in open_ones}
    recorded = [ident for ident, one in found.items() if one.recorded]
    if not recorded:
        return set()
    name = remote(root)
    merges = _read_merges(root, name, data)
    return {ident for ident in recorded if _stands(root, name, path.stem, ident, found[ident], merges)}


def _recorded_said(found: Hold) -> str:
    sessions = f", session {', '.join(found.sessions)}" if found.sessions else ""
    held = "; ".join(found.criteria)
    return f"delivered by {found.person}{sessions}, on {when(found.worked)}" + (f" — {held}" if held else "")


def _answers(item: dict, given: list[str]) -> dict[int, list[str]] | str:
    """Each criterion's answers, or why not. `#12` answers every criterion; `2=#12` the second; a criterion
    given more than once keeps each answer, in the order given, once (#346)."""
    listed = item.get("acceptance")
    criteria = listed if isinstance(listed, list) else [listed] if isinstance(listed, str) else []
    answers: dict[int, list[str]] = {}
    for one in given:
        found = _ANSWER.fullmatch(one.strip())
        if not found:
            return f"'{one.strip()}' names no pull request or commit.\n      Action: --held '#12', or --held '2=#12' for the second criterion."
        numbers = [int(found["criterion"])] if found["criterion"] else range(1, len(criteria) + 1)
        for number in numbers:
            if not 1 <= number <= len(criteria):
                return (f"criterion {number} does not exist: the deliverable has {len(criteria)}.\n"
                        "      Action: number them as the cycle lists them, from 1.")
            if found["answer"] not in answers.setdefault(number, []):
                answers[number].append(found["answer"])
    missing = [number for number in range(1, len(criteria) + 1) if number not in answers]
    if missing:
        told = "\n".join(f"      criterion {number}: {criteria[number - 1]}" for number in missing)
        return f"nothing says what holds:\n{told}\n      Action: --held '{missing[0]}=#<pull request>'; one only a person can try waits for their answer."
    return answers


def deliver(root: Path, ident: str, given: list[str], session: str | None = None, person: str | None = None) -> int:
    """Records a delivery on the hold's branch: no pull request, nothing under docs/ (PDR-0022)."""
    found = _deliverable(root, ident)
    if isinstance(found, str):
        print(f"FAIL [deliver] {found}")
        return 1
    cycle, _ = found
    path, data = plan.accepted_cycle(root)
    person, session = _person(root, person), (session or "").strip() or None
    if any(not value.isprintable() for value in (person, session or "")):
        print("FAIL [deliver] a person or a session holds a line break or a control character.\n      Action: name them on one line.")
        return 1
    try:
        name = fetch(root)
    except Unreachable as error:
        print(f"FAIL [deliver] the remote cannot be read.\n      {error}\n      Action: check it, then again.")
        return 1
    if _shallow(root):
        print(f"FAIL [deliver] a shallow clone cannot read {ident}'s merges.\n      Action: git fetch --unshallow, then again.")
        return 1
    current, seen = read(root, cycle, ident), _read_merges(root, name, data)
    merges = seen.live
    if _stands(root, name, cycle, ident, current, seen):
        print(f"{ident} is already delivered: {_recorded_said(current)}.")
        return 0
    charter = plan.read_front_matter(root / plan.CHARTER)[0] if (root / plan.CHARTER).is_file() else None
    decider = str((charter or {}).get("decider") or "")
    on_hold = bool(session) and session.casefold() in {one.casefold() for one in current.sessions}
    if current.held and not on_hold and not same(current.person, person) and not (decider and same(decider, person)):
        print(f"FAIL [deliver] {ident} is {said(current)}: only a session on the hold, its person or the decider ({decider or 'none named'}) records "
              f"its delivery.\n      Action: ask them; a stale hold is taken over first, with nstack claim {ident} --take-over.")
        return 1
    carried = not merges.get(ident) and ident in seen.earlier
    if not merges.get(ident) and not carried:
        print(f"FAIL [deliver] the default branch records no merge of {ident} since the cycle started: nothing is "
              f"delivered yet, or every merge was reverted.\n      Action: merge its work, its title ending ({ident}), then again. "
              "A spike whose product is a record, not shipped code, has no merge to record: it is a spike outside the code, "
              "`module: null` — on an accepted cycle, a re-framing on the decider's word —, and the closure accepts it from "
              "its line (.nstack/playbooks/framing.md §2, §4).")
        return 1
    items = {str(item.get("id")): item for item in data["deliverables"] if isinstance(item, dict)}
    if not items[ident].get("acceptance"):
        print(f"FAIL [deliver] {ident} has no acceptance criteria: nothing can be held.\n      Action: the cycle lists them (C4).")
        return 1
    answers = _answers(items[ident], given)
    if isinstance(answers, str):
        print(f"FAIL [deliver] {ident}: {answers}")
        return 1
    named = _named_for(path, ident)
    mine = seen.citable.get(ident, [])  # carried over, merged in an earlier cycle: only a person's answer is left to name
    for number, answer in ((number, one) for number, ones in answers.items() for one in ones):
        pull = answer[1:] if answer.startswith("#") else None
        known = any(one[1] == pull for one in mine) or bool(re.search(rf"#{pull}\b", named)) if pull else \
            any(one[0].startswith(answer) for one in mine)
        if not known:
            print(f"FAIL [deliver] {ident}, criterion {number}: {answer} is no merge of {ident}, nor named in {path.name}.\n"
                  f"      Action: name one of {', '.join('#' + one[1] if one[1] else one[0][:9] for one in mine) or 'none'}, "
                  "or the acceptance issue named beside its state, in its section, or in a table's row with its id.")
            return 1
    sha = _event(root, current.tip, ident, "deliver", person, session,
                 criteria=[f"{number} {' '.join(answers[number])}" for number in sorted(answers)])
    ok, where = _record(root, name, cycle, ident, sha)
    if not ok:
        print(f"FAIL [deliver] {ident}'s hold moved meanwhile: {where}\n      Action: run nstack plan, then again.")
        return 1
    print(f"{ident} delivered, on record; {where}. No pull request: nstack plan says it, and the closure writes the state.")
    return 0


def deliver_command(root: Path, ident: str | None, given: list[str], session: str | None, person: str | None, states: bool) -> int:
    """One deliverable, or the states at a closure: never both, never neither."""
    if states and (ident or given):
        print("FAIL [deliver] --write-states takes no deliverable and no --held.\n      Action: nstack deliver --write-states.")
        return 1
    if states:
        return write_states(root)
    if not ident:
        print("FAIL [deliver] no deliverable named.\n      Action: nstack deliver D<n> --held '#<pull request>', or --write-states at a closure.")
        return 1
    return deliver(root, ident, given, session, person)


def _named_for(path: Path, ident: str) -> str:
    """Where a cycle names a deliverable's acceptance issue: beside its state, in its section, or on
    a table's row with its id in a cell, as what needs a person — never elsewhere in the file,
    where any number may stand."""
    text = path.read_text(encoding="utf-8")
    front = plan.FRONT_MATTER.match(text)
    body = text[front.end():] if front else text
    heading = re.search(rf"^(#{{2,4}}) +{re.escape(ident)}\b", body, re.M)
    section = ""
    if heading:
        rest = body[heading.end():]
        ended = re.search(rf"^#{{1,{len(heading[1])}}} ", rest, re.M)
        section = rest[:ended.start()] if ended else rest
    # A row of a table naming it, as `| D38, D39 on a Mac | … | #426 |`: a sentence mentioning it answers nothing.
    lines = [line for line in body.splitlines() if re.search(rf"^\s*\|.*\b{re.escape(ident)}\b(?!-).*\|", line)]
    block = re.search(rf"^[ \t]*-[ \t]*id:[ \t]*[\"']?{re.escape(ident)}[\"']?\b.*?(?=^[ \t]*-[ \t]*id:|\Z)", front[1] if front else "", re.S | re.M)
    state = re.search(r"^[ \t]*state:.*$", block[0], re.M) if block else None
    return "\n".join([state[0] if state else "", section, *lines])


def _with_state(front: str, ident: str) -> str | None:
    """The front matter with this deliverable's state accepted, or None when its lines are not the
    form a cycle file takes: `- id: D1`, then `state:` at that key's indent."""
    lines = front.split("\n")
    for index, line in enumerate(lines):
        found = re.fullmatch(rf"([ \t]*)-([ \t]+)id:[ \t]*[\"']?{re.escape(ident)}[\"']?[ \t]*(?:#.*)?\r?", line)
        if not found:
            continue
        key = " " * (len(found[1]) + 1 + len(found[2]))
        for at in range(index + 1, len(lines)):
            if re.match(rf"{re.escape(found[1])}-[ \t]", lines[at]):
                return None
            state = re.fullmatch(rf"({key}state:[ \t]*)(\S+)([ \t]*(?:#.*)?\r?)", lines[at])
            if state:
                lines[at] = f"{state[1]}accepted{state[3]}"
                return "\n".join(lines)
    return None


def write_states(root: Path) -> int:
    """At a closure, what the records say goes in the cycle file, for its one pull request."""
    cycle = plan.accepted_cycle(root)
    if cycle is None:
        print("FAIL [deliver] no accepted cycle: there is no state to write.")
        return 1
    path, data = cycle
    try:
        fetch(root)
    except Unreachable as error:
        print(f"FAIL [deliver] the remote cannot be read: nothing is known of the records.\n      {error}")
        return 1
    if _shallow(root):
        print("FAIL [deliver] a shallow clone cannot tell whether a record still stands.\n      Action: git fetch --unshallow, then again.")
        return 1
    done = sorted(delivered(root, path, data))
    with open(path, encoding="utf-8", newline="") as handle:  # a CRLF file stays one, its diff one line
        text = handle.read()
    matter = re.match(r"\A---\r?\n(.*?)\r?\n---\r?\n", text, re.S)
    front = matter[1] if matter else ""
    for ident in done:
        written = _with_state(front, ident)
        if written is None:
            print(f"FAIL [deliver] {ident}'s state could not be found in {path.name}: nothing written.\n      Action: write the states by hand.")
            return 1
        front = written
    wanted = {str(item.get("id")): {**item, "state": "accepted"} if str(item.get("id")) in done else item
              for item in data.get("deliverables") or [] if isinstance(item, dict)}
    try:
        reread = yaml.safe_load(front) or {}
    except yaml.YAMLError:
        reread = {}
    now = {str(item.get("id")): item for item in reread.get("deliverables") or [] if isinstance(item, dict)}
    if done and now != wanted:  # read back: anything else changed is a refusal, never a success
        print(f"FAIL [deliver] writing the states would change more than they in {path.name}: nothing written.\n      Action: write them by hand.")
        return 1
    if done:
        with open(path, "w", encoding="utf-8", newline="") as handle:
            handle.write(text[:matter.start(1)] + front + text[matter.end(1):])
    print(f"{path.name}: {', '.join(done)} accepted, from their records; commit it in the closure's pull request." if done
          else f"{path.name}: no record to write.")
    return 0


def _landed(root: Path, ident: str, ref: str, base: str) -> bool:
    """The default branch records the deliverable's delivery since the start branch left it: the
    `Deliverable:` line of a pull request, or its id in parentheses or opening a subject — a commit
    merely speaking of it is no delivery, and a live hold's branch is not named for it."""
    name = ident.upper()
    pattern = rf"\({name}\)|^Deliverable:[ \t]*{name}([^0-9]|$)|^{name} [—–-]"
    return bool(_git(root, "log", "-1", "--format=%H", "--extended-regexp", f"--grep={pattern}", f"{ref}~1..{base}").stdout.strip())


def _held_in_a_live_cycle(root: Path, ident: str) -> bool:
    """A hold on the remote this checkout's cycle files do not explain: its id moved on a commit not
    pulled here. A hold of a closed cycle ended with it."""
    prefix = f"{MIRROR}/hold" if remote(root) else f"refs/heads/{PREFIX}"
    closed = {path.stem for path in plan.cycle_files(root)
              if plan.one_of((plan.read_front_matter(path)[0] or {}).get("status"), plan.OUTCOMES)}
    cycles = _git(root, "for-each-ref", "--format=%(refname)", f"{prefix}/*/{ident}").stdout.split()
    return any(ref.split("/")[-2] not in closed and read(root, ref.split("/")[-2], ident).held for ref in cycles)


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
