"""
The framework's own identifiers stay home (D79).

A project holds its own `docs/pdr/` and `docs/adr/`, numbered from 0001, and its deliverables
are D1, D2… A message that cites "(PDR-0005)" sends its reader to a record of *their* project
that says something else, or to none. And a rule code — K1, T4, M7 — printed by a refusal and
defined in no page the project holds is a word the reader cannot look up.

These cases read the engine's strings and the files a project receives. Comments and
docstrings of the engine are ours and keep their references: nobody outside reads them.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
ENGINE = ROOT / "src/napkinstack"
RECEIVED = [ROOT / "skeleton", ENGINE / "templates"]
RULES = ROOT / "skeleton/docs/os/RULES.md"
RECORD = re.compile(r"\b(?:PDR|ADR)-\d{4}\b|\(D\d+\)")
CODE = r"[A-Z]{1,2}\d{1,2}"


def spoken(path: Path) -> list[tuple[int, str]]:
    """The strings a module can print: every string constant that is not a docstring."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    docstrings = {id(node.body[0].value) for node in ast.walk(tree)
                  if isinstance(node, (ast.Module, ast.FunctionDef, ast.ClassDef))
                  and ast.get_docstring(node) and isinstance(node.body[0], ast.Expr)}
    return [(node.lineno, node.value) for node in ast.walk(tree)
            if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in docstrings]


def engine_codes() -> set[str]:
    """Every rule code the engine names: printed as [X1], or held as the bare string "X1"."""
    codes: set[str] = set()
    for path in ENGINE.rglob("*.py"):
        for _, text in spoken(path):
            codes.update(re.findall(rf"\[({CODE})\]", text))
            if re.fullmatch(CODE, text):
                codes.add(text)
    return codes


def test_no_message_cites_a_record_of_this_repository() -> None:
    cited = [f"{path.relative_to(ROOT)}:{line}: {text.strip()[:90]}"
             for path in sorted(ENGINE.rglob("*.py")) for line, text in spoken(path) if RECORD.search(text)]
    assert not cited, "a project reads these and owns other records under the same numbers:\n" + "\n".join(cited)


def test_no_file_a_project_receives_cites_a_record_of_this_repository() -> None:
    cited = [f"{path.relative_to(ROOT)}:{number}: {line.strip()[:90]}"
             for folder in RECEIVED for path in sorted(folder.rglob("*")) if path.is_file()
             for number, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1)
             if RECORD.search(line)]
    assert not cited, "these lines reach every project:\n" + "\n".join(cited)


def test_every_rule_code_is_defined_in_one_page_the_project_holds() -> None:
    """Both ways: a code printed and not defined cannot be looked up; a code defined and never
    printed is a rule the page promises and nothing enforces."""
    defined = set(re.findall(rf"^\| `({CODE})` \|", RULES.read_text(encoding="utf-8"), re.M))
    printed = engine_codes()
    assert printed - defined == set(), f"printed by the engine, defined nowhere: {sorted(printed - defined)}"
    assert defined - printed == set(), f"defined in RULES.md, printed by nothing: {sorted(defined - printed)}"


@pytest.mark.parametrize("name", ["PRODUCT.md"])
def test_no_rule_forbids_a_product_a_file_name(name: str) -> None:
    """L4 refused a file called PRODUCT.md, which was this repository's and never a project's
    to begin with — while PDR-0010 asks a project to write about its product."""
    assert "L4" not in engine_codes(), "L4 is retired; its number is not reused"
    held = [f"{path.relative_to(ROOT)}:{line}" for path in sorted(ENGINE.rglob("*.py"))
            for line, text in spoken(path) if name in text]
    assert not held, f"the engine still speaks of {name}: {held}"
