#!/usr/bin/env python3
"""
Fitness function 1 — Validation des manifests.

Vérifie que chaque module déclare ce qu'il doit déclarer et que son état de
cycle de vie est cohérent (docs/os/02-modules.md §6, docs/os/07-gouvernance.md §3).

Contrôles :
  M1  chaque module possède un MANIFEST.yaml
  M2  champs obligatoires présents
  M3  valeurs de lifecycle / criticality valides
  M4  responsabilité en UNE phrase (pas de "et" coordonnant deux capacités)
  M5  module Déprécié → removal_date obligatoire et non dépassée
  M6  contrat deprecated → removal_date obligatoire et non dépassée
  M7  verbes standards déclarés (check / test au minimum)
  M8  runbook obligatoire si criticality >= eleve
  M9  enveloppe de fichiers complète (AGENTS.md, README.md, tests/)

Usage :  nstack manifests [--root RACINE]
Sortie :  0 si tout passe, 1 sinon. Chaque échec explique la règle violée.
"""

from __future__ import annotations
import sys
import datetime
from pathlib import Path

import yaml

LIFECYCLES = {"Proposé", "Actif", "Maintenance", "Déprécié", "Retiré"}
CRITICALITIES = {"prototype", "standard", "eleve", "critique"}
REQUIRED_FIELDS = ["name", "responsibility", "owner", "lifecycle", "criticality"]
REQUIRED_COMMANDS = ["check", "test"]
MODULE_DIRS = ["modules", "services", "apps", "packages", "contracts", "platform"]
MODULE_BASES = ["modules", "services", "apps", "packages"]  # bases dont chaque dossier est un module
SECTIONS = {"module": dict, "provides": list, "consumes": list, "data": dict,
            "commands": dict, "docs": dict, "dependencies": list}
TYPES = {dict: "dictionnaire", list: "liste"}

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
    """Dossiers de module sans MANIFEST.yaml (M1)."""
    return [enfant for base in MODULE_BASES if (root / base).is_dir()
            for enfant in sorted((root / base).iterdir())
            if enfant.is_dir() and not enfant.name.startswith(".") and not (enfant / "MANIFEST.yaml").is_file()]


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
        fail(rel, "M2", f"MANIFEST.yaml illisible : {exc}")
        return
    if not isinstance(data, dict):
        fail(rel, "M2", "MANIFEST.yaml doit être un dictionnaire YAML (sections module, commands, docs…).")
        return
    for section, attendu in SECTIONS.items():
        if data.get(section) is not None and not isinstance(data[section], attendu):
            fail(rel, "M2", f"section {section} : {TYPES[attendu]} attendu, "
                            f"{type(data[section]).__name__} trouvé.")
            data[section] = attendu()

    mod = data.get("module") or {}

    # M2 — champs obligatoires
    for field in REQUIRED_FIELDS:
        if not mod.get(field):
            fail(rel, "M2", f"champ obligatoire manquant : module.{field}")

    # M3 — valeurs valides
    lifecycle = mod.get("lifecycle")
    if lifecycle and lifecycle not in LIFECYCLES:
        fail(rel, "M3", f"lifecycle invalide : '{lifecycle}'. Attendu : {sorted(LIFECYCLES)}")
    criticality = mod.get("criticality")
    if criticality and criticality not in CRITICALITIES:
        fail(rel, "M3", f"criticality invalide : '{criticality}'. Attendu : {sorted(CRITICALITIES)}")

    # M4 — responsabilité en une phrase
    resp = (mod.get("responsibility") or "").strip()
    if resp:
        if resp.count(".") > 1:
            warn(rel, "M4", "responsabilité en plusieurs phrases : le module fait-il deux choses ?")
        if " et " in resp.lower() and len(resp.split()) > 12:
            warn(rel, "M4", f"responsabilité contient 'et' : capacité cohérente ? → \"{resp}\"")

    # M5 — dépréciation du module
    if lifecycle == "Déprécié":
        dep = mod.get("deprecation")
        dep = dep if isinstance(dep, dict) else {}
        removal = parse_date(dep.get("removal_date"))
        if not removal:
            fail(rel, "M5", "module Déprécié sans module.deprecation.removal_date valide (AAAA-MM-JJ)")
        elif removal < today:
            fail(rel, "M5", f"date de retrait dépassée ({removal}). État intermédiaire permanent — "
                            "retirer le module ou superséder la décision.")

    # M6 — dépréciation des contrats produits
    for provided in data.get("provides") or []:
        if not isinstance(provided, dict):
            fail(rel, "M2", "entrée de provides : dictionnaire attendu (contract, version, stability).")
            continue
        if provided.get("stability") == "deprecated":
            name = f"{provided.get('contract')}@{provided.get('version')}"
            removal = parse_date(provided.get("removal_date"))
            if not removal:
                fail(rel, "M6", f"contrat déprécié {name} sans removal_date")
            elif removal < today:
                fail(rel, "M6", f"contrat {name} : date de retrait dépassée ({removal}). "
                                "Terminer la contraction (docs/os/03-contrats.md §4).")

    # M7 — verbes standards
    commands = data.get("commands") or {}
    for verb in REQUIRED_COMMANDS:
        if not commands.get(verb):
            fail(rel, "M7", f"verbe standard manquant : commands.{verb} "
                            "(docs/os/09-plateforme.md §2)")

    # M8 — runbook si criticité élevée
    if criticality in {"eleve", "critique"}:
        runbook = (data.get("docs") or {}).get("runbook")
        if not runbook or not (path.parent / runbook).is_file():
            fail(rel, "M8", f"criticality={criticality} exige un runbook existant "
                            "(docs/os/08-qualite.md §7)")

    # M9 — enveloppe de fichiers
    for expected in ["AGENTS.md", "README.md"]:
        if not (path.parent / expected).is_file():
            fail(rel, "M9", f"fichier d'enveloppe manquant : {expected}")
    if not (path.parent / "tests").is_dir() and criticality != "prototype":
        fail(rel, "M9", "dossier tests/ absent")


def run(root: Path) -> int:
    failures.clear()
    warnings.clear()
    today = datetime.date.today()
    manifests = find_manifests(root)
    orphans = find_orphans(root)
    if not manifests and not orphans:
        print("Aucun MANIFEST.yaml trouvé. Rien à valider.")
        return 0
    for orphan in orphans:
        fail(orphan.name, "M1", f"{orphan.relative_to(root)}/ n'a pas de MANIFEST.yaml. "
                                "Action : le créer, ou créer le module avec nstack new-module.")

    for manifest in manifests:
        check_manifest(manifest, today)

    print(f"Manifests analysés : {len(manifests)}")
    for w in warnings:
        print(f"  AVERTISSEMENT {w}")
    for f in failures:
        print(f"  ÉCHEC {f}")

    if failures:
        print(f"\n{len(failures)} violation(s). Voir docs/os/02-modules.md et docs/os/07-gouvernance.md.")
        return 1
    print("Manifests : conformes.")
    return 0


if __name__ == "__main__":
    sys.exit(run(Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()))
