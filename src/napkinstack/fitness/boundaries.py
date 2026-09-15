#!/usr/bin/env python3
"""
Fitness function 2 — Frontières entre modules.

Compare le graphe DÉCLARÉ (manifests) au graphe RÉEL (références dans le code),
puis vérifie l'absence de cycles (docs/os/02-modules.md §8, docs/os/07-gouvernance.md §3).

Contrôles :
  B1  aucune référence vers un module non déclaré dans `consumes`
  B2  aucun import direct de l'implémentation d'un autre module (src/, internal/)
  B3  aucune dépendance circulaire entre modules
  B4  dépendance déclarée mais jamais utilisée (avertissement)
  B5  aucun accès direct aux données d'un autre module (tables déclarées ailleurs)

DÉTECTION — à calibrer pour ton langage.
La détection est textuelle et volontairement simple : on cherche, dans les lignes
ressemblant à un import, les jetons identifiant un autre module. Deux sources :
  - le chemin du module   ("modules/billing", "@org/billing", "org.billing")
  - le champ `code_name` du manifest, s'il diffère du nom de dossier.
Ajuste IMPORT_HINTS et SOURCE_SUFFIXES selon ta stack. Un faux positif se corrige
en déclarant la dépendance ; un faux négatif se corrige en enrichissant les motifs.

Usage :  nstack boundaries [--root RACINE]
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
            data = yaml.safe_load(manifest.read_text(encoding="utf-8")) or {}
            mod = data.get("module") or {}
            name = mod.get("name") or manifest.parent.name
            modules[name] = {
                "path": manifest.parent,
                "dirname": manifest.parent.name,
                "code_name": mod.get("code_name") or name,
                "declared": {c.get("module") for c in (data.get("consumes") or [])
                             if c.get("module")},
                "owns_data": set(((data.get("data") or {}).get("owns")) or []),
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
    """Jetons qui identifient un autre module dans une ligne d'import."""
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

                    # B2 — import de l'implémentation interne
                    if any(marker in line.replace("\\", "/") for marker in INTERNAL_MARKERS):
                        fail("B2", f"{rel}:{lineno}",
                             f"'{name}' importe l'implémentation interne de '{other_name}'. "
                             f"Passer par son contrat (docs/os/03-contrats.md).")
                    # B1 — dépendance non déclarée
                    elif other_name not in mod["declared"]:
                        fail("B1", f"{rel}:{lineno}",
                             f"'{name}' référence '{other_name}' sans le déclarer dans "
                             f"consumes du MANIFEST. Déclarer le contrat consommé, "
                             f"ou supprimer la dépendance.")

    # B5 — accès aux données d'autrui
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
                         f"'{name}' accède à la table '{table}' possédée par '{owner}'. "
                         f"Couplage par la base (docs/os/08-qualite.md §8).")
                    break

    # B4 — déclaré mais inutilisé
    for name, mod in modules.items():
        for declared in mod["declared"]:
            if declared in modules and declared not in real[name]:
                warn("B4", name,
                     f"dépendance déclarée vers '{declared}' mais aucune utilisation détectée. "
                     f"Nettoyer le MANIFEST, ou ajuster les motifs de détection.")
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
        print(f"{len(modules)} module(s) : pas de frontière à vérifier.")
        return 0

    real = analyse(root, modules)

    for cycle in find_cycles(real):
        fail("B3", " → ".join(cycle),
             "dépendance circulaire : ces modules sont devenus inséparables "
             "(docs/os/02-modules.md §9).")

    print(f"Modules analysés : {len(modules)}")
    print("Graphe réel détecté :")
    for name in sorted(real):
        deps = ", ".join(sorted(real[name])) or "—"
        print(f"  {name} → {deps}")

    for w in warnings:
        print(f"  AVERTISSEMENT {w}")
    for f in failures:
        print(f"  ÉCHEC {f}")

    if failures:
        print(f"\n{len(failures)} violation(s) de frontière.")
        return 1
    print("Frontières : conformes.")
    return 0


if __name__ == "__main__":
    sys.exit(run(Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()))
