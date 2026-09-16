"""
nstack discover — starts a project's discovery from an idea file (PDR-0002, extension).

Deterministic, no model called: the idea is kept in docs/project/inputs/, the discovery
document is created from its template, and the instruction for the team's agent is
printed. The conversation itself happens in the agent (playbooks/discovery.md).

Usage :  nstack discover <idea-file> [--root ROOT]
Output:  0 when the discovery is started, 1 otherwise.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from napkinstack.fitness.plan import DISCOVERY, PROJECT

INPUTS = PROJECT / "inputs"
TEMPLATE = PROJECT / "_DISCOVERY_TEMPLATE.md"
SUFFIXES = {".md", ".txt"}


def run(root: Path, idea: Path) -> int:
    if not (root / TEMPLATE).is_file():
        print(f"FAIL [discover] {TEMPLATE} not found in {root}: not a project created by nstack init, "
              "or one older than the discovery.\n      Action: run it at the project root, or update "
              "the project (nstack update).")
        return 1
    if not idea.is_file() or idea.suffix.lower() not in SUFFIXES:
        print(f"FAIL [discover] {idea}: a Markdown or text file expected.\n      Action: write the idea "
              "in a .md or .txt file — a few lines are enough.")
        return 1
    if (root / DISCOVERY).exists():
        print(f"FAIL [discover] {DISCOVERY} already exists: one discovery per project.\n      Action: "
              "continue it in your agent (playbooks/discovery.md), as a new round of the same document.")
        return 1
    kept = root / INPUTS / idea.name
    if kept.exists() and kept.resolve() != idea.resolve():
        print(f"FAIL [discover] {INPUTS / idea.name} already exists.\n      Action: rename the idea file.")
        return 1
    kept.parent.mkdir(parents=True, exist_ok=True)
    if kept.resolve() != idea.resolve():
        shutil.copyfile(idea, kept)
    source = (INPUTS / idea.name).as_posix()
    template = (root / TEMPLATE).read_text(encoding="utf-8")
    (root / DISCOVERY).write_text(template.replace("<idea file>", source), encoding="utf-8")
    print(f"Discovery started: {source} kept, {DISCOVERY} created.")
    print("\nNext, in your agent:")
    print(f"  Follow playbooks/discovery.md on {source}: interview me, one question at a time.")
    print("Then, in another session, have the document challenged (stage 5); the decider decides: "
          "go, clarify or kill.")
    return 0
