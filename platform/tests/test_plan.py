"""
The charter and the cycles (PDR-0002): every rule proves it fails (P5) and names itself
(P6). Run by platform/tests/run.sh; its helpers are shared with test_pull_request.py.
"""

from __future__ import annotations

import datetime
from pathlib import Path

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
    "C2 success criterion left as the template's (D51)": (lambda r: framed(
        r, {**CHARTER, "success_criteria": ["<An observable result, and when it is observed>"]}), "C2", True),
    "C4 title left as the template's (D51)": (lambda r: framed(r, cycles={"01.md": cycle(deliverables=[
        deliverable(title="<An outcome a user can observe; for a spike, the question it answers>")])}), "C4", True),
    "C4 acceptance left as the template's (D51)": (lambda r: framed(r, cycles={"01.md": cycle(deliverables=[
        deliverable(acceptance=["Given <context>, when <action>, then <observable result>"])])}), "C4", True),
}


@pytest.mark.parametrize(("prepare", "rule", "fails"), PLAN_CASES.values(), ids=PLAN_CASES.keys())
def test_plan(tmp_path, capsys, prepare, rule, fails):
    prepare(tmp_path)
    code = plan.run(tmp_path)
    output = capsys.readouterr().out
    assert f"[{rule}]" in output, output
    assert code == (1 if fails else 0), output


def test_a_deliverable_with_no_executable_criterion_is_told_where_it_belongs(tmp_path, capsys):
    """D72. The pilot's D1 was "five private invitations, and we count who acts". C4 asked for
    acceptance criteria; the agent stopped and asked — the rule worked — and the answer, five
    times, was "simulate it". A gate that cannot be paid is paid in counterfeit, and the
    counterfeit is merged and reviewed like the rest.

    The framework already had the right home: a **spike**, whose criteria name what will be
    recorded and the threshold it is read against, and where **a refuted result is a delivered
    one** (05-workflow.md §3, .nstack/playbooks/framing.md). "Nobody acted" was a delivered D1. The door
    existed and the refusal did not mention it, so the rule stays and the message opens it."""
    framed(tmp_path, cycles={"01.md": cycle(deliverables=[deliverable(
        title="The private invitation: five DMs, and we count who acts", acceptance=None)])})
    assert plan.run(tmp_path) == 1
    output = capsys.readouterr().out
    assert "[C4]" in output, output
    assert "knowledge" in output, output            # what such work produces
    assert "spike" in output, output                # the framework's own home for it
    assert "refuted result is a delivered one" in output, output   # what the pilot did not know
    assert "dependency with a date" in output, output              # and what is not a deliverable
    assert "looks like proof" in output, output     # why leaving one door open costs


def test_plan_framed(tmp_path, capsys):
    framed(tmp_path, cycles={"01-first.md": cycle(), "_TEMPLATE.md": "not a cycle",
                             "00-before.md": cycle(status="closed", outcome="completed", ended_on=TODAY.isoformat()),
                             "02-next.md": cycle(status="proposed", deliverables=[deliverable(state="proposed", acceptance=None)])})
    assert plan.run(tmp_path) == 0, capsys.readouterr().out


def test_plan_not_framed_yet(tmp_path, capsys):
    (tmp_path / "docs" / "project" / "cycles").mkdir(parents=True)
    assert plan.run(tmp_path) == 0
    assert "the project is unframed" in capsys.readouterr().out


def test_plan_not_applicable(tmp_path, capsys):
    assert plan.run(tmp_path) == 0
    assert "not applicable" in capsys.readouterr().out


@pytest.mark.parametrize("decider", ["@alice", "alice", "@a-l-i-c-e", "a" * 39])
def test_plan_accepts_a_person(tmp_path, capsys, decider):
    """A decision has one owner, named the way GitHub names people (PDR-0004, rule 3)."""
    framed(tmp_path, {**CHARTER, "decider": decider})
    assert plan.run(tmp_path) == 0, capsys.readouterr().out


@pytest.mark.parametrize("criterion", [
    "The first invoice reaches a customer before 2026-12-31",
    "The 95th percentile stays < 200 ms on launch day",
])
def test_plan_accepts_a_filled_criterion(tmp_path, capsys, criterion):
    """D51: a placeholder opens on a non-space, so a comparison is not one."""
    framed(tmp_path, {**CHARTER, "success_criteria": [criterion]})
    assert plan.run(tmp_path) == 0, capsys.readouterr().out


def skeleton_front_page() -> str:
    return (Path(__file__).resolve().parents[2] / "skeleton/README.md.jinja").read_text(encoding="utf-8")


def test_the_form_s_words_are_the_skeleton_s():
    """C8 reads words, so it must read the ones the skeleton writes: a placeholder reworded in
    the form and not in the rule is a rule that silently stopped refusing anything."""
    written = [line for line in skeleton_front_page().splitlines() if line.startswith("<") and line.endswith(">")]
    assert written and set(written) == set(plan.FRONT_PAGE_FORM), (written, plan.FRONT_PAGE_FORM)


def test_an_accepted_charter_refuses_a_front_page_left_as_its_form(tmp_path, capsys):
    """PDR-0010. Three projects were created and read: on each the front page said nothing of
    the product once the charter had said everything. The charter's acceptance is the first
    moment the front page can be written, and the last moment nobody has an excuse."""
    framed(tmp_path)
    (tmp_path / "README.md").write_text(skeleton_front_page().replace("{{ project_name }}", "Demo"), encoding="utf-8")
    assert plan.run(tmp_path) == 1
    output = capsys.readouterr().out
    assert "[C8] README.md" in output, output
    assert "<One sentence: what this project does.>" in output, output   # it names the words left
    assert ".nstack/handbook/06-decisions.md §10" in output, output               # and where the form is explained


@pytest.mark.parametrize("front_page", [
    None,                                                                  # a project with no README breaks no rule
    "# Demo\n\nNeighbours lend each other tools.\n\n<img src='a.png'>\n",  # an HTML tag is not a form's word
], ids=["no front page", "written, with a tag"])
def test_a_written_or_absent_front_page_is_not_refused(tmp_path, capsys, front_page):
    framed(tmp_path)
    if front_page is not None:
        (tmp_path / "README.md").write_text(front_page, encoding="utf-8")
    assert plan.run(tmp_path) == 0, capsys.readouterr().out


def test_a_proposed_charter_leaves_the_form_alone(tmp_path, capsys):
    """Before the charter is accepted nobody can honestly write what the product is: refusing
    the form then would be asking for the counterfeit C4 already taught us about (D72)."""
    framed(tmp_path, {**CHARTER, "status": "proposed"}, cycles={})
    (tmp_path / "README.md").write_text(skeleton_front_page(), encoding="utf-8")
    assert plan.run(tmp_path) == 0, capsys.readouterr().out


GO = {"decision": "go", "decider": "@alice", "decided_on": "2026-10-01", "challenger": "@bob",
      "idea": "docs/project/inputs/idea.md", "round": 1}
SENTENCE, DIAGRAM, RUN = plan.FRONT_PAGE_FORM
MAP = plan.MODULE_MAP_FORM


def test_a_go_asks_for_the_sentence_and_nothing_more(tmp_path, capsys):
    """A document has its moment. At a go the decider has confirmed for whom and what — one
    sentence — and nothing else: no charter says yet what the product talks to or how it runs.
    Asking for the whole front page here is asking for counterfeit; asking for nothing leaves
    a project that has decided to exist with a front page that says so nowhere."""
    write(tmp_path, "discovery.md", GO)
    (tmp_path / "README.md").write_text(skeleton_front_page(), encoding="utf-8")
    assert plan.run(tmp_path) == 1
    output = capsys.readouterr().out
    assert "[C8] README.md" in output and SENTENCE in output, output
    assert DIAGRAM not in output and RUN not in output, output          # not due yet
    assert "the discovery's decision is go" in output, output            # the event is named
    (tmp_path / "README.md").write_text(skeleton_front_page().replace(SENTENCE, "Neighbours lend tools."),
                                        encoding="utf-8")
    assert plan.run(tmp_path) == 0, capsys.readouterr().out


def test_a_discovery_not_decided_asks_nothing_of_the_front_page(tmp_path, capsys):
    write(tmp_path, "discovery.md", {**GO, "decision": "proposed", "decided_on": None, "challenger": ""})
    (tmp_path / "README.md").write_text(skeleton_front_page(), encoding="utf-8")
    assert plan.run(tmp_path) == 0, capsys.readouterr().out


def test_the_module_map_is_due_with_the_first_module(tmp_path, capsys):
    """The map of the modules cannot be drawn before there is one, and is the first thing a
    newcomer needs once there are two. Read from the repository, never declared — and, like
    every rule on a module, from its first file of code: the scaffolding's output stays green."""
    framed(tmp_path)
    (tmp_path / "modules").mkdir()
    (tmp_path / "modules" / "README.md").write_text(f"# Modules\n\n{MAP}\n", encoding="utf-8")
    assert plan.run(tmp_path) == 0, capsys.readouterr().out             # no module: nothing to draw
    (tmp_path / "modules" / "billing").mkdir()
    (tmp_path / "modules" / "billing" / "MANIFEST.yaml").write_text("name: billing\n", encoding="utf-8")
    assert plan.run(tmp_path) == 0, capsys.readouterr().out             # a scaffold stays green
    (tmp_path / "modules" / "billing" / "src").mkdir()
    (tmp_path / "modules" / "billing" / "src" / "invoice.py").write_text("TOTAL = 0\n", encoding="utf-8")
    assert plan.run(tmp_path) == 1
    output = capsys.readouterr().out
    assert "[C8] modules/README.md" in output and MAP in output, output
    assert "billing" in output, output                                   # the event is named


def test_the_map_s_words_are_the_skeleton_s():
    written = [line for line in (Path(__file__).resolve().parents[2] / "skeleton/modules/README.md")
               .read_text(encoding="utf-8").splitlines() if line.startswith("<") and line.endswith(">")]
    assert written == [plan.MODULE_MAP_FORM], written
