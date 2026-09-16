#!/usr/bin/env python3
"""
Fitness function 2 — Boundaries between modules.

Compares the DECLARED graph (manifests) with the REAL graph (references in the code),
then checks for cycles (docs/os/02-modules.md §8, docs/os/07-gouvernance.md §3).

Rules:
  B1  no reference to a module absent from `consumes`
  B2  no direct import of another module's implementation (src/, internal/)
  B3  no circular dependency between modules
  B4  dependency declared but never used (warning)
  B5  no direct access to another module's data (tables declared elsewhere)

DETECTION — calibrate this for your language.
Detection is textual and deliberately simple: in lines that look like an import, it
looks for the tokens identifying another module. Two sources:
  - the module path       ("modules/billing", "@org/billing", "org.billing")
  - the manifest's `code_name` field, when it differs from the folder name.
Adjust IMPORT_HINTS and SOURCE_SUFFIXES for your stack. A false positive is fixed by
declaring the dependency; a false negative by enriching the patterns.

Usage :  nstack boundaries [--root ROOT]
"""

from __future__ import annotations
import re
import sys
from pathlib import Path

import yaml

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
INTERNAL_MARKERS = ("/src/", "/internal/", "/lib/internal", "\\src\\")

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
            consumes = data.get("consumes") if isinstance(data.get("consumes"), list) else []
            section = data.get("data") if isinstance(data.get("data"), dict) else {}
            owns = section.get("owns") if isinstance(section.get("owns"), list) else []
            name = mod.get("name") or manifest.parent.name
            modules[name] = {
                "path": manifest.parent,
                "dirname": manifest.parent.name,
                "code_name": mod.get("code_name") or name,
                "declared": {c.get("module") for c in consumes if isinstance(c, dict) and c.get("module")},
                "owns_data": set(owns),
                "raw": data,
            }
    return modules


def iter_sources(module_path: Path):
    for path in module_path.rglob("*"):
        if not path.is_file() or path.suffix not in SOURCE_SUFFIXES:
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        yield path


def tokens_for(other: dict) -> list[str]:
    """Tokens identifying another module inside an import line."""
    return list({
        f"modules/{other['dirname']}",
        f"services/{other['dirname']}",
        f"packages/{other['dirname']}",
        f"/{other['code_name']}/",
        f"@{other['code_name']}",
        f".{other['code_name']}.",
    })


def analyse(root: Path, modules: dict[str, dict]) -> dict[str, set[str]]:
    real: dict[str, set[str]] = {name: set() for name in modules}

    for name, mod in modules.items():
        for source in iter_sources(mod["path"]):
            try:
                lines = source.read_text(encoding="utf-8", errors="ignore").splitlines()
            except OSError:
                continue
            for lineno, line in enumerate(lines, 1):
                if not IMPORT_HINTS.search(line):
                    continue
                for other_name, other in modules.items():
                    if other_name == name:
                        continue
                    if not any(tok in line for tok in tokens_for(other)):
                        continue
                    real[name].add(other_name)
                    rel = source.relative_to(root)

                    # B2 - import of the internal implementation
                    if any(marker in line.replace("\\", "/") for marker in INTERNAL_MARKERS):
                        fail("B2", f"{rel}:{lineno}",
                             f"'{name}' imports the internal implementation of '{other_name}'. "
                             f"Go through its contract (docs/os/03-contrats.md).")
                    # B1 - undeclared dependency
                    elif other_name not in mod["declared"]:
                        fail("B1", f"{rel}:{lineno}",
                             f"'{name}' references '{other_name}' without declaring it in "
                             f"the MANIFEST consumes section. Declare the contract consumed, "
                             f"or remove the dependency.")

    # B5 - access to someone else's data
    for name, mod in modules.items():
        others_tables = {t: o for o, m in modules.items() if o != name
                         for t in m["owns_data"]}
        if not others_tables:
            continue
        for source in iter_sources(mod["path"]):
            text = source.read_text(encoding="utf-8", errors="ignore").lower()
            for table, owner in others_tables.items():
                if re.search(rf"\b(from|join|into|update|table)\s+[\"'`\[]?{re.escape(table.lower())}\b", text):
                    fail("B5", str(source.relative_to(root)),
                         f"'{name}' accesses table '{table}' owned by '{owner}'. "
                         f"Coupling through the database (docs/os/08-qualite.md §8).")
                    break

    # B4 - declared but unused
    for name, mod in modules.items():
        for declared in mod["declared"]:
            if declared in modules and declared not in real[name]:
                warn("B4", name,
                     f"dependency declared on '{declared}' but no use detected. "
                     f"Clean up the MANIFEST, or adjust the detection patterns.")
    return real


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

    if len(modules) < 2:
        print(f"{len(modules)} module(s): no boundary to check.")
        return 0

    real = analyse(root, modules)

    for cycle in find_cycles(real):
        fail("B3", " → ".join(cycle),
             "circular dependency: these modules have become inseparable "
             "(docs/os/02-modules.md §9).")

    print(f"Modules checked: {len(modules)}")
    print("Real graph detected:")
    for name in sorted(real):
        deps = ", ".join(sorted(real[name])) or "-"
        print(f"  {name} → {deps}")

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
