"""
The charter and the cycles (PDR-0002): every rule proves it fails (P5) and names itself
(P6). Run by platform/tests/run.sh; its helpers are shared with test_pull_request.py.
"""

from __future__ import annotations

import datetime

import pytest
import yaml

from napkinstack.fitness import plan

TODAY = datetime.date.today()
CHARTER = {"status": "accepted", "decider": "@alice",
           "success_criteria": ["Customers receive their invoice the day their order ships"]}


def cycle(start: datetime.date | None = None, weeks: int = 3, **changes) -> dict:
    """An accepted cycle started a week ago, with one ready deliverable; `None` removes a key."""
    start = start or TODAY - datetime.timedelta(days=7)
    data = {"goal": "Customers receive their invoices", "status": "accepted", "appetite_weeks": weeks,
            "start": start.isoformat(), "end": (start + datetime.timedelta(weeks=weeks)).isoformat(),
            "deliverables": [{"id": "D1", "title": "Send an invoice", "module": "login", "state": "ready",
                              "acceptance": ["Given an order, when it ships, then an invoice is sent"]}]}
    for key, value in changes.items():
        if value is None:
            data.pop(key, None)
        else:
            data[key] = value
    return data


def write(root, relative: str, front, body: str = "\n# Document\n") -> None:
    path = root / "docs" / "project" / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    text = front if isinstance(front, str) else "---\n" + yaml.safe_dump(front, sort_keys=False) + "---\n"
    path.write_text(text + body, encoding="utf-8")


def framed(root, charter=CHARTER, cycles: dict | None = None) -> None:
    write(root, "charter.md", charter)
    for name, data in (cycles if cycles is not None else {"01-first.md": cycle()}).items():
        write(root, f"cycles/{name}", data)


def deliverable(**changes) -> dict:
    item = cycle()["deliverables"][0]
    return {key: value for key, value in {**item, **changes}.items() if value is not None}


PLAN_CASES = {
    "C1 no front matter": (lambda r: write(r, "charter.md", "# Charter only"), "C1", True),
    "C1 front matter as a list": (lambda r: write(r, "charter.md", "---\n- a\n---\n"), "C1", True),
    "C2 unknown status": (lambda r: framed(r, {**CHARTER, "status": "draft"}), "C2", True),
    "C2 no decider": (lambda r: framed(r, {**CHARTER, "decider": ""}), "C2", True),
    "C2 no success criterion": (lambda r: framed(r, {**CHARTER, "success_criteria": []}), "C2", True),
    "C2 decider left as the template placeholder": (lambda r: framed(
        r, {**CHARTER, "decider": "@<github-handle>"}), "C2", True),
    "C2 decider not a handle": (lambda r: framed(r, {**CHARTER, "decider": "Fred Smith"}), "C2", True),
    "C2 decider a team, not a person": (lambda r: framed(
        r, {**CHARTER, "decider": "@NapkinStack/maintainers"}), "C2", True),
    "C3 no goal": (lambda r: framed(r, cycles={"01.md": cycle(goal="")}), "C3", True),
    "C3 unknown status": (lambda r: framed(r, cycles={"01.md": cycle(status="running")}), "C3", True),
    "C3 appetite zero": (lambda r: framed(r, cycles={"01.md": cycle(appetite_weeks=0)}), "C3", True),
    "C3 appetite as a boolean": (lambda r: framed(r, cycles={"01.md": cycle(appetite_weeks=True)}), "C3", True),
    "C3 end not set by the appetite": (lambda r: framed(r, cycles={"01.md": cycle(end=TODAY.isoformat())}), "C3", True),
    "C3 start not a date": (lambda r: framed(r, cycles={"01.md": {**cycle(), "start": "soon"}}), "C3", True),
    "C4 no deliverable": (lambda r: framed(r, cycles={"01.md": cycle(deliverables=[])}), "C4", True),
    "C4 invalid id": (lambda r: framed(r, cycles={"01.md": cycle(deliverables=[deliverable(id="X1")])}), "C4", True),
    "C4 id used twice": (lambda r: framed(r, cycles={"01.md": cycle(deliverables=[deliverable(), deliverable()])}), "C4", True),
    "C4 no title": (lambda r: framed(r, cycles={"01.md": cycle(deliverables=[deliverable(title="")])}), "C4", True),
    "C4 unknown state": (lambda r: framed(r, cycles={"01.md": cycle(deliverables=[deliverable(state="wip")])}), "C4", True),
    "C4 ready without criteria": (lambda r: framed(r, cycles={"01.md": cycle(deliverables=[deliverable(acceptance=None)])}), "C4", True),
    "C5 two accepted cycles": (lambda r: framed(r, cycles={"01.md": cycle(), "02.md": cycle()}), "C5", True),
    "C5 accepted cycle, charter proposed": (lambda r: framed(r, {**CHARTER, "status": "proposed"}), "C5", True),
    "C6 closed without outcome": (lambda r: framed(r, cycles={"01.md": cycle(status="closed", ended_on=TODAY.isoformat())}), "C6", True),
    "C6 stopped, outcome of a closed cycle": (lambda r: framed(r, cycles={"01.md": cycle(
        status="stopped", outcome="shipped", ended_on=TODAY.isoformat())}), "C6", True),
    "C6 closed without its date": (lambda r: framed(r, cycles={"01.md": cycle(status="closed", outcome="completed")}), "C6", True),
}


@pytest.mark.parametrize(("prepare", "rule", "fails"), PLAN_CASES.values(), ids=PLAN_CASES.keys())
def test_plan(tmp_path, capsys, prepare, rule, fails):
    prepare(tmp_path)
    code = plan.run(tmp_path)
    output = capsys.readouterr().out
    assert f"[{rule}]" in output, output
    assert code == (1 if fails else 0), output


def test_plan_framed(tmp_path, capsys):
    framed(tmp_path, cycles={"01-first.md": cycle(), "_TEMPLATE.md": "not a cycle",
                             "00-before.md": cycle(status="closed", outcome="completed", ended_on=TODAY.isoformat()),
                             "02-next.md": cycle(status="proposed", deliverables=[deliverable(state="proposed", acceptance=None)])})
    assert plan.run(tmp_path) == 0, capsys.readouterr().out


def test_plan_not_framed_yet(tmp_path, capsys):
    (tmp_path / "docs" / "project" / "cycles").mkdir(parents=True)
    assert plan.run(tmp_path) == 0
    assert "not framed yet" in capsys.readouterr().out


def test_plan_not_applicable(tmp_path, capsys):
    assert plan.run(tmp_path) == 0
    assert "not applicable" in capsys.readouterr().out


@pytest.mark.parametrize("decider", ["@alice", "alice", "@a-l-i-c-e", "a" * 39])
def test_plan_accepts_a_person(tmp_path, capsys, decider):
    """A decision has one owner, named the way GitHub names people (PDR-0004, rule 3)."""
    framed(tmp_path, {**CHARTER, "decider": decider})
    assert plan.run(tmp_path) == 0, capsys.readouterr().out
