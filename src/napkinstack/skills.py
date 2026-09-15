"""
Génère les skills Claude Code à partir des playbooks.

Les playbooks sont la SOURCE DE VÉRITÉ (docs/os/06-decisions.md §9). Les skills en
sont dérivées : fichiers générés, jamais édités à la main, jamais commités.

Pourquoi générer plutôt qu'écrire directement des skills :
  - portabilité — l'OS doit rester utilisable par un agent qui ne connaît pas les
    skills. Un outil est un adaptateur, jamais une fondation
    (docs/tooling-profile.md).
  - source unique — deux copies d'une même règle divergent toujours.

Contrôles (mode --check, exécuté en CI) :
  S1  chaque playbook a une entrée dans .nstack/skills.yaml
  S2  chaque entrée pointe vers un playbook existant
  S3  les skills générées correspondent aux playbooks actuels
  S4  nom et description conformes à la spécification Agent Skills

S3 ne s'applique que si .claude/skills/ existe. Les skills sont gitignorées : un clone
vierge, donc la CI, n'en a aucune, et aucune ne peut y être désynchronisée.

Une racine sans playbooks/ ni .nstack/skills.yaml, comme le dépôt NapkinStack lui-même,
n'est pas concernée.

Usage :
    nstack skills [--root RACINE]            # génère .claude/skills/
    nstack skills --check [--root RACINE]    # vérifie sans écrire
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

import yaml

SKILL_NAME = re.compile(r"[a-z0-9]+(-[a-z0-9]+)*")
BANNER = (
    "<!-- GÉNÉRÉ depuis {source} par nstack skills — NE PAS ÉDITER.\n"
    "     Modifier le playbook, puis relancer `nstack skills`. -->"
)
MAPPING = Path(".nstack") / "skills.yaml"


def normalise(text: str) -> str:
    """Description sur une seule ligne, pour un frontmatter YAML propre."""
    return " ".join(text.split())


def build(root: Path, name: str, entry: dict) -> tuple[Path, str]:
    body = (root / entry["source"]).read_text(encoding="utf-8")
    # Sérialisé, jamais concaténé : « : » ou « # » dans une description casserait le YAML.
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
            print(f"Skills : non applicable, ni playbooks/ ni {MAPPING} dans {root}.")
            return 0
        print(f"  ÉCHEC [S1] {MAPPING} introuvable dans {root} : aucun playbook n'a d'entrée.\n"
              f"      Créer {MAPPING}, une entrée par playbook (source, description).")
        return 1

    mapping = (yaml.safe_load(map_file.read_text(encoding="utf-8")) or {}).get("skills") or {}
    failures: list[str] = []

    # S1 — tout playbook doit avoir une entrée
    declared = {Path(e["source"]).name for e in mapping.values() if e.get("source")}
    for playbook in sorted(playbook_dir.glob("*.md")):
        if playbook.name not in declared:
            failures.append(
                f"[S1] {playbook.relative_to(root)} n'a pas d'entrée dans "
                f"{MAPPING}.\n      Ajouter une description, ou retirer le "
                f"playbook s'il ne sert plus (docs/os/10-mesure.md §6)."
            )

    # S2 — toute entrée doit pointer vers un playbook existant
    for name, entry in mapping.items():
        if not (root / entry.get("source", "")).is_file():
            failures.append(f"[S2] skill '{name}' : source introuvable ({entry.get('source')})")
        if not normalise(entry.get("description", "")):
            failures.append(f"[S2] skill '{name}' : description vide")

    # S4 — spécification Agent Skills (https://agentskills.io/specification)
    for name, entry in mapping.items():
        if len(name) > 64 or not SKILL_NAME.fullmatch(name):
            failures.append(
                f"[S4] skill '{name}' : nom invalide. 1 à 64 caractères, a-z, 0-9 et "
                "tirets simples, sans tiret au début ni à la fin."
            )
        if len(normalise(entry.get("description", ""))) > 1024:
            failures.append(f"[S4] skill '{name}' : description de plus de 1024 caractères")

    if failures:
        for failure in failures:
            print(f"  ÉCHEC {failure}")
        return 1

    # S3 — génération ou comparaison
    if check_only and not skill_dir.is_dir():
        print(f"Skills : S1, S2 et S4 conformes. S3 non applicable : "
              f"{skill_dir.relative_to(root)}/ absent, aucune skill générée ici.")
        return 0

    stale: list[str] = []
    written = 0
    for name, entry in sorted(mapping.items()):
        path, content = build(root, name, entry)
        if check_only:
            if not path.is_file():
                stale.append(f"[S3] skill '{name}' absente de .claude/skills/")
            elif digest(path.read_text(encoding="utf-8")) != digest(content):
                stale.append(f"[S3] skill '{name}' désynchronisée de {entry['source']}")
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
            written += 1

    if check_only:
        if stale:
            for item in stale:
                print(f"  ÉCHEC {item}")
            print("\nLancer `nstack skills` pour régénérer.")
            return 1
        print(f"Skills : {len(mapping)} synchronisées avec les playbooks.")
        return 0

    print(f"Skills générées dans .claude/skills/ : {written}")
    for name in sorted(mapping):
        print(f"  - {name}")
    print("\nElles se déclenchent seules selon leur description ; l'agent peut aussi")
    print("les invoquer par leur nom. Le kernel reste dans AGENTS.md.")
    return 0
