"""A defect of the framework, met in a project, has a way back to the framework.

Measured on 2026-10-12: bringing a second contributor in took a prompt of seventy lines,
because nothing a project holds said what to do when the framework itself is wrong. The
kernel names the door, the manual holds the steps, and this repository's own page receives
whoever comes through it — a private project included.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SKELETON = ROOT / "skeleton"
SECTION = "## When the framework is wrong"


def test_the_kernel_names_the_door() -> None:
    kernel = (SKELETON / "AGENTS.md").read_text(encoding="utf-8")
    rows = [line for line in kernel.splitlines() if line.startswith("|") and "The framework itself is wrong" in line]
    assert len(rows) == 1, "the kernel's stopping rules do not say what to do when the framework is wrong"
    assert ".nstack/handbook/INSTALL.md" in rows[0] and "workaround" in rows[0].lower(), rows[0]


def test_the_manual_holds_the_steps() -> None:
    manual = (SKELETON / ".nstack/handbook/INSTALL.md.jinja").read_text(encoding="utf-8")
    assert manual.count(SECTION) == 1, "the manual has no section on a defect of the framework"
    section = manual.split(SECTION, 1)[1].split("\n## ", 1)[0]
    for needed in ("```mermaid", "**Legend**", "git clone", "uv run --project", "--root .", "CONTRIBUTING.md",
                   "nstack update --ref", "private"):
        assert needed in section, f"the section does not hold: {needed}"


def test_the_framework_receives_who_comes_from_a_project() -> None:
    page = (ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8")
    head = page.split("## A workstream's journey", 1)[0]
    assert "## You come from a project" in head, "the contributing page does not open on the contributor's case"
    for needed in ("fork", "private", "never name the project", "platform/tests/run.sh"):
        assert needed in head, f"the contributor's section does not hold: {needed}"
