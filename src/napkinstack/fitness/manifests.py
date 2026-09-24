#!/usr/bin/env python3
"""
Fitness function 1 — Manifest validation.

Checks that every module declares what it must declare and that its lifecycle
state is coherent (docs/os/02-modules.md §6, docs/os/07-governance.md §3).

Rules:
  M1  every module has a MANIFEST.yaml
  M2  required fields present
  M3  valid lifecycle / criticality values
  M4  responsibility in ONE sentence (no "and" joining two capabilities)
  M5  module deprecated -> removal_date required and not passed
  M6  contract deprecated -> removal_date required and not passed
  M7  standard verbs declared (check / test at least), once the module holds more than
      its description
  M8  runbook required when criticality >= high
  M9  complete file envelope (AGENTS.md, README.md, tests/)
  M10 user_facing declared: true when a user sees the module (docs/os/05-workflow.md §7)

Usage :  nstack manifests [--root ROOT]
Output:  0 if everything passes, 1 otherwise. Every failure explains the rule broken.
"""

from __future__ import annotations
import sys
import datetime
import re
import subprocess
from pathlib import Path

import yaml

from napkinstack import assurance

LIFECYCLES = {"proposed", "active", "maintenance", "deprecated", "retired"}
CRITICALITIES = set(assurance.CRITICALITIES)  # one list, ascending, held in assurance
REQUIRED_FIELDS = ["name", "responsibility", "owner", "lifecycle", "criticality"]
REQUIRED_COMMANDS = ["check", "test"]
MODULE_DIRS = ["modules", "services", "apps", "packages", "contracts", "platform"]
MODULE_BASES = ["modules", "services", "apps", "packages"]  # bases where every folder is a module
SECTIONS = {"module": dict, "provides": list, "consumes": list, "data": dict,
            "commands": dict, "docs": dict, "dependencies": list}
TYPES = {dict: "mapping", list: "list"}
DESCRIPTION = {"MANIFEST.yaml", "AGENTS.md", "README.md"}
STABILITIES = {"experimental", "stable", "deprecated"}
CONTRACT_FIELDS = {"provides": ("contract", "version", "path"), "consumes": ("contract", "version", "module")}

failures: list[str] = []
warnings: list[str] = []


def fail(module: str, rule: str, message: str) -> None:
    failures.append(f"[{rule}] {module}\n      {message}")


def warn(module: str, rule: str, message: str) -> None:
    warnings.append(f"[{rule}] {module}\n      {message}")


def find_manifests(root: Path) -> list[Path]:
    found = []
    for base in MODULE_DIRS:
        d = root / base
        if not d.is_dir():
            continue
        for manifest in sorted(d.glob("*/MANIFEST.yaml")):
            found.append(manifest)
        direct = d / "MANIFEST.yaml"
        if direct.is_file():
            found.append(direct)
    return found


def find_orphans(root: Path) -> list[Path]:
    """Module folders without a MANIFEST.yaml (M1)."""
    return [child for base in MODULE_BASES if (root / base).is_dir()
            for child in sorted((root / base).iterdir())
            if child.is_dir() and not child.name.startswith(".") and not (child / "MANIFEST.yaml").is_file()]


def contract_entries(data: dict, section: str) -> list[dict]:
    """The entries of `provides` or `consumes` whose contract fields are text: the others are
    reported by M2 and read by no other check (D40)."""
    value = data.get(section)
    if not isinstance(value, list):
        return []
    return [entry for entry in value if isinstance(entry, dict)
            and all(isinstance(entry.get(field), (str, type(None))) for field in CONTRACT_FIELDS[section])]


UNFILLED = re.compile(r"<[^<>\s][^<>]*>")  # the angle-bracket placeholder of a template
TODO = re.compile(r"^TODO\b", re.I)


def unfilled(value) -> bool:
    """Whether a declaration still holds the template's words: empty, carrying a placeholder
    such as <github-handle>, or opening with TODO (D51).

    A *declaration* is unfilled as soon as it carries a placeholder — nobody writes a success
    criterion around one. A *cell* of a test sheet is unfilled only when it is nothing but a
    placeholder, which is the template's example row: that one is `pull_request.PLACEHOLDER`,
    and the two meanings are deliberately different. A placeholder opens on a non-space, so
    "stays < 200 ms" is a comparison, not a placeholder.
    """
    text = str(value or "").strip()
    return not text or bool(UNFILLED.search(text)) or bool(TODO.match(text))


def is_description(path: str) -> bool:
    """A module's description — its manifest, AGENTS.md, README.md, docs/ — or an empty
    placeholder, `path` relative to the module's folder. Changing it changes no behaviour
    (D24); a module holding nothing else has nothing to check yet (D33)."""
    return path in DESCRIPTION or path.startswith("docs/") or path.rsplit("/", 1)[-1] == ".gitkeep"


def _relief(criticality: str | None, row: str, user_facing: bool = False) -> str:
    """assurance.relief as a refusal's closing line (P6): what the value below would change."""
    said = assurance.relief(criticality, row, user_facing)
    return f".\n      {said[0].upper()}{said[1:]}." if said else "."


def module_content(folder: Path) -> list[str]:
    """What a module holds beyond its description, relative to its folder: the files git
    would commit — tracked, or untracked and not ignored — or every file outside a repository."""
    try:
        listed = subprocess.run(["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard", "."],
                                cwd=folder, capture_output=True, text=True)
    except OSError:  # no git on the path: read the folder as outside a repository
        listed = subprocess.CompletedProcess([], 1)
    if listed.returncode == 0:
        files = [path for path in listed.stdout.split("\0") if path]
    else:
        files = [path.relative_to(folder).as_posix() for path in folder.rglob("*") if path.is_file()]
    return sorted(path for path in files if not is_description(path))


def changed_files(root: Path, base: str, head: str = "HEAD") -> list[str]:
    """The files a change touches since its fork from `base`: both sides of a move, since git
    reports a rename under its new name only, and every name as written, never quoted (D38)."""
    listed = subprocess.run(["git", "diff", "--name-only", "--no-renames", "-z", f"{base}...{head}"],
                            cwd=root, capture_output=True, text=True).stdout
    return [path for path in listed.split("\0") if path]


def parse_date(value) -> datetime.date | None:
    if isinstance(value, datetime.date):
        return value
    try:
        return datetime.date.fromisoformat(str(value))
    except ValueError:
        return None


def check_manifest(path: Path, today: datetime.date) -> None:
    rel = path.parent.name
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        fail(rel, "M2", f"MANIFEST.yaml unreadable: {exc}")
        return
    if not isinstance(data, dict):
        fail(rel, "M2", "MANIFEST.yaml must be a YAML mapping (sections module, commands, docs...).")
        return
    for section, expected_type in SECTIONS.items():
        if data.get(section) is not None and not isinstance(data[section], expected_type):
            fail(rel, "M2", f"section {section}: expected a {TYPES[expected_type]}, "
                            f"found {type(data[section]).__name__}.")
            data[section] = expected_type()

    mod = data.get("module") or {}
    for field in ("name", "code_name"):
        if field in mod and not isinstance(mod[field], str):
            fail(rel, "M2", f"module.{field} {mod[field]!r} must be text.")
    owns = (data.get("data") or {}).get("owns")
    if isinstance(owns, list) and not all(isinstance(table, str) for table in owns):
        fail(rel, "M2", "data.owns: every entry names a table, as text.")

    # M2 - required fields
    for field in REQUIRED_FIELDS:
        if not mod.get(field):
            fail(rel, "M2", f"required field missing: module.{field}")

    # M3 - valid values
    lifecycle = mod.get("lifecycle")
    if lifecycle and lifecycle not in LIFECYCLES:
        fail(rel, "M3", f"invalid lifecycle: '{lifecycle}'. Expected one of: {sorted(LIFECYCLES)}")
    criticality = mod.get("criticality")
    if criticality and criticality not in CRITICALITIES:
        fail(rel, "M3", f"invalid criticality: '{criticality}'. Expected one of: {sorted(CRITICALITIES)}")

    # M4 - responsibility in one sentence
    resp = (mod.get("responsibility") or "").strip()
    if resp:
        if resp.count(".") > 1:
            warn(rel, "M4", "responsibility spans several sentences: does the module do two things?")
        if " and " in resp.lower() and len(resp.split()) > 12:
            warn(rel, "M4", f"responsibility contains 'and': is the capability coherent? -> \"{resp}\"")

    # M5 - module deprecation
    if lifecycle == "deprecated":
        dep = mod.get("deprecation")
        dep = dep if isinstance(dep, dict) else {}
        removal = parse_date(dep.get("removal_date"))
        if not removal:
            fail(rel, "M5", "module deprecated without a valid module.deprecation.removal_date (YYYY-MM-DD)")
        elif removal < today:
            fail(rel, "M5", f"removal date passed ({removal}). Permanent intermediate state - "
                            "remove the module or supersede the decision.")

    # M2 - the contract entries the boundaries and the versions are judged on (D36)
    for section, fields in CONTRACT_FIELDS.items():
        for entry in data.get(section) or []:
            if not isinstance(entry, dict):
                continue  # reported below for provides; ignored by the checks that read them
            for field in fields:
                if field in entry and not isinstance(entry[field], str):
                    fail(rel, "M2", f"{section}: {field} {entry[field]!r} must be text — "
                                    f"write it quoted, for example \"v1\".")
            if section == "provides" and entry.get("stability", "experimental") not in STABILITIES:
                fail(rel, "M2", f"provides: stability {entry.get('stability')!r}, expected one of "
                                f"{sorted(STABILITIES)}: a stable or deprecated version is frozen (V1).")

    # M6 - deprecation of provided contracts
    for provided in data.get("provides") or []:
        if not isinstance(provided, dict):
            fail(rel, "M2", "entry of provides: expected a mapping (contract, version, stability).")
            continue
        if provided.get("stability") == "deprecated":
            name = f"{provided.get('contract')}@{provided.get('version')}"
            removal = parse_date(provided.get("removal_date"))
            if not removal:
                fail(rel, "M6", f"deprecated contract {name} without a removal_date")
            elif removal < today:
                fail(rel, "M6", f"contract {name}: removal date passed ({removal}). "
                                "Finish the contraction (docs/os/03-contracts.md §4).")

    commands = data.get("commands") or {}
    content = module_content(path.parent)

    # M2 - the responsibility still the template's, once the module holds more than its
    # description: a module is green as created (D33) and says what it does from its first
    # file of code.
    if content and unfilled(resp):
        fail(rel, "M2", f'module.responsibility is still the template\'s: "{resp}"\n'
                        "      Action: one sentence naming the capability this module covers, "
                        "in MANIFEST.yaml (docs/os/02-modules.md §5).")

    # M7 - standard verbs, once there is something to check (D33)
    for verb in REQUIRED_COMMANDS:
        if content and not commands.get(verb):
            fail(rel, "M7", f"standard verb missing: commands.{verb}, and the module holds more "
                            f"than its description ({content[0]}).\n      Action: declare its stack's "
                            "command in the manifest (docs/os/09-platform.md §2).")

    # M8 - what the criticality requires, read from the matrix of 05-workflow.md §7 and
    # never from a threshold copied here (D67). Each refusal names the value that produced it and
    # what the value below would change, so that the declaration can be judged (P6, D70).
    if assurance.requires(criticality, "runbook"):
        runbook = (data.get("docs") or {}).get("runbook")
        if not runbook or not (path.parent / runbook).is_file():
            declared = (f"criticality={criticality}" if criticality in assurance.CRITICALITIES
                        else f"criticality {criticality!r} is not a value M3 accepts and is "
                             "read as critical, which")
            fail(rel, "M8", f"{declared} requires an existing runbook "
                            "(docs/os/05-workflow.md §7; what it holds: playbooks/operations.md)"
                            f"{_relief(criticality, 'runbook')}\n      Action: declare docs.runbook "
                            "in MANIFEST.yaml and create that file — nstack new-module writes one.")

    # M9 - file envelope
    for expected in ["AGENTS.md", "README.md"]:
        if not (path.parent / expected).is_file():
            fail(rel, "M9", f"envelope file missing: {expected}")
    if not (path.parent / "tests").is_dir() and criticality != "prototype":
        fail(rel, "M9", "tests/ folder missing")

    # M10 - a user-visible surface declared: it decides the test sheet (docs/os/05-workflow.md §7)
    if not isinstance(mod.get("user_facing"), bool):
        fail(rel, "M10", "module.user_facing must be true or false: does a user see this module? "
                         "true requires a test sheet on its pull requests from standard up "
                         "(docs/os/05-workflow.md §7)")


def run(root: Path) -> int:
    failures.clear()
    warnings.clear()
    today = datetime.date.today()
    manifests = find_manifests(root)
    orphans = find_orphans(root)
    if not manifests and not orphans:
        print("No MANIFEST.yaml found. Nothing to validate.")
        return 0
    for orphan in orphans:
        fail(orphan.name, "M1", f"{orphan.relative_to(root)}/ has no MANIFEST.yaml. "
                                "Action: create it, or create the module with nstack new-module.")

    for manifest in manifests:
        check_manifest(manifest, today)

    print(f"Manifests checked: {len(manifests)}")
    for w in warnings:
        print(f"  WARNING {w}")
    for f in failures:
        print(f"  FAIL {f}")

    if failures:
        print(f"\n{len(failures)} violation(s). See docs/os/02-modules.md and docs/os/07-governance.md.")
        return 1
    print("Manifests: compliant.")
    return 0


if __name__ == "__main__":
    sys.exit(run(Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()))
