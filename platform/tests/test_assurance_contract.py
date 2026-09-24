"""
The assurance contract: what a criticality value requires is described in ONE place (D67).

The framework described it three times — a four-value diagram in `07-governance.md` §6, the
Definition of Done of `05-workflow.md` §7, and the reliability table of `08-quality.md` §7 — in
three shapes, and only the diagram carried `prototype`. The engine spent a single threshold, so
an agent reading two detailed tables and finding no machine that says "enough" took the top
value by prudence.

These cases fail when a second description of the requirements appears, when any document names
a different set of values from the engine's, or when a row of the table stops saying who judges
it. They guard a contract, not a wording: every assertion below names the defect it prevents.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from napkinstack.fitness.manifests import CRITICALITIES

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / "skeleton/docs/os/05-workflow.md"
GOVERNANCE = ROOT / "skeleton/docs/os/07-governance.md"
QUALITY = ROOT / "skeleton/docs/os/08-quality.md"
MANIFEST = ROOT / "src/napkinstack/templates/module/MANIFEST.yaml"
MATRIX = "05-workflow.md` §7"
JUDGES = {"machine", "owed"}


def section(path: Path, number: int) -> str:
    """The text of `## <number>.` up to the next `## `, headings excluded."""
    text = path.read_text(encoding="utf-8")
    start = re.search(rf"^## {number}\..*$", text, re.M)
    assert start, f"section {number} not found in {path.name}"
    rest = text[start.end():]
    end = re.search(r"^## ", rest, re.M)
    return rest[: end.start()] if end else rest


def rows(block: str) -> list[list[str]]:
    """The rows of the FIRST markdown table of `block`, separator excluded. First, not all of
    them: §7 also holds the test sheet's example table, and mixing the two hides a real gap
    behind a false one."""
    table: list[str] = []
    for line in block.splitlines():
        if line.strip().startswith("|"):
            table.append(line)
        elif table:
            break
    assert table, "no table found"
    cells = [[cell.strip() for cell in line.strip().strip("|").split("|")] for line in table]
    return [row for row in cells if not set("".join(row)) <= set("-: ")]


def test_the_matrix_names_the_engine_s_four_values() -> None:
    """The table that decides is the engine's contract: a column missing here is a value the
    framework asks a project to declare and then never prices. `prototype` was that value."""
    header = rows(section(WORKFLOW, 7))[0]
    assert set(header) - {"Validation", "Judged by"} == CRITICALITIES, header


def test_every_row_of_the_matrix_says_who_judges_it() -> None:
    """A framework that claims CI verifies a UAT teaches its readers to stop believing the rest
    of the table. Each row is either enforced by a check, or owed to a human, by name."""
    header, *data = rows(section(WORKFLOW, 7))
    column = header.index("Judged by")
    unmarked = [row[0] for row in data if row[column] not in JUDGES]
    assert not unmarked, f"rows without a judge: {unmarked}"


def test_human_review_is_not_in_the_matrix() -> None:
    """Who must approve is a property of the project's exposure, not of the code's blast radius
    (`07-governance.md` §7). Two axes, two owners: a row here would give it two homes."""
    validations = [row[0] for row in rows(section(WORKFLOW, 7))]
    assert "Human review" not in validations, validations


def test_governance_points_at_the_matrix_rather_than_describing_it() -> None:
    """D67's shape: §6 held a second set of requirements, in another form. It may name the
    values and say how a module changes value; it may not price them again."""
    block = section(GOVERNANCE, 6)
    assert MATRIX in block, "§6 must name the single source of the requirements"
    for row in rows(block) if "|" in block else []:
        named = CRITICALITIES & set(row)
        assert len(named) < 2, f"§6 describes the requirements again: {row}"


def test_quality_keeps_the_what_and_gives_up_the_when() -> None:
    """The third description. Operability is a real subject and stays; when each capability is
    required is read from the matrix, and its columns may never exceed the engine's values."""
    block = section(QUALITY, 7)
    assert MATRIX in block, "§7 of 08-quality must defer to the matrix for the when"
    header = rows(block)[0]
    assert set(header) - {"Capability"} <= CRITICALITIES, header


def test_the_manifest_template_lists_the_engine_s_values() -> None:
    """The comment under the agent's cursor at the moment it chooses (D70). A value missing here
    is a value that never gets picked."""
    comment = "\n".join(line for line in MANIFEST.read_text(encoding="utf-8").splitlines()
                        if line.lstrip().startswith("#"))
    missing = sorted(value for value in CRITICALITIES if value not in comment)
    assert not missing, f"values absent from the template's comment: {missing}"


# The sections that name the values, and may therefore mislead about them. The whole file is
# too wide: "an internal channel in SECURITY.md" is a legitimate sentence elsewhere.
@pytest.mark.parametrize(("path", "number"), [(WORKFLOW, 7), (GOVERNANCE, 6), (QUALITY, 7)])
def test_no_section_invents_a_fifth_value(path: Path, number: int) -> None:
    """A word that reads like a criticality value but is not one sends a reader to a value the
    engine refuses (M3). The diagram this milestone replaced offered four: `internal`,
    `sensitive`, `MINIMAL` and `MAXIMAL`."""
    block = section(path, number)
    invented = sorted(word for word in ("internal", "sensitive", "minimal", "maximal")
                      if re.search(rf"\b{word}\b", block, re.I))
    assert not invented, f"{path.name} §{number} names values the engine does not know: {invented}"
