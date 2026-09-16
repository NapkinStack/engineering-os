"""
Generates Claude Code skills from the playbooks.

The playbooks are the SOURCE OF TRUTH (docs/os/06-decisions.md §9). Skills are derived
from them: generated files, never edited by hand, never committed.

Why generate rather than write skills directly:
  - portability — the OS must stay usable by an agent that knows nothing about
    skills. A tool is an adapter, never a foundation
    (docs/tooling-profile.md).
  - single source — two copies of the same rule always diverge.

Rules (--check mode, run in CI):
  S1  every playbook has an entry in .nstack/skills.yaml
  S2  every entry points at an existing playbook
  S3  generated skills match the current playbooks
  S4  name and description follow the Agent Skills specification

S3 only applies when .claude/skills/ exists. Skills are gitignored: a fresh clone, and
therefore CI, has none, and none can be out of sync there.

A root with neither playbooks/ nor .nstack/skills.yaml, such as the NapkinStack
repository itself, is out of scope.

Usage:
    nstack skills [--root ROOT]            # generates .claude/skills/
    nstack skills --check [--root ROOT]    # checks without writing
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

import yaml

SKILL_NAME = re.compile(r"[a-z0-9]+(-[a-z0-9]+)*")
BANNER = (
    "<!-- GENERATED from {source} by nstack skills - DO NOT EDIT.\n"
    "     Edit the playbook, then run `nstack skills` again. -->"
)
MAPPING = Path(".nstack") / "skills.yaml"


def normalise(text: str) -> str:
    """Description on a single line, for a clean YAML frontmatter."""
    return " ".join(text.split())


def build(root: Path, name: str, entry: dict) -> tuple[Path, str]:
    body = (root / entry["source"]).read_text(encoding="utf-8")
    # Serialised, never concatenated: a ":" or "#" in a description would break the YAML.
    frontmatter = yaml.safe_dump(
        {"name": name, "description": normalise(entry["description"])},
        allow_unicode=True, sort_keys=False, width=float("inf"),
    )
    content = "---\n" + frontmatter + "---\n\n" + BANNER.format(source=entry["source"]) + "\n\n" + body
    return root / ".claude" / "skills" / name / "SKILL.md", content


def digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def run(root: Path, check_only: bool = False) -> int:
    map_file = root / MAPPING
    playbook_dir = root / "playbooks"
    skill_dir = root / ".claude" / "skills"

    if not map_file.is_file():
        if not playbook_dir.is_dir():
            print(f"Skills: not applicable, neither playbooks/ nor {MAPPING} in {root}.")
            return 0
        print(f"  FAIL [S1] {MAPPING} not found in {root}: no playbook has an entry.\n"
              f"      Create {MAPPING}, one entry per playbook (source, description).")
        return 1

    try:
        raw = yaml.safe_load(map_file.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        print(f"  FAIL [S2] {MAPPING} unreadable: {exc}")
        return 1
    mapping = raw.get("skills") if isinstance(raw, dict) else None
    if not isinstance(mapping, dict):
        print(f"  FAIL [S2] {MAPPING}: expected a skills section, a mapping of name to source and "
              "description.")
        return 1
    failures: list[str] = [f"[S2] skill '{name}': invalid entry, source and description expected"
                           for name, entry in mapping.items() if not isinstance(entry, dict)]
    mapping = {name: entry for name, entry in mapping.items() if isinstance(entry, dict)}

    # S1 - every playbook must have an entry
    declared = {Path(e["source"]).name for e in mapping.values() if e.get("source")}
    for playbook in sorted(playbook_dir.glob("*.md")):
        if playbook.name not in declared:
            failures.append(
                f"[S1] {playbook.relative_to(root)} has no entry in "
                f"{MAPPING}.\n      Add a description, or remove the "
                f"playbook if it is no longer used (docs/os/10-measurement.md §6)."
            )

    # S2 - every entry must point at an existing playbook
    for name, entry in mapping.items():
        if not (root / entry.get("source", "")).is_file():
            failures.append(f"[S2] skill '{name}': source not found ({entry.get('source')})")
        if not normalise(entry.get("description", "")):
            failures.append(f"[S2] skill '{name}': empty description")

    # S4 - Agent Skills specification (https://agentskills.io/specification)
    for name, entry in mapping.items():
        if len(name) > 64 or not SKILL_NAME.fullmatch(name):
            failures.append(
                f"[S4] skill '{name}': invalid name. 1 to 64 characters, a-z, 0-9 and "
                "single hyphens, with no leading or trailing hyphen."
            )
        if len(normalise(entry.get("description", ""))) > 1024:
            failures.append(f"[S4] skill '{name}': description longer than 1024 characters")

    if failures:
        for failure in failures:
            print(f"  FAIL {failure}")
        return 1

    # S3 - generation or comparison
    if check_only and not skill_dir.is_dir():
        print(f"Skills: S1, S2 and S4 compliant. S3 not applicable: "
              f"{skill_dir.relative_to(root)}/ missing, no skill generated here.")
        return 0

    stale: list[str] = []
    written = 0
    for name, entry in sorted(mapping.items()):
        path, content = build(root, name, entry)
        if check_only:
            if not path.is_file():
                stale.append(f"[S3] skill '{name}' missing from .claude/skills/")
            elif digest(path.read_text(encoding="utf-8")) != digest(content):
                stale.append(f"[S3] skill '{name}' out of sync with {entry['source']}")
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
            written += 1

    if check_only:
        if stale:
            for item in stale:
                print(f"  FAIL {item}")
            print("\nRun `nstack skills` to regenerate.")
            return 1
        print(f"Skills: {len(mapping)} in sync with the playbooks.")
        return 0

    print(f"Skills generated in .claude/skills/: {written}")
    for name in sorted(mapping):
        print(f"  - {name}")
    print("\nThey trigger on their own from their description; an agent can also")
    print("invoke them by name. The kernel stays in AGENTS.md.")
    return 0
