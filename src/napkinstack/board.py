"""
The plan shown on the forge, one way (PDR-0016, ADR-0008).

The cycle files are the plan; this command shows them on GitHub — a milestone per accepted,
closed or stopped cycle, an issue per deliverable — and keeps the display equal to them. Its own
objects carry a marker in their body; an object without one is never touched. What the forge
holds decides nothing but whether the display must be rewritten.

Usage :  nstack board [--root ROOT] [--dry-run]
Output:  0 whatever the forge answers — what was made, changed, restored or not shown is said.
"""

from __future__ import annotations

import datetime
import os
import re
import time
import urllib.parse
from dataclasses import dataclass, field
from pathlib import Path

from napkinstack.fitness import plan
from napkinstack.pull_request import DELIVERABLE

SHOWN = {"accepted", "closed", "stopped"}  # a proposed cycle decides nothing yet
OPEN_STATES = {"proposed", "ready", "in-progress"}
LABEL = "deliverable"
STATE_LABEL = "state: {}"
EDITED_THERE = "Generated from {path}: the plan is edited there, in a pull request — an edit made here is undone."
PACE = 1.0  # seconds between two writes: GitHub's advice for content-creating requests
NUMBER = re.compile(r"^(\d+)")
HEADING = re.compile(r"^#\s+(.+?)\s*$", re.M)


def marker(kind: str, key: str) -> str:
    return f"<!-- nstack:{kind} {key} -->"


MARKER = re.compile(r"<!-- nstack:(cycle|deliverable) (\S+) -->")


@dataclass
class Shown:
    """What the files call for, for one forge object."""

    kind: str  # cycle | deliverable
    key: str  # the cycle's number, or the deliverable's identifier
    title: str
    body: str
    state: str  # open | closed
    reason: str | None = None  # an issue's state_reason when closed
    due: str | None = None  # a milestone's due date, ISO
    cycle: str | None = None  # a deliverable's cycle number
    labels: list[str] = field(default_factory=list)
    assignee: str | None = None
    start: datetime.date | None = None  # a cycle's start: how far back pull requests are read


def _handle(person: str) -> str | None:
    """A GitHub login from a hold's person, when it names one: a handle, or a noreply address."""
    found = re.fullmatch(r"\s*@?([A-Za-z0-9](?:[A-Za-z0-9-]{0,38}))\s*", person)
    if found:
        return found[1]
    noreply = re.search(r"<(?:\d+\+)?([A-Za-z0-9-]+)@users\.noreply\.github\.com>", person)
    return noreply[1] if noreply else None


def _reason(state: str) -> str:
    return "completed" if state == "accepted" else "not_planned"


def desired(root: Path, holders: dict[str, str] | None = None, pulls: dict[str, list[int]] | None = None,
            today: datetime.date | None = None) -> tuple[list[Shown], list[str]]:
    """The display the cycle files call for, and what cannot be shown and why. `holders`:
    deliverable identifier to the hold's person; `pulls`: identifier to the pull requests whose
    description names it."""
    holders, pulls = holders or {}, pulls or {}
    cycles: dict[str, list[tuple[Path, dict]]] = {}
    for path in plan.cycle_files(root):
        data = plan.read_front_matter(path)[0]
        found = NUMBER.match(path.stem)
        if data and data.get("status") in SHOWN and found:
            cycles.setdefault(found[1], []).append((path, data))
    said = [f"cycle {number} not shown: {len(files)} cycle files carry its number "
            f"({', '.join(path.name for path, _ in files)})" for number, files in cycles.items() if len(files) > 1]
    seen: dict[str, list[str]] = {}
    for number, files in cycles.items():
        items = files[0][1].get("deliverables") if len(files) == 1 else None
        for item in items if isinstance(items, list) else []:
            if isinstance(item, dict) and item.get("id"):
                seen.setdefault(str(item["id"]), []).append(number)
    twice = {ident for ident, numbers in seen.items() if len(numbers) > 1}
    said += [f"{ident} not shown: its identifier is used in cycles {', '.join(seen[ident])}" for ident in sorted(twice)]
    shown: list[Shown] = []
    for number, files in sorted(cycles.items()):
        if len(files) > 1:
            continue
        path, data = files[0]
        relative = path.relative_to(root).as_posix()
        closed = data.get("status") != "accepted"
        text = path.read_text(encoding="utf-8", errors="replace")
        front = plan.FRONT_MATTER.match(text)
        heading = HEADING.search(text[front.end():] if front else text)
        title = heading[1] if heading and heading[1].lower().startswith("cycle") else f"Cycle {path.stem}"
        goal = str(data.get("goal") or "").strip()
        end = plan.as_date(data.get("end"))
        shown.append(Shown(
            kind="cycle", key=number, title=title, state="closed" if closed else "open",
            body="\n\n".join(part for part in (goal, plan.progress_of(path, data, today, appetite=False),
                                               EDITED_THERE.format(path=relative), marker("cycle", number)) if part),
            due=str(end) if end else None, start=plan.as_date(data.get("start"))))
        items = data.get("deliverables")
        for item in items if isinstance(items, list) else []:
            if not isinstance(item, dict) or not item.get("id") or str(item["id"]) in twice:
                continue
            ident, state = str(item["id"]), str(item.get("state") or "")
            listed = item.get("acceptance")
            criteria = [f"- [{'x' if state == 'accepted' else ' '}] {line}"
                        for line in (listed if isinstance(listed, list) else [listed] if isinstance(listed, str) else [])
                        if isinstance(line, str)]
            person = holders.get(ident)
            lines = [f"**Module**: `{item.get('module')}`" if item.get("module") else "",
                     f"**State**: {state}" + (f" · **held by** {person}" if person else ""),
                     "**Acceptance criteria**\n\n" + "\n".join(criteria) if criteria else "",
                     "**Pull requests**: " + ", ".join(f"#{n}" for n in pulls.get(ident, [])[:10]) if pulls.get(ident) else "",
                     EDITED_THERE.format(path=relative), marker("deliverable", ident)]
            shut = closed or state not in OPEN_STATES  # a closed cycle's unfinished work closes with it
            shown.append(Shown(
                kind="deliverable", key=ident, title=f"{ident} — {item.get('title') or ident}",
                body="\n\n".join(line for line in lines if line), cycle=number,
                state="closed" if shut else "open", reason=_reason(state) if shut else None,
                labels=[LABEL, STATE_LABEL.format(state)], assignee=_handle(person) if person else None))
    return shown, said


# --- the forge -------------------------------------------------------------------------------

def _pages(forge, path: str, stop=lambda item: False) -> list[dict]:
    """Every object a listing returns, page after page — or until `stop` says the rest is older."""
    from napkinstack.hold import _call

    found, page = [], 1
    while True:
        answer = _call(forge, "GET", f"{path}{'&' if '?' in path else '?'}per_page=100&page={page}")
        if not isinstance(answer, list) or not answer:
            return found
        for item in answer:
            if isinstance(item, dict):
                if stop(item):
                    return found
                found.append(item)
        if len(answer) < 100:
            return found
        page += 1


def _own(objects: list[dict], field_name: str, kind: str) -> dict[str, dict]:
    """The display's own objects, by the key their marker carries; others are never touched."""
    own = {}
    for item in objects:
        found = MARKER.search(str(item.get(field_name) or ""))
        if found and found[1] == kind:
            own.setdefault(found[2], item)
    return own


def _holders(root: Path, idents: list[tuple[str, str]]) -> dict[str, str] | None:
    """The person holding each open deliverable, or None when the holds cannot be read."""
    from napkinstack import hold

    try:
        hold.fetch(root)
    except hold.Unreachable:
        return None
    stems = {NUMBER.match(path.stem)[1]: path.stem for path in plan.cycle_files(root) if NUMBER.match(path.stem)}
    holders = {}
    for number, ident in idents:
        found = hold.read(root, stems.get(number, number), ident)
        if found.held:
            holders[ident] = found.person
    return holders


def _pulls(forge, since: datetime.date | None) -> dict[str, list[int]]:
    """The pull requests whose description names a deliverable, newest first, back to the
    earliest start of a shown cycle — read with the rule K3 reads."""
    def older(item: dict) -> bool:
        created = str(item.get("created_at") or "")[:10]
        return bool(since and created and created < since.isoformat())

    pulls: dict[str, list[int]] = {}
    for item in _pages(forge, "/pulls?state=all&sort=created&direction=desc", older):
        found = DELIVERABLE.search(str(item.get("body") or ""))
        if found and item.get("number"):
            pulls.setdefault(found[1].upper(), []).append(int(item["number"]))
    return pulls


def _clean(text) -> str:
    return "\n".join(line.rstrip() for line in str(text or "").replace("\r\n", "\n").strip().split("\n"))


def run(root: Path, dry_run: bool = False, today: datetime.date | None = None) -> int:
    from napkinstack import hold

    first, said = desired(root, today=today)
    if not first:
        _tell(said, "Plan on the forge: nothing to show — no accepted, closed or stopped cycle")
        return 0
    forge = hold._forge(root, hold.remote(root))
    if forge is None:
        _tell(["not shown: no GitHub remote, or no token"], "Plan on the forge")
        return 0
    lines = list(said)
    try:
        open_ones = [(item.cycle, item.key) for item in first if item.kind == "deliverable" and item.state == "open"]
        holders = _holders(root, open_ones)
        if holders is None:
            lines.append("holders not shown: the holds cannot be read — assignees left as they are")
        starts = [item.start for item in first if item.kind == "cycle" and item.start]
        shown, _ = desired(root, holders or {}, _pulls(forge, min(starts) if starts else None), today)
        milestones = _pages(forge, "/milestones?state=all")
        # Every issue, not those carrying the label: a label removed by hand leaves the marker.
        issues = [item for item in _pages(forge, "/issues?state=all") if "pull_request" not in item]
        lines += _apply(forge, shown, milestones, issues, dry_run, keep_assignees=holders is None)
    except hold.Refused as error:
        limited = re.search(r"HTTP 429|rate limit", str(error), re.I)
        lines.append(f"not shown further: {error}" + (" — partially shown, the rest at the next run" if limited else ""))
    except Exception as error:  # an answer nobody foresaw: said, never a failed merge
        lines.append(f"not shown further: {type(error).__name__}: {error}")
    _tell(lines, f"Plan on the forge ({forge[1]})" + (" — dry run, nothing applied" if dry_run else ""))
    return 0


def _tell(lines: list[str], head: str) -> None:
    """Said in the output; in GitHub Actions, also in the job's summary, and what was not shown as
    a warning a person sees on the run."""
    print(f"{head}:")
    print("\n".join(f"  {line}" for line in lines) or "  in step with the cycle files: nothing to change")
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as out:
            out.write(f"### {head}\n\n" + ("\n".join(f"- {line}" for line in lines) or "In step: nothing to change.") + "\n")
    if os.environ.get("GITHUB_ACTIONS") == "true":
        for line in lines:
            if "not shown" in line:
                print(f"::warning title=Plan on the forge::{line}")


def _apply(forge, shown: list[Shown], milestones: list[dict], issues: list[dict], dry_run: bool,
           keep_assignees: bool = False) -> list[str]:
    from napkinstack.hold import Refused, _call

    said: list[str] = []

    def call(*args):
        if dry_run:
            return {}
        answer = _call(forge, *args)
        time.sleep(PACE)
        return answer

    own_milestones, own_issues = _own(milestones, "description", "cycle"), _own(issues, "body", "deliverable")
    foreign_titles = {item.get("title") for item in milestones if not MARKER.search(str(item.get("description") or ""))}
    present = {str(label.get("name") or "").lower() for label in _pages(forge, "/labels")}  # one name, any case
    for name in sorted(label for label in {label for item in shown for label in item.labels} if label.lower() not in present):
        call("POST", "/labels", {"name": name, "color": "1d76db" if name == LABEL else "c5def5",
                                 "description": "Shown from the cycle files by nstack board"})
        said.append(f"made label {name}")

    numbers: dict[str, int | None] = {}
    for item in (entry for entry in shown if entry.kind == "cycle"):
        # Noon, UTC: GitHub keeps a due date as midnight, Pacific time, of the day it receives —
        # sent at midnight UTC, it would read the day before.
        want = {"title": item.title, "description": item.body, "state": item.state,
                **({"due_on": f"{item.due}T12:00:00Z"} if item.due else {})}
        have = own_milestones.get(item.key)
        if have is None:
            if item.title in foreign_titles:
                said.append(f"cycle {item.key} not shown: a milestone titled '{item.title}' exists that the display "
                            "did not make — rename it, or put the marker back")
                numbers[item.key] = None
                continue
            made = call("POST", "/milestones", want)
            numbers[item.key] = made.get("number") if isinstance(made, dict) else None
            said.append(f"made milestone {item.title}")
            continue
        numbers[item.key] = have.get("number")
        if not have.get("number"):
            continue
        changed = [name for name in ("title", "state") if have.get(name) != want[name]]
        if _clean(have.get("description")) != _clean(want["description"]):
            changed.append("description")
        if item.due and str(have.get("due_on") or "")[:10] != item.due:
            changed.append("due date")
        if changed:
            call("PATCH", f"/milestones/{have['number']}", want)
            said.append(f"restored milestone {item.title}: {', '.join(changed)} — the plan is edited in the cycle file")
        ours = sum(1 for issue in own_issues.values()
                   if isinstance(issue.get("milestone"), dict) and issue["milestone"].get("number") == have.get("number"))
        theirs = int(have.get("open_issues") or 0) + int(have.get("closed_issues") or 0) - ours
        if theirs > 0:
            said.append(f"{theirs} item(s) in {item.title} not from the plan: GitHub's bar counts them, the "
                        "description's line does not")

    assignable: dict[str, bool] = {}

    def can_assign(login: str) -> bool:
        if login not in assignable:
            try:
                _call(forge, "GET", f"/assignees/{urllib.parse.quote(login)}")
                assignable[login] = True
            except Refused:
                assignable[login] = False
        return assignable[login]

    for item in (entry for entry in shown if entry.kind == "deliverable"):
        have = own_issues.get(item.key)
        if have is not None and not have.get("number"):
            continue
        assignees = [item.assignee] if item.assignee and can_assign(item.assignee) else []
        if keep_assignees and have is not None:
            assignees = sorted(a.get("login") for a in have.get("assignees") or [] if isinstance(a, dict))
        want = {"title": item.title, "body": item.body, "labels": item.labels,
                "milestone": numbers.get(item.cycle), "assignees": assignees}
        if have is None:
            made = call("POST", "/issues", want)
            if item.state == "closed" and isinstance(made, dict) and made.get("number"):
                call("PATCH", f"/issues/{made['number']}", {"state": "closed", "state_reason": item.reason})
            said.append(f"made issue {item.title}")
            continue
        changed = ["title"] if have.get("title") != want["title"] else []
        if _clean(have.get("body")) != _clean(want["body"]):
            changed.append("body")
        if ({str(label.get("name") or "").lower() for label in have.get("labels") or [] if isinstance(label, dict)}
                != {label.lower() for label in item.labels}):
            changed.append("labels")
        milestone = have.get("milestone")
        if (milestone.get("number") if isinstance(milestone, dict) else None) != want["milestone"]:
            changed.append("milestone")
        if {a.get("login") for a in have.get("assignees") or [] if isinstance(a, dict)} != set(assignees):
            changed.append("assignees")
        if have.get("state") != item.state:
            changed.append("state")
            want.update(state=item.state, state_reason=item.reason or "reopened")
        elif item.state == "closed" and have.get("state_reason") != item.reason:
            changed.append("state reason")
            want.update(state="closed", state_reason=item.reason)
        if changed:
            call("PATCH", f"/issues/{have['number']}", want)
            said.append(f"restored issue {item.title}: {', '.join(changed)}")

    wanted = {item.key for item in shown if item.kind == "deliverable"}
    for key, have in own_issues.items():
        if key not in wanted and have.get("state") == "open" and have.get("number"):
            call("PATCH", f"/issues/{have['number']}", {"state": "closed", "state_reason": "not_planned"})
            said.append(f"closed issue {have.get('title')}: its deliverable is no longer in a shown cycle")
    return said
