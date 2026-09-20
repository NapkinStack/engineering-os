#!/usr/bin/env python3
"""
Fitness function 2 — Boundaries between modules.

Compares the DECLARED graph (manifests) with the REAL graph read from the modules' files,
then checks for cycles (docs/os/02-modules.md §8, docs/os/07-governance.md §3). Two
modules know each other only through a contract: the real graph is the contracts a
module's files read, and any reference to another module's code is a violation.

Rules:
  B1  no contract read without being declared: a module reads only the contracts it
      provides, or consumes in the version it declares
  B2  no reference to another module's code: an import of it, or a path into its folder
  B3  no circular dependency between modules, through their contracts or their code
  B4  consumed contract never read (warning)
  B5  no direct access to another module's data (tables declared elsewhere)
  B6  a consumed contract is provided: its contract, version and module match a provides entry
  B7  a provided contract exists: its path holds its document, inside a module's folder
  B8  a contract consumed from a deprecated module (warning): a deprecated module takes no
      new consumer, and the existing ones migrate before its removal date

DETECTION — textual and deliberately simple, with no stack assumed.
  - A contract is read where a module's file names its path (contracts/billing-api/v1),
    its name and version (billing-api/v1), or its name as a quoted string ("billing-api").
  - Another module's code is referenced where an import line names its folder from the root
    (modules.billing, modules/billing, from modules import billing) or its package — opening
    the statement, or quoted as a module specifier, or alone on a Go import block's line — or
    where any line reaches into its folder (../billing/, modules/billing/). Its package is its
    folder's name, or `code_name` when the code names it otherwise (com.acme.billing). A
    relative path is read from the file's folder and from the module's — where the verbs run —
    and a path that names something of the module's own, or a contract it provides, is none.
A module's files are those git would commit, beyond its description (D33). A false positive
is fixed by rewording the line, or by `code_name`; a false negative by the stack's own import
checker, named in docs/tooling-profile.md and run by the module's `check` verb.

Usage :  nstack boundaries [--root ROOT]
"""

from __future__ import annotations
import posixpath
import re
import sys
from pathlib import Path

import yaml

from napkinstack.fitness.manifests import contract_entries, find_manifests, module_content

MODULE_DIRS = ["modules", "services", "apps", "packages"]
SOURCE_SUFFIXES = {
    ".py", ".ts", ".tsx", ".js", ".jsx", ".go", ".rs", ".java", ".kt",
    ".rb", ".php", ".cs", ".swift", ".scala", ".ex", ".exs",
}
SKIP_DIRS = {"node_modules", "dist", "build", "target", "vendor", ".git",
             "__pycache__", ".venv", "venv", "coverage", "generated"}
IMPORT_HINTS = re.compile(
    r"\b(import|from|require|use|using|include|#include|extern crate|go:import)\b|"
    r"^\s*(import|from)\s", re.IGNORECASE
)
TOO_LARGE = 1_000_000  # bytes: a generated file or a data dump, not code

failures: list[str] = []
warnings: list[str] = []


def fail(rule: str, where: str, message: str) -> None:
    failures.append(f"[{rule}] {where}\n      {message}")


def warn(rule: str, where: str, message: str) -> None:
    warnings.append(f"[{rule}] {where}\n      {message}")


def load_modules(root: Path) -> dict[str, dict]:
    modules: dict[str, dict] = {}
    for base in MODULE_DIRS:
        d = root / base
        if not d.is_dir():
            continue
        for manifest in sorted(d.glob("*/MANIFEST.yaml")):
            try:
                data = yaml.safe_load(manifest.read_text(encoding="utf-8")) or {}
            except yaml.YAMLError:
                continue  # reported by nstack manifests (M2)
            mod = data.get("module") if isinstance(data, dict) else None
            if not isinstance(mod, dict):
                continue  # reported by nstack manifests (M2)
            section = data.get("data") if isinstance(data.get("data"), dict) else {}
            owns = section.get("owns") if isinstance(section.get("owns"), list) else []
            name = mod.get("name") if isinstance(mod.get("name"), str) and mod["name"] else manifest.parent.name
            code_name = mod.get("code_name")
            deprecation = mod.get("deprecation") if isinstance(mod.get("deprecation"), dict) else {}
            modules[name] = {
                "path": manifest.parent,
                "dirname": manifest.parent.name,
                "code_name": code_name if isinstance(code_name, str) and code_name else name,
                "lifecycle": mod.get("lifecycle") if isinstance(mod.get("lifecycle"), str) else None,
                "removal": deprecation.get("removal_date"),
                "provides": contract_entries(data, "provides"),
                "consumes": contract_entries(data, "consumes"),
                "owns_data": {table for table in owns if isinstance(table, str)},
            }
    return modules


def read_files(module: dict):
    """(relative path, lines) of every text file the module holds beyond its description."""
    for relative in module_content(module["path"]):
        path = module["path"] / relative
        if any(part in SKIP_DIRS for part in Path(relative).parts) or not path.is_file():
            continue
        if path.stat().st_size > TOO_LARGE:
            continue
        data = path.read_bytes()
        if b"\0" in data[:8192]:
            continue  # binary
        yield relative, data.decode("utf-8", errors="ignore").splitlines()


def code_patterns(other: dict) -> tuple[re.Pattern, re.Pattern, re.Pattern]:
    """(import of its code, path into its folder). On an import line: its folder named from the
    root, or its package opening the statement (Python, Rust, Java) or quoted as a module
    specifier (JavaScript, TypeScript, Ruby). On any line: a relative or rooted path into its
    folder — ending where the folder's name does, so that ../billing.csv is not billing."""
    code, folder = re.escape(other["code_name"]), re.escape(other["dirname"])
    rooted = "|".join(MODULE_DIRS)
    imports = re.compile(rf"(?<![\w-])(?:{rooted})[./]{folder}(?![\w-])"
                         rf"|^\s*from\s+(?:{rooted})\s+import\s+(?:[\w\s]*,\s*)?{folder}(?![\w-])"
                         rf"|^\s*(?:from|import|(?:pub\s+)?use|extern\s+crate)\s+{code}(?![\w-])"
                         rf"|(?:\bfrom\s+|\b(?:require|import)\s*\(\s*|^\s*(?:import|require)\s+)"
                         rf"[\"'](?:@[\w.-]+/)?{code}(?:/[^\"']*)?[\"']")
    reach = re.compile(rf"(?<![\w.-])\.\./(?:\.\./)*{folder}(?=/|[\"'\s)]|$)"
                       rf"|(?<![\w-])(?:{rooted})/{folder}/")
    block = re.compile(rf"^\s*(?:\w+\s+)?\"[^\"]*(?<![\w-])(?:{rooted})/{folder}(?:/[^\"]*)?\"\s*$")
    return imports, reach, block


TOKEN = re.compile(r"[^\s'\"`)(,;]+")


def _names_a_contract(root: Path, mod: dict, relative: str, found: str, contracts: list[str]) -> bool:
    """Whether the path starting with `found` leads to a contract a module provides — read
    from the root, from the file's folder, or from the module's."""
    folder = mod["path"].relative_to(root).as_posix()
    places = [found] if not found.startswith("..") else [
        posixpath.normpath(posixpath.join(folder, posixpath.dirname(relative), found)),
        posixpath.normpath(posixpath.join(folder, found))]
    return any(place == contract or place.startswith(f"{contract}/") for place in places for contract in contracts)


def _lands_elsewhere(root: Path, mod: dict, relative: str, found: str, other: dict) -> bool:
    """Whether a path found in a module's file reaches into another module's folder: read from
    the file's folder and from the module's — where the verbs run — unless, from the file's
    folder, it names something the module holds."""
    folder = mod["path"].relative_to(root).as_posix()
    target = other["path"].relative_to(root).as_posix()
    if not found.startswith(".."):
        return True  # rooted: modules/<other>/
    from_file = posixpath.normpath(posixpath.join(folder, posixpath.dirname(relative), found))
    if from_file.startswith(f"{folder}/") and (root / from_file).exists():
        return False
    from_module = posixpath.normpath(posixpath.join(folder, found))
    return any(place == target or place.startswith(f"{target}/") for place in (from_file, from_module))


def contract_patterns(modules: dict[str, dict]) -> list[tuple[str, str | None, re.Pattern]]:
    """(contract, version or None, pattern) for every contract a module provides."""
    patterns = []
    for mod in modules.values():
        for provided in mod["provides"]:
            name, version = provided.get("contract"), provided.get("version")
            if not isinstance(name, str) or not isinstance(version, str):
                continue
            n, v = re.escape(name), re.escape(version)
            paths = [rf"(?<![\w-]){n}/{v}(?![\w-])"]
            if isinstance(provided.get("path"), str):
                paths.append(re.escape(provided["path"].strip("/")))
            patterns.append((name, version, re.compile("|".join(paths))))
            patterns.append((name, None, re.compile(rf"[\"'`]{n}[\"'`]")))
    return patterns


def check_contracts(root: Path, modules: dict[str, dict]) -> dict[str, dict[str, set[str]]]:
    """B6, B7, B1 and B4. Returns module -> producer -> contracts it reads from it."""
    provided = {(p.get("contract"), p.get("version")): name
                for name, mod in modules.items() for p in mod["provides"]}
    holders = [m.parent.relative_to(root).as_posix() for m in find_manifests(root)]

    for name, mod in modules.items():
        # B7 - what a module provides exists
        for p in mod["provides"]:
            label = f"{p.get('contract')} {p.get('version')}"
            path = root / str(p.get("path") or "")
            if not p.get("path") or not path.exists() or (path.is_dir() and not any(
                    f.is_file() for f in path.rglob("*"))):
                fail("B7", name, f"provides {label} at '{p.get('path')}', which holds no document.\n"
                                 "      Action: commit the contract there, or correct provides[].path.")
            elif not any(str(p.get("path")).strip("/").startswith(f"{holder}/") for holder in holders):
                fail("B7", name, f"provides {label} at '{p.get('path')}', outside every module's folder: "
                                 "nothing compares its versions (V1).\n      Action: keep it under contracts/.")
        # B6 - what a module consumes is provided
        for c in mod["consumes"]:
            key = (c.get("contract"), c.get("version"))
            producer = provided.get(key)
            offered = ", ".join(f"{k[0]} {k[1]} by {v}" for k, v in sorted(provided.items(), key=str)) or "none"
            if producer is None:
                fail("B6", name, f"consumes {key[0]} {key[1]}, which no module provides (provided: {offered}).\n"
                                 "      Action: consume a provided version, or have its producer declare it.")
            elif c.get("module") not in (None, producer):
                fail("B6", name, f"consumes {key[0]} {key[1]} from '{c.get('module')}', which is "
                                 f"provided by '{producer}'.\n      Action: name the producer.")
            # B8 - a deprecated producer. Reported, not refused: what is already declared is
            # bounded by the removal date, which M5 turns red once it has passed.
            elif modules[producer]["lifecycle"] == "deprecated":
                when = modules[producer]["removal"]
                warn("B8", name, f"consumes {key[0]} {key[1]} from '{producer}', which is deprecated"
                                 + (f" (removal {when})" if when else "")
                                 + ": a deprecated module takes no new consumer.\n      Action: "
                                 "migrate to the module that replaces it before that date "
                                 "(docs/os/02-modules.md §6); M5 turns red once it has passed.")

    patterns = contract_patterns(modules)
    reads: dict[str, dict[str, set[str]]] = {name: {} for name in modules}
    for name, mod in modules.items():
        own = {p.get("contract") for p in mod["provides"]}
        consumed = {(c.get("contract"), c.get("version")) for c in mod["consumes"]}
        seen: set[tuple[str, str | None]] = set()
        for relative, lines in read_files(mod):
            for lineno, line in enumerate(lines, 1):
                for contract, version, pattern in patterns:
                    if contract in own or not pattern.search(line):
                        continue
                    producer = next((v for k, v in provided.items() if k[0] == contract), None)
                    if producer:
                        reads[name].setdefault(producer, set()).add(contract)
                    where = f"{mod['path'].relative_to(root) / relative}:{lineno}"
                    versions = {v for c, v in consumed if c == contract}
                    # B1 - a contract read without being declared, or in another version
                    if (contract, version) in seen:
                        continue
                    seen.add((contract, version))
                    if not versions:
                        fail("B1", where, f"'{name}' reads contract '{contract}' without declaring it.\n"
                                          f"      Action: add {{contract: {contract}, version: "
                                          f"{version or '<version>'}, module: {producer}}} to consumes "
                                          "in its MANIFEST, or stop reading it.")
                    elif version is not None and version not in versions:
                        fail("B1", where, f"'{name}' reads {contract} {version} and consumes "
                                          f"{', '.join(sorted(versions))}.\n      Action: declare the version "
                                          "it reads (docs/os/03-contracts.md §4, the migration step).")
        # B4 - declared but never read
        for c in mod["consumes"]:
            if c.get("contract") and not any(c.get("contract") in read for read in reads[name].values()):
                warn("B4", name, f"consumes {c.get('contract')} {c.get('version')} but no file reads it.\n"
                                 "      Action: remove the entry, or name the contract where it is read.")
    return reads


def check_code(root: Path, modules: dict[str, dict]) -> dict[str, set[str]]:
    """B2 and B5. Returns module -> modules whose code it references."""
    code: dict[str, set[str]] = {name: set() for name in modules}
    others = {name: code_patterns(mod) for name, mod in modules.items()}
    contracts = [str(p.get("path")).strip("/") for mod in modules.values() for p in mod["provides"] if p.get("path")]
    for name, mod in modules.items():
        for relative, lines in read_files(mod):
            source = Path(relative).suffix in SOURCE_SUFFIXES
            for lineno, line in enumerate(lines, 1):
                imports = source and IMPORT_HINTS.search(line)
                text = line.replace("\\", "/")
                for other_name, (code_import, reach, block) in others.items():
                    if other_name == name:
                        continue
                    via_import = (imports and code_import.search(line)) or (source and block.search(line))
                    reaches = [m for m in reach.finditer(text)
                               if not _names_a_contract(root, mod, relative,
                                                        TOKEN.match(text, m.start()).group(), contracts)
                               and _lands_elsewhere(root, mod, relative, m.group(), modules[other_name])]
                    if not via_import and not reaches:
                        continue
                    code[name].add(other_name)
                    fail("B2", f"{mod['path'].relative_to(root) / relative}:{lineno}",
                         f"'{name}' references the code of '{other_name}'"
                         f"{' through an import' if via_import else ' through a path into its folder'}. "
                         f"Two modules know each other only through a contract (docs/os/03-contracts.md): "
                         f"read the one '{other_name}' provides.")

    # B5 - access to someone else's data
    for name, mod in modules.items():
        others_tables = {t: o for o, m in modules.items() if o != name for t in m["owns_data"]}
        if not others_tables:
            continue
        for relative, lines in read_files(mod):
            text = "\n".join(lines).lower()
            for table, owner in others_tables.items():
                if re.search(rf"\b(from|join|into|update|table)\s+[\"'`\[]?{re.escape(table.lower())}\b", text):
                    fail("B5", str(mod["path"].relative_to(root) / relative),
                         f"'{name}' accesses table '{table}' owned by '{owner}'. "
                         f"Coupling through the database (docs/os/08-quality.md §8).")
                    break
    return code


def find_cycles(graph: dict[str, set[str]]) -> list[list[str]]:
    cycles, stack, visiting, visited = [], [], set(), set()

    def walk(node: str) -> None:
        if node in visiting:
            cycles.append(stack[stack.index(node):] + [node])
            return
        if node in visited:
            return
        visiting.add(node)
        stack.append(node)
        for nxt in sorted(graph.get(node, ())):
            walk(nxt)
        stack.pop()
        visiting.discard(node)
        visited.add(node)

    for node in sorted(graph):
        walk(node)
    return cycles


def run(root: Path) -> int:
    failures.clear()
    warnings.clear()
    modules = load_modules(root)
    if not modules:
        print("0 module(s): no boundary to check.")
        return 0

    reads = check_contracts(root, modules)
    code = check_code(root, modules)
    graph = {name: set(reads[name]) | code[name] for name in modules}
    for cycle in find_cycles(graph):
        fail("B3", " → ".join(cycle),
             "circular dependency: these modules have become inseparable "
             "(docs/os/02-modules.md §9).")

    print(f"Modules checked: {len(modules)}")
    print("Real graph detected:")
    for name in sorted(modules):
        edges = [f"{producer} (contract {', '.join(sorted(contracts))})"
                 for producer, contracts in sorted(reads[name].items())]
        edges += [f"{other} (code)" for other in sorted(code[name])]
        print(f"  {name} → {', '.join(edges) or '-'}")

    for w in warnings:
        print(f"  WARNING {w}")
    for f in failures:
        print(f"  FAIL {f}")

    if failures:
        print(f"\n{len(failures)} boundary violation(s).")
        return 1
    print("Boundaries: compliant.")
    return 0


if __name__ == "__main__":
    sys.exit(run(Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()))
