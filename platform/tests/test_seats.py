"""
The form, not the content (PDR-0010): what the skeleton writes into a project, and whose it is.

A file of the skeleton is one of two things. **Method** is the framework's: every update merges
it. A **seat** is the project's: the framework writes its form once, and no update touches it
again. The defect these cases guard against is the mixed file — the framework's manual on the
product's front page, which the project does not delete because it looks official and the
framework conflicts on because the project wrote in it.

Each assertion names the defect it prevents. They read files, never a wording: the one sentence
quoted below is the standard's own, because "stated once" can only be counted.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
SKELETON = ROOT / "skeleton"
OVERVIEW = SKELETON / "docs/os/00-overview.md"
DECISIONS = SKELETON / "docs/os/06-decisions.md"
FORMS = SKELETON / ".github/ISSUE_TEMPLATE"
FRAMEWORK = re.compile(r"napkinstack|\bnstack\b", re.I)
STANDARD = "a diagram with its legend before the prose"
SEATS = [seat.lstrip("/") for seat in
         yaml.safe_load((ROOT / "copier.yml").read_text(encoding="utf-8"))["_skip_if_exists"]]


def source(seat: str) -> Path:
    """The skeleton file a seat is generated from: itself, or its `.jinja`."""
    plain, template = SKELETON / seat, SKELETON / f"{seat}.jinja"
    assert plain.is_file() or template.is_file(), f"{seat} is a seat and the skeleton has no such file"
    return plain if plain.is_file() else template


def subsection(path: Path, title: str) -> str:
    """The text under the heading holding `title`, up to the next heading of any level."""
    text = path.read_text(encoding="utf-8")
    start = re.search(rf"^#+ .*{re.escape(title)}.*$", text, re.M)
    assert start, f"no heading holding '{title}' in {path.name}"
    rest = text[start.end():]
    end = re.search(r"^#+ ", rest, re.M)
    return rest[: end.start()] if end else rest


def test_the_handbook_and_the_template_name_the_same_seats() -> None:
    """Two lists of what belongs to the project drift apart in one release: a file the handbook
    promises the project and an update still rewrites is the pilot's README again."""
    which = [line for line in subsection(OVERVIEW, "Method and seat").splitlines() if "**Which**" in line]
    assert len(which) == 1, "the table of method and seat has no row saying which files are seats"
    told = set(re.findall(r"`([^`]+\.md)`", which[0]))
    assert told == set(SEATS), (
        f"00-overview.md names {sorted(told)}, copier.yml skips {sorted(SEATS)}: one list, two copies")


@pytest.mark.parametrize("seat", SEATS)
def test_a_seat_names_the_framework_on_one_line_at_most(seat: str) -> None:
    """A seat is the product's page. One pointer to the manual is a courtesy the team deletes;
    a second line about the tooling is the manual coming back."""
    lines = [line for line in source(seat).read_text(encoding="utf-8").splitlines() if FRAMEWORK.search(line)]
    assert len(lines) <= 1, f"{seat} names the framework on {len(lines)} lines:\n" + "\n".join(lines[:5])


def test_the_front_page_is_a_form() -> None:
    """Criterion 1: the name, the sentence, the headings, one line to the manual, and no
    installation instruction. Forty lines is not a style rule: the manual it replaces had 249."""
    readme = source("README.md").read_text(encoding="utf-8")
    assert readme.startswith("# {{ project_name }}\n"), "the front page opens on the project's name"
    assert "<One sentence: what this project does.>" in readme, "the sentence C8 asks for at a go is gone"
    assert len(readme.splitlines()) < 40, "the front page grew back into a manual"
    assert sum("docs/os/INSTALL.md" in line for line in readme.splitlines()) == 1, (
        "exactly one line points at the manual")
    assert "```bash" not in readme, "a command block on the front page is an installation instruction"


def test_the_manual_is_whole_and_one_click_away() -> None:
    """Criterion 2: moved, not rewritten. Its sections are counted by name so that a later
    trim of the manual is a decision somebody sees, not a side effect of moving it."""
    manual = (SKELETON / "docs/os/INSTALL.md.jinja").read_text(encoding="utf-8")
    for heading in ("## Prerequisites", "## Installation", "## Receiving a new version",
                    "## To do once on GitHub", "## What is in this repository", "## The commands",
                    "## Claude Code skills", "## The three rules to remember",
                    "## What is not provided", "## What is left to wire after the installation"):
        assert heading in manual, f"the manual lost '{heading}' in the move"


def test_the_documentation_standard_is_stated_once_where_agents_load_it() -> None:
    """Criterion 5 — and the lesson of the day it was built: stated in the handbook, the
    standard reached humans and no agent, since the handbook is never loaded into a context.
    The agents write the documents. So it is stated once, in a playbook; the handbook says why
    and points at it. Naming a tool, it would stop being a rule and become a dependency."""
    holders = [path.relative_to(SKELETON).as_posix() for path in sorted(SKELETON.rglob("*"))
               if path.is_file() and path.suffix in {".md", ".jinja", ".yml"}
               and STANDARD in path.read_text(encoding="utf-8")]
    assert holders == ["playbooks/documentation.md"], f"the standard is stated in {holders}"
    playbook = (SKELETON / "playbooks/documentation.md").read_text(encoding="utf-8")
    tools = set(re.findall(r"\b(Mermaid|PlantUML|Graphviz|GitHub)\b", playbook))
    assert not tools, f"the playbook names {sorted(tools)}: a tool belongs to docs/tooling-profile.md"
    assert "playbooks/documentation.md" in subsection(DECISIONS, "The project's documents"), (
        "the handbook does not say where the standard is")
    assert "Diagrams as text" in (SKELETON / "docs/tooling-profile.md").read_text(encoding="utf-8"), (
        "no tool is mapped to the diagram the standard asks for")


def test_the_kernel_sends_whoever_writes_a_document_to_the_standard() -> None:
    """A playbook nobody is told to load is a page of the handbook under another name."""
    kernel = (SKELETON / "AGENTS.md").read_text(encoding="utf-8")
    rows = [line for line in kernel.splitlines() if line.startswith("|") and "`documentation.md`" in line]
    assert len(rows) == 1, "the kernel's trigger table does not name documentation.md once"
    assert len(kernel.splitlines()) <= 250, "the kernel is over its 250 lines"


def test_a_module_s_page_is_the_module_s() -> None:
    """The page `new-module` writes is a seat too: written once, never updated. Four lines of
    the engine's commands on it were the front page's defect at a smaller scale."""
    page = (ROOT / "src/napkinstack/templates/module/README.md").read_text(encoding="utf-8")
    lines = [line for line in page.splitlines() if FRAMEWORK.search(line)]
    assert len(lines) <= 1, f"a module's page names the framework on {len(lines)} lines:\n" + "\n".join(lines)
    assert any(line.startswith("<A diagram") for line in page.splitlines()), (
        "a module's page has no place for its diagram")


def test_planned_and_unplanned_work_name_different_places() -> None:
    """Criterion 3: 'Work to be done → Issues' sent a project's plan to a place the engine never
    reads, while K3 asked every pull request for a deliverable. Measured: 23 pull requests, 0 issues."""
    table = subsection(DECISIONS, "Sources of truth")
    rows = {cells[0]: cells[1] for cells in
            ([cell.strip() for cell in line.strip().strip("|").split("|")]
             for line in table.splitlines() if line.strip().startswith("|")) if len(cells) == 2}
    planned, unplanned = rows.get("Planned work", ""), rows.get("Unplanned work", "")
    assert "docs/project/cycles/" in planned and "issue" not in planned.lower(), (
        f"planned work must live in the cycle, which is what K3 reads: '{planned}'")
    assert "issue" in unplanned.lower(), f"unplanned work has no home: '{unplanned}'"
    assert "Work to be done" not in rows, "the row that named one place for both is still there"


def test_no_issue_form_claims_what_a_deliverable_claims() -> None:
    """Criterion 4: a form that asks for a deliverable describes planned work twice, in two
    places that will disagree. A feature and a spike are deliverables of a cycle."""
    forms = {path.name: yaml.safe_load(path.read_text(encoding="utf-8")) for path in sorted(FORMS.glob("*.yml"))}
    assert {form["name"] for form in forms.values()} == {"Request", "Bug", "Architecture", "Technical debt"}, (
        f"the forms are {sorted(form['name'] for form in forms.values())}")
    for name, form in forms.items():
        ids = {field.get("id") for field in form["body"]}
        assert "deliverable" not in ids, f"{name} asks for a deliverable: that work is already in a cycle"
