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


# --- D138: a cycle's progress in one line (#219) --------------------------------------------

def progress_cycle(start, weeks=3, states=("accepted", "accepted", "in-progress", "ready", "dropped")):
    return cycle(start=start, weeks=weeks, deliverables=[deliverable(id=f"D{n}", state=state)
                                                         for n, state in enumerate(states, 1)])


def test_the_accepted_cycle_says_its_progress_in_one_line(tmp_path, capsys):
    framed(tmp_path, cycles={"03-the-window.md": progress_cycle(TODAY - datetime.timedelta(days=3))})
    assert plan.run(tmp_path) == 0
    line = next(line for line in capsys.readouterr().out.splitlines() if line.startswith("Cycle 03-the-window:"))
    end = (TODAY - datetime.timedelta(days=3) + datetime.timedelta(weeks=3)).isoformat()
    assert line == f"Cycle 03-the-window: 2 of 4 accepted · 1 in progress · 1 ready · day 4 of 21, 18 left (ends {end})"


def test_a_dropped_deliverable_counts_in_nothing_and_a_state_absent_is_not_said(tmp_path, capsys):
    framed(tmp_path, cycles={"01-first.md": progress_cycle(TODAY, states=("accepted", "dropped"))})
    plan.run(tmp_path)
    line = next(line for line in capsys.readouterr().out.splitlines() if line.startswith("Cycle 01-first:"))
    assert line.startswith("Cycle 01-first: 1 of 1 accepted · day 1 of 21")


def test_a_cycle_past_its_end_says_the_circuit_breaker(tmp_path, capsys):
    start = TODAY - datetime.timedelta(weeks=4)
    framed(tmp_path, cycles={"01-first.md": progress_cycle(start)})
    plan.run(tmp_path)
    out = capsys.readouterr().out
    ended = (start + datetime.timedelta(weeks=3)).isoformat()
    assert f"ended on {ended}, 7 days ago — the circuit breaker: the decider chooses" in out


def test_a_cycle_not_started_says_when_it_starts(tmp_path, capsys):
    framed(tmp_path, cycles={"01-first.md": progress_cycle(TODAY + datetime.timedelta(days=2))})
    plan.run(tmp_path)
    assert "starts in 2 days" in capsys.readouterr().out


def test_no_accepted_cycle_says_no_line(tmp_path, capsys):
    framed(tmp_path, cycles={"01-first.md": cycle(status="proposed")})
    plan.run(tmp_path)
    assert not any(line.startswith("Cycle ") for line in capsys.readouterr().out.splitlines())


def test_the_handbook_says_where_progress_is_read():
    page = (Path(__file__).resolve().parents[2] / "skeleton/.nstack/handbook/project.md").read_text(encoding="utf-8")
    assert "## A cycle's progress" in page and "nstack plan" in page.split("## A cycle's progress", 1)[1]


def test_a_cycle_whose_deliverables_are_not_a_list_is_reported_never_a_crash(tmp_path, capsys):
    framed(tmp_path, cycles={"01-first.md": cycle(deliverables=5)})
    assert plan.run(tmp_path) == 1
    assert "[C4]" in capsys.readouterr().out


@pytest.mark.parametrize("days_before_end, said", [(1, "day 21 of 21, 1 left"),
                                                   (0, "ended on")], ids=["last day", "end date"])
def test_the_end_date_is_the_first_day_over(tmp_path, capsys, days_before_end, said):
    """The cycle form: `end` is the first day the cycle is over — the circuit breaker."""
    start = TODAY + datetime.timedelta(days=days_before_end) - datetime.timedelta(weeks=3)
    framed(tmp_path, cycles={"01-first.md": progress_cycle(start)})
    plan.run(tmp_path)
    assert said in capsys.readouterr().out


@pytest.mark.parametrize("start, said", [(TODAY + datetime.timedelta(days=1), "starts in 1 day ("),
                                         (TODAY - datetime.timedelta(weeks=3, days=1), "1 day ago")])
def test_one_day_is_said_in_the_singular(tmp_path, capsys, start, said):
    framed(tmp_path, cycles={"01-first.md": progress_cycle(start)})
    plan.run(tmp_path)
    assert said in capsys.readouterr().out


def test_a_state_the_line_does_not_name_is_counted_as_other(tmp_path, capsys):
    framed(tmp_path, cycles={"01-first.md": progress_cycle(TODAY, states=("accepted", "doing"))})
    plan.run(tmp_path)
    assert "1 of 2 accepted · 1 other" in capsys.readouterr().out


def test_the_handbook_s_example_is_one_the_engine_prints():
    page = (Path(__file__).resolve().parents[2] / "skeleton/.nstack/handbook/project.md").read_text(encoding="utf-8")
    example = next(line for line in page.splitlines() if line.startswith("Cycle 03-the-window:"))
    import re
    day, length, left = map(int, re.search(r"day (\d+) of (\d+), (\d+) left", example).groups())
    assert day - 1 + left == length, example


# --- D155: the project across its cycles ------------------------------------------------------

def history(root, later: str = "") -> None:
    """Three cycles as a project lives them: one stopped and reframed, one closed, one running."""
    framed(root, charter={**CHARTER, "success_criteria": CHARTER["success_criteria"] * 3}, cycles={})
    write(root, "cycles/01-first.md", progress_cycle(TODAY - datetime.timedelta(weeks=6), states=(
        "accepted", "deferred", "deferred"), ) | {"status": "stopped", "outcome": "reframed", "ended_on": "2026-10-13"})
    write(root, "cycles/02-second.md", progress_cycle(TODAY - datetime.timedelta(weeks=3), states=(
        "accepted", "accepted")) | {"status": "closed", "outcome": "completed", "ended_on": "2026-10-17"})
    write(root, "cycles/03-third.md", progress_cycle(TODAY - datetime.timedelta(days=3)),
          body="\n# Cycle 03\n\n## Later\n\n" + later + "\n## Open questions\n")


def test_the_project_is_said_across_its_cycles(tmp_path):
    history(tmp_path, later="- Windows\n- macOS,\n  with the colleagues\n1. export\n")
    end = (TODAY - datetime.timedelta(days=3) + datetime.timedelta(weeks=3)).isoformat()
    assert plan.project(tmp_path) == [
        "Project: 0 of 3 success criteria met, recorded at each cycle's closure · 3 cycles: "
        "1 accepted, 1 closed, 1 stopped",
        "  01-first   stopped (reframed) on 2026-10-13 · 1 of 3 accepted · 2 deferred",
        "  02-second  closed (completed) on 2026-10-17 · 2 of 2 accepted",
        f"  03-third   in progress, ends {end} · 2 of 4 accepted · 1 in progress · 1 ready",
        "  Later in 03-third, for the next framing: 3 candidates",
    ]


@pytest.mark.parametrize("later, said", [
    ("", None),
    (plan.LATER_FORM[:60] + "\n" + plan.LATER_FORM[60:] + "\n", None),
    ("Export, and the other systems, once the window holds.\n", "candidates written as prose"),
    ("Candidates: export; the other systems.\n\n- the tray, added on the decider's word\n",
     "1 candidate listed, and prose"),
], ids=["absent", "the form's words", "prose", "prose and a list"])
def test_later_is_counted_said_or_left_out(tmp_path, later, said):
    history(tmp_path, later=later)
    lines = [line for line in plan.project(tmp_path) if "Later in" in line]
    assert lines == ([f"  Later in 03-third, for the next framing: {said}"] if said else [])


def test_the_later_form_is_the_cycle_form_s():
    form = (Path(__file__).resolve().parents[2] / "skeleton/.nstack/forms/cycle.md").read_text(encoding="utf-8")
    assert " ".join(form.split("## Later", 1)[1].split("## Open questions", 1)[0].split()) == plan.LATER_FORM


def test_between_two_cycles_the_ended_one_s_later_is_said_not_the_next_proposal_s(tmp_path):
    history(tmp_path)
    (tmp_path / "docs/project/cycles/03-third.md").unlink()
    write(tmp_path, "cycles/02-second.md", progress_cycle(TODAY - datetime.timedelta(weeks=3), states=("accepted",))
          | {"status": "closed", "outcome": "completed", "ended_on": "2026-10-17"}, body="\n## Later\n\n- the window\n")
    write(tmp_path, "cycles/03-third.md", cycle(status="proposed"), body="\n## Later\n\n" + plan.LATER_FORM + "\n")
    assert plan.project(tmp_path)[-1] == "  Later in 02-second, for the next framing: 1 candidate"


def test_what_the_rules_refuse_is_said_plainly_never_printed_raw(tmp_path):
    framed(tmp_path, charter={**CHARTER, "status": "draft"}, cycles={
        "01-a.md": cycle(status=None), "02-b.md": cycle(status="done"), "03-c.md": cycle(end=None),
        "04-d.md": {key: value for key, value in cycle(status="proposed").items() if key != "start"}})
    lines = plan.project(tmp_path)
    assert "None" not in "\n".join(lines), lines
    assert lines[0] == "Project: the charter's status unknown (C2) · 4 cycles: 1 accepted, 1 proposed, 2 other"
    assert [line.split("  ")[-1].split(" · ")[0] for line in lines[1:]] == [
        "status unknown (C3)", "status unknown (C3)", "in progress", "proposed"]


def test_an_unreadable_cycle_or_charter_is_said_never_a_crash(tmp_path):
    write(tmp_path, "charter.md", "# no front matter")
    write(tmp_path, "cycles/01-first.md", "# no front matter either")
    assert plan.project(tmp_path) == ["Project: no charter readable · 1 cycle: 1 other",
                                      "  01-first  front matter unreadable (C1)"]


def test_a_proposed_charter_and_cycle_are_said_as_proposals(tmp_path):
    framed(tmp_path, charter={**CHARTER, "status": "proposed"}, cycles={"01-first.md": cycle(status="proposed")})
    lines = plan.project(tmp_path)
    assert lines[0] == "Project: the charter is proposed · 1 cycle: 1 proposed"
    assert lines[1].startswith("  01-first  proposed, starts ")


def test_no_project_says_nothing(tmp_path, capsys):
    assert plan.project(tmp_path) == []
    (tmp_path / ".copier-answers.yml").write_text("_commit: v0.16.0\n", encoding="utf-8")
    assert plan.show(tmp_path) == 0 and capsys.readouterr().out == ""


def test_nstack_plan_says_the_project_and_fitness_does_not(tmp_path, capsys):
    from napkinstack import cli
    history(tmp_path)
    cli.main(["plan", "--root", str(tmp_path)])
    assert "\nProject: 0 of 3 success criteria met" in capsys.readouterr().out
    cli.main(["fitness", "--root", str(tmp_path)])
    assert "Project:" not in capsys.readouterr().out


def test_the_handbook_says_where_the_project_is_read():
    page = (Path(__file__).resolve().parents[2] / "skeleton/.nstack/handbook/project.md").read_text(encoding="utf-8")
    assert "## The project across its cycles" in page
    assert "nstack plan" in page.split("## The project across its cycles", 1)[1].split("\n## ", 1)[0]


# --- D158: what cannot be read is refused, never a traceback (#268) ---------------------------

@pytest.mark.parametrize("content, said", [
    ("---\nstart: 2026-13-45\n---\n".encode(), "a date that does not exist"),
    (b"---\ngoal: caf\xe9\n---\n", "not UTF-8 text"),
], ids=["impossible date", "not UTF-8"])
def test_a_front_matter_that_cannot_be_read_is_refused_as_c1(tmp_path, capsys, content, said):
    framed(tmp_path)
    (tmp_path / "docs/project/cycles/02-second.md").write_bytes(content)
    assert plan.run(tmp_path) == 1
    out = capsys.readouterr().out
    assert "[C1] docs/project/cycles/02-second.md" in out and said in out, out


# --- D159: the project's success, recorded where a cycle closes (PDR-0019) --------------------

def closed(*records, status="closed", outcome="completed") -> dict:
    data = progress_cycle(TODAY - datetime.timedelta(weeks=3), states=("accepted",)) | {
        "status": status, "outcome": outcome, "ended_on": "2026-10-17"}
    return data | ({"success": list(records)} if records else {})


def test_the_latest_closure_s_record_is_a_criterion_s_state(tmp_path):
    history(tmp_path)
    write(tmp_path, "cycles/01-first.md", closed({"criterion": 1, "state": "met"},
                                                 {"criterion": 2, "state": "observing", "since": "2026-10-01"},
                                                 status="stopped", outcome="reframed"))
    write(tmp_path, "cycles/02-second.md", closed({"criterion": 1, "state": "observing", "since": "2026-10-15"},
                                                  {"criterion": 2, "state": "met"}))
    assert plan.run(tmp_path) == 0
    assert plan.project(tmp_path)[0].startswith(
        "Project: 1 of 3 success criteria met · criterion 1 observed since 2026-10-15 · 3 cycles:")


def test_every_criterion_met_says_the_goal_is_reached(tmp_path):
    history(tmp_path)
    write(tmp_path, "cycles/02-second.md", closed(*({"criterion": n, "state": "met"} for n in (1, 2, 3))))
    assert plan.project(tmp_path)[0].startswith(
        "Project: 3 of 3 success criteria met — the charter's goal is reached: the decider says whether")


def test_a_record_only_a_closure_makes(tmp_path, capsys):
    history(tmp_path)
    write(tmp_path, "cycles/03-third.md", progress_cycle(TODAY - datetime.timedelta(days=3))
          | {"success": [{"criterion": 1, "state": "met"}]})
    assert plan.run(tmp_path) == 1
    assert "[C6] docs/project/cycles/03-third.md" in capsys.readouterr().out
    assert plan.project(tmp_path)[0].startswith("Project: 0 of 3 success criteria met")


@pytest.mark.parametrize("record, said", [
    ({"criterion": 4, "state": "met"}, "criterion 4, and the charter's filled criteria are numbered 1, 2, 3"),
    ("met", "expected a mapping (criterion, state, since)"),
    ({"criterion": "first", "state": "met"}, "criterion 'first', expected a number from 1"),
    ({"criterion": 1, "state": "done"}, "state 'done', expected one of ['met', 'observing']"),
    ({"criterion": 1, "state": "observing"}, "observing since when?"),
], ids=["outside the charter", "not a mapping", "not a number", "unknown state", "observing with no day"])
def test_a_record_the_charter_cannot_hold_is_refused_as_c6(tmp_path, capsys, record, said):
    history(tmp_path)
    write(tmp_path, "cycles/02-second.md", closed(record))
    assert plan.run(tmp_path) == 1
    out = capsys.readouterr().out
    assert "[C6] docs/project/cycles/02-second.md" in out and said in out, out


def test_the_cycle_form_shows_the_record_commented():
    form = (Path(__file__).resolve().parents[2] / "skeleton/.nstack/forms/cycle.md").read_text(encoding="utf-8")
    front = form.split("---", 2)[1]
    assert "# success:" in front and "observing" in front
    assert "success" not in (plan.read_front_matter(
        Path(__file__).resolve().parents[2] / "skeleton/.nstack/forms/cycle.md")[0] or {})


def test_the_form_s_example_left_in_the_charter_is_listed_never_counted(tmp_path, capsys):
    history(tmp_path)
    write(tmp_path, "charter.md", {**CHARTER, "success_criteria": [
        "First", "<An observable result, and when it is observed>", "Third"]})
    write(tmp_path, "cycles/02-second.md", closed({"criterion": 1, "state": "met"}, {"criterion": 3, "state": "met"}))
    assert plan.project(tmp_path)[0].startswith("Project: 2 of 2 success criteria met — the charter's goal is reached")
    write(tmp_path, "cycles/02-second.md", closed({"criterion": 2, "state": "met"}))
    assert plan.run(tmp_path) == 1
    assert "criterion 2, and the charter's filled criteria are numbered 1, 3" in capsys.readouterr().out


def test_what_c6_refuses_the_view_never_counts(tmp_path, capsys):
    history(tmp_path)
    write(tmp_path, "cycles/02-second.md", closed(*({"criterion": n, "state": "met"} for n in (True, -1, 0, 1, 1))))
    assert plan.run(tmp_path) == 1
    assert "criterion 1 recorded twice in this closure" in capsys.readouterr().out
    assert plan.project(tmp_path)[0].startswith("Project: 1 of 3 success criteria met")


# --- D160: a value of the wrong kind is refused, never a traceback --------------------------

WRONG_KIND = {
    "charter status": (lambda r: framed(r, {**CHARTER, "status": ["accepted"]}), "C2"),
    "cycle status": (lambda r: framed(r, cycles={"01-first.md": cycle(status={"a": 1})}), "C3"),
    "deliverable state": (lambda r: framed(r, cycles={"01-first.md": cycle(deliverables=[deliverable(state=["ready"])])}), "C4"),
    "outcome": (lambda r: framed(r, cycles={"01-first.md": closed(outcome=["completed"])}), "C6"),
    "success state": (lambda r: framed(r, cycles={"01-first.md": closed({"criterion": 1, "state": ["met"]})}), "C6"),
    "discovery decision": (lambda r: write(r, "discovery.md", {"decision": ["go"]}), "C7"),
}


@pytest.mark.parametrize("prepare, rule", WRONG_KIND.values(), ids=WRONG_KIND.keys())
def test_a_value_of_the_wrong_kind_is_refused_never_a_traceback(tmp_path, capsys, prepare, rule):
    from napkinstack import board, cli
    prepare(tmp_path)
    assert plan.run(tmp_path) == 1
    assert f"[{rule}] docs/project/" in capsys.readouterr().out
    cli.main(["plan", "--root", str(tmp_path)])
    board.desired(tmp_path)
    said = "\n".join(plan.project(tmp_path))
    assert "['" not in said and "{'" not in said, said


def test_a_deliverable_state_of_the_wrong_kind_is_not_taken_nor_delivered(tmp_path):
    from napkinstack import hold, pull_request
    framed(tmp_path, cycles={"01-first.md": cycle(deliverables=[deliverable(state=["ready"])])})
    assert "is '['ready']': work starts on a ready deliverable" in hold._deliverable(tmp_path, "D1")
    failed = []
    pull_request.check_cycle(tmp_path, "Deliverable: D1", set(), TODAY, lambda rule, message: failed.append(rule))
    assert "K3" in failed
