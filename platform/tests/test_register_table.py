"""The register is one table: every row has its header's cells. A `|` unescaped in a cell — even
inside backticks, as GitHub reads a table — splits it, and the row's state lands in a column of
its own (D154: D129's `checks: forge | attested`, D141's `--github-repo | --repository`).
"""

import re
from pathlib import Path

REGISTER = Path(__file__).resolve().parents[2] / "docs/governance/workstreams.md"
CELL = re.compile(r"(?<!\\)\|")


def test_every_row_of_the_register_has_its_table_s_cells():
    width, broken = None, []
    for number, line in enumerate(REGISTER.read_text(encoding="utf-8").splitlines(), 1):
        if not line.startswith("|"):
            width = None
            continue
        cells = len(CELL.findall(line.strip())) - 1
        if width is None:
            width = cells
        elif cells != width:
            broken.append(f"workstreams.md:{number}: {cells} cells, the table has {width} — escape a | as \\|")
    assert not broken, "\n".join(broken)
