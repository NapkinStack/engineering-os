"""
A project's modules: creation (nstack new-module) and standard verbs (nstack bootstrap,
check, test, run), with no imposed stack (PRODUCT.md P1, PDR-0001 R5).

Each verb runs the command declared in the `commands` section of the module's
MANIFEST.yaml, from its folder, through the system shell. NapkinStack never assumes a
Makefile, a package.json or anything else: the project declares, nstack runs. Conventions
borrowed from Nx (`nx test <project>`) and moon (`moon run project:task`).
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import yaml

from napkinstack.fitness.manifests import find_manifests, module_content

TEMPLATE = Path(__file__).resolve().parent / "templates" / "module"
NAME = re.compile(r"[a-z][a-z0-9-]*")
# A GitHub person: 1 to 39 characters, alphanumerics and single hyphens, none at either end.
# Defined once here, the identity rule's home: fitness/plan.py reads it for a charter's decider.
HANDLE = r"(?=[A-Za-z0-9-]{1,39}$)[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*"
LOGIN = r"[A-Za-z0-9](?:-?[A-Za-z0-9]){0,38}"  # the same rule, unanchored: a handle inside a sentence
OWNER = re.compile(  # same rule as copier.yml: organisation/team, or a GitHub user
    rf"[A-Za-z0-9-]+/[A-Za-z0-9._-]+|{HANDLE}")
OPTIONAL = {"bootstrap": "nothing to prepare", "e2e": "no end-to-end scenario"}  # undeclared: skipped
NEEDS_RUNBOOK = {"high", "critical"}  # M8, kept in step with CRITICALITIES
NEEDS_SHEET = {"high", "critical"}  # pull_request.SHEET_CRITICALITIES, T1

RUNBOOK = """# Runbook - {name}

> Required for criticality={criticality} (docs/os/08-quality.md §7).
> An empty runbook fails CI. Fill it in before going to production.

## Alerts and responses
| Alert | Meaning | First action |
|---|---|---|
| | | |

## Rollback
<A tested procedure, not an assumed one.>

## Post-deployment verification
<What you watch, and for how long.>

## Dependencies and degradation
<What happens when each dependency is unavailable?>
"""


def create(root: Path, name: str, owner: str, criticality: str, user_facing: bool = False) -> int:
    if not NAME.fullmatch(name):
        print(f"FAIL [new-module] invalid name '{name}': kebab-case expected, for example billing.")
        return 1
    if not OWNER.fullmatch(owner):
        print(f"FAIL [new-module] invalid owner '{owner}': a GitHub team, organisation/team, "
              "or a user when the project has no organisation, for example acme/billing "
              "(CODEOWNERS, docs/os/07-governance.md §7).")
        return 1
    folder = root / "modules" / name
    if folder.exists():
        print(f"FAIL [new-module] modules/{name} already exists.")
        return 1

    shutil.copytree(TEMPLATE, folder)
    values = {"{{MODULE_NAME}}": name, "{{OWNER}}": owner, "{{CRITICALITY}}": criticality}
    for file_ in (f for f in folder.rglob("*") if f.is_file()):
        text = file_.read_text(encoding="utf-8")
        for marker, value in values.items():
            text = text.replace(marker, value)
        file_.write_text(text, encoding="utf-8")

    if user_facing:
        manifest = folder / "MANIFEST.yaml"
        manifest.write_text(re.sub(r"^( *)user_facing: false", r"\1user_facing: true",
                                   manifest.read_text(encoding="utf-8"), flags=re.M), encoding="utf-8")

    runbook = criticality in NEEDS_RUNBOOK
    if runbook:
        (folder / "docs").mkdir(exist_ok=True)
        (folder / "docs" / "runbook.md").write_text(
            RUNBOOK.format(name=name, criticality=criticality), encoding="utf-8")
        manifest = folder / "MANIFEST.yaml"
        manifest.write_text(re.sub(r"^( *)# runbook:", r"\1runbook:",
                                   manifest.read_text(encoding="utf-8"), flags=re.M), encoding="utf-8")

    codeowners = root / ".github" / "CODEOWNERS"
    line = f"/modules/{name}/"
    if codeowners.is_file():
        content = codeowners.read_text(encoding="utf-8")
        if not any(existing.split()[:1] == [line] for existing in content.splitlines()):
            codeowners.write_text(content.rstrip("\n") + f"\n{line:<31}@{owner}\n", encoding="utf-8")
    else:
        print(f"WARNING: .github/CODEOWNERS missing; add \"{line} @{owner}\" to it.")

    print(f"Module created: modules/{name} (owner {owner}, criticality {criticality}"
          + (", user-facing" if user_facing else "") + (", runbook to fill in" if runbook else "") + ").")
    print("It holds only its description: fitness, check and test pass as it stands.")
    for number, step in enumerate(next_steps(root, name, criticality, user_facing), 1):
        print(("\nNext steps:\n" if number == 1 else "") + f"  {number}. {step}")
    return 0


def next_steps(root: Path, name: str, criticality: str, user_facing: bool) -> list[str]:
    """What the module's first pull requests will be asked, from facts nstack holds (D33)."""
    from napkinstack.fitness import plan  # here: plan reads HANDLE from this module

    steps = ["Creation ADR in docs/adr/: capability, boundary, alternatives",
             "MANIFEST.yaml: the responsibility in ONE sentence",
             f"modules/{name}/AGENTS.md: what is specific to the module, never the kernel",
             "Before its first file of code: commands.check and commands.test for its stack — "
             "fitness (M7) requires them once the module holds more than its description"]
    if user_facing or criticality in NEEDS_SHEET:
        why = "user-facing" if user_facing else f"criticality {criticality}"
        steps.append(f"Every pull request that changes its behaviour carries a test sheet ({why}), "
                     "run by a verifier who is not its author (T1–T5, docs/os/05-workflow.md §7)")
    cycle = plan.accepted_cycle(root) if plan.charter_accepted(root) else None
    if cycle is None:
        steps.append("The project is not framed: delivery work needs an accepted charter and cycle (K1), "
                     "or the out-of-cycle label with its justification (K4)")
    else:
        steps.append(f"Delivery work names a ready deliverable of {cycle[0].name} (K3), "
                     "or carries the out-of-cycle label with its justification (K4)")
    steps.append(f"nstack fitness, then nstack check {name} and nstack test {name}")
    return steps


def listing(root: Path, base: str | None = None) -> list[dict[str, str]] | None:
    """Every module — a folder holding a MANIFEST.yaml, contracts/ and platform/ included —
    or, given a base, those with a file changed since it; None when the base is unknown."""
    found = [{"name": manifest.parent.name, "folder": manifest.parent.relative_to(root).as_posix()}
             for manifest in find_manifests(root)]
    if base is None:
        return found
    if subprocess.run(["git", "rev-parse", "--verify", "--quiet", f"{base}^{{commit}}"], cwd=root,
                      capture_output=True).returncode:
        return None
    changed = subprocess.run(["git", "diff", "--name-only", f"{base}...HEAD"], cwd=root,
                             capture_output=True, text=True).stdout.split()
    return [module for module in found if any(path.startswith(f"{module['folder']}/") for path in changed)]


def _modules(root: Path) -> dict[str, Path]:
    """Name to folder, for every MANIFEST.yaml the fitness functions recognise."""
    return {manifest.parent.name: manifest.parent for manifest in find_manifests(root)}


def run_verb(root: Path, verb: str, name: str | None) -> int:
    known = _modules(root)
    if name is not None and name not in known:
        print(f"FAIL [{verb}] module '{name}' not found in {root}: no MANIFEST.yaml under that name.\n"
              f"      Known modules: {', '.join(known) or 'none'}.")
        return 1
    targets = [name] if name is not None else list(known)
    if not targets:
        print(f"No module in {root}: nothing to run.")
        return 0
    for target in targets:
        if not module_content(known[target]):
            print(f"-> {target}: holds only its description, nothing to {verb} yet.")
            continue
        manifest = known[target] / "MANIFEST.yaml"
        try:
            commands = (yaml.safe_load(manifest.read_text(encoding="utf-8")) or {}).get("commands") or {}
        except yaml.YAMLError as error:
            print(f"FAIL [{verb}] {manifest} unreadable: {error}\n      Action: nstack manifests.")
            return 1
        command = commands.get(verb)
        if not command:
            if verb in OPTIONAL:
                print(f"-> {target}: {verb} not declared, {OPTIONAL[verb]}.")
                continue
            print(f"FAIL [{verb}] module '{target}': commands.{verb} not declared in {manifest}.\n"
                  "      Action: declare the module stack's command there (docs/os/09-platform.md §2).")
            return 1
        print(f"-> {target}: {command}", flush=True)
        code = subprocess.run(command, shell=True, cwd=known[target]).returncode
        if code:
            print(f"FAIL [{verb}] module '{target}': `{command}` exited with {code}.")
            return code
    return 0
