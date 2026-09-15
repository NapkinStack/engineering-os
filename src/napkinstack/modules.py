"""
Modules d'un projet : création (nstack new-module) et verbes standards (nstack bootstrap,
check, test, run), sans stack imposée (PRODUCT.md P1, PDR-0001 R5).

Chaque verbe exécute la commande déclarée dans la section `commands` du MANIFEST.yaml du
module, depuis son dossier, par le shell du système. NapkinStack ne suppose jamais un
Makefile, un package.json ni rien d'autre : le projet déclare, nstack exécute. Conventions
reprises de Nx (`nx test <projet>`) et de moon (`moon run projet:tâche`).
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import yaml

from napkinstack.fitness.manifests import find_manifests

GABARIT = Path(__file__).resolve().parent / "templates" / "module"
NOM = re.compile(r"[a-z][a-z0-9-]*")
EQUIPE = re.compile(r"[A-Za-z0-9-]+/[A-Za-z0-9._-]+")  # même règle que copier.yml
FACULTATIFS = {"bootstrap"}  # absent : rien à préparer

RUNBOOK = """# Runbook — {nom}

> Obligatoire pour criticality={criticite} (docs/os/08-qualite.md §7).
> Un runbook vide fait échouer la CI. À remplir avant la mise en production.

## Alertes et réponses
| Alerte | Signification | Première action |
|---|---|---|
| | | |

## Rollback
<Procédure testée, pas supposée.>

## Vérification post-déploiement
<Ce qu'on regarde, et pendant combien de temps.>

## Dépendances et dégradation
<Que se passe-t-il si chaque dépendance est indisponible ?>
"""


def nouveau(root: Path, nom: str, owner: str, criticite: str) -> int:
    if not NOM.fullmatch(nom):
        print(f"ÉCHEC [new-module] nom '{nom}' invalide : kebab-case attendu, par exemple facturation.")
        return 1
    if not EQUIPE.fullmatch(owner):
        print(f"ÉCHEC [new-module] owner '{owner}' invalide : une équipe GitHub organisation/équipe, "
              "par exemple acme/facturation (CODEOWNERS, docs/os/07-gouvernance.md §7).")
        return 1
    dossier = root / "modules" / nom
    if dossier.exists():
        print(f"ÉCHEC [new-module] modules/{nom} existe déjà.")
        return 1

    shutil.copytree(GABARIT, dossier)
    valeurs = {"{{MODULE_NAME}}": nom, "{{OWNER}}": owner, "{{CRITICALITY}}": criticite}
    for fichier in (f for f in dossier.rglob("*") if f.is_file()):
        texte = fichier.read_text(encoding="utf-8")
        for marque, valeur in valeurs.items():
            texte = texte.replace(marque, valeur)
        fichier.write_text(texte, encoding="utf-8")

    runbook = criticite in {"eleve", "critique"}
    if runbook:
        (dossier / "docs").mkdir(exist_ok=True)
        (dossier / "docs" / "runbook.md").write_text(RUNBOOK.format(nom=nom, criticite=criticite),
                                                      encoding="utf-8")
        manifest = dossier / "MANIFEST.yaml"
        manifest.write_text(re.sub(r"^( *)# runbook:", r"\1runbook:",
                                   manifest.read_text(encoding="utf-8"), flags=re.M), encoding="utf-8")

    codeowners = root / ".github" / "CODEOWNERS"
    ligne = f"/modules/{nom}/"
    if codeowners.is_file():
        contenu = codeowners.read_text(encoding="utf-8")
        if not any(existante.split()[:1] == [ligne] for existante in contenu.splitlines()):
            codeowners.write_text(contenu.rstrip("\n") + f"\n{ligne:<31}@{owner}\n", encoding="utf-8")
    else:
        print(f"AVERTISSEMENT : .github/CODEOWNERS absent ; y ajouter « {ligne} @{owner} ».")

    print(f"Module créé : modules/{nom} (owner {owner}, criticité {criticite})"
          + (", runbook à remplir" if runbook else "") + ".")
    print("\nÉtapes suivantes :")
    print("  1. ADR de création dans docs/adr/ : capacité, frontière, alternatives")
    print("  2. MANIFEST.yaml : responsabilité en UNE phrase, puis les commandes check et test de la stack")
    print(f"  3. modules/{nom}/AGENTS.md : le spécifique du module, jamais le kernel")
    print(f"  4. nstack fitness, puis nstack check {nom} et nstack test {nom}")
    return 0
