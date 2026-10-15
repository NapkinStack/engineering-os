"""
The register says what is true (`docs/governance/workstreams.md`).

The register is this repository's roadmap and the place every defect number resolves to. Two
copies of the same state drift: a row cited by number that has no row (D103), a row whose
status is open and that the table of open work does not list (D104), a decision whose index
says one status and whose file another. These cases read the files themselves.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "docs/governance/workstreams.md"
INDEXES = [ROOT / "docs/adr/README.md", ROOT / "docs/pdr/README.md"]


def section(text: str, title: str) -> str:
    """The lines under a `## title` heading, up to the next one."""
    match = re.search(rf"^## {re.escape(title)}\n(.*?)(?=^## |\Z)", text, re.S | re.M)
    assert match, f"{REGISTER.name}: no section '## {title}'. Action: restore it."
    return match.group(1)


def rows(block: str) -> list[list[str]]:
    """The cells of each table row, header and separator excluded."""
    found = []
    for line in block.splitlines():
        if line.startswith("|") and not re.match(r"\|\s*[-:#]", line):
            found.append([cell.strip() for cell in line.strip().strip("|").split("|")])
    return found


def test_every_defect_number_cited_has_its_row() -> None:
    text = REGISTER.read_text(encoding="utf-8")
    own = {cells[0] for cells in rows(text)}
    cited = sorted(set(re.findall(r"\bD\d+\b", text)) - own, key=lambda d: int(d[1:]))
    assert not cited, (f"{REGISTER.relative_to(ROOT)}: cited with no row of their own: {', '.join(cited)}. "
                       "Action: add each one's row to 'The record', or stop citing it.")


def test_every_open_row_is_in_the_table_of_open_work() -> None:
    text = REGISTER.read_text(encoding="utf-8")
    listed = " ".join(cells[0] for cells in rows(section(text, "Open")))
    missing = [cells[0] for cells in rows(section(text, "The record"))
               if len(cells) > 2 and re.match(r"\**Open\b", cells[2]) and not re.search(rf"\b{re.escape(cells[0])}\b", listed)]
    assert not missing, (f"{REGISTER.relative_to(ROOT)}: open in 'The record', absent from 'Open': {', '.join(missing)}. "
                         "Action: list each one in the table of open work, with what it waits for.")


def test_a_decision_s_status_is_the_same_in_its_file_and_its_index() -> None:
    differ = []
    for index in INDEXES:
        for cells in rows(index.read_text(encoding="utf-8")):
            link = re.search(r"\]\(\./([^)]+)\)", cells[0])
            if not link or len(cells) < 3:
                continue
            record = index.parent / link.group(1)
            status = re.search(r"^- \*\*Status\*\*: \**(\w+)", record.read_text(encoding="utf-8"), re.M)
            listed = re.match(r"\**(\w+)", cells[2])
            if not status or not listed or status.group(1) != listed.group(1):
                differ.append(f"{record.relative_to(ROOT)}: file says "
                              f"{status.group(1) if status else 'nothing'}, index says {listed.group(1) if listed else 'nothing'}")
    assert not differ, "\n".join(differ) + "\nAction: correct the one that is wrong; the file is the decision."
