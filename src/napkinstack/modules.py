"""
A project's modules: creation (nstack new-module) and standard verbs (nstack bootstrap,
check, test, run, e2e, clean, release), with no imposed stack (PRODUCT.md P1, PDR-0001 R5).

Each verb runs the command declared in the `commands` section of the module's
MANIFEST.yaml, from its folder, through the system shell. NapkinStack never assumes a
Makefile, a package.json or anything else: the project declares, nstack runs. Conventions
borrowed from Nx (`nx test <project>`) and moon (`moon run project:task`).
"""

from __future__ import annotations

import os
import re
import shutil
import shlex
import subprocess
from pathlib import Path

import yaml

from napkinstack import assurance
from napkinstack.fitness.manifests import (changed_files, contract_entries, find_manifests,
                                           module_content)

TEMPLATE = Path(__file__).resolve().parent / "templates" / "module"
NAME = re.compile(r"[a-z][a-z0-9-]*")
# A GitHub person: 1 to 39 characters, alphanumerics and single hyphens, none at either end.
# Defined once here, the identity rule's home: fitness/plan.py reads it for a charter's decider.
HANDLE = r"(?=[A-Za-z0-9-]{1,39}$)[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*"
LOGIN = r"[A-Za-z0-9](?:-?[A-Za-z0-9]){0,38}"  # the same rule, unanchored: a handle inside a sentence
OWNER = re.compile(  # same rule as copier.yml: organisation/team, or a GitHub user
    rf"[A-Za-z0-9-]+/[A-Za-z0-9._-]+|{HANDLE}")
OPTIONAL = {"bootstrap": "nothing to prepare", "e2e": "no end-to-end scenario", "clean": "nothing to clean"}  # undeclared: skipped
# Undeclared, skipped when every module is released; asked of one module by name, it is owed.
ALL_ONLY = {"release": "nothing to release"}
# What a criticality requires is the matrix of .nstack/handbook/05-workflow.md §7, read once (assurance).

RUNBOOK = """# Runbook - {name}

> Required for criticality={criticality} (.nstack/handbook/05-workflow.md §7).
> CI checks that it exists, not what it says: fill it in before going to production.

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
              "(CODEOWNERS, .nstack/handbook/07-governance.md §7).")
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

    runbook = assurance.requires(criticality, "runbook")
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
    for line in price(criticality, user_facing):
        print(f"  {line}")
    for number, step in enumerate(next_steps(root, name, criticality, user_facing), 1):
        print(("\nNext steps:\n" if number == 1 else "") + f"  {number}. {step}")
    return 0


CONTRACTS = Path(__file__).resolve().parent / "templates" / "contracts"
RESERVED = {"docs", "tests"}  # folders of the contracts module itself
CONTRACT = """# {name} — version 1

<One sentence: what this contract promises to whoever consumes it.>

<A diagram, with its legend, when the contract carries a flow or a state. Otherwise delete this line.>

## What it carries

<The fields, the files or the messages, each with its meaning and its unit. A reader who has
never seen the producer's code must be able to consume it from this page.>

## What it never does

<What a consumer must not rely on, although it may look true today.>

## Examples

<One valid example, and one a consumer must refuse.>
"""


def create_contract(root: Path, name: str, owner: str | None = None) -> int:
    """A contract, and — the first time — the module that holds every contract (PDR-0012): a
    project has no `contracts/` before it has a boundary between two modules to write down."""
    if not NAME.fullmatch(name):
        print(f"FAIL [new-contract] invalid name '{name}': kebab-case expected, for example session-audio.")
        return 1
    if name in RESERVED:
        print(f"FAIL [new-contract] '{name}' is reserved: it is a folder of the contracts module itself.")
        return 1
    try:
        answers = yaml.safe_load((root / ".copier-answers.yml").read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        answers = {}
    owner = owner or str(answers.get("owner_team") or "")
    if not OWNER.fullmatch(owner):
        print(f"FAIL [new-contract] no valid owner for the contracts module ('{owner}').\n"
              "      Action: pass --owner organisation/team — a boundary is never orphaned "
              "(.nstack/handbook/03-contracts.md §2).")
        return 1
    module, folder = root / "contracts", root / "contracts" / name
    if folder.exists():
        print(f"FAIL [new-contract] contracts/{name} already exists.\n      Action: a change to it is a new "
              "version beside the first, never an edit of it (.nstack/handbook/03-contracts.md §4).")
        return 1

    created = not (module / "MANIFEST.yaml").is_file()
    if created:
        shutil.copytree(CONTRACTS, module, dirs_exist_ok=True)
        values = {"{{OWNER}}": owner, "{{GITHUB_REPO}}": str(answers.get("github_repo") or "")}
        manifest = module / "MANIFEST.yaml"
        text = manifest.read_text(encoding="utf-8")
        for marker, value in values.items():
            text = text.replace(marker, value)
        manifest.write_text(text, encoding="utf-8")
        codeowners = root / ".github" / "CODEOWNERS"
        line = "/contracts/"
        if codeowners.is_file():
            content = codeowners.read_text(encoding="utf-8")
            if not any(existing.split()[:1] == [line] for existing in content.splitlines()):
                codeowners.write_text(content.rstrip("\n") + "\n\n# Contracts: the most critical boundary "
                                      f"in the system, never orphaned.\n{line:<31}@{owner}\n", encoding="utf-8")
        else:
            print(f"WARNING: .github/CODEOWNERS missing; add \"{line} @{owner}\" to it.")
        print(f"contracts/ created: the module that holds every contract (owner {owner}, criticality high).")
    (folder / "v1").mkdir(parents=True)
    (folder / "v1" / "README.md").write_text(CONTRACT.format(name=name), encoding="utf-8")
    print(f"Contract created: contracts/{name}/v1.")
    steps = [f"contracts/{name}/v1/README.md: what it promises, what it carries, an example",
             f"The producer's MANIFEST.yaml: a `provides` entry for contracts/{name}/v1",
             "Each consumer's MANIFEST.yaml: a `consumes` entry, with the version it reads",
             "contracts/tests/: the contract's tests, run on both sides (.nstack/handbook/03-contracts.md §5)",
             "Before the contract's first schema or test: commands.check and commands.test in "
             "contracts/MANIFEST.yaml — fitness (M7) asks for them once the module holds more than pages",
             "nstack fitness"]
    for number, step in enumerate(steps, 1):
        print(("\nNext steps:\n" if number == 1 else "") + f"  {number}. {step}")
    return 0


def price(criticality: str, user_facing: bool) -> list[str]:
    """What the chosen value requires, and what the value below would change — printed where the
    choice is made rather than discovered later (P6, D70). A reader who cannot see the neighbour
    cannot judge the declaration, which is the decision an agent took alone when nothing told it
    where to stop."""
    rows = [("a test sheet on every pull request that changes its behaviour, run by a verifier "
             "who is not its author", "sheet"),
            ("a runbook", "runbook"),
            ("every scenario of the sheet re-run at the head commit after a fix", "rerun_at_head")]
    required = [what for what, row in rows if assurance.requires(criticality, row, user_facing)]
    said = [f"At criticality {criticality} it needs: " + "; ".join(required) + "."
            if required else f"At criticality {criticality} it needs none of the sheet, the "
                             "runbook or a re-run at the head."]
    below = assurance.below(criticality)
    if below is not None:
        dropped = [what for what, row in rows
                   if assurance.requires(criticality, row, user_facing)
                   and not assurance.requires(below, row, user_facing)]
        said.append(f"At {below} it would drop: " + "; ".join(dropped) + "." if dropped
                    else f"At {below} nothing of that would change.")
    return said


def next_steps(root: Path, name: str, criticality: str, user_facing: bool) -> list[str]:
    """What the module's first pull requests will be asked, from facts nstack holds (D33)."""
    from napkinstack.fitness import plan  # here: plan reads HANDLE from this module

    steps = [f"Creation ADR in the project's docs/adr/, Scope: module {name}: capability, boundary, "
             "alternatives — and the criticality "
             f"with one sentence saying why {criticality} and not the value below or above; it is "
             "the decider who settles it",
             "MANIFEST.yaml: the responsibility in ONE sentence",
             f"modules/{name}/AGENTS.md: what is specific to the module, never the kernel",
             "Before its first file of code: commands.check and commands.test for its stack — "
             "fitness (M7) requires them once the module holds more than its description"]
    if assurance.requires(criticality, "sheet", user_facing):
        why = "user-facing" if user_facing else f"criticality {criticality}"
        steps.append(f"Every pull request that changes its behaviour carries a test sheet ({why}), "
                     "run by a verifier who is not its author (T1–T5, .nstack/handbook/05-workflow.md §7)")
    framed = plan.charter_accepted(root)
    cycle = plan.accepted_cycle(root) if framed else None
    if not framed:
        steps.append("The project is unframed: no cycle bounds its delivery work yet, and every "
                     "other rule applies. Framing is worth it when there is something to bound "
                     "(.nstack/playbooks/framing.md)")
    elif cycle is None:
        # The charter is accepted: only the next cycle is missing (D47).
        steps.append("No accepted cycle: delivery work needs one (K1), or the out-of-cycle label "
                     "with its justification (K4)")
    else:
        steps.append(f"Delivery work names a ready deliverable of {cycle[0].name} (K3), "
                     "or carries the out-of-cycle label with its justification (K4)")
    steps.append(f"nstack fitness, then nstack check {name} and nstack test {name}")
    return steps


def _load(manifest: Path) -> dict:
    try:
        data = yaml.safe_load(manifest.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError:
        return {}  # reported by nstack manifests (M2)
    return data if isinstance(data, dict) else {}


def _contract_sides(root: Path, changed: list[str]) -> set[str]:
    """The folders of the modules on either side of a contract version the change touches: the
    module that provides it, and those that declare it in consumes. The handbook asks for the
    checks of both sides (.nstack/handbook/03-contracts.md §5); the declared graph says who they are, so
    one repository needs no broker to know (D53)."""
    provided: dict[tuple[str, str], tuple[str, str]] = {}
    declared: list[tuple[str, list[dict]]] = []
    for manifest in find_manifests(root):
        data = _load(manifest)
        folder = manifest.parent.relative_to(root).as_posix()
        for entry in contract_entries(data, "provides"):
            key, path = (entry.get("contract"), entry.get("version")), entry.get("path")
            if isinstance(path, str) and all(isinstance(part, str) for part in key):
                provided[key] = (path.strip("/"), folder)
        declared.append((folder, contract_entries(data, "consumes")))
    touched = {key: folder for key, (path, folder) in provided.items()
               if any(file == path or file.startswith(f"{path}/") for file in changed)}
    return set(touched.values()) | {folder for folder, consumes in declared for entry in consumes
                                    if (entry.get("contract"), entry.get("version")) in touched}


def listing(root: Path, base: str | None = None,
            with_contract_sides: bool = False) -> list[dict[str, str]] | None:
    """Every module — a folder holding a MANIFEST.yaml, contracts/ and platform/ included — or,
    given a base, those with a file changed since it, and with `with_contract_sides` both sides
    of a contract version the change touches (D53); None when the base is unknown."""
    found = [{"name": manifest.parent.name, "folder": manifest.parent.relative_to(root).as_posix()}
             for manifest in find_manifests(root)]
    if base is None:
        return found
    if subprocess.run(["git", "rev-parse", "--verify", "--quiet", f"{base}^{{commit}}"], cwd=root,
                      capture_output=True).returncode:
        return None
    changed = changed_files(root, base)
    folders = {module["folder"] for module in found
               if any(path.startswith(f"{module['folder']}/") for path in changed)}
    if with_contract_sides:
        folders |= _contract_sides(root, changed)
    return [module for module in found if module["folder"] in folders]


def _modules(root: Path) -> dict[str, Path]:
    """Name to folder, for every MANIFEST.yaml the fitness functions recognise."""
    return {manifest.parent.name: manifest.parent for manifest in find_manifests(root)}


def release_order(known: dict[str, Path]) -> list[str]:
    """Every module after those its release assembles (D127); otherwise in their order."""
    wants = {}
    for target, folder in known.items():
        try:
            listed = (yaml.safe_load((folder / "MANIFEST.yaml").read_text(encoding="utf-8")) or {}).get("assembles")
        except (yaml.YAMLError, AttributeError):
            listed = None
        wants[target] = [other for other in listed if other in known] if isinstance(listed, list) else []
    order: list[str] = []

    def place(target: str, path: tuple[str, ...]) -> None:
        if target in order or target in path:  # a loop is M11's to refuse
            return
        for other in wants[target]:
            place(other, path + (target,))
        order.append(target)

    for target in known:
        place(target, ())
    return order


def run_verb(root: Path, verb: str, name: str | None, arguments: list[str] | None = None) -> int:
    known = _modules(root)
    if name is not None and name not in known:
        print(f"FAIL [{verb}] module '{name}' not found in {root}: no MANIFEST.yaml under that name.\n"
              f"      Known modules: {', '.join(known) or 'none'}.")
        return 1
    targets = [name] if name is not None else (release_order(known) if verb == "release" else list(known))
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
            if verb in OPTIONAL or (verb in ALL_ONLY and name is None):
                print(f"-> {target}: {verb} not declared, {OPTIONAL.get(verb) or ALL_ONLY[verb]}.")
                continue
            print(f"FAIL [{verb}] module '{target}': commands.{verb} not declared in {manifest}.\n"
                  "      Action: declare the module stack's command there (.nstack/handbook/09-platform.md §2).")
            return 1
        if arguments:
            command = " ".join([command, *map(shlex.quote, arguments)])
        environment = None
        if verb == "release":
            # Its artefacts, and nothing left from an earlier release: dist/<module>, emptied first.
            dist = root / "dist" / target
            odd = next((path for path in (dist.parent, dist) if path.is_symlink() or (path.exists() and not path.is_dir())), None)
            if odd is not None:
                print(f"FAIL [release] {odd.relative_to(root)} is a link or a file, not a folder of the project's own: "
                      "nothing is emptied through it.\n      Action: remove it, then release again.")
                return 1
            shutil.rmtree(dist, ignore_errors=True)
            dist.mkdir(parents=True)
            environment = {**os.environ, "NSTACK_DIST": str(dist.resolve())}
        if verb == "e2e":
            # Its evidence: a folder of its own, its output kept, its logs read after (ADR-0009).
            from napkinstack import evidence

            folder = evidence.prepare(root, known[target])
            if isinstance(folder, str):
                print(f"FAIL [e2e] module '{target}': {folder}")
                return 1
            print(f"-> {target}: {command}", flush=True)
            code, held = evidence.run(command, known[target], {**os.environ, "NSTACK_EVIDENCE": str(folder.resolve())},
                                      folder)
            passed = evidence.finish(root, target, known[target], folder, code, held)
            if code:
                print(f"FAIL [{verb}] module '{target}': `{command}` exited with {code}.")
                return code
            if not passed:
                return 1
            continue
        print(f"-> {target}: {command}", flush=True)
        code = subprocess.run(command, shell=True, cwd=known[target], env=environment).returncode
        if code:
            print(f"FAIL [{verb}] module '{target}': `{command}` exited with {code}.")
            return code
    return 0
