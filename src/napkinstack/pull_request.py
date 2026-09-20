"""
Pull request rules read from its description: the test sheet (PDR-0003) and the cycle
(PDR-0002).

Rules:
  T1  a test sheet when the pull request changes a user-facing module, or one of
      criticality high or critical — at the base or at the head, the stricter
  T2  a verifier named who is not an author of the change, and every scenario row filled
      in: id, given · when · then, a kind (automated, explored, human only — reason), a
      result (passed, failed, not verified)
  T3  no scenario passed without its evidence and the commit it was verified on
  T4  evidence produced on the pull request's head commit: the others are to run again
  T5  no scenario failed; none left not verified, unless it is human only
  K1  delivery work needs an accepted charter and an accepted cycle, and says which of
      the two is missing
  K2  delivery work stops once the cycle is past its end date: the circuit breaker
  K3  delivery work names a ready or in-progress deliverable of the cycle
  K4  the out-of-cycle label carries its justification

Delivery work: a pull request that changes a module — a folder holding a MANIFEST.yaml —
beyond its description: its manifest, AGENTS.md, README.md and docs/ (D24). A NapkinStack
update or a documentation fix is neither delivery work nor a reason for a sheet.
The out-of-cycle label lifts K1 to K3, visibly and countably (docs/os/10-measurement.md).

Usage :  nstack pr-check [--root ROOT] [--base BASE] [--body-file FILE]
In CI :  PR_BODY, PR_LABELS, PR_HEAD_SHA and PR_AUTHOR come from the pull_request event.

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
from napkinstack.fitness.manifests import MODULE_DIRS, changed_files, find_manifests, is_description
from napkinstack.modules import LOGIN

LABEL = "out-of-cycle"
DELIVERABLE = re.compile(r"^Deliverable:[ \t]*(D[1-9][0-9]*)\b", re.I | re.M)
JUSTIFICATION = re.compile(r"^Out of cycle:[ \t]*(\S.*)$", re.I | re.M)
SHEET_CRITICALITIES = {"high", "critical"}
COLUMNS = ("#", "given · when · then", "kind", "result", "evidence", "commit")
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
    touched = {}
    for path, found in sorted(manifests.items()):
        folder = path.removesuffix("/MANIFEST.yaml")
        if any(file.startswith(f"{folder}/") and not is_description(file[len(folder) + 1:]) for file in files):
            touched[folder] = found
    return touched


def sheet_reason(folder: str, manifests: list[dict]) -> str | None:
    """Why a module requires a test sheet (T1), or None: the stricter of its manifests, so
    that a pull request cannot lower its own requirement."""
    modules = [data["module"] for data in manifests if isinstance(data.get("module"), dict)]
    if any(module.get("user_facing") is True for module in modules):
        return f"{folder} (user-facing)"
    for module in modules:
        if module.get("criticality") in SHEET_CRITICALITIES:
            return f"{folder} (criticality {module['criticality']})"
    return None


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


def check_verifier(verifier: str, authorship: tuple[set[str], set[str], list[str]], fail: Fail) -> None:
    """T2: the verifier is named — people as @handle anywhere on the line, an agent session as
    `session <id>` opening it — and none of the names is an author of the change."""
    opening = SESSION.match(verifier)
    session = opening["session"].casefold() if opening else None
    handles = {m["handle"].lower().removesuffix("[bot]") for m in HANDLES.finditer(verifier)}
    if not session and not handles:
        fail("T2", "Test sheet: the verifier is not named as a person or a session.\n      Action: "
                   "\"Verifier: @<handle>\" for a person, \"Verifier: session <id>\" for an agent "
                   "session — the identifier its own commits would carry (docs/os/05-workflow.md §7).")
        return
    logins, sessions, unnamed = authorship
    if named := sorted(handles & logins):
        fail("T2", f"Test sheet: the verifier @{', @'.join(named)} is an author of this change.\n      Action: "
                   "the sheet is run by someone who did not write the change (playbooks/verification.md).")
    elif session and session in sessions:
        fail("T2", f"Test sheet: the verifier, session {session}, wrote commits of this change "
                   f"({SESSION_TRAILER} trailer).\n      Action: run the sheet from another session, "
                   "with a fresh context (playbooks/verification.md).")
    elif session and unnamed:
        fail("T2", f"Test sheet: an agent's commits name no session ({', '.join(unnamed)}): the verifier "
                   f"cannot be told from their author.\n      Action: the authoring session commits with "
                   f"the trailer \"{SESSION_TRAILER}: <id>\" (AGENTS.md §0), then the sheet is run again.")


def _result(cell: str) -> str:
    return re.split(r"[ \t]+[—–-][ \t]+", cell.replace("*", "").strip(), maxsplit=1)[0].lower()


def check_sheet(body: str, head: str, reasons: list[str], fail: Fail,
                authorship: tuple[set[str], set[str], list[str]] = (set(), set(), [])) -> list[str]:
    """T1 to T5; returns the human-only scenarios, listed apart for the approver."""
    verifier, header, rows = read_sheet(body)
    if reasons and not rows:
        fail("T1", f"Test sheet missing: this pull request touches {', '.join(reasons)}.\n"
                   "      Action: fill in the \"Test sheet\" section of the description — scenarios "
                   "from the acceptance criteria, run by a verifier who is not the author "
                   "(docs/os/05-workflow.md §7).")
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
    human_only, rerun = [], []
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
        elif result in {"passed", "failed"} and SHA.fullmatch(commit) and not head.startswith(commit):
            rerun.append(ident)
        if result == "failed":
            fail("T5", f"scenario {ident}: failed.\n      Action: fix the change, or have the decider "
                       "change the expected result, visibly in the sheet's history.")
        elif result == "not verified" and reason:
            human_only.append(f"{ident} — {reason[1]}")
        elif result == "not verified":
            fail("T5", f"scenario {ident}: not verified.\n      Action: run it, or mark it "
                       "human only — <reason>.")
    if rerun:
        fail("T4", f"scenarios verified on another commit than the head {head[:7]}: "
                   f"{', '.join(rerun)}.\n      Action: run them again on the head commit.")
    return human_only


def check_cycle(root: Path, body: str, labels: set[str], today: datetime.date, fail: Fail) -> None:
    """K1 to K4, for delivery work."""
    if LABEL in labels:
        if not JUSTIFICATION.search(body):
            fail("K4", f"label {LABEL} without its justification.\n      Action: add "
                       "\"Out of cycle: <reason>\" to the description — an incident, a production defect.")
        return
    cycle = plan.accepted_cycle(root)
    if not plan.charter_accepted(root):
        fail("K1", "the project is not framed: no accepted charter in docs/project/.\n"
                   "      Action: frame it with your agent (playbooks/framing.md), or add the "
                   f"{LABEL} label with a justification.")
        return
    if cycle is None:
        # The charter is accepted: sending the reader back to framing would be false (D47).
        fail("K1", "no accepted cycle: the charter is accepted, and no cycle is open.\n"
                   "      Action: open the next cycle with your agent "
                   "(docs/project/cycles/_TEMPLATE.md), or add the "
                   f"{LABEL} label with a justification.")
        return
    path, data = cycle
    end = plan.as_date(data.get("end"))
    if end is not None and today > end:
        fail("K2", f"circuit breaker: {path.name} ended on {end}, with no automatic extension.\n"
                   "      Action: the decider chooses — ship what is accepted (status: closed), "
                   "frame a new cycle with a new appetite, or stop the project (status: stopped).")
        return
    match = DELIVERABLE.search(body)
    states = {str(item.get("id")): item.get("state") for item in data.get("deliverables") or []
              if isinstance(item, dict)}
    if not match:
        fail("K3", f"no deliverable named.\n      Action: \"Deliverable: D<n>\" in the description, "
                   f"a deliverable of {path.name}.")
    elif match[1] not in states:
        fail("K3", f"deliverable {match[1]} is not in {path.name}.\n      Action: name one of "
                   f"{', '.join(states) or 'its deliverables'}, or re-frame the cycle with the decider.")
    elif states[match[1]] not in {"ready", "in-progress"}:
        fail("K3", f"deliverable {match[1]} is '{states[match[1]]}': work starts on a ready "
                   "deliverable (definition of ready).")


def run(root: Path, base: str, body_file: Path | None = None) -> int:
    if body_file is not None:
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
    labels = {label.strip() for label in os.environ.get("PR_LABELS", "").split(",") if label.strip()}

    failures: list[str] = []

    def fail(rule: str, message: str) -> None:
        failures.append(f"[{rule}] {message}")

    reasons = [reason for folder, found in modules.items() if (reason := sheet_reason(folder, found))]
    authorship = authors(root, base, head, os.environ.get("PR_AUTHOR", ""))
    human_only = check_sheet(body, head, reasons, fail, authorship)
    if modules:
        check_cycle(root, body, labels, datetime.date.today(), fail)

    print(f"Modules touched : {len(modules)}" + "".join(f"\n  - {folder}" for folder in modules))
    print(f"Test sheet      : {'required' if reasons else 'not required'}")
    for scenario in human_only:
        print(f"  For the approver, human only: {scenario}")
    for failure in failures:
        print(f"FAIL {failure}")
    if failures:
        return 1
    print("Pull request rules: compliant.")
    return 0
