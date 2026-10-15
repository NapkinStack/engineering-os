"""
This repository's own working files say what this repository does.

Its pull request template was a project's — one module, contracts, a fourteen-box definition of
done — so its pull requests stopped using it, and the definition of done that applies here lived
in the register instead. Its issue forms are the skeleton's, with this repository's paths: copied
by hand, they drift the day the skeleton's change.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
TEMPLATE = ROOT / ".github/pull_request_template.md"
FORMS = ROOT / ".github/ISSUE_TEMPLATE"
SKELETON_FORMS = ROOT / "skeleton/.github/ISSUE_TEMPLATE"


def test_the_pull_request_template_is_a_workstream_s() -> None:
    text = TEMPLATE.read_text(encoding="utf-8")
    assert "## Workstream" in text and "platform/tests/run.sh" in text and "## Definition of Done" in text, (
        f"{TEMPLATE.relative_to(ROOT)}: no workstream, no oracle, or no definition of done.\n"
        "Action: write it for a workstream (PRODUCT.md §5).")
    assert "modules/<name>" not in text, f"{TEMPLATE.relative_to(ROOT)}: asks for a module; read a workstream."


def test_the_definition_of_done_lives_in_the_template_only() -> None:
    register = (ROOT / "docs/governance/workstreams.md").read_text(encoding="utf-8")
    assert "## Definition of Done" not in register, (
        "docs/governance/workstreams.md holds a second definition of done.\n"
        "Action: keep it in .github/pull_request_template.md only.")


@pytest.mark.parametrize("form", sorted(path.name for path in FORMS.glob("*.yml")))
def test_an_issue_form_is_the_skeleton_s_with_this_repository_s_paths(form: str) -> None:
    source = SKELETON_FORMS / form
    if not source.exists():
        source = SKELETON_FORMS / f"{form}.jinja"
    assert source.exists(), f".github/ISSUE_TEMPLATE/{form}: no skeleton form of that name. Action: remove it."
    expected = re.sub(r"(?<![\w/])\.nstack/", "skeleton/.nstack/", source.read_text(encoding="utf-8"))
    expected = expected.replace("{{ github_repo }}", "NapkinStack/engineering-os")
    assert (FORMS / form).read_text(encoding="utf-8") == expected, (
        f".github/ISSUE_TEMPLATE/{form} drifted from {source.relative_to(ROOT)}.\n"
        "Action: copy the skeleton's form, with this repository's paths.")
