"""
Pull request rules read from its description: the test sheet (PDR-0003) and the cycle
(PDR-0002).

Rules:
  T1  a test sheet when the matrix asks one of a module the pull request changes — a
      user-facing one from standard up, any high or critical one — at the base or at the
      head, the stricter
  T2  a verifier named who is not an author of the change, and every scenario row filled
      in: id, given · when · then, a kind (automated, explored, human only — reason), a
      result (passed, failed, not verified)
  T3  no scenario passed without its evidence and the commit it was verified on
  T4  evidence at the head commit: an automated scenario is run again, one explored by hand
      is confirmed at the head instead — and at criticality critical, run again like the rest
  T5  no scenario failed; none left not verified, unless it is human only
  K1  in a framed project, delivery work needs an accepted cycle, and says which of
      the two is missing
  K2  delivery work stops once the cycle is past its end date: the circuit breaker
  K3  delivery work names a ready or in-progress deliverable of the cycle
  K4  the out-of-cycle label carries its justification
  K5  delivery work for a deliverable someone holds comes from its holder: one of the hold's
      sessions, or its person's account (`nstack claim`)

Delivery work: a pull request that changes a module — a folder holding a MANIFEST.yaml —
beyond its description: its manifest, AGENTS.md, README.md and docs/ (D24). A NapkinStack
update or a documentation fix is neither delivery work nor a reason for a sheet.
The out-of-cycle label lifts K1 to K3 and K5, visibly and countably (.nstack/handbook/10-measurement.md).

Usage :  nstack pr-check [--root ROOT] [--base BASE] [--body-file FILE] [--labels a,b]
In CI :  PR_BODY, PR_LABELS, PR_HEAD_SHA and PR_AUTHOR come from the pull_request event;
         --labels, when given, takes the place of PR_LABELS, as for nstack attest.

The verifier (T2) is a person, `@handle`, or an agent session, `session <id>`. The change's
authors are the pull request's author, the GitHub accounts behind its commits' authors,
committers and co-authors — read from GitHub's noreply addresses; another address names no
account — and the sessions its commits name in an `Agent-Session:` trailer.
It is a declaration checked against the history, not a proof of identity: it refuses the
session that verifies its own work, not one that lies about its name (ADR-0004, measurement).
Output:  0 when every applicable rule passes, 1 otherwise.
"""

from __future__ import annotations

import datetime
import os
import re
import subprocess
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
    every module whose behaviour the files may change, a deleted module included."""
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
               for file in files):
            touched[folder] = found
    return touched


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
        rows.append(dict(zip(header, values + [""] * (len(header) - len(values)))))
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


def check_verifier(verifier: str, authorship: tuple[set[str], set[str], list[str]], fail: Fail) -> None:
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


def _result(cell: str) -> str:
    return re.split(r"[ \t]+[—–-][ \t]+", cell.replace("*", "").strip(), maxsplit=1)[0].lower()


def check_sheet(body: str, head: str, reasons: list[str], fail: Fail,
                authorship: tuple[set[str], set[str], list[str]] = (set(), set(), []),
                strict: bool = False, unchanged: Callable[[str], bool] = lambda commit: False) -> list[str]:
    """T1 to T5; returns the human-only scenarios, listed apart for the approver."""
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
        check_verifier(verifier, authorship, fail)
    human_only, rerun, unconfirmed = [], [], []
    for row in rows:
        ident = row["#"] or "?"
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
            if kind.lower() == "automated" or strict:
                rerun.append(ident)
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
                   f"      {why} (.nstack/handbook/05-workflow.md §7).")
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
        # Never a silent fall back to unframed: a broken file would then switch three rules off.
        fail("C1", f"{plan.CHARTER} cannot be read: the project's stage is unknown, and nothing is "
                   "assumed.\n      Action: fix its front matter — nstack plan says what is wrong.")
        return
    if stage != plan.FRAMED:
        return  # unframed: K1 to K3 and K5 bound work inside a cycle, and there is none (PDR-0007)
    cycle = plan.accepted_cycle(root)
    if cycle is None:
        # The charter is accepted: sending the reader back to framing would be false (D47).
        fail("K1", "no accepted cycle: the charter is accepted, and no cycle is open.\n"
                   "      Action: open the next cycle with your agent "
                   "(.nstack/forms/cycle.md), or add the "
                   f"{LABEL} label with a justification.")
        return
    path, data = cycle
    end = plan.as_date(data.get("end"))
    if end is not None and today >= end:  # `end` is the first day the cycle is over (the cycle form)
        fail("K2", f"circuit breaker: {path.name} ended on {end}, with no automatic extension.\n"
                   "      Action: the decider chooses — ship what is accepted (status: closed), "
                   "frame a new cycle with a new appetite, or stop the project (status: stopped).")
        return
    match = DELIVERABLE.search(body)
    match = match and [match[0], match[1].upper()]
    states = {str(item.get("id")): item.get("state") for item in (data.get("deliverables") if isinstance(data.get("deliverables"), list) else [])
              if isinstance(item, dict)}
    if not match:
        fail("K3", f"no deliverable named.\n      Action: \"Deliverable: D<n>\" in the description, "
                   f"a deliverable of {path.name}.")
    elif match[1] not in states:
        fail("K3", f"deliverable {match[1]} is not in {path.name}.\n      Action: name one of "
                   f"{', '.join(states) or 'its deliverables'}, or re-frame the cycle with the decider.")
    elif not plan.one_of(states[match[1]], {"ready", "in-progress"}):
        fail("K3", f"deliverable {match[1]} is '{states[match[1]]}': work starts on a ready "
                   "deliverable (definition of ready).")
    elif states[match[1]] == "ready" and not _held(root, match[1]):
        # Said, not refused. The hold says the work started; the cycle file stays the decider's
        # record, never changed by a delivery — under `docs/`, a human would have to approve it.
        warn(f"[K3] deliverable {match[1]} is still 'ready' and nobody holds it while this pull request "
             f"delivers it.\n      Action: nstack claim {match[1]} — the hold says it is in progress; "
             f"{path.name} changes in the plan's own pull requests, never in a delivery's.")


def _held(root: Path, ident: str) -> bool:
    """Whether someone holds the deliverable; holds that cannot be read count as none (K5 says so)."""
    from napkinstack import hold

    found = hold.judge(root, ident)
    return found is not None and not isinstance(found, str)


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
        warn(f"[K5] the holds are not read ({found}): who holds {ident} is not judged here.")
        return
    if found is None:
        return
    logins, sessions, _ = authorship
    if ({session.casefold() for session in found.sessions} & sessions
            or any(hold.same(found.person, someone) for someone in [*logins, *people])):
        return
    fail("K5", f"{ident} is {hold.said(found)}: this pull request comes from none of its sessions "
               f"and not from its person.\n      Action: the holder gives it back (nstack unclaim {ident}), "
               f"or once stale nstack claim {ident} --take-over. The holder working from another session "
               f"names it on the hold first: nstack claim {ident} --session <it>.")


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


def check_attested(root: Path, head: str, fail) -> str:
    """Where the checks are judged, as the decider's answer `checks` says (A1, A2): on the forge's
    CI, or attested on a workstation by `nstack attest` — then a complete, passed record of the
    head is required. Returns the line the summary prints."""
    from napkinstack import attest  # the record's reader, and the one list of checks

    try:
        answers = yaml.safe_load((root / ANSWERS).read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        answers = {}
    attest.fetch(root)
    record = attest.latest(root, head)
    if answers.get("checks", "forge") != "attested":
        shown = ""
        if record:
            passed = sum(1 for check in record["checks"] if check["passed"])
            shown = f"; a record of the head: attested {passed} of {len(record['checks'])} (information)"
        return "the forge's CI" + shown
    if os.environ.get("NSTACK_ATTESTING") == head:
        return "attested — this run is the record being made"
    if os.environ.get("GITHUB_ACTIONS") == "true":
        # CI's checkout keeps no credential to fetch the notes: where the checks are attested, the
        # record is read where the merge is decided, never failed here for want of a fetch.
        return "attested — judged where nstack attest runs, not in CI"
    if record is None:
        fail("A1", f"no record of the head {head[:7]}: this project's checks are attested, and none ran on "
                   "this commit.\n      Action: run nstack attest on the head, then push.")
        return "attested — no record of the head"
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
    labels = {label.strip() for label in given.split(",") if label.strip()}

    failures: list[str] = []
    warnings = charter_without_pdr(root, base, files)

    def fail(rule: str, message: str) -> None:
        failures.append(f"[{rule}] {message}")

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
    human_only = check_sheet(body, head, reasons, fail, authorship, rerun_at_head(modules),
                             lambda commit: bool(tree_of(commit)) and tree_of(commit) == tree_of(head)) if carried else []
    if modules:
        check_cycle(root, body, labels, datetime.date.today(), fail, warnings.append)
        check_hold(root, body, labels, authorship, fail, warnings.append, identities(root, base, head))
    checks = check_attested(root, head, fail)

    print(f"Modules touched : {len(modules)}" + "".join(f"\n  - {folder}" for folder in modules))
    print(f"Test sheet      : {'required' if reasons else 'not required'}"
          + ("" if carried or not reasons else " — no carrier: forge none has no pull request. T1 to T5 "
             "judge a sheet filled in docs/pull_request_template.md — with its Deliverable line — passed by "
             "nstack attest --body-file <file>"))
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
