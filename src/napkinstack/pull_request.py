"""
Pull request rules read from its description: the test sheet (PDR-0003) and the cycle
(PDR-0002).

Rules:
  T1  a test sheet when the matrix asks one of a module the pull request changes — a
      user-facing one from standard up, any high or critical one — at the base or at the
      head, the stricter
  T2  a verifier named who is not an author of the change — a person named, whose hand is on the
      pull request: an edit of its description, a review or a comment —, and every scenario row filled
      in: id, given · when · then, a kind (automated, explored, human only — reason), a
      result (passed, failed, not verified); a | that splits a row is said (D187)
  T3  no scenario passed without its evidence and the commit it was verified on
  T4  evidence at the head commit: an automated scenario is run again, one explored by hand
      is confirmed at the head instead — and at criticality critical, run again like the rest;
      an explored row whose Commit cell moved, its evidence unchanged since a record of the pull
      request's commits read it, was not explored again (D214); moved from the commit the first
      record of that evidence names, so putting it back stands (D243), or setting it back to any
      ancestor of that commit, explored before a record held it (D254); an automated row waiting
      only for the head's record is left to attest's required status on the forge's run (#495)
  T5  no scenario failed; none left not verified, unless it is human only
  K1  in a framed project, delivery work needs an accepted cycle, and says which of
      the two is missing
  K2  delivery work stops once the cycle is past its end date: the circuit breaker
  K3  delivery work names a ready or in-progress deliverable of the cycle
  K4  the out-of-cycle label carries its justification
  K5  delivery work for a deliverable someone holds comes from its holder: one of the hold's
      sessions — named by any commit it brings, a merge included, as after a take-over — or its
      person's account (`nstack claim`)
  A1  where checks are attested and the forge does not require nstack attest's status, a record
      of the head — warned where CI cannot read it
  A2  that record complete and passed, never voided, keeping nothing from a voided run — left to
      the required status where the forge requires it
  C1  the charter readable: the project's stage is never assumed
  C9  an accepted charter changed with no decision record, warned
  R1  an approval given before commits other than the base branch's, warned (D227)
  R2  every approval Copilot's code review, warned (D246)

Delivery work: a pull request that changes a module — a folder holding a MANIFEST.yaml —
beyond its description: its manifest, AGENTS.md, README.md and docs/ (D24) — or whose manifest
moves its criticality or its user-facing surface, which is the decider's call (D184). A NapkinStack
update or a documentation fix is neither delivery work nor a reason for a sheet.
The out-of-cycle label lifts K1 to K3 and K5, visibly and countably (.nstack/handbook/10-measurement.md).

Usage :  nstack pr-check [--root ROOT] [--base BASE] [--body-file FILE] [--labels a,b]
In CI :  PR_BODY, PR_LABELS, PR_HEAD_SHA and PR_AUTHOR come from the pull_request event;
         --labels, when given, takes the place of PR_LABELS, as for nstack attest. Elsewhere, with
         a token and one open pull request at the head, its own labels are read, and a label
         given that it does not carry is refused (#368).

The verifier (T2) is a person, `@handle`, or an agent session, `session <id>`. The change's
authors are the pull request's author, the GitHub accounts behind its commits' authors,
committers and co-authors — read from GitHub's noreply addresses; another address names no
account — and the sessions its commits name in an `Agent-Session:` trailer.
It is a declaration checked against the history, not a proof of identity: it refuses the
session that verifies its own work, not one that lies about its name (ADR-0004, measurement).
Each person named must have left a hand on the pull request, read in one GraphQL query from PR_NUMBER,
GITHUB_REPOSITORY and GH_TOKEN or GITHUB_TOKEN (#363): an author who writes another's name over results
of its own is refused. Without a number — a run on a workstation, or under nstack attest — it is not
read; on the forge's run, unread is said as a warning, never failed.
Output:  0 when every applicable rule passes, 1 otherwise.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import os
import re
import shlex
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from pathlib import Path

import yaml

from napkinstack.fitness import plan
from napkinstack import assurance, project
from napkinstack.fitness.manifests import MODULE_DIRS, changed_files, find_manifests, is_description
from napkinstack.modules import LOGIN
from napkinstack.project import ANSWERS

CHARTER = plan.CHARTER.as_posix()  # docs/project/charter.md, as the diff names it

LABEL = "out-of-cycle"
DELIVERABLE = re.compile(r"^Deliverable:[ \t]*(D[1-9][0-9]*)\b", re.I | re.M)
JUSTIFICATION = re.compile(r"^Out of cycle:[ \t]*(\S.*)$", re.I | re.M)

COLUMNS = ("#", "given · when · then", "kind", "result", "evidence", "commit")
# Optional seventh column, read only when a scenario needs it: the head commit and what
# changed since. A sheet no fix has disturbed never has to carry it (T4, D71).
CONFIRMED = "confirmed"
CELLS = "cells read"  # how many a row held
PIPED = "a pipe in a code span"  # a bare |: the table ends the cell there, as GitHub does
KINDS = {"automated", "explored"}
RESULTS = {"passed", "failed", "not verified"}
SECTION = re.compile(r"^##[ \t]+Test sheet[ \t]*$", re.I | re.M)
NEXT_SECTION = re.compile(r"^#{1,2}[ \t]", re.M)
VERIFIER = re.compile(r"^Verifier:[ \t]*(.*)$", re.I | re.M)
HUMAN_ONLY = re.compile(r"human only[ \t]*[—–-][ \t]*(\S.*)", re.I)
PLACEHOLDER = re.compile(r"<[^<>]*>")
EMPTY = {"", "—", "-"}
SHA = re.compile(r"[0-9a-f]{7,40}")
HANDLES = re.compile(rf"(?<![\w@])@(?P<handle>{LOGIN}(?:\[bot\])?)(?![\w-])")
SESSION = re.compile(r"^\s*session[ \t]+(?P<session>[\w.:/-]*\w)", re.I)
NOREPLY = re.compile(r"(?:\d+\+)?(?P<login>[^@<>\s]+)@users\.noreply\.github\.com", re.I)
SESSION_TRAILER = "Agent-Session"
LOG = (f"%h%x1f%ae%x1f%ce%x1f%(trailers:key={SESSION_TRAILER},valueonly,separator=%x1d)"
       "%x1f%(trailers:key=Co-authored-by,valueonly,separator=%x1d)%x1e")

Fail = Callable[[str, str], None]


def _git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=root, capture_output=True, text=True)


def _manifest(text: str) -> dict:
    try:
        data = yaml.safe_load(text) or {}
    except yaml.YAMLError:
        data = {}
    return data if isinstance(data, dict) else {}


def touched_modules(root: Path, base: str, files: list[str]) -> dict[str, list[dict]]:
    """Folder, relative to the root, to its manifests — at the head and at the base — for
    every module whose behaviour the files may change, a deleted module included, or whose
    manifest moved what it owes."""
    manifests = {path.relative_to(root).as_posix(): [_manifest(path.read_text(encoding="utf-8"))]
                 for path in find_manifests(root)}
    listed = _git(root, "ls-tree", "-r", "--name-only", base).stdout.split()
    for path in listed:
        parts = path.split("/")
        if parts[-1] == "MANIFEST.yaml" and parts[0] in MODULE_DIRS and len(parts) in (2, 3):
            manifests.setdefault(path, []).append(_manifest(_git(root, "show", f"{base}:{path}").stdout))
    relied = relied_on_pages(root, manifests)
    touched = {}
    for path, found in sorted(manifests.items()):
        folder = path.removesuffix("/MANIFEST.yaml")
        if any(file.startswith(f"{folder}/") and (not is_description(file[len(folder) + 1:]) or file in relied)
               for file in files) or _owes_differently(found):
            touched[folder] = found
    return touched


def _owes_differently(manifests: list[dict]) -> bool:
    """True when the manifest moved what its module owes (.nstack/handbook/05-workflow.md §7): the
    rest of a manifest is a description, these two say which checks the module answers to (D184)."""
    owed = [(module.get("criticality"), module.get("user_facing") is True)
            for module in (data.get("module") for data in manifests) if isinstance(module, dict)]
    return len(set(owed)) > 1


CONTRACT_PAGE = re.compile(r"(?P<path>.+/(?P<contract>[^/]+)/(?P<version>v\d+))/README\.md")


def relied_on_pages(root: Path, manifests: dict[str, list[dict]]) -> set[str]:
    """The pages of the contract versions someone relies on — a module consumes the version, or
    it holds a schema — relative to the root (D133). Such a page is the contract: its prose is
    held by review and by nothing else (03-contracts.md), so changing it changes its module. A
    version nobody relies on yet keeps PDR-0012's relief: its page is a description."""
    consumed = {(str(entry.get("contract")), str(entry.get("version")))
                for found in manifests.values() for data in found[:1]
                for entry in (data.get("consumes") or []) if isinstance(entry, dict)}
    pages = set()
    for data in (found[0] for found in manifests.values() if found):
        for entry in data.get("provides") or []:
            if not isinstance(entry, dict) or not entry.get("path"):
                continue
            page = f"{str(entry['path']).rstrip('/')}/README.md"
            match = CONTRACT_PAGE.fullmatch(page)
            if match and ((match["contract"], match["version"]) in consumed
                          or any((root / match["path"]).glob("*.schema.json"))):
                pages.add(page)
    return pages


def sheet_reason(folder: str, manifests: list[dict]) -> str | None:
    """Why a module requires a test sheet (T1), or None: the stricter of its manifests, so
    that a pull request cannot lower its own requirement. What each criticality requires is read
    from the matrix of .nstack/handbook/05-workflow.md §7, never from a threshold copied here."""
    modules = [data["module"] for data in manifests if isinstance(data.get("module"), dict)]
    for module in modules:
        criticality = module.get("criticality")
        facing = module.get("user_facing") is True
        if not assurance.requires(criticality, "sheet", facing):
            continue
        why = f"criticality {criticality}" + (", user-facing" if facing else "")
        relief = assurance.relief(criticality, "sheet", facing)
        return f"{folder} ({why})" + (f" — {relief}" if relief else "")
    return None


def rerun_at_head(found: dict[str, list[dict]]) -> bool:
    """True when a touched module is strict enough that no confirmation stands in for a re-run:
    the `rerun_at_head` row of the matrix, `critical` alone (.nstack/handbook/05-workflow.md §7)."""
    for manifests in found.values():
        for data in manifests:
            module = data.get("module")
            if isinstance(module, dict) and assurance.requires(module.get("criticality"), "rerun_at_head"):
                return True
    return False


def _cells(line: str) -> list[str]:
    inner = line.strip().removeprefix("|").removesuffix("|")
    return [cell.strip().replace("\\|", "|") for cell in re.split(r"(?<!\\)\|", inner)]


def read_sheet(body: str) -> tuple[str, list[str], list[dict[str, str]]]:
    """(verifier, header, filled rows) of the "Test sheet" section; empty when absent."""
    match = SECTION.search(body)
    if not match:
        return "", [], []
    section = body[match.end():]
    if following := NEXT_SECTION.search(section):
        section = section[:following.start()]
    found = VERIFIER.search(section)
    verifier = found[1].strip() if found else ""
    verifier = "" if PLACEHOLDER.fullmatch(verifier) else verifier
    lines = [line for line in section.splitlines() if line.strip().startswith("|")]
    if len(lines) < 2:
        return verifier, [], []
    header = [" ".join(cell.lower().split()) for cell in _cells(lines[0])]
    rows = []
    for line in lines[2:]:
        values = _cells(line)
        if all(value in EMPTY or PLACEHOLDER.fullmatch(value) for value in values[1:]):
            continue  # the template's example row
        piped = any("|" in span for span in re.findall(r"`[^`]*`", line.replace("\\|", "")))
        rows.append({**dict(zip(header, values + [""] * (len(header) - len(values)))), CELLS: len(values), PIPED: piped})
    return verifier, header, rows


def authors(root: Path, base: str, head: str, opener: str) -> tuple[set[str], set[str], list[str]]:
    """(GitHub logins, agent sessions, agent commits naming no session) of the commits the pull
    request brings — its head, less the base, less merges: CI checks out a merge commit, and
    updating a branch merges the base in. A login is lower-cased and loses its `[bot]` suffix,
    so that `@napkinstack-agent` names the App."""
    logins = {opener.lower().removesuffix("[bot]")} if opener else set()
    sessions, unnamed = set(), []
    for record in _git(root, "log", "--no-merges", f"--format={LOG}", f"{base}..{head}").stdout.split("\x1e"):
        if not record.strip():
            continue
        commit, author, committer, named, coauthors = record.strip("\n").split("\x1f")
        found = {m["login"].lower() for m in NOREPLY.finditer(" ".join([author, committer, coauthors]))}
        logins |= {login.removesuffix("[bot]") for login in found}
        named = {value.strip() for value in named.split("\x1d") if value.strip()}
        sessions |= {session.casefold() for session in named}
        if not named and any(login.endswith("[bot]") for login in found):
            unnamed.append(commit)
    return logins, sessions, unnamed


# A later commit does not name the earlier ones: the trailer is read on every commit an agent
# made (D93). Said as two ways out, because rewriting a reviewed branch is not always allowed.
UNNAMED_ACTION = (f"every commit an agent made carries \"{SESSION_TRAILER}: <id>\" (AGENTS.md §0) — "
                  "a commit added now does not name the earlier ones: recommit them, on a new branch "
                  "where the history is not rewritten; or have a person run the sheet.")


def summary(body: str, authorship: tuple[set[str], set[str], list[str]]) -> list[str]:
    """What the check read of a sheet, in a line, and what stands in a session's way before one
    has done the work (D93): a verdict of one word told a verifier nothing of either."""
    verifier, _, rows = read_sheet(body)
    if not rows:
        return []
    counts: dict[str, int] = {}
    for row in rows:
        result = _result(row.get("result", ""))
        result = result if result in RESULTS else "unreadable"
        counts[result] = counts.get(result, 0) + 1
    said = ", ".join(f"{number} {result}" for result, number in counts.items())
    lines = [f"  Read: {len(rows)} scenario(s) — {said}; verifier: {verifier or 'not named'}, "
             f"compared with {len(authorship[0])} account(s) and {len(authorship[1])} session(s) of the change"]
    if authorship[2] and not SESSION.match(verifier):
        lines.append(f"  NOTE: an agent's commits name no session ({', '.join(authorship[2])}): as it stands, "
                     f"only a person can verify this change.\n        To let a session verify it: {UNNAMED_ACTION}")
    return lines


TRACES = """query($owner: String!, $name: String!, $number: Int!) {
  repository(owner: $owner, name: $name) { pullRequest(number: $number) {
    reviews(first: 100) { totalCount nodes { author { login } } }
    comments(first: 100) { totalCount nodes { author { login } } }
    userContentEdits(first: 100) { totalCount nodes { editor { login } } } } } }"""


def _pull_request(root: Path, query: str) -> dict | str | None:
    """The pull request as one GraphQL query reads it; why it is not read; None with no pull
    request number, on a workstation, and while `nstack attest` records the head: what the forge
    holds is judged on the forge's own run."""
    number = os.environ.get("PR_NUMBER", "").strip()
    if not re.fullmatch(r"[0-9]+", number) or os.environ.get("NSTACK_ATTESTING"):
        return None
    repository = os.environ.get("GITHUB_REPOSITORY") or project.answer(root, "github_repo") or ""
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not token or "/" not in repository:
        return "no token (GH_TOKEN or GITHUB_TOKEN) or no repository"
    owner, name = repository.split("/", 1)
    request = urllib.request.Request(
        os.environ.get("GITHUB_GRAPHQL_URL") or "https://api.github.com/graphql",
        data=json.dumps({"query": query, "variables": {"owner": owner, "name": name, "number": int(number)}}).encode(),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json", "User-Agent": "nstack"})
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            answer = json.loads(response.read())
        if answer.get("errors"):  # a field refused leaves the rest of the answer partial
            return f"the forge refused part of the query ({answer['errors'][0].get('type', 'error')})"
        found = answer["data"]["repository"]["pullRequest"]
        return found if isinstance(found, dict) else "the forge did not answer (no pull request)"
    except (OSError, ValueError, KeyError, TypeError, AttributeError, IndexError) as error:
        return f"the forge did not answer ({type(error).__name__})"


def traces(root: Path) -> set[str] | str | None:
    """The accounts whose hand is on the pull request — its description's editors, its reviewers,
    its commenters —, lower case and without `[bot]`; why they are not read; None where the pull
    request is not read (`_pull_request`): the hand is judged on the forge's run, which an edit of
    the description starts again."""
    found = _pull_request(root, TRACES)
    if not isinstance(found, dict):
        return found
    try:
        hands = [(found[kind], key) for kind, key in (("reviews", "author"), ("comments", "author"),
                                                       ("userContentEdits", "editor"))]
        if any(connection["totalCount"] > len(connection["nodes"]) for connection, _ in hands):
            return "more traces than one page"
        return {node[key]["login"].lower().removesuffix("[bot]") for connection, key in hands
                for node in connection["nodes"] if node and node.get(key)}
    except (KeyError, TypeError, AttributeError) as error:
        return f"the forge did not answer ({type(error).__name__})"


# Each reviewer's latest review that approved or asked for changes: a dismissed one is not APPROVED,
# so where the forge dismisses stale approvals (G13) none is ever read here as covering the head.
APPROVALS = """query($owner: String!, $name: String!, $number: Int!) {
  repository(owner: $owner, name: $name) { pullRequest(number: $number) {
    latestOpinionatedReviews(first: 100) { totalCount nodes { state author { login } commit { oid } } } } } }"""


def approvals(root: Path) -> list[tuple[str, str]] | str | None:
    """Each approving reviewer's login and the commit their approval was given on; why they are not
    read; None where the pull request is not read (`_pull_request`)."""
    found = _pull_request(root, APPROVALS)
    if not isinstance(found, dict):
        return found
    try:
        reviews = found["latestOpinionatedReviews"]
        if reviews["totalCount"] > len(reviews["nodes"]):
            return "more reviewers than one page"
        return [(node["author"]["login"] if node.get("author") else "a deleted account",
                 str((node.get("commit") or {}).get("oid") or "").lower())
                for node in reviews["nodes"] if node and node.get("state") == "APPROVED"]
    except (KeyError, TypeError, AttributeError) as error:
        return f"the forge did not answer ({type(error).__name__})"


def check_approvals(root: Path, base: str, head: str, found: list[tuple[str, str]] | str | None,
                    warn: Callable[[str], None]) -> None:
    """R1 (#377): where the forge keeps an approval once new commits are pushed — no ruleset, or
    stale approvals not dismissed —, "approved" no longer says the head was read. An approval on
    an earlier commit covers the head when only the base branch was merged in since; otherwise it
    is said, with whom and which commits. A warning, never a failure: a review starts no run (D218),
    so a check failed on it would stay red after the approver read the head and approved again."""
    if isinstance(found, str):
        warn(f"[R1] whether each approval covers the head is not read: {found}.")
        return
    for login, commit in found or []:
        if commit == head:
            continue
        known = bool(commit) and not _git(root, "merge-base", "--is-ancestor", commit, head).returncode
        since = _git(root, "rev-list", f"{commit}..{head}", f"^{base}").stdout.split() if known else []
        # A merge counts when it carries content of its own — a conflict resolved, an edit made
        # while merging —: what a clean merge of the base would not have written.
        since = [one for one in since if _git(root, "rev-list", "--no-walk", "--merges", one).stdout.strip() == ""
                 or _git(root, "show", "--remerge-diff", "--format=", one).stdout.strip()]
        if known and not since:
            continue  # only the base branch merged in: nothing the approver has not read
        what = (f"{len(since)} commit(s) pushed since" if known
                else "a commit this branch does not hold — rewritten since, or not found here")
        line = (f"[R1] @{login} approved {commit[:7] or 'an unknown commit'}, not the head {head[:7]}, at this run: "
                f"{what}, which the approval does not cover.")
        warn(f"{line}\n        Action: @{login} reads them and approves again before the merge; where the forge "
             "dismisses stale approvals on push, it does this itself (.nstack/handbook/07-governance.md §7).")
        if os.environ.get("GITHUB_ACTIONS") == "true":  # seen on the check, not only in its log
            print(f"::warning title=R1 approval behind the head::{line.removeprefix('[R1] ')}")


# Copilot's code review, as the forge names it: GraphQL's author login, REST's user login
# (measured on public pull requests it approved, 2026-11-19).
COPILOT_REVIEWER = {"copilot-pull-request-reviewer", "copilot-pull-request-reviewer[bot]"}


def check_copilot(found: list[tuple[str, str]] | str | None, warn: Callable[[str], None]) -> None:
    """R2 (D246): GitHub lets a repository count Copilot's approval toward the required ones — a
    setting its API does not expose, so doctor cannot read it. Where every approval is Copilot's,
    the merge may rest on it alone, though it ran no test sheet and names no session: said, as R1
    is, never failed."""
    if isinstance(found, str) or not found:
        return
    if all(login.lower() in COPILOT_REVIEWER for login, _ in found):
        line = ("[R2] the only approval is Copilot's code review: GitHub counts it where the repository lets "
                "it, yet it ran no test sheet and names no session.")
        warn(f"{line}\n        Action: a human code owner approves — or, on approval: agent, the verifying "
             "agent under its own identity (.nstack/handbook/07-governance.md §7).")
        if os.environ.get("GITHUB_ACTIONS") == "true":
            print(f"::warning title=R2 approval by Copilot alone::{line.removeprefix('[R2] ')}")


def check_verifier(verifier: str, authorship: tuple[set[str], set[str], list[str]], fail: Fail,
                   hands: set[str] | None = None) -> None:
    """T2: the verifier is named — people as @handle anywhere on the line, an agent session as
    `session <id>` opening it — and none of the names is an author of the change."""
    opening = SESSION.match(verifier)
    session = opening["session"].casefold() if opening else None
    handles = {m["handle"].lower().removesuffix("[bot]") for m in HANDLES.finditer(verifier)}
    if not session and not handles:
        fail("T2", "Test sheet: the verifier is not named as a person or a session.\n      Action: "
                   "\"Verifier: @<handle>\" for a person, \"Verifier: session <id>\" for an agent "
                   "session — the identifier its own commits would carry (.nstack/handbook/05-workflow.md §7).")
        return
    logins, sessions, unnamed = authorship
    if named := sorted(handles & logins):
        fail("T2", f"Test sheet: the verifier @{', @'.join(named)} is an author of this change.\n      Action: "
                   "the sheet is run by someone who did not write the change (.nstack/playbooks/verification.md).")
    elif session and session in sessions:
        fail("T2", f"Test sheet: the verifier, session {session}, wrote commits of this change "
                   f"({SESSION_TRAILER} trailer).\n      Action: run the sheet from another session, "
                   "with a fresh context (.nstack/playbooks/verification.md).")
    elif session and unnamed:
        fail("T2", f"Test sheet: an agent's commits name no session ({', '.join(unnamed)}): the verifier "
                   f"cannot be told from their author.\n      Action: {UNNAMED_ACTION}")
    elif hands is not None and (absent := sorted(handles - hands)):
        named = ", @".join(absent)
        fail("T2", f"Test sheet: the verifier @{named} left no trace on this pull request — no edit of its "
                   "description, no review, no comment: the sheet says who should have verified, not who did.\n"
                   f"      Action: @{named} runs the sheet and writes it in the description, or reviews it; or the "
                   "sheet names only who did (.nstack/playbooks/verification.md). A review or a comment is read at "
                   "the next run: an edit of the description starts one.")


def _result(cell: str) -> str:
    return re.split(r"[ \t]+[—–-][ \t]+", cell.replace("*", "").strip(), maxsplit=1)[0].lower()


def _split(row: dict, width: int) -> bool:
    """A bare | moved the row's columns. A row that reads well has not moved, whatever it holds:
    cells beyond the header are ignored, as GitHub ignores them, and backticks prove nothing."""
    result = _result(row["result"])
    commit = SHA.fullmatch(row["commit"].strip().strip("`").lower())
    kind = row["kind"].lower() in KINDS or HUMAN_ONLY.fullmatch(row["kind"])
    if kind and result in RESULTS and (commit or result == "not verified"):
        return False
    late = SHA.fullmatch(row.get(CONFIRMED, "").strip().strip("`").lower())  # one cell after the commit's
    return bool(row[PIPED] or late or row[CELLS] > width)


def check_sheet(body: str, head: str, reasons: list[str], fail: Fail,
                authorship: tuple[set[str], set[str], list[str]] = (set(), set(), []),
                strict: bool = False, unchanged: Callable[[str], bool] = lambda commit: False,
                hands: set[str] | None = None, same_inputs: Callable[[str], str | None] = lambda commit: "") -> list[str]:
    """T1 to T5; returns the human-only scenarios, listed apart for the approver. `same_inputs` says why an
    automated row at another commit is not kept by its inputs (D223): None when it is, "" when there is
    nothing to say (#491)."""
    verifier, header, rows = read_sheet(body)
    if reasons and not rows:
        fail("T1", "Test sheet missing: this pull request touches\n"
                   + "".join(f"      - {reason}\n" for reason in reasons) +
                   "      Action: fill in the \"Test sheet\" section of the description — scenarios "
                   "from the acceptance criteria, run by a verifier who is not the author "
                   "(.nstack/handbook/05-workflow.md §7).")
        return []
    if not rows:
        return []
    missing = [column for column in COLUMNS if column not in header]
    if missing:
        fail("T2", f"Test sheet: columns missing: {', '.join(missing)}.\n"
                   f"      Expected: | {' | '.join(COLUMNS)} |")
        return []
    if not verifier:
        fail("T2", "Test sheet: no verifier named.\n      Action: \"Verifier: @<handle>\" or "
                   "\"Verifier: session <id>\", someone other than the author of the change.")
    else:
        check_verifier(verifier, authorship, fail, hands)
    human_only, rerun, unconfirmed, why_rerun = [], [], [], []
    for row in rows:
        ident = row["#"] or "?"
        if _split(row, len(header)):
            fail("T2", f"scenario {ident}: a | splits its row ({row[CELLS]} cells, the header {len(header)}): its "
                       "columns cannot be read.\n      Action: a | in a cell ends it, in a code span too: "
                       "write it \\|.")
            continue
        kind = row["kind"]
        reason = HUMAN_ONLY.fullmatch(kind)
        result = _result(row["result"])
        if row["given · when · then"] in EMPTY or PLACEHOLDER.fullmatch(row["given · when · then"]):
            fail("T2", f"scenario {ident}: given · when · then missing")
        if kind.lower() not in KINDS and not reason:
            fail("T2", f"scenario {ident}: kind '{kind}', expected automated, explored, "
                       "or human only — <reason>")
        if result not in RESULTS:
            fail("T2", f"scenario {ident}: result '{row['result']}', expected passed, failed or "
                       "not verified")
            continue
        commit = row["commit"].strip().strip("`").lower()
        if result == "passed" and (row["evidence"] in EMPTY or not SHA.fullmatch(commit)):
            fail("T3", f"scenario {ident}: passed without evidence and the commit verified.\n"
                       "      Action: link the screenshot, video, trace or log, and give the commit.")
        elif (result in {"passed", "failed"} and SHA.fullmatch(commit) and not head.startswith(commit)
              and not unchanged(commit)):
            # T4 split by kind (D71). An automated scenario is cheap and CI replays it when e2e is
            # declared, so it is re-run. One that was explored by hand costs a round: its evidence keeps the commit
            # it was produced on, and the verifier confirms at the head, naming what moved since.
            # At `critical` nothing stands in for a re-run: that is what the top value buys.
            # Each clause of the cell starts with the commit it confirms: a later confirmation
            # joins an earlier one after a `;`, never replacing it (#288).
            confirmed = [clause.strip().split(" ", 1)[0].strip("`").lower()
                         for clause in row.get(CONFIRMED, "").split(";")]
            why = same_inputs(commit) if kind.lower() == "automated" and not strict else ""
            if why is None:
                pass  # what its module reads is unchanged since that run, and the run is fresh (D223)
            elif kind.lower() == "automated" or strict:
                rerun.append(ident)
                if why:
                    why_rerun.append(f"{ident}: {why}")
            elif not any(SHA.fullmatch(commit) and head.startswith(commit) for commit in confirmed):
                unconfirmed.append(ident)
        if result == "failed":
            fail("T5", f"scenario {ident}: failed.\n      Action: fix the change, or have the decider "
                       "change the expected result, visibly in the sheet's history.")
        elif result == "not verified" and reason:
            human_only.append(f"{ident} — {reason[1]}")
        elif result == "not verified":
            fail("T5", f"scenario {ident}: not verified.\n      Action: run it, or mark it "
                       "human only — <reason>.")
    if rerun:
        why = ("At criticality critical every scenario is re-run at the head, and the confirmation "
               "a lighter value allows does not apply" if strict else
               "An automated scenario is re-run, never confirmed: CI replays it when the module "
               "declares e2e, and its Commit cell takes the head")
        fail("T4", f"scenarios verified on another commit than the head {head[:7]}: "
                   f"{', '.join(rerun)}.\n      Action: run them again on the head commit.\n"
                   f"      {why} (.nstack/handbook/05-workflow.md §7)."
                   + "".join(f"\n      Not kept by its inputs — {line}" for line in why_rerun))
    if unconfirmed:
        fail("T4", f"scenarios explored before the head {head[:7]} and not confirmed on it: "
                   f"{', '.join(unconfirmed)}.\n      Action: re-read what changed since, then "
                   f"add the head commit in a Confirmed column: `{head[:7]} — <what moved, and why "
                   "it leaves this scenario's result standing>`, after a `;` when the cell holds an "
                   "earlier one.\n      Running the whole sheet again is the other way, and it is not "
                   "required: a confirmation is not a round "
                   "(.nstack/handbook/05-workflow.md §7).")
    return human_only


def check_cycle(root: Path, body: str, labels: set[str], today: datetime.date, fail: Fail,
                warn: Callable[[str], None] = lambda message: None) -> None:
    """K1 to K4, for delivery work."""
    if LABEL in labels:
        if not JUSTIFICATION.search(body):
            fail("K4", f"label {LABEL} without its justification.\n      Action: add "
                       "\"Out of cycle: <reason>\" to the description — an incident, a production defect.")
        return
    stage = plan.stage(root)
    if stage == plan.UNREADABLE:
        # Never a silent fall back to unframed: a broken file would then switch K1 to K3 and K5 off.
        fail("C1", f"{plan.CHARTER} cannot be read: the project's stage is unknown, and nothing is "
                   "assumed.\n      Action: fix its front matter — nstack plan says what is wrong.")
        return
    if stage != plan.FRAMED:
        return  # unframed: K1 to K3 and K5 bound work inside a cycle, and there is none (PDR-0007)
    cycle = plan.accepted_cycle(root)
    if cycle is None:
        # The charter is accepted: sending the reader back to framing would be false (D47) — and so would
        # framing a cycle the decider already accepted while the last one ran (#354).
        waiting = next((path for path in plan.cycle_files(root)
                        if (data := plan.read_front_matter(path)[0]) and data.get("status") == "proposed"
                        and "accepted_on" in data), None)
        action = (f"set {waiting.name}'s status: accepted and its start, in a pull request the decider approves"
                  if waiting else "open the next cycle with your agent (.nstack/forms/cycle.md)")
        fail("K1", "no accepted cycle: the charter is accepted, and no cycle is open.\n"
                   f"      Action: {action}, or add the {LABEL} label with a justification.")
        return
    path, data = cycle
    end = plan.as_date(data.get("end"))
    if end is not None and today >= end:  # `end` is the first day the cycle is over (the cycle form)
        fail("K2", f"circuit breaker: {path.name} ended on {end}, with no automatic extension.\n"
                   "      Action: the decider chooses — ship what is delivered or accepted (status: closed), "
                   "frame a new cycle with a new appetite, or stop the project (status: stopped).")
        return
    match = DELIVERABLE.search(body)
    match = match and [match[0], match[1].upper()]
    states = {str(item.get("id")): item.get("state") for item in (data.get("deliverables") if isinstance(data.get("deliverables"), list) else [])
              if isinstance(item, dict)}
    if not match:
        fail("K3", f"no deliverable named.\n      Action: \"Deliverable: D<n>\" in the description, "
                   f"a deliverable of {path.name}."
                   + ("" if labels else f"\n      This run read no label. If the pull request is out of cycle, it "
                      f"carries the {LABEL} label, put on the pull request: a run on a workstation reads it there "
                      f"with a token, or is given it with --labels {LABEL} (or PR_LABELS)."))
    elif match[1] not in states:
        fail("K3", f"deliverable {match[1]} is not in {path.name}.\n      Action: name one of "
                   f"{', '.join(states) or 'its deliverables'}, or re-frame the cycle with the decider.")
    elif not plan.one_of(states[match[1]], {"ready", "in-progress"}):
        fail("K3", f"deliverable {match[1]} is '{states[match[1]]}': work starts on a ready "
                   "deliverable (definition of ready).")
    elif _on_record(root, path, data, match[1]):
        warn(f"[K3] deliverable {match[1]} is on record as delivered, and this pull request delivers it again.\n"
             f"      Action: if its record is wrong, nstack unclaim {match[1]}; a defect found since is an issue of its own.")
    elif states[match[1]] == "ready" and _nobody_holds(root, match[1]):
        # Said, not refused. The hold says the work started; the cycle file stays the decider's
        # record, never changed by a delivery — under `docs/`, a human would have to approve it.
        from napkinstack import hold

        warn(f"[K3] deliverable {match[1]} is still 'ready' and nobody holds it on {hold.remote(root) or 'this repository'} "
             f"while this pull request delivers it.\n      Action: nstack claim {match[1]} — the hold says it is in "
             f"progress; {path.name} changes never in a delivery's pull request.")


def _on_record(root: Path, path: Path, data: dict, ident: str) -> bool:
    """On CI's fresh clone nothing has fetched the holds yet; unreadable, K5 says so."""
    from napkinstack import hold

    try:
        hold.fetch(root)
    except hold.Unreachable:
        return False
    return ident in plan.delivered_in(root, path, data)


def _nobody_holds(root: Path, ident: str) -> bool:
    """Whether the holds were read and none holds the deliverable. Holds that cannot be read are
    no answer: K5 says why, and K3 never concludes "nobody"."""
    from napkinstack import hold

    return hold.judge(root, ident) is None


def merge_sessions(root: Path, base: str, head: str) -> set[str]:
    """The agent sessions named by the merges the pull request brings. For K5 alone (#439): a
    deliverable taken over, its new session merges the default branch into the former session's
    branch, and that merge may be its only commit. A sheet's authors stay the non-merge commits'."""
    log = _git(root, "log", "--merges", f"--format=%(trailers:key={SESSION_TRAILER},valueonly,separator=%x1d)%x1e",
               f"{base}..{head}").stdout
    return {value.strip().casefold() for record in log.split("\x1e") for value in record.split("\x1d") if value.strip()}


def identities(root: Path, base: str, head: str) -> set[str]:
    """The git identities, `Name <email>`, of the authors and committers of the commits the pull
    request brings."""
    log = _git(root, "log", "--no-merges", "--format=%an <%ae>%n%cn <%ce>", f"{base}..{head}").stdout
    return {line for line in log.splitlines() if line.strip()}


def check_hold(root: Path, body: str, labels: set[str], authorship: tuple[set[str], set[str], list[str]],
               fail: Fail, warn: Callable[[str], None], people: set[str] = frozenset()) -> None:
    """K5: the deliverable a pull request delivers is not held by someone else. Nobody holds it:
    nothing is asked — claiming protects, it is no toll. The holds cannot be read: said."""
    from napkinstack import hold

    match = DELIVERABLE.search(body)
    if LABEL in labels or not match or plan.stage(root) != plan.FRAMED:
        return
    ident = match[1].upper()
    found = hold.judge(root, ident)
    if isinstance(found, str):
        warn(f"[K5] the holds are not read: who holds {ident} is not judged here.\n      {found}")
        return
    if found is None:
        return
    logins, sessions, _ = authorship
    if ({session.casefold() for session in found.sessions} & sessions
            or any(hold.same(found.person, someone) for someone in [*logins, *people])):
        return
    person = shlex.quote(found.person)
    fail("K5", f"{ident} is {hold.said(found)}: this pull request comes from none of its sessions "
               f"and not from its person.\n      Action: the holder gives it back (nstack unclaim {ident}), "
               f"or once stale nstack claim {ident} --take-over. The holder's person moves it to another "
               f"session on their word: nstack claim {ident} --take-over --person {person} --session <it>; "
               f"an agent restarted under a new session renews its own hold, from that session in nstack agent "
               f"run: nstack claim {ident} --person {person} --session <it>.")


def charter_without_pdr(root: Path, base: str, files: list[str]) -> list[str]:
    """C9: an accepted charter changes only through a PDR (it is the project's founding
    decision). Said as a warning where the change is — a typo in it is not a decision — and
    never while the charter is still proposed, which is when the framing writes it."""
    if CHARTER not in files:
        return []
    before = _git(root, "show", f"{base}:{CHARTER}")
    status = re.search(r"^status:\s*['\"]?(\w+)", before.stdout.split("\n---", 1)[0], re.M) if before.returncode == 0 else None
    if not status or status.group(1) != "accepted":
        return []
    if any(path.startswith("docs/pdr/") and not path.endswith("README.md") for path in files):
        return []
    return [f"[C9] {CHARTER}: the accepted charter changes, and no decision record comes with it.\n"
            "      Action: write the PDR that decides the change, and cite it in the charter; a "
            "correction that decides nothing needs none (.nstack/playbooks/framing.md, Decisions)."]


def this_pull(root: Path, head: str) -> dict:
    """What names the pull request a record is made for (#508): its number where the forge gives it,
    and the branch it is made on — a branch started on another's carries that one's records too."""
    actions = os.environ.get("GITHUB_ACTIONS") == "true"
    ref = re.fullmatch(r"refs/pull/(\d+)/(?:merge|head)", os.environ.get("GITHUB_REF", "")) if actions else None
    pulled = None if actions else _pull_labels(root, head)
    number = int(ref[1]) if ref else pulled[0] if isinstance(pulled, tuple) and pulled[0] else None
    branch = os.environ.get("GITHUB_HEAD_REF", "").strip() if actions else _branch(root)
    return {**({"number": number} if number else {}), **({"branch": branch} if branch else {})}


def _branch(root: Path) -> str:
    """The pull request's branch as this checkout knows it: the remote branch it tracks — a verifier's
    `git switch -c check origin/d1-x` names d1-x —, else its own name; none when detached."""
    local = _git(root, "symbolic-ref", "-q", "HEAD").stdout.strip()
    if not local:
        return ""
    upstream = _git(root, "for-each-ref", "--format=%(upstream)", local).stdout.strip()
    if upstream.startswith("refs/remotes/"):
        return upstream.split("/", 3)[3]
    return local.removeprefix("refs/heads/")


def same_pull(made_for: object, this: dict) -> bool:
    """A record is this pull request's unless what both name differs: the number first, else the
    branch. A record naming neither — made before #508, or by nothing that knew — is read."""
    for key in ("number", "branch"):
        if isinstance(made_for, dict) and key in made_for and key in this:
            return made_for[key] == this[key]
    return True


def recorded_rows(root: Path, fork: str, head: str, this: dict | None = None) -> list[tuple[str, str, dict]]:
    """Every sheet row a record of this pull request's commits holds: (commit, at, row) — each run of
    each note, since an author may attest one commit twice with two descriptions. A record made for
    another pull request — one whose branch this one started on (#508) — is not this one's history."""
    from napkinstack import attest

    commits = _git(root, "rev-list", f"{fork}..{head}").stdout.split()
    found = []
    for commit in commits:
        shown = _git(root, "notes", f"--ref={attest.NOTES}", "show", commit)
        for line in shown.stdout.splitlines() if shown.returncode == 0 else []:
            try:
                run = json.loads(line)
            except json.JSONDecodeError:
                continue
            sheet = (run.get("sheet") if isinstance(run, dict) and run.get("record") == attest.RECORD
                     and run.get("commit") == commit and same_pull(run.get("pull"), this or {}) else None)
            for ident, row in (sheet.items() if isinstance(sheet, dict) else []):
                if isinstance(row, dict):
                    found.append((commit, str(run.get("at", "")), {**row, "#": ident}))
    return found


# A removal said (#485): `Removed: S3, S4 — <why>`, on a line of its own; with no reason it says nothing.
REMOVED = re.compile(r"^\s*Removed:\s*([^\s—–-][^—–]*?)\s+[—–-]\s+\S", re.MULTILINE)


def check_moved(body: str, recorded: list[tuple[str, str, dict]], fail: Fail, warn: Callable[[str], None],
                same_files: Callable[[str, str], bool] = lambda one, other: False,
                before_it: Callable[[str, str], bool] = lambda older, newer: False) -> None:
    """T4, the sheet's history (D214, #384): the description is edited by author and verifier alike.
    A row explored at one commit whose Commit cell now names another, its evidence unchanged, was
    never explored again — as a forge dismisses an approval the head moved past. The row's commit is
    the one the first record holding that evidence names, whatever a later record held. An automated row
    may move: CI, or the head's record, ran it. A row a record held, gone from the sheet, is said."""
    _, header, rows = read_sheet(body)
    if any(column not in header for column in COLUMNS):
        return  # T2 says which column is missing
    now = {row["#"]: row for row in rows if row["#"]}
    for ident, row in now.items():
        commit = row.get("commit", "").strip().strip("`").lower()
        if row.get("kind", "").lower() != "explored" or _result(row.get("result", "")) not in {"passed", "failed"} or not SHA.fullmatch(commit):
            continue
        evidence = hashlib.sha256(row.get("evidence", "").strip().encode()).hexdigest()[:16]
        # The commit it was explored at: the first record holding this evidence. A later record that
        # held the cell moved does not make the move the row's commit (D243, #444).
        before = next((was for _, _, was in sorted(recorded, key=lambda r: r[1])
                       if was["#"] == ident and was.get("evidence") == evidence and SHA.fullmatch(was.get("commit", ""))), None)
        # A cell set back to an ancestor of that commit claims less, not more — explored before the
        # first record held it there, the head confirmed beside it (#460): only a move forward is said.
        if before and not (before["commit"].startswith(commit) or commit.startswith(before["commit"])
                           or same_files(before["commit"], commit) or before_it(commit, before["commit"])):
            fail("T4", f"scenario {ident}: its Commit cell moved from {before['commit'][:7]} to {commit[:7]}, its "
                       "evidence unchanged: nothing shows it was explored again.\n"
                       f"      Action: the verifier explores it at the head and links that run's own evidence — or puts "
                       f"{before['commit'][:7]} back and confirms the head in the Confirmed column.")
    said = {ident.strip() for found in REMOVED.finditer(body) for ident in found.group(1).split(",")}
    gone = sorted({was["#"] for _, _, was in recorded
                   if was["#"] not in now and was["#"] not in said and was.get("result") in {"passed", "failed"}})
    if gone:
        warn(f"[T5] scenario(s) {', '.join(gone)} were in the sheet a record of this pull request read, and are "
             "gone from it.\n      Action: say why under the sheet — a line `Removed: <ids> — <why>` — for the "
             "approver to judge; restore it from the description's history otherwise.")


def _pull_labels(root: Path, head: str) -> tuple[int, set[str]] | str | None:
    """The open pull request whose head is `head`, and its labels, read on the forge (#368); why not,
    when it was asked; None when nothing is asked: off GitHub or without a token, and where the
    labels given are already the pull request's — the forge's own run, and the checks nstack attest
    runs with the labels it read."""
    if os.environ.get("GITHUB_ACTIONS") == "true" or os.environ.get("NSTACK_ATTESTING") == head:
        return None
    from napkinstack import attest, hold

    forge = hold._forge(root, attest._remote(root) or "origin")
    if forge is None:
        return None
    try:
        answer = hold._call(forge, "GET", f"/commits/{head}/pulls")
    except hold.Refused as error:
        return str(error)
    pulls = [pull for pull in answer if isinstance(pull, dict) and pull.get("state") == "open"
             and isinstance(pull.get("head"), dict) and pull["head"].get("sha") == head] if isinstance(answer, list) else []
    if len(pulls) != 1:
        return "no open pull request has this head" if not pulls else f"{len(pulls)} open pull requests have this head"
    names = {str(label["name"]) for label in pulls[0].get("labels") or [] if isinstance(label, dict) and label.get("name")}
    return int(pulls[0].get("number") or 0), names


def labels_for(root: Path, head: str, given: str) -> tuple[set[str], str, str | None]:
    """The labels judged, where they come from, and a refusal: the pull request's own when it is read
    — a label given that it does not carry is refused, since a label is what the reviewer sees on the
    forge (#368); else the ones given, said as the caller's."""
    named = {label.strip() for label in given.split(",") if label.strip()}
    found = _pull_labels(root, head)
    if isinstance(found, tuple):
        number, carried = found
        if extra := sorted(name for name in named if name.lower() not in {label.lower() for label in carried}):
            return named, "", (f"pull request #{number} carries no label {', '.join(extra)}: a label is judged as the "
                               f"reviewer sees it on the forge.\n      Action: put it on pull request #{number}, or "
                               "run without --labels and with PR_LABELS unset: the pull request's own are read.")
        return carried, f"read from pull request #{number}", None
    if os.environ.get("GITHUB_ACTIONS") == "true":
        return named, "the pull request event's", None
    if os.environ.get("NSTACK_ATTESTING") == head:
        return named, "as nstack attest read them", None
    return named, ("given by the caller (--labels, PR_LABELS)" if named else "none given") + (
        f" — the pull request's not read: {found}" if found else ""), None


def status_required(root: Path) -> bool:
    """Whether the base branch's rules require the record's own status, `nstack / local checks`
    (D221, #399): read on the forge's run only, from the rules that apply to the branch — readable
    with the job's token. A record is made after the description's last edit (D214) and travels by
    notes, which start no run; its status, posted by `nstack attest` with it, is the event that
    says it. Unread — no token, a refusal — is False: the run judges the record itself, as before."""
    from napkinstack import attest

    branch = os.environ.get("GITHUB_BASE_REF", "")
    repository = os.environ.get("GITHUB_REPOSITORY") or project.answer(root, "github_repo") or ""
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if os.environ.get("GITHUB_ACTIONS") != "true" or not branch or not token or "/" not in repository:
        return False
    api = os.environ.get("GITHUB_API_URL") or "https://api.github.com"
    request = urllib.request.Request(f"{api}/repos/{repository}/rules/branches/{urllib.parse.quote(branch, safe='')}"
                                     "?per_page=100",
                                     headers={"Accept": "application/vnd.github+json", "User-Agent": "nstack",
                                              "Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            rules = json.loads(response.read())
    except (OSError, ValueError):
        return False
    return any(isinstance(rule, dict) and rule.get("type") == "required_status_checks"
               and any(isinstance(check, dict) and check.get("context") == attest.CONTEXT
                       for check in (rule.get("parameters") or {}).get("required_status_checks") or [])
               for rule in rules if isinstance(rules, list))


def _module_inputs(record: dict | None, root: Path | None = None, commit: str = "") -> tuple[str, str, str | None] | None:
    """A record's `Module checks` digest, its first run's time and base (ADR-0006, D223); none when
    it was kept from a run since voided (#429)."""
    from napkinstack import attest

    checks = record.get("checks") if isinstance(record, dict) and isinstance(record.get("checks"), list) else []
    found = next((c for c in checks if isinstance(c, dict) and c.get("name") == "Module checks"), None)
    if not found or found.get("passed") is not True or not found.get("inputs"):
        return None
    if root is not None and attest.kept_from_voided(root, found, commit):
        return None
    return str(found["inputs"]), str(found.get("kept_from") or record.get("at", "")), \
        found.get("kept_base") or record.get("base_commit")


def same_inputs(root: Path, head: str, base: str,
                warn: Callable[[str], None] = lambda message: None) -> Callable[[str], str | None]:
    """T4's relief for an automated row (D223): the record of the row's commit and the head's hold
    the same inputs digest, and the row's run is fresh. While nstack attest makes the head's record,
    the digest it computed stands in for it. The callable returns None when the row stands, else why
    it does not — the cheap path first (#491). The forge's run starts at the push, before that record:
    where the ruleset requires attest's status, a row waiting for it is left to that status, as A1 is,
    and said (#495)."""
    from napkinstack import attest

    try:
        answers = yaml.safe_load((root / ANSWERS).read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        answers = {}
    if not isinstance(answers, dict) or answers.get("checks") != "attested":
        return lambda commit: ""  # the forge's CI replays it: the relief is for attested checks
    cache: dict[str, str | None] = {}
    waiting: set[str] = set()

    def head_digest() -> str | None:
        if "head" not in cache:
            if os.environ.get("NSTACK_ATTESTING") == head:
                cache["head"] = os.environ.get("NSTACK_INPUTS") or None
            else:
                attest.read_remote(root)
                record = attest.latest(root, head)
                found = _module_inputs(record, root, head)
                cache["head"] = found[0] if found else None
                # The forge's run, made at the push, comes before the head's record (#495): where the
                # ruleset requires attest's status, a row waiting only for that record is left to it.
                # A record that exists and holds no digest waits for nothing; attest's own run never waits.
                cache["waits"] = "yes" if record is None and status_required(root) else None
        return cache["head"]

    def same(commit: str) -> str | None:
        digest = head_digest()  # first: it fetches the remote's records, the row's commit's among them
        full = _git(root, "rev-parse", "--verify", "--quiet", f"{commit}^{{commit}}").stdout.strip()
        found = _module_inputs(attest.latest(root, full), root, full) if full else None
        if not found:
            return (f"{commit} has no passing record of its module checks: nstack attest with {commit} checked out, and "
                    "the row stands while what its modules read is unchanged since")
        if not digest:
            if cache.get("waits"):
                if commit not in waiting:
                    waiting.add(commit)
                    warn(f"[T4] automated rows run at {commit} wait for the record of the head {head[:7]}: the required "
                         f"status '{attest.CONTEXT}' judges them — nstack attest's own check keeps them while what "
                         "their modules read is unchanged, and fails T4 otherwise.\n      Action: nstack attest on "
                         f"the head {head[:7]}, with a token that may write commit statuses.")
                return None
            return (f"the head {head[:7]} has no passing record of its module checks yet: nstack attest on it, "
                    "and the row stands while what its modules read is unchanged since")
        if found[0] != digest:
            return f"what its modules read changed between {commit} and the head {head[:7]}" + \
                _what_changed(root, base, full, head)
        base_commit = _git(root, "rev-parse", "--verify", "--quiet", f"{base}^{{commit}}").stdout.strip() or None
        if not attest._fresh(root, found[1], found[2], base_commit):
            return (f"its run at {commit} is older than {attest.FRESH_DAYS} days, or than "
                    f"{attest.FRESH_COMMITS} commits of the default branch")
        return None

    return same


def _what_changed(root: Path, base: str, commit: str, head: str) -> str:
    """What `attest.inputs` reads and differs between two commits (D275): each folder read whole, with
    how many of its files changed, and each other path; the digest's other parts when no file did."""
    from napkinstack import attest

    nothing = " — no file they read differs; the modules run, the engine or who runs it changed"
    scope = attest.input_scope(root, base)
    listed = _git(root, "diff", "--name-only", "-z", "--no-renames", commit, head)
    if scope is None or listed.returncode:
        return ""  # what is read, or what differs, cannot be told: nothing is said rather than a guess
    _, folders, inside = scope
    counted: dict[str, int] = {}
    for path in filter(None, listed.stdout.split("\0")):
        folder = next((one for one in folders if path.startswith(f"{one}/")), None)
        if folder:
            counted[folder] = counted.get(folder, 0) + 1
        elif not path.startswith((*inside, *attest.RECORDS)):
            counted[path] = 0
    if not counted:
        return nothing
    said = [f"{name} ({count} file{'s' if count > 1 else ''})" if count else name for name, count in sorted(counted.items())]
    return ": " + ", ".join(said[:5]) + (f", and {len(said) - 5} more" if len(said) > 5 else "")


def check_attested(root: Path, head: str, fail, warn=lambda message: None) -> str:
    """Where the checks are judged, as the decider's answer `checks` says (A1, A2): on the forge's
    CI, or attested on a workstation by `nstack attest` — then a complete, passed record of the
    head is required, read from the remote's notes wherever it runs, CI included (#367). Returns
    the line the summary prints."""
    from napkinstack import attest  # the record's reader, and the one list of checks

    try:
        answers = yaml.safe_load((root / ANSWERS).read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        answers = {}
    _, unread = attest.read_remote(root)
    record = attest.latest(root, head)
    if answers.get("checks", "forge") != "attested":
        shown = ""
        if record:
            passed = sum(1 for check in record["checks"] if check["passed"])
            shown = (f"; a record of the head: voided — {record['void']} (information)" if record.get("void")
                     else f"; a record of the head: attested {passed} of {len(record['checks'])} (information)")
        return "the forge's CI" + shown
    if os.environ.get("NSTACK_ATTESTING") == head:
        return "attested — this run is the record being made"
    if status_required(root):
        if record is not None and (record.get("void") or not all(check["passed"] for check in record["checks"])
                                   or any(attest.kept_from_voided(root, check, head) for check in record["checks"])):
            # The status is the last attest that could post one; a later run without a token is in the
            # notes only — said, since the forge's green may be an earlier record's.
            warn(f"[A2] the latest record of the head {head[:7]} does not pass, and the status "
                 f"'{attest.CONTEXT}' may be an earlier record's.\n      Action: fix what failed, commit, and run "
                 "nstack attest again with a token that may write commit statuses.")
        return (f"attested — judged by the required status '{attest.CONTEXT}', which nstack attest posts with "
                "the record")
    if record is None and unread and os.environ.get("GITHUB_ACTIONS") == "true":
        # The record may well be there, out of reach: said, never failed for want of a fetch — and
        # never the silent line that let an unattested head through (#367).
        warn(f"[A1] the record of the head is not read here ({unread}): whether {head[:7]} was attested is "
             "unknown to this run.\n      Action: give the job a token that reads the repository "
             "(GH_TOKEN, contents: read), or run nstack pr-check where the merge is decided.")
        return "attested — the record of the head not read here"
    if record is None:
        fail("A1", f"no record of the head {head[:7]}: this project's checks are attested, and none ran on "
                   "this commit.\n      Action: run nstack attest on the head, then push — the forge's check reads the "
                   "record again at its next run: a push, or an edit of the description. Or require the status "
                   f"'{attest.CONTEXT}' in the branch's ruleset: nstack attest posts it with the record, and this "
                   "run leaves the record to it (07-governance.md §7).")
        return "attested — no record of the head"
    if record.get("void"):
        fail("A2", f"the record of the head {head[:7]} was voided by {record.get('by')} at {record.get('at')}: "
                   f"{record['void']}.\n      Action: run nstack attest on the head again — nothing is kept from a "
                   "voided record.")
        return "attested — the record of the head was voided"
    unsound = [check["name"] for check in record["checks"] if attest.kept_from_voided(root, check, head)]
    if unsound:
        fail("A2", f"the record of the head {head[:7]} keeps {', '.join(unsound)} from a run since voided.\n"
                   "      Action: run nstack attest on the head again — nothing is kept from a voided run.")
        return "attested — the record of the head keeps a voided run"
    names = [check["name"] for check in record["checks"]]
    missing = [check.name for check in attest.CHECKS if check.name not in names]
    failed = [check["name"] for check in record["checks"] if not check["passed"]]
    if missing or failed:
        said = "; ".join(part for part in (f"missing: {', '.join(missing)}" if missing else "",
                                           f"failed: {', '.join(failed)}" if failed else "") if part)
        fail("A2", f"the record of the head {head[:7]} is not complete and passed ({said}).\n"
                   "      Action: fix what failed, commit, and run nstack attest again.")
        return "attested — the record of the head does not pass"
    return f"attested on a workstation, by {record['by']}, at {record['at']}"


def run(root: Path, base: str, body_file: Path | None = None, labels_given: str | None = None) -> int:
    if body_file is not None:
        if not body_file.is_file():
            print(f"FAIL [pr-check] {body_file} not found: no description to read.\n"
                  "      Action: pass the pull request's filled form with --body-file.")
            return 1
        body = body_file.read_text(encoding="utf-8")
    elif "PR_BODY" in os.environ:
        body = os.environ["PR_BODY"]
    else:
        print("Pull request description not provided (PR_BODY or --body-file): not checked.")
        return 0
    if _git(root, "rev-parse", "--verify", "--quiet", base).returncode:
        print(f"FAIL [pr-check] base '{base}' not found: the change cannot be read.\n"
              "      Action: fetch the history (fetch-depth: 0), or pass an existing commit.")
        return 1
    files = changed_files(root, base)
    head = (os.environ.get("PR_HEAD_SHA") or _git(root, "rev-parse", "HEAD").stdout).strip().lower()
    fork = _git(root, "merge-base", base, "HEAD").stdout.strip() or base
    modules = touched_modules(root, fork, files)
    # The option, else PR_LABELS: one way for pr-check and attest alike (D147).
    given = os.environ.get("PR_LABELS", "") if labels_given is None else labels_given
    labels, labels_from, refused = labels_for(root, head, given)

    failures: list[str] = []
    warnings = charter_without_pdr(root, base, files)

    def fail(rule: str, message: str) -> None:
        failures.append(f"[{rule}] {message}")

    if refused:
        fail("labels", refused)

    reasons = [reason for folder, found in modules.items() if (reason := sheet_reason(folder, found))]
    authorship = authors(root, base, head, os.environ.get("PR_AUTHOR", ""))
    # A commit whose tree is the head's is the head, for a sheet (D93): merging the default
    # branch into a pull request that already carried it changes a hash and no file.
    def tree_of(commit: str) -> str:
        return _git(root, "rev-parse", "--verify", "--quiet", f"{commit}^{{tree}}").stdout.strip()

    forge = project.forge(root)
    # With no forge there is no pull request to carry a sheet: one filled in the form's file and
    # passed with --body-file is judged; none at all is said, not failed (ADR-0010 §6).
    carried = forge != "none" or bool(body.strip())
    verifier = read_sheet(body)[0]
    hands = traces(root) if forge == "github" and HANDLES.search(verifier) and not SESSION.match(verifier) else None
    if isinstance(hands, str):
        warnings.append(f"[T2] whether {', '.join(m[0] for m in HANDLES.finditer(verifier))}'s hand is on this pull "
                        f"request is not read: {hands}.")
    human_only = check_sheet(body, head, reasons, fail, authorship, rerun_at_head(modules),
                             lambda commit: bool(tree_of(commit)) and tree_of(commit) == tree_of(head),
                             hands if isinstance(hands, set) else None, same_inputs(root, head, base, warnings.append)) if carried else []
    if modules:
        check_cycle(root, body, labels, datetime.date.today(), fail, warnings.append)
        logins, sessions, unnamed = authorship
        check_hold(root, body, labels, (logins, sessions | merge_sessions(root, base, head), unnamed),
                   fail, warnings.append, identities(root, base, head))
    checks = check_attested(root, head, fail, warnings.append)
    if forge == "github":
        found = approvals(root)
        check_approvals(root, base, head, found, warnings.append)
        check_copilot(found, warnings.append)
    if carried and reasons:
        check_moved(body, recorded_rows(root, fork, head, this_pull(root, head)), fail, warnings.append,
                    lambda one, other: bool(tree_of(one)) and tree_of(one) == tree_of(other),
                    lambda older, newer: _git(root, "merge-base", "--is-ancestor", older, newer).returncode == 0)

    print(f"Modules touched : {len(modules)}" + "".join(f"\n  - {folder}" for folder in modules))
    print(f"Test sheet      : {'required' if reasons else 'not required'}"
          + ("" if carried or not reasons else " — no carrier: forge none has no pull request. T1 to T5 "
             "judge a sheet filled in docs/pull_request_template.md — with its Deliverable line — passed by "
             "nstack attest --body-file <file>"))
    print(f"Labels          : {', '.join(sorted(labels)) or 'none'} — {labels_from}")
    print(f"Checks          : {checks}")
    for line in summary(body, authorship) if reasons and carried else []:
        print(line)
    if reasons and carried and forge != "github":
        print(f"  Off GitHub (forge {forge}): the verifier compared with the change's agent sessions and "
              "GitHub's noreply addresses only — no person is recognised as an author off GitHub by any other address")
    for scenario in human_only:
        print(f"  For the approver, human only: {scenario}")
    for warning in warnings:
        print(f"WARNING {warning}")
    for failure in failures:
        print(f"FAIL {failure}")
    if failures:
        return 1
    print("Pull request rules: compliant.")
    return 0
