"""
Fitness function 4 — The project's charter and cycles (PDR-0002).

A project is framed by a charter and bounded by cycles, written in docs/project/. Their
front matter, a YAML block between two --- lines at the top of the file, is what the
checks read; the prose below it is for humans and agents.

Rules:
  C1  front matter readable: a YAML mapping at the top of the file
  C2  charter: status proposed or accepted, a decider who is one named person, at least
      one success criterion
  C3  cycle: a goal, a known status, appetite_weeks, start and end, end = start + appetite
  C4  deliverables: ids D1, D2… unique, a title, a known state, acceptance criteria once ready
  C5  at most one accepted cycle, and only under an accepted charter
  C6  a closed or stopped cycle records its outcome and the date it ended
  C7  discovery: a known decision, its decider and date once decided, a challenger for a go;
      a charter follows a go

Templates, whose file name starts with "_", are not checked.

Usage :  nstack plan [--root ROOT]
Output:  0 when the charter and the cycles are valid, or absent; 1 otherwise.
A root without docs/project/, such as the NapkinStack repository itself, is out of scope.
"""

from __future__ import annotations

import datetime
import re
from pathlib import Path

import yaml

from napkinstack.fitness.manifests import unfilled
from napkinstack.modules import HANDLE

PROJECT = Path("docs") / "project"
CHARTER = PROJECT / "charter.md"
CYCLES = PROJECT / "cycles"
DISCOVERY = PROJECT / "discovery.md"
DECISIONS = {"proposed", "go", "clarify", "kill"}
CHARTER_STATUSES = {"proposed", "accepted"}
CYCLE_STATUSES = {"proposed", "accepted", "closed", "stopped"}
DELIVERABLE_STATES = {"proposed", "ready", "in-progress", "accepted", "deferred", "dropped"}
WITHOUT_CRITERIA = {"proposed", "deferred", "dropped"}  # acceptance criteria not required yet
OUTCOMES = {"closed": {"completed", "shipped"}, "stopped": {"reframed", "stopped"}}
DELIVERABLE_ID = re.compile(r"D[1-9][0-9]*")
FRONT_MATTER = re.compile(r"\A---\n(.*?)\n---\n", re.S)
DECIDER = re.compile(rf"@?{HANDLE}")  # one person, the way GitHub names people


def check_decider(rule: str, path: Path, value, fail) -> None:
    """A decision has one owner, and it must be possible to route what it decides to them."""
    decider = str(value or "").strip()
    if not decider:
        fail(rule, path, "decider missing: the GitHub handle of the human who validates the charter "
                         "and the cycles, and decides at the circuit breaker")
    elif not DECIDER.fullmatch(decider):
        fail(rule, path, f"decider '{decider}': expected one person's GitHub handle, such as @alice. "
                         "Not a team, and not the template's placeholder — a decision has one owner, "
                         "and the framework has to be able to reach them")


def read_front_matter(path: Path) -> tuple[dict | None, str]:
    """The front matter as a mapping, or None and the reason it cannot be read (C1)."""
    match = FRONT_MATTER.match(path.read_text(encoding="utf-8"))
    if not match:
        return None, "no front matter: the file must start with a YAML block between two --- lines"
    try:
        data = yaml.safe_load(match[1])
    except yaml.YAMLError as exc:
        return None, f"front matter unreadable: {exc}"
    if not isinstance(data, dict):
        return None, "front matter must be a YAML mapping"
    return data, ""


def as_date(value) -> datetime.date | None:
    if isinstance(value, datetime.datetime):
        return value.date()
    if isinstance(value, datetime.date):
        return value
    try:
        return datetime.date.fromisoformat(str(value))
    except ValueError:
        return None


def cycle_files(root: Path) -> list[Path]:
    folder = root / CYCLES
    return sorted(p for p in folder.glob("*.md") if not p.name.startswith("_")) if folder.is_dir() else []


def charter_accepted(root: Path) -> bool:
    path = root / CHARTER
    data = read_front_matter(path)[0] if path.is_file() else None
    return bool(data) and data.get("status") == "accepted"


def accepted_cycle(root: Path) -> tuple[Path, dict] | None:
    """The cycle in progress: the one accepted cycle, when its front matter is readable."""
    for path in cycle_files(root):
        data = read_front_matter(path)[0]
        if data and data.get("status") == "accepted":
            return path, data
    return None


def _check_charter(path: Path, fail) -> bool:
    data, reason = read_front_matter(path)
    if data is None:
        fail("C1", path, reason)
        return False
    if data.get("status") not in CHARTER_STATUSES:
        fail("C2", path, f"status '{data.get('status')}': expected one of {sorted(CHARTER_STATUSES)}")
    check_decider("C2", path, data.get("decider"), fail)
    criteria = data.get("success_criteria")
    if not isinstance(criteria, list) or not [c for c in criteria if not unfilled(c)]:
        fail("C2", path, "success_criteria: at least one, filled in — they say when the project "
                         "itself ends. The template's example is not one")
    return data.get("status") == "accepted"


def _check_deliverables(path: Path, deliverables, fail) -> None:
    if not isinstance(deliverables, list) or not deliverables:
        fail("C4", path, "deliverables: a finite, non-empty list — what the cycle delivers")
        return
    seen: set[str] = set()
    for index, item in enumerate(deliverables, start=1):
        if not isinstance(item, dict):
            fail("C4", path, f"deliverable no. {index}: expected a mapping (id, title, state, acceptance)")
            continue
        ident = str(item.get("id") or "")
        where = ident or f"no. {index}"
        if not DELIVERABLE_ID.fullmatch(ident):
            fail("C4", path, f"deliverable {where}: id expected as D1, D2…")
        elif ident in seen:
            fail("C4", path, f"deliverable {ident}: id used twice")
        seen.add(ident)
        if unfilled(item.get("title")):
            fail("C4", path, f"deliverable {where}: title missing, or still the template's")
        state = item.get("state")
        if state not in DELIVERABLE_STATES:
            fail("C4", path, f"deliverable {where}: state '{state}', expected one of {sorted(DELIVERABLE_STATES)}")
        criteria = item.get("acceptance")
        filled = isinstance(criteria, list) and [c for c in criteria if not unfilled(c)]
        if state in DELIVERABLE_STATES - WITHOUT_CRITERIA and not filled:
            # The criteria are right, and the refusal names the door the framework already had.
            # Work whose product is knowledge is a SPIKE: its criteria name what will be recorded
            # and the threshold it is read against, and a refuted result is a delivered one. The
            # pilot did not know that and answered a criterion it could not meet with five
            # simulated proofs, merged and reviewed like the rest (D72). The door existed; the
            # refusal did not mention it.
            fail("C4", path, f"deliverable {where}: state '{state}' requires acceptance criteria "
                             "filled in — the definition of ready, and the source of its test "
                             "sheet (PDR-0003).\n      Action: write them, or make it a spike. "
                             "A deliverable whose product is knowledge — a probe, interviews, a "
                             "legal question — names what will be recorded and the threshold it "
                             "is read against, and a refuted result is a delivered one "
                             "(playbooks/framing.md, docs/os/05-workflow.md §3).\n      What has "
                             "no criterion at all, because it waits on someone outside the "
                             "project, is a dependency with a date and not a deliverable. A "
                             "criterion nobody can meet gets met with something that looks like "
                             "proof.")


def _check_cycle(path: Path, fail) -> str | None:
    data, reason = read_front_matter(path)
    if data is None:
        fail("C1", path, reason)
        return None
    if not str(data.get("goal") or "").strip():
        fail("C3", path, "goal missing: one sentence")
    status = data.get("status")
    if status not in CYCLE_STATUSES:
        fail("C3", path, f"status '{status}': expected one of {sorted(CYCLE_STATUSES)}")
    weeks = data.get("appetite_weeks")
    if isinstance(weeks, bool) or not isinstance(weeks, int) or weeks < 1:
        fail("C3", path, "appetite_weeks: a whole number of weeks, decided rather than estimated")
        weeks = None
    start, end = as_date(data.get("start")), as_date(data.get("end"))
    if start is None or end is None:
        fail("C3", path, "start and end: dates, YYYY-MM-DD")
    elif weeks is not None and end != start + datetime.timedelta(weeks=weeks):
        fail("C3", path, f"end {end}: the appetite sets it, start + {weeks} week(s) = "
                         f"{start + datetime.timedelta(weeks=weeks)}")
    _check_deliverables(path, data.get("deliverables"), fail)
    if status in OUTCOMES:
        if data.get("outcome") not in OUTCOMES[status]:
            fail("C6", path, f"a {status} cycle records its outcome: one of {sorted(OUTCOMES[status])}")
        if as_date(data.get("ended_on")) is None:
            fail("C6", path, f"a {status} cycle records ended_on, the date it ended")
    return status if isinstance(status, str) else None


def _check_discovery(path: Path, fail) -> str | None:
    data, reason = read_front_matter(path)
    if data is None:
        fail("C1", path, reason)
        return None
    decision = data.get("decision")
    if decision not in DECISIONS:
        fail("C7", path, f"decision '{decision}': expected one of {sorted(DECISIONS)}")
    elif decision != "proposed":
        check_decider("C7", path, data.get("decider"), fail)
        if as_date(data.get("decided_on")) is None:
            fail("C7", path, f"a decision ({decision}) records decided_on, YYYY-MM-DD")
        if decision == "go" and unfilled(data.get("challenger")):
            fail("C7", path, "a go names its challenger: another session, or a human, challenged the "
                             "document first (playbooks/discovery.md, stage 5)")
    return decision if isinstance(decision, str) else None


def run(root: Path) -> int:
    failures: list[str] = []

    def fail(rule: str, path: Path, message: str) -> None:
        failures.append(f"[{rule}] {path.relative_to(root)}\n      {message}")

    if not (root / PROJECT).is_dir():
        print(f"Plan: not applicable, no {PROJECT}/ in {root}.")
        return 0
    charter = root / CHARTER
    discovery = root / DISCOVERY
    cycles = cycle_files(root)
    if not charter.is_file() and not cycles and not discovery.is_file():
        print(f"Plan: no charter and no cycle in {PROJECT}/ — the project is not framed yet "
              "(playbooks/framing.md).")
        return 0
    decision = _check_discovery(discovery, fail) if discovery.is_file() else None
    accepted_charter = _check_charter(charter, fail) if charter.is_file() else False
    if accepted_charter and discovery.is_file() and decision != "go":
        fail("C7", charter, f"the charter is accepted, but the discovery's decision is '{decision}': "
                            "a charter follows a go (docs/project/discovery.md)")
    accepted = [path for path in cycles if _check_cycle(path, fail) == "accepted"]
    if len(accepted) > 1:
        names = ", ".join(path.name for path in accepted)
        fail("C5", root / CYCLES, f"{len(accepted)} accepted cycles ({names}): one cycle at a time — "
                                  "close or stop the others")
    if accepted and not accepted_charter:
        fail("C5", accepted[0], "an accepted cycle requires an accepted charter "
                                f"({CHARTER}, status: accepted)")

    print(f"Plan: charter {'present' if charter.is_file() else 'absent'}, {len(cycles)} cycle(s).")
    for failure in failures:
        print(f"  FAIL {failure}")
    if failures:
        print(f"\n{len(failures)} violation(s). See docs/project/README.md and playbooks/framing.md.")
        return 1
    print("Plan: compliant.")
    return 0
