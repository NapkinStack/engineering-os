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
  C6  a closed or stopped cycle records its outcome and the date it ended, and may record the
      charter's success criteria it moved: each by its number, met or observing since a day
  C7  discovery: a known decision, its decider and date once decided, a challenger for a go;
      a charter follows a go
  C8  a seat is written when its moment comes: README.md holds its sentence once the
      discovery's decision is go, and none of its form's words once the charter is accepted;
      modules/README.md none of its own once a module holds more than its description
  C10 (a warning) a closure reads the decisions whose criterion is due: an accepted record of
      docs/pdr/ or docs/adr/ whose success criterion names a closed or stopped cycle, or a date
      its end has reached, says so in a reading line (PDR-0020)

Templates, whose file name starts with "_", are not checked. `nstack plan` then says the project
across its cycles (`project`), a display that never fails.

Usage :  nstack plan [--root ROOT]
Output:  0 when the charter and the cycles are valid, or absent; 1 otherwise.
A root without docs/project/, such as the NapkinStack repository itself, is out of scope.
"""

from __future__ import annotations

import datetime
import re
from pathlib import Path

import yaml

from napkinstack.fitness.manifests import module_content, unfilled
from napkinstack.modules import HANDLE

PROJECT = Path("docs") / "project"
CHARTER = PROJECT / "charter.md"
CYCLES = PROJECT / "cycles"
DISCOVERY = PROJECT / "discovery.md"
FRONT_PAGE = Path("README.md")
# The words the skeleton writes where the project's go (skeleton/README.md.jinja; a test binds
# the two). Exact lines, never a pattern: a front page may hold any tag or any <argument>.
FRONT_PAGE_FORM = (
    "<One sentence: what this project does.>",
    "<A diagram of the product, with its legend: who uses it, what it does for them, what it talks to. "
    "Then three lines at most.>",
    "<How to start it and see it work, from a fresh clone.>",
)
MODULE_MAP = Path("modules") / "README.md"
MODULE_MAP_FORM = "<A diagram of this project's modules and the contracts between them, with its legend.>"
DECISIONS = {"proposed", "go", "clarify", "kill"}
CHARTER_STATUSES = {"proposed", "accepted"}
CYCLE_STATUSES = {"proposed", "accepted", "closed", "stopped"}
DELIVERABLE_STATES = {"proposed", "ready", "in-progress", "accepted", "deferred", "dropped"}
WITHOUT_CRITERIA = {"proposed", "deferred", "dropped"}  # acceptance criteria not required yet
OUTCOMES = {"closed": {"completed", "shipped"}, "stopped": {"reframed", "stopped"}}
SUCCESS_STATES = {"met", "observing"}  # a criterion never recorded is not yet (PDR-0019)
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
    """The front matter as a mapping, or None and the reason it cannot be read (C1). A file that
    is not UTF-8, or a date no calendar holds — YAML builds it and Python refuses it — is a reason
    like the others, never a traceback (#268)."""
    try:
        match = FRONT_MATTER.match(path.read_text(encoding="utf-8"))
    except UnicodeDecodeError as exc:
        return None, f"not UTF-8 text: {exc.reason} at byte {exc.start}; save the file as UTF-8"
    if not match:
        return None, "no front matter: the file must start with a YAML block between two --- lines"
    try:
        data = yaml.safe_load(match[1])
    except yaml.YAMLError as exc:
        return None, f"front matter unreadable: {exc}"
    except ValueError as exc:
        return None, f"front matter unreadable: a date that does not exist ({exc}); dates are YYYY-MM-DD"
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


def one_of(value, choices) -> bool:
    """A front matter's value among the words a rule knows. A list or a mapping is none of them,
    and never a traceback: `in` alone fails on a value it cannot hash."""
    return isinstance(value, str) and value in choices


def cycle_files(root: Path) -> list[Path]:
    folder = root / CYCLES
    return sorted(p for p in folder.glob("*.md") if not p.name.startswith("_")) if folder.is_dir() else []


FRAMED, UNFRAMED, UNREADABLE = "framed", "unframed", "unreadable"


def stage(root: Path) -> str | None:
    """Where a project stands, read from its tracked files and never declared: framed once its
    charter is accepted, unframed before — a stage, not a violation. A charter that cannot be
    read is neither: nothing is assumed from a file nobody can parse. None outside a project."""
    if not (root / PROJECT).is_dir() and not (root / ".copier-answers.yml").is_file():
        return None
    path = root / CHARTER
    if not path.is_file():
        return UNFRAMED
    data = read_front_matter(path)[0]
    if data is None:
        return UNREADABLE
    return FRAMED if data.get("status") == "accepted" else UNFRAMED


def stage_line(root: Path) -> str | None:
    """What every judging run says of the project's stage, beside the framework that judges.
    A framed project is never told the other word."""
    return {
        UNFRAMED: "Project unframed — no accepted charter: the cycle rules (K1 to K3, K5) do not apply "
                  "here, every other rule does.",
        FRAMED: "Project framed — the cycle rules (K1 to K3, K5) apply.",
        UNREADABLE: f"Project stage unknown — {CHARTER} cannot be read (C1): nothing is assumed.",
    }.get(stage(root) or "")


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


PROGRESS = (("accepted", "accepted"), ("in-progress", "in progress"), ("ready", "ready"),
            ("proposed", "proposed"), ("deferred", "deferred"))  # dropped: out of the count


def progress(root: Path, today: datetime.date | None = None) -> str | None:
    """The accepted cycle in one line, read from its front matter and never written down:
    deliverables by state — a dropped one counts in nothing — and where the cycle stands in its
    appetite (#219). None when no cycle is accepted."""
    cycle = accepted_cycle(root)
    return None if cycle is None else progress_of(*cycle, today=today)


def progress_of(path: Path, data: dict, today: datetime.date | None = None, appetite: bool = True) -> str:
    """One cycle's line, accepted or not: what `progress` says. Without the appetite — the
    day and the days left, which change every day — it is what the forge's display repeats
    (ADR-0008)."""
    items = data.get("deliverables")
    states = [item.get("state") for item in (items if isinstance(items, list) else []) if isinstance(item, dict)]
    counted = [state for state in states if state != "dropped"]
    said = [f"{states.count('accepted')} of {len(counted)} accepted"]
    said += [f"{counted.count(state)} {name}" for state, name in PROGRESS[1:] if counted.count(state)]
    other = len(counted) - sum(counted.count(state) for state, _ in PROGRESS)
    said += [f"{other} other"] if other else []
    today = today or datetime.date.today()
    start, end = as_date(data.get("start")), as_date(data.get("end"))

    def days(count: int) -> str:
        return f"{count} day" + ("" if count == 1 else "s")

    if start and end and appetite:
        if today < start:
            said.append(f"starts in {days((start - today).days)} ({start})")
        elif today >= end:  # the first day the cycle is over (the cycle form), as K2 reads it
            said.append(f"ended on {end}, {days((today - end).days)} ago — the circuit breaker: the decider chooses")
        else:
            said.append(f"day {(today - start).days + 1} of {(end - start).days}, {(end - today).days} left (ends {end})")
    return f"Cycle {path.stem}: " + " · ".join(said)


LATER = re.compile(r"^## Later[ \t]*\n(.*?)(?=^## |\Z)", re.S | re.M)
# The words the cycle form writes under *Later* (.nstack/forms/cycle.md; a test binds the two).
LATER_FORM = "<Candidates for the next framing: what framing left out, and ideas that came up during the cycle.>"
ITEM = re.compile(r"^(?:[-*+]|\d+[.)])\s", re.M)  # a top-level item: one candidate each


def _cycle_said(path: Path, data: dict | None) -> str:
    """One cycle of the project's history: its status, the date that matters for it, and its
    deliverables as `progress_of` counts them — one figure, wherever it is said. What its own
    rules refuse (C3, C6) is said plainly, never as a value printed raw."""
    if data is None:
        return "front matter unreadable (C1)"
    status, counts = data.get("status"), progress_of(path, data, appetite=False).split(": ", 1)[1]
    if not one_of(status, CYCLE_STATUSES):
        return f"status unknown (C3) · {counts}"
    if status in OUTCOMES:
        ended = as_date(data.get("ended_on"))
        outcome = data.get("outcome") if one_of(data.get("outcome"), OUTCOMES[status]) else "outcome unknown (C6)"
        return f"{status} ({outcome})" + (f" on {ended}" if ended else "") + f" · {counts}"
    key, said = ("end", "in progress, ends") if status == "accepted" else ("start", "proposed, starts")
    date = as_date(data.get(key))
    return (f"{said} {date}" if date else said.split(",")[0]) + f" · {counts}"


def _later(path: Path) -> str | None:
    """What the cycle's *Later* holds for the next framing: its candidates counted when the
    section is a list — an item each, its wrapped lines with it —, said as prose otherwise,
    nothing when the section is absent or still the form's."""
    match = LATER.search(path.read_text(encoding="utf-8", errors="replace"))
    text = " ".join(match[1].split()) if match else ""  # the form wraps its line
    if not text or text == LATER_FORM:
        return None
    lines = [line for line in match[1].splitlines() if line.strip()]
    count = len(ITEM.findall(match[1]))
    prose = any(not ITEM.match(line) and not line[:1].isspace() for line in lines)
    held = f"{count} candidate" + ("" if count == 1 else "s")
    held = (f"{held} listed, and prose" if count else "candidates written as prose") if prose else held
    return f"Later in {path.stem}, for the next framing: {held}"


def criteria(root: Path) -> list[int] | None:
    """The numbers of the charter's success criteria, from 1 in the order it lists them, that
    are filled in — the template's example left among them is listed and never counted, so the
    charter's goal can be reached without declaring it met; None when no charter can be read."""
    path = root / CHARTER
    data = read_front_matter(path)[0] if path.is_file() else None
    listed = data.get("success_criteria") if data else None
    return [n for n, c in enumerate(listed, start=1) if not unfilled(c)] if isinstance(listed, list) else None


def _record(record) -> tuple[int, str, datetime.date | None] | None:
    """One success record as the view reads it and C6 accepts it: a mapping, its criterion a
    number from 1, its state known, a day when it is observed. None otherwise."""
    if not isinstance(record, dict):
        return None
    number, state, since = record.get("criterion"), record.get("state"), as_date(record.get("since"))
    if isinstance(number, bool) or not isinstance(number, int) or number < 1 or not one_of(state, SUCCESS_STATES):
        return None
    return None if state == "observing" and since is None else (number, state, since)


def success(read: list[tuple[Path, dict | None]]) -> dict[int, tuple[str, datetime.date | None]]:
    """Each criterion's state: its latest record, in the order of the cycles — a later closure
    may record a criterion met again as observing (PDR-0019). Only closures record."""
    states: dict[int, tuple[str, datetime.date | None]] = {}
    for _, data in read:
        records = data.get("success") if data and one_of(data.get("status"), OUTCOMES) else None
        for found in map(_record, records if isinstance(records, list) else []):
            if found:
                states[found[0]] = found[1:]
    return states


def _success_said(numbers: list[int], states: dict[int, tuple[str, datetime.date | None]]) -> str:
    """The project's own progress: the criteria met, then each one observed and since when."""
    met = sum(1 for number in numbers if states.get(number, ("",))[0] == "met")
    said = f"{met} of {len(numbers)} success criteri{'on' if len(numbers) == 1 else 'a'} met"
    if numbers and met == len(numbers):
        return said + " — the charter's goal is reached: the decider says whether the project is finished"
    observed = [f"criterion {number} observed since {states[number][1]}"
                for number in numbers if states.get(number, ("",))[0] == "observing"]
    return " · ".join([said, *observed]) if observed or states else said + ", recorded at each cycle's closure"


def project(root: Path) -> list[str]:
    """The project across its cycles, for `nstack plan`: the charter's success criteria counted,
    every cycle in one line, and what the latest cycle left for the next framing — read from the
    files, never written down. Deliverables are not summed across cycles: a deliverable deferred
    by one cycle is often framed again in the next, and a total would count it twice. Nothing
    outside a project, or before a charter or a cycle exists."""
    charter, cycles = root / CHARTER, cycle_files(root)
    if stage(root) is None or (not charter.is_file() and not cycles):
        return []
    data = read_front_matter(charter)[0] if charter.is_file() else None
    read = [(path, read_front_matter(path)[0]) for path in cycles]
    if data is None:
        head = "no charter readable" if charter.is_file() else "no charter"
    elif data.get("status") == "accepted":
        head = _success_said(criteria(root) or [], success(read))
    else:
        head = "the charter is proposed" if data.get("status") == "proposed" else "the charter's status unknown (C2)"
    statuses = [data.get("status") if data else None for _, data in read]
    known = ("accepted", "proposed", "closed", "stopped")
    tally = [f"{statuses.count(s)} {s}" for s in known if statuses.count(s)]
    other = len(statuses) - sum(statuses.count(s) for s in known)
    tally += [f"{other} other"] if other else []
    lines = [f"Project: {head} · {len(read)} cycle{'' if len(read) == 1 else 's'}"
             + (f": {', '.join(tally)}" if tally else "")]
    width = max(len(path.stem) for path in cycles) if cycles else 0
    lines += [f"  {path.stem.ljust(width)}  {_cycle_said(path, data)}" for path, data in read]
    # The cycle running, else the last one ended — where the next framing starts —, else the last.
    ended = [path for path, data in read if data and one_of(data.get("status"), OUTCOMES)]
    latest = next((path for path, data in read if data and data.get("status") == "accepted"),
                  ended[-1] if ended else (cycles[-1] if cycles else None))
    if latest and (later := _later(latest)):
        lines.append(f"  {later}")
    return lines


def show(root: Path) -> int:
    """`nstack plan`'s view of the project: said, never a failure of its own — a file the plan's
    checks cannot read stops them first."""
    if lines := project(root):
        print("\n" + "\n".join(lines))
    return 0


def _left(path: Path, form: tuple[str, ...]) -> list[str]:
    """The words of `form` a seat still holds, as whole lines: a page may hold any tag."""
    lines = {line.strip() for line in path.read_text(encoding="utf-8", errors="replace").splitlines()}
    return [words for words in form if words in lines]


def _check_seats(root: Path, decision: str | None, accepted_charter: bool, fail) -> None:
    """C8: each seat has the event that makes it writable, read from the repository. Before
    it, the form stays a form and nothing is asked; after it, a form left as it came says
    nothing to whoever opens the project."""
    where = "What each document holds, and when it is written: .nstack/handbook/06-decisions.md §10."
    front = root / FRONT_PAGE
    if front.is_file() and (accepted_charter or decision == "go"):
        if accepted_charter:
            due, event = FRONT_PAGE_FORM, "the charter is accepted"
            action = "write them from the charter, in the pull request that accepts it (.nstack/playbooks/framing.md)"
        else:
            due, event = FRONT_PAGE_FORM[:1], "the discovery's decision is go"
            action = ("write the sentence the decider confirmed, in the pull request that records the "
                      "decision (.nstack/playbooks/discovery.md); the rest of the page waits for the charter")
        if left := _left(front, due):
            quoted = "\n      ".join(f'"{words}"' for words in left)
            fail("C8", front, f"{event} and the front page still holds its form's words:\n"
                              f"      {quoted}\n      Action: {action}. {where}")
    module_map = root / MODULE_MAP
    # Like every rule on a module, from its first file of code: what the scaffolding writes
    # stays green, so creating a module never turns a project red by itself.
    modules = sorted(path.parent.name for path in (root / "modules").glob("*/MANIFEST.yaml")
                     if module_content(path.parent))
    if modules and module_map.is_file() and _left(module_map, (MODULE_MAP_FORM,)):
        named = ", ".join(modules[:3]) + (f" and {len(modules) - 3} more" if len(modules) > 3 else "")
        fail("C8", module_map, f"the project has modules holding code ({named}) and its module map still holds its "
                               f"form's words:\n      \"{MODULE_MAP_FORM}\"\n      Action: draw the modules "
                               "and the contracts between them, in the pull request that brings a "
                               f"module its first code. {where}")


def _check_charter(path: Path, fail) -> bool:
    data, reason = read_front_matter(path)
    if data is None:
        fail("C1", path, reason)
        return False
    if not one_of(data.get("status"), CHARTER_STATUSES):
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
        if not one_of(state, DELIVERABLE_STATES):
            fail("C4", path, f"deliverable {where}: state '{state}', expected one of {sorted(DELIVERABLE_STATES)}")
        criteria = item.get("acceptance")
        filled = isinstance(criteria, list) and [c for c in criteria if not unfilled(c)]
        if one_of(state, DELIVERABLE_STATES - WITHOUT_CRITERIA) and not filled:
            # The criteria are right, and the refusal names the door the framework already had.
            # Work whose product is knowledge is a SPIKE: its criteria name what will be recorded
            # and the threshold it is read against, and a refuted result is a delivered one. The
            # pilot did not know that and answered a criterion it could not meet with five
            # simulated proofs, merged and reviewed like the rest (D72). The door existed; the
            # refusal did not mention it.
            fail("C4", path, f"deliverable {where}: state '{state}' requires acceptance criteria "
                             "filled in — the definition of ready, and the source of its test "
                             "sheet.\n      Action: write them, or make it a spike. "
                             "A deliverable whose product is knowledge — a probe, interviews, a "
                             "legal question — names what will be recorded and the threshold it "
                             "is read against, and a refuted result is a delivered one "
                             "(.nstack/playbooks/framing.md, .nstack/handbook/05-workflow.md §3).\n      What has "
                             "no criterion at all, because it waits on someone outside the "
                             "project, is a dependency with a date and not a deliverable. A "
                             "criterion nobody can meet gets met with something that looks like "
                             "proof.")


def _check_success(path: Path, data: dict, status, numbers: list[int] | None, fail) -> None:
    """C6: the criteria a closure moved, each by its number in the charter's list (PDR-0019)."""
    records = data.get("success")
    if records is None:
        return
    action = ("Action: name each criterion by its number in docs/project/charter.md, from 1, as met, or as "
              "observing with since: YYYY-MM-DD, the day observation started (.nstack/playbooks/framing.md, "
              "the end of a cycle)")
    if not one_of(status, OUTCOMES):
        fail("C6", path, f"success: recorded by a cycle that is {status or 'of no known status'}, not closed "
                         "or stopped — a criterion moves at a closure, when the decider says so. Action: "
                         "record it in the closure's pull request, with status and outcome")
        return
    if not isinstance(records, list):
        fail("C6", path, f"success: a list of records, one per criterion moved. {action}")
        return
    seen: set[int] = set()
    for index, record in enumerate(records, start=1):
        where = f"success record no. {index}"
        if not isinstance(record, dict):
            fail("C6", path, f"{where}: expected a mapping (criterion, state, since). {action}")
            continue
        number, state = record.get("criterion"), record.get("state")
        if isinstance(number, bool) or not isinstance(number, int) or number < 1:
            fail("C6", path, f"{where}: criterion '{number}', expected a number from 1. {action}")
        elif number in seen:
            fail("C6", path, f"{where}: criterion {number} recorded twice in this closure — keep the one "
                             "the decider said")
        elif numbers is not None and number not in numbers:
            fail("C6", path, f"{where}: criterion {number}, and the charter's filled criteria are numbered "
                             f"{', '.join(map(str, numbers)) or 'nothing'}. If a decision changed the charter's "
                             "list, renumber this record to match it, or remove it, with that decision")
        if isinstance(number, int):
            seen.add(number)
        if not one_of(state, SUCCESS_STATES):
            fail("C6", path, f"{where}: state '{state}', expected one of {sorted(SUCCESS_STATES)}. {action}")
        elif state == "observing" and as_date(record.get("since")) is None:
            fail("C6", path, f"{where}: observing since when? {action}")


def _check_cycle(path: Path, fail, numbers: list[int] | None = None) -> str | None:
    data, reason = read_front_matter(path)
    if data is None:
        fail("C1", path, reason)
        return None
    if not str(data.get("goal") or "").strip():
        fail("C3", path, "goal missing: one sentence")
    status = data.get("status")
    if not one_of(status, CYCLE_STATUSES):
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
    if one_of(status, OUTCOMES):
        if not one_of(data.get("outcome"), OUTCOMES[status]):
            fail("C6", path, f"a {status} cycle records its outcome: one of {sorted(OUTCOMES[status])}")
        if as_date(data.get("ended_on")) is None:
            fail("C6", path, f"a {status} cycle records ended_on, the date it ended")
    _check_success(path, data, status, numbers, fail)
    return status if isinstance(status, str) else None


def _check_discovery(path: Path, fail) -> str | None:
    data, reason = read_front_matter(path)
    if data is None:
        fail("C1", path, reason)
        return None
    decision = data.get("decision")
    if not one_of(decision, DECISIONS):
        fail("C7", path, f"decision '{decision}': expected one of {sorted(DECISIONS)}")
    elif decision != "proposed":
        check_decider("C7", path, data.get("decider"), fail)
        if as_date(data.get("decided_on")) is None:
            fail("C7", path, f"a decision ({decision}) records decided_on, YYYY-MM-DD")
        if decision == "go" and unfilled(data.get("challenger")):
            fail("C7", path, "a go names its challenger: another session, or a human, challenged the "
                             "document first (.nstack/playbooks/discovery.md, stage 5)")
    return decision if isinstance(decision, str) else None


RECORDS = (Path("docs") / "pdr", Path("docs") / "adr")
CRITERION = re.compile(r"^## Success criterion[^\n]*\n(.*?)(?=^## |\Z)", re.S | re.M)
READING = re.compile(r"Read at `?(.+?)`?'s closure, (\d{4}-\d{2}-\d{2}): (?:met|missed|superseded)\b", re.I)
DAY = re.compile(r"(?<![\d-])\d{4}-\d{2}-\d{2}(?![\d-])")
NUMBERED = re.compile(r"\bcycle\s+0*(\d+)\b", re.I)
HEADER = re.compile(r"^[-*\s]*\**(Status|Date)\**\s*:\**\s*(\S+)", re.M | re.I)


def _names(text: str, stem: str) -> bool:
    """Whether `text` names the cycle of file `stem`: by its file (`03-the-window`), or as `cycle 03`."""
    number = re.match(r"\d+", stem)
    return bool(re.search(rf"(?<![\w-]){re.escape(stem)}(?![\w-])", text)
                or number and int(number[0]) in {int(n) for n in NUMBERED.findall(text)})


def _due(root: Path, read: list[tuple[Path, dict | None]]) -> list[str]:
    """C10: each accepted decision record whose success criterion is due at a closure and says no
    reading of it (PDR-0020). Only the criterion section is read: a cycle named by its file or as
    *cycle NN*, a date written YYYY-MM-DD. A named cycle is due at its closure; a date at the first
    closure that reaches it — read once, a later date waits for a later closure, and a reading on or
    after a date answers it, even at a cycle that stopped before it. A closure before the record's own
    date is not one it could be read at. Said, never refused."""
    closures = sorted(((ended, path.stem) for path, data in read
                       if data and one_of(data.get("status"), OUTCOMES)
                       and (ended := as_date(data.get("ended_on")))))
    if not closures:
        return []
    said = []
    for path in sorted(p for folder in RECORDS if (root / folder).is_dir()
                       for p in (root / folder).glob("*.md")
                       if p.is_file() and p.name != "README.md" and not p.name.startswith("_")):
        text = path.read_text(encoding="utf-8", errors="replace")
        header = {key.lower(): value.strip("*,.") for key, value in HEADER.findall(text.split("\n## ", 1)[0])}
        section = CRITERION.search(text)
        if header.get("status", "").lower() != "accepted" or not section:
            continue
        criterion = re.sub(r"<!--.*?-->", "", section[1], flags=re.S)
        readings = [(name, day) for name, on in READING.findall(criterion) if (day := as_date(on))]
        criterion = "\n".join(line for line in criterion.splitlines() if not READING.search(line))
        since = as_date(header.get("date", ""))
        open_ = [(ended, stem) for ended, stem in closures if since is None or ended >= since]
        due = {closure for closure in open_ if _names(criterion, closure[1])}
        for day in filter(None, map(as_date, DAY.findall(criterion))):
            # A reading on or after the date has seen it pass, at whichever closure it was written.
            reached = next((closure for closure in open_ if closure[0] >= day), None)
            if reached and not any(on >= day for _, on in readings):
                due.add(reached)
        for ended, stem in sorted(due):
            if not any(_names(name, stem) and on >= ended for name, on in readings):
                said.append(f"[C10] {path.relative_to(root)}\n      its success criterion is due at {stem}'s "
                            f"closure ({ended}), and holds no line saying it was read.\n      Action: read it, and "
                            f"write in its success criterion: \"Read at {stem}'s closure, <YYYY-MM-DD>: met | "
                            "missed | superseded\" — a missed one is the decider's to answer, by a decision of its "
                            "own (.nstack/playbooks/framing.md, Decisions).")
    return said


def run(root: Path) -> int:
    failures: list[str] = []

    def fail(rule: str, path: Path, message: str) -> None:
        failures.append(f"[{rule}] {path.relative_to(root)}\n      {message}")

    if not (root / PROJECT).is_dir() and not (root / ".copier-answers.yml").is_file():
        print(f"Plan: not applicable, no {PROJECT}/ in {root}.")
        return 0
    charter = root / CHARTER
    discovery = root / DISCOVERY
    cycles = cycle_files(root)
    decision = _check_discovery(discovery, fail) if discovery.is_file() else None
    accepted_charter = _check_charter(charter, fail) if charter.is_file() else False
    _check_seats(root, decision, accepted_charter, fail)
    if not charter.is_file() and not cycles and not discovery.is_file() and not failures:
        print(f"Plan: no charter and no cycle in {PROJECT}/ — the project is unframed, which is a "
              "stage and not a fault (.nstack/playbooks/framing.md).")
        return 0
    if accepted_charter and discovery.is_file() and decision != "go":
        fail("C7", charter, f"the charter is accepted, but the discovery's decision is '{decision}': "
                            "a charter follows a go (docs/project/discovery.md)")
    numbers = criteria(root)
    accepted = [path for path in cycles if _check_cycle(path, fail, numbers) == "accepted"]
    if len(accepted) > 1:
        names = ", ".join(path.name for path in accepted)
        fail("C5", root / CYCLES, f"{len(accepted)} accepted cycles ({names}): one cycle at a time — "
                                  "close or stop the others")
    if accepted and not accepted_charter:
        fail("C5", accepted[0], "an accepted cycle requires an accepted charter "
                                f"({CHARTER}, status: accepted)")

    print(f"Plan: charter {'present' if charter.is_file() else 'absent'}, {len(cycles)} cycle(s).")
    if len(accepted) == 1 and accepted_charter:
        print(progress(root))
    for warning in _due(root, [(path, read_front_matter(path)[0]) for path in cycles]):
        print(f"  WARNING {warning}")
    for failure in failures:
        print(f"  FAIL {failure}")
    if failures:
        print(f"\n{len(failures)} violation(s). See .nstack/handbook/project.md and .nstack/playbooks/framing.md.")
        return 1
    print("Plan: compliant.")
    return 0
