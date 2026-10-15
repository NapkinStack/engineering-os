"""
What a real project taught the playbooks (D81, D82, D83, and a criticality proposed too low).

A playbook line is not a check: nothing can verify that an agent asked the question. These
cases only keep each lesson where the next reader looks — one sentence, in the stage where the
mistake was made — so that a later rewrite of the page does not lose it in silence.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

SKELETON = Path(__file__).resolve().parents[2] / "skeleton" / ".nstack"
DISCOVERY = (SKELETON / "playbooks/discovery.md").read_text(encoding="utf-8")
FRAMING = (SKELETON / "playbooks/framing.md").read_text(encoding="utf-8")


def stage(text: str, title: str) -> str:
    start = text.index(f"## {title}")
    end = text.find("\n## ", start + 4)
    return text[start: end if end != -1 else len(text)]


def test_the_intake_asks_in_which_language_the_project_writes() -> None:
    """D82. The idea file was in French and the forms in English; the question was asked
    because the framer happened to notice. Its answer is the project's first rule."""
    intake = stage(DISCOVERY, "1. Intake")
    assert "language" in intake and "docs/project/rules/always.md" in intake, intake
    assert "language" in stage(FRAMING, "1. Frame the project"), "a project framed without a discovery is never asked"


def test_a_legal_claim_is_read_at_its_source_or_is_an_assumption() -> None:
    """D83. The framer concluded from publishers' blogs that an indicator on the user's screen
    made a recording lawful; the article presumes consent from what the *recorded* people see.
    The challenger found it by reading the text. *Secondary* is not a mark a law may carry."""
    research = stage(DISCOVERY, "2. Research")
    assert "legal or regulatory claim" in research and "primary source" in research and "assumption" in research, research


def test_a_criticality_is_proposed_from_the_rule_not_from_a_feeling() -> None:
    """The framer proposed `high` for a module the handbook's own sentence makes `critical`,
    and corrected it only because the price table was open for another reason."""
    charter = stage(FRAMING, "1. Frame the project")
    assert "critical" in charter and "deviation" in charter, "nothing sends the framer to the rule before proposing a value"


def test_a_project_s_rule_has_no_earliest_moment() -> None:
    """D81. The handbook said a project has no rule of its own before its charter; the third
    project's first rule was settled at the discovery's intake, and was right to be written."""
    overview = (SKELETON / "handbook/00-overview.md").read_text(encoding="utf-8")
    decisions = (SKELETON / "handbook/06-decisions.md").read_text(encoding="utf-8")
    assert "no rule of its own before it has a charter" not in overview
    row = next(line for line in decisions.splitlines() if line.startswith("| The project's own rules"))
    assert "The charter is accepted: its constraints are the first ones" not in row, row
    assert "first decision that binds" in row, row


def test_framing_says_when_a_decision_is_due():
    """06-decisions.md holds the moments of decisions, and no agent loads the handbook."""
    assert "## Decisions" in FRAMING, "framing.md says nothing of when a decision record is due"
    section = FRAMING[FRAMING.index("## Decisions"):]
    assert "PDR" in section and "ADR" in section and "closure" in section.lower(), section[:400]


# --- One list of triggers (2026-10-15) ---
# The kernel's table, each playbook's header, the skills' descriptions and a diagram of the
# handbook each said when a playbook loads, in four versions: "dependencies" triggered the
# security playbook by its header and by no other copy, so an agent without skills and one
# with them did not load the same rules for the same task. The kernel's table is the list —
# it is what every agent reads first (P2); a header says it again word for word, and a skill's
# "when" is generated from it.

import re as _re

KERNEL = (SKELETON.parent / "AGENTS.md").read_text(encoding="utf-8")
ROWS = dict((playbook, phrase) for phrase, playbook in _re.findall(r"^\| ([^|]+?) \| `(\w[\w-]*\.md)` \|$", KERNEL, _re.M))


def test_the_kernel_lists_every_playbook_once():
    playbooks = sorted(path.name for path in (SKELETON / "playbooks").glob("*.md"))
    assert sorted(ROWS) == playbooks, f"kernel §4 lists {sorted(ROWS)}, the skeleton holds {playbooks}"


@pytest.mark.parametrize("playbook", sorted(ROWS))
def test_a_playbook_s_trigger_is_the_kernel_s_word_for_word(playbook):
    from napkinstack import skills

    said = skills.trigger((SKELETON / "playbooks" / playbook).read_text(encoding="utf-8"))
    expected = f"Load this playbook when you are touching: {ROWS[playbook]}."
    assert said == expected, (
        f".nstack/playbooks/{playbook}: its trigger is not the kernel's.\n      Kernel §4: {ROWS[playbook]}\n"
        f"      Action: write its header as `> **Trigger.** {expected}`.")


@pytest.mark.parametrize("playbook", sorted(ROWS))
def test_a_skill_says_when_from_its_playbook(tmp_path, playbook):
    from napkinstack import skills

    root = SKELETON.parent
    entries = yaml.safe_load((SKELETON / "skills.yaml").read_text(encoding="utf-8"))["skills"]
    name = playbook.removesuffix(".md")
    _, text = skills.build(root, name, entries[name])
    described = yaml.safe_load(text.split("---")[1])["description"]
    assert ROWS[playbook] in described, described
    assert "should be used when" not in normalised(entries[name]["description"]), (
        f".nstack/skills.yaml: {name} still says when itself; the playbook's trigger says it")


def normalised(text: str) -> str:
    return " ".join(text.split())


def test_the_handbook_draws_no_list_of_triggers():
    ai = (SKELETON / "handbook/04-ai-context.md").read_text(encoding="utf-8")
    assert "+ security.md" not in ai and "+ ux.md" not in ai, "04-ai-context.md keeps its own list of triggers"


# --- What a session reads of the cycle, and when it asks for approval (PDR-0002, clarified 2026-10-15) ---
# Measured on the third project: its current cycle was 57 % of what a session loads before its
# first line of work, most of it a journal of what each deliverable had tried. And the kernel
# said "present steps 1 to 5 before changing anything" while the handbook's diagram committed
# the oracle first, then presented the plan.

def test_a_session_reads_its_deliverable_s_section_of_the_cycle():
    loading = KERNEL[KERNEL.index("Load, in this order"): KERNEL.index("**Playbooks — triggers.**")]
    assert "of the current cycle, its front matter and your deliverable's section" in loading, loading
    assert "MANIFEST.yaml and AGENTS.md of the module concerned" in loading, loading


def test_the_cycle_s_form_gives_each_deliverable_its_section():
    form = (SKELETON / "forms/cycle.md").read_text(encoding="utf-8")
    assert "### D1" in form and "log issue" in form, "the form keeps free notes for every deliverable together"


def test_the_plan_is_approved_before_any_file_is_written():
    assert "Before writing any file, present steps 1 to 3" in KERNEL
    assert "always.md" not in KERNEL[KERNEL.index("## 2. Working loop"): KERNEL.index("## 3. Stopping rules")], (
        "a project's rule may add to the kernel or tighten it, never waive its approval (PDR-0002)")
    loop = (SKELETON / "handbook/05-workflow.md").read_text(encoding="utf-8")
    loop = loop[loop.index("## 2. The loop"): loop.index("## 3.")]
    assert loop.index("Present the plan") < loop.index("ORACLE: write"), "the diagram commits the oracle before the plan"


def test_the_kernel_names_who_hears_of_a_framework_defect():
    row = next(line for line in KERNEL.splitlines() if line.startswith("| The framework itself is wrong"))
    assert "Report it to the decider" in row and "the decider assigns" in row, row


# --- One vocabulary (2026-10-15) ---
# The standard verbs were four in one page, six in a diagram and ten in the platform's table;
# three pages promised a producer/consumer matrix "generated from the manifests" that no command
# produces; the manual's command table had lost a verb's meaning; this repository's own module
# page said G1-G18 after a nineteenth rule.

ROOT = SKELETON.parent.parent


def test_no_page_promises_a_generated_matrix():
    pages = [SKELETON / "handbook/02-modules.md", SKELETON / "handbook/03-contracts.md",
             ROOT / "src/napkinstack/templates/contracts/AGENTS.md"]
    said = [page.name for page in pages if _re.search(r"matrix[^.]*\bgenerated\b|\bgenerated\b[^.]*matrix|is \*\*generated\*\*",
                                                     " ".join(page.read_text(encoding="utf-8").split()))]
    assert not said, f"a generated producer/consumer matrix promised in {said}; no command produces it"


def test_the_standard_verbs_are_listed_once():
    diagram = (SKELETON / "handbook/02-modules.md").read_text(encoding="utf-8")
    page = (ROOT / "src/napkinstack/templates/module/README.md").read_text(encoding="utf-8")
    assert "migrate · release" not in diagram, "02-modules.md draws its own list of verbs"
    assert "`bootstrap`, `check`, `test`, `run`" not in page and "09-platform.md` §2" in page, page


def test_the_manual_names_every_verb_the_engine_runs():
    manual = (SKELETON / "handbook/INSTALL.md.jinja").read_text(encoding="utf-8")
    commands = manual[manual.index("## The commands"):]
    for verb in ("bootstrap", "check", "test", "run", "e2e", "clean", "compat"):
        assert f"nstack {verb}" in commands, f"INSTALL's commands do not name `nstack {verb}`"
    assert "--user-facing" in commands, "the flag that decides a test sheet is documented nowhere"


def test_the_platform_page_names_every_rule_doctor_holds():
    from napkinstack import doctor

    highest = max(int(rule[1:]) for rule, _, _ in doctor.CHECKLIST)
    page = (ROOT / "platform/README.md").read_text(encoding="utf-8")
    assert f"G1-G{highest}" in page, f"platform/README.md does not say G1-G{highest}"


def test_a_fitness_function_nothing_ships_says_whose_it_is():
    governance = " ".join((SKELETON / "handbook/07-governance.md").read_text(encoding="utf-8").split())
    assert "the project's to build" in governance, "07-governance.md announces budgets and layering as if checked"
