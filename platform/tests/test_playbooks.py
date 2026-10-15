"""
What a real project taught the playbooks (D81, D82, D83, and a criticality proposed too low).

A playbook line is not a check: nothing can verify that an agent asked the question. These
cases only keep each lesson where the next reader looks — one sentence, in the stage where the
mistake was made — so that a later rewrite of the page does not lose it in silence.
"""

from __future__ import annotations

from pathlib import Path

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
