"""
Generates the agents' skills from the playbooks: one SKILL.md per playbook (the Agent Skills
format), in every folder an agent tool reads — `.claude/skills/` for Claude Code,
`.agents/skills/` for Codex and the other tools that follow the open layout (D245).

The playbooks are the SOURCE OF TRUTH (.nstack/handbook/06-decisions.md §9). Skills are derived
from them: generated files, never edited by hand — and committed (D252), as a lockfile is, so that
an agent starting from a fresh clone (a cloud agent, a new contributor) has them; S3, run in CI on
the committed files, says one that drifted from its playbook.

Why generate rather than write skills directly:
  - portability — the OS must stay usable by an agent that knows nothing about
    skills. A tool is an adapter, never a foundation
    (.nstack/tooling-profile.md).
  - single source — two copies of the same rule always diverge.

Rules (--check mode, run in CI):
  S1  every playbook has an entry in .nstack/skills.yaml
  S2  every entry points at an existing playbook
  S3  generated skills match the current playbooks
  S4  name and description follow the Agent Skills specification

S3 reads each of those folders that holds a skill nstack generates — named after a playbook, or
with its banner —, and only those: a folder of a person's own skills, tracked, is not asked for
every playbook (D248). A project that never generated has none, and S3 does not apply there.

A root with neither .nstack/playbooks/ nor .nstack/skills.yaml, such as the NapkinStack
repository itself, is out of scope.

Usage:
    nstack skills [--root ROOT]            # generates .claude/skills/ and .agents/skills/
    nstack skills --check [--root ROOT]    # checks without writing
"""

from __future__ import annotations

import hashlib
import re
import subprocess
from pathlib import Path

import yaml

SKILL_NAME = re.compile(r"[a-z0-9]+(-[a-z0-9]+)*")
BANNER = (
    "<!-- GENERATED from {source} by nstack skills - DO NOT EDIT.\n"
    "     Edit the playbook, then run `nstack skills` again. -->"
)
MAPPING = Path(".nstack") / "skills.yaml"
MARK = "by nstack skills - DO NOT EDIT"  # in every generated skill's banner, never in a person's
# Where each agent tool looks for skills: Claude Code, then Codex and the open layout (D245).
FOLDERS = (Path(".claude") / "skills", Path(".agents") / "skills")


def normalise(text: str) -> str:
    """Description on a single line, for a clean YAML frontmatter."""
    return " ".join(text.split())


def trigger(playbook: str) -> str:
    """A playbook's trigger, as its header says it — the kernel's words (§4), on one line."""
    match = re.search(r"^> \*\*Trigger\.\*\* (.+?)(?=\n>\s*\n|\n\n|\Z)", playbook, re.S | re.M)
    return normalise(match.group(1).replace("\n> ", " ")) if match else ""


def described(entry: dict, playbook: str) -> str:
    """What the skill holds, from the mapping, and when it loads, from its playbook: one list of
    triggers, the kernel's, which the playbook's header says again word for word."""
    when = trigger(playbook)
    return normalise(entry["description"]) + (f" {when}" if when else "")


def build(root: Path, name: str, entry: dict, folder: Path = FOLDERS[0]) -> tuple[Path, str]:
    body = (root / entry["source"]).read_text(encoding="utf-8")
    # Serialised, never concatenated: a ":" or "#" in a description would break the YAML.
    frontmatter = yaml.safe_dump(
        {"name": name, "description": described(entry, body)},
        allow_unicode=True, sort_keys=False, width=float("inf"),
    )
    content = "---\n" + frontmatter + "---\n\n" + BANNER.format(source=entry["source"]) + "\n\n" + body
    return root / folder / name / "SKILL.md", content


def digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def run(root: Path, check_only: bool = False) -> int:
    map_file = root / MAPPING
    playbook_dir = root / ".nstack" / "playbooks"

    if not map_file.is_file():
        if not playbook_dir.is_dir():
            print(f"Skills: not applicable, neither .nstack/playbooks/ nor {MAPPING} in {root}.")
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
                f"playbook if it is no longer used (.nstack/handbook/10-measurement.md §6)."
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

    # S3 - generation or comparison, in each folder an agent tool reads
    present = [folder for folder in FOLDERS if _generated(root / folder, set(mapping))]
    if check_only and not present:
        print("Skills: S1, S2 and S4 compliant. S3 not applicable: "
              f"no skill generated here, in {' or '.join(f'{folder.as_posix()}/' for folder in FOLDERS)}.")
        return 0

    if check_only:
        stale: list[str] = []
        for folder in present:
            for name, entry in sorted(mapping.items()):
                path, content = build(root, name, entry, folder)
                if not path.is_file():
                    stale.append(f"[S3] skill '{name}' missing from {folder.as_posix()}/")
                elif digest(path.read_text(encoding="utf-8")) != digest(content):
                    stale.append(f"[S3] skill '{name}' out of sync with {entry['source']}, in {folder.as_posix()}/")
        if stale:
            for item in stale:
                print(f"  FAIL {item}")
            print("\nRun `nstack skills` to regenerate.")
            return 1
        print(f"Skills: {len(mapping)} in sync with the playbooks.")
        return 0

    removed: set[str] = set()
    for folder in FOLDERS:
        for name, entry in sorted(mapping.items()):
            path, content = build(root, name, entry, folder)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        # A playbook gone leaves its skill behind, still loaded by the agent: removed when generated
        # here, never a skill a person wrote (no banner).
        for made_dir in sorted((root / folder).glob("*/")):
            made = made_dir / "SKILL.md"
            if made_dir.name not in mapping and made.is_file() and MARK in made.read_text(encoding="utf-8", errors="replace"):
                made.unlink()
                if not any(made_dir.iterdir()):
                    made_dir.rmdir()
                removed.add(made_dir.name)
    print(f"Skills generated in {' and '.join(f'{folder.as_posix()}/' for folder in FOLDERS)}: {len(mapping)}"
          + (f"; removed, their playbook gone: {', '.join(sorted(removed))}" if removed else ""))
    for name in sorted(mapping):
        print(f"  - {name}")
    for folder in _ignored(root):
        print(f"WARNING: {folder}/ is ignored by git: an agent starting from a fresh clone would not have the "
              "skills.\n"
              f"      Action: remove the {folder}/ line from .gitignore — nstack update does — then commit the folder.")
    print("\nThey trigger on their own from their description; an agent can also")
    print("invoke them by name. The kernel stays in AGENTS.md.")
    return 0


def _generated(folder: Path, names: set[str]) -> bool:
    """A folder holding a skill nstack generates — named after a playbook, or carrying its banner —
    rather than a person's own skills alone."""
    return folder.is_dir() and any(
        made.parent.name in names or MARK in made.read_text(encoding="utf-8", errors="replace")
        for made in folder.glob("*/SKILL.md"))


def _ignored(root: Path) -> list[str]:
    """The skill folders git ignores here, which a commit would leave out: none outside a repository."""
    found = []
    for folder in FOLDERS:
        try:
            done = subprocess.run(["git", "-C", str(root), "check-ignore", "-q", f"{folder.as_posix()}/x/SKILL.md"],
                                  capture_output=True, check=False)
        except OSError:
            return []
        if done.returncode == 128:  # not a repository
            return []
        if done.returncode == 0:
            found.append(folder.as_posix())
    return found
