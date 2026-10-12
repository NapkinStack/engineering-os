"""
The levels of rules: what every project shares, what one project adds, what one module adds.

The handbook has named three levels since the beginning — framework, project, module — and
said that a project rule is written "in a project document, never in the kernel or a playbook".
It named no document. So a project with a rule of its own — "health data never leaves the EU" —
had three bad places for it: the kernel or a playbook, where the next update conflicts on it;
a module's AGENTS.md, where the next module never reads it; or nowhere.

These cases guard the place, and the fact that whoever loads a playbook is told to load the
project's layer with it. They do not read a project's rules: those are the project's.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from napkinstack.fitness import plan

ROOT = Path(__file__).resolve().parents[2]
SKELETON = ROOT / "skeleton"
RULES = "docs/project/rules"
PLAYBOOKS = sorted(path.stem for path in (SKELETON / ".nstack" / "playbooks").glob("*.md"))


@pytest.mark.parametrize("playbook", PLAYBOOKS)
def test_a_playbook_names_the_project_s_layer_on_its_subject(playbook: str) -> None:
    """Said once, in the block that says when to load it: an agent that loads the playbook as a
    skill never sees the kernel's table, and would apply every project's rules to this one
    without ever reading this one's."""
    text = (SKELETON / ".nstack" / "playbooks" / f"{playbook}.md").read_text(encoding="utf-8")
    head = text[: text.index("\n---\n")] if "\n---\n" in text else text[:1200]
    assert head.count(f"`{RULES}/{playbook}.md`") == 1, (
        f".nstack/playbooks/{playbook}.md does not name {RULES}/{playbook}.md once in its trigger block")


def test_the_kernel_loads_the_project_s_rules_and_ranks_them() -> None:
    kernel = (SKELETON / "AGENTS.md").read_text(encoding="utf-8")
    loading = kernel[kernel.index("Load, in this order"): kernel.index("**Playbooks — triggers.**")]
    assert f"{RULES}/" in loading, "the loading order does not name the project's rules"
    precedence = kernel[kernel.index("## 9. Precedence of instructions"):]
    order = [precedence.index(level) for level in
             ("the module's local AGENTS.md", "the project's rules", "the triggered playbook")]
    assert order == sorted(order), "the nearer level must come first: module, then project, then playbook"
    assert len(kernel.splitlines()) <= 250, "the kernel is over its 250 lines"


def test_the_form_of_a_project_rule_asks_how_it_is_checked() -> None:
    """A rule nobody checks is a wish. The form cannot make a project automate it; it can make
    the absence of a check a cell somebody had to fill in."""
    form = (SKELETON / ".nstack" / "forms" / "rules.md").read_text(encoding="utf-8")
    header = next(line for line in form.splitlines() if line.startswith("| #"))
    assert [cell.strip() for cell in header.strip("|").split("|")][-1] == "Checked by", header
    assert not re.search(r"napkinstack|\bnstack\b", form, re.I), "the form of a project's rules names the framework"


def test_the_handbook_says_where_each_level_writes() -> None:
    overview = (SKELETON / ".nstack/handbook/00-overview.md").read_text(encoding="utf-8")
    levels = overview[overview.index("three levels of rules"): overview.index("### Method and seat")]
    for place in ("`.nstack/playbooks/`", f"`{RULES}/`", "`AGENTS.md`"):
        assert place in levels, f"the table of levels does not name {place}"


def test_a_project_s_rules_are_not_read_as_a_charter_or_a_cycle(tmp_path, capsys) -> None:
    """They live beside the charter and the cycles, which a check reads for their front
    matter. A rules file has none, and must not be refused for it."""
    folder = tmp_path / RULES
    folder.mkdir(parents=True)
    (folder / "security.md").write_text("# Rules of this project — security\n\n| # | Rule |\n", encoding="utf-8")
    assert plan.run(tmp_path) == 0, capsys.readouterr().out
