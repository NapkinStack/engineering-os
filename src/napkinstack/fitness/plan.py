"""
Fitness function 4 — The project's charter and cycles (PDR-0002).

A project is framed by a charter and bounded by cycles, written in docs/project/. Their
front matter, a YAML block between two --- lines at the top of the file, is what the
checks read; the prose below it is for humans and agents.

Rules:
  C1  front matter readable: a YAML mapping at the top of the file
  C2  charter: status proposed or accepted, a decider, at least one success criterion
  C3  cycle: a goal, a known status, appetite_weeks, start and end, end = start + appetite
  C4  deliverables: ids D1, D2… unique, a title, a known state, acceptance criteria once ready
  C5  at most one accepted cycle, and only under an accepted charter
  C6  a closed or stopped cycle records its outcome and the date it ended

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

PROJECT = Path("docs") / "project"
CHARTER = PROJECT / "charter.md"
CYCLES = PROJECT / "cycles"
CHARTER_STATUSES = {"proposed", "accepted"}
CYCLE_STATUSES = {"proposed", "accepted", "closed", "stopped"}
DELIVERABLE_STATES = {"proposed", "ready", "in-progress", "accepted", "deferred", "dropped"}
WITHOUT_CRITERIA = {"proposed", "deferred", "dropped"}  # acceptance criteria not required yet
OUTCOMES = {"closed": {"completed", "shipped"}, "stopped": {"reframed", "stopped"}}
DELIVERABLE_ID = re.compile(r"D[1-9][0-9]*")
FRONT_MATTER = re.compile(r"\A---\n(.*?)\n---\n", re.S)


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
    if not str(data.get("decider") or "").strip():
        fail("C2", path, "decider missing: the GitHub handle of the human who validates the charter "
                         "and the cycles, and decides at the circuit breaker")
    criteria = data.get("success_criteria")
    if not isinstance(criteria, list) or not [c for c in criteria if str(c or "").strip()]:
        fail("C2", path, "success_criteria: at least one, they say when the project itself ends")
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
        if not str(item.get("title") or "").strip():
            fail("C4", path, f"deliverable {where}: title missing")
        state = item.get("state")
        if state not in DELIVERABLE_STATES:
            fail("C4", path, f"deliverable {where}: state '{state}', expected one of {sorted(DELIVERABLE_STATES)}")
        criteria = item.get("acceptance")
        filled = isinstance(criteria, list) and [c for c in criteria if str(c or "").strip()]
        if state in DELIVERABLE_STATES - WITHOUT_CRITERIA and not filled:
            fail("C4", path, f"deliverable {where}: state '{state}' requires acceptance criteria — "
                             "the definition of ready, and the source of its test sheet (PDR-0003)")


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


def run(root: Path) -> int:
    failures: list[str] = []

    def fail(rule: str, path: Path, message: str) -> None:
        failures.append(f"[{rule}] {path.relative_to(root)}\n      {message}")

    if not (root / PROJECT).is_dir():
        print(f"Plan: not applicable, no {PROJECT}/ in {root}.")
        return 0
    charter = root / CHARTER
    cycles = cycle_files(root)
    if not charter.is_file() and not cycles:
        print(f"Plan: no charter and no cycle in {PROJECT}/ — the project is not framed yet "
              "(playbooks/framing.md).")
        return 0
    accepted_charter = _check_charter(charter, fail) if charter.is_file() else False
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
