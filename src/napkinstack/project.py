"""
Création et mise à jour d'un projet (PDR-0001), par Copier (ADR-0001).

Copier est piloté par son API, jamais en mode « unsafe ». Ses refus arrivent avant toute
modification et sont traduits en messages qui nomment la règle, l'endroit et l'action (P6).

Une mise à jour part d'un état commité et pose la version cible, fusionnée avec les
adaptations du projet, sur la branche nstack/update-<version>. Un conflit n'est jamais
commité : il reste marqué dans le fichier pour l'équipe, et le hook check-merge-conflict
comme la CI refusent tout marqueur restant.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import yaml

from napkinstack import __version__

SOURCE = "https://github.com/NapkinStack/engineering-os.git"
ANSWERS = ".copier-answers.yml"
DOWNGRADE = re.compile(r"You are downgrading from (\S+) to (\S+)\.")


def default_ref() -> str:
    """Le squelette de la version du moteur : ils montent ensemble (PDR-0001 R2)."""
    return f"v{__version__}"


def _git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=root, capture_output=True, text=True)


def _answers(root: Path) -> dict:
    return yaml.safe_load((root / ANSWERS).read_text(encoding="utf-8")) or {}


def _explain(exc: Exception, command: str, where: Path, source: str, ref: str) -> str:
    """Traduit un refus de Copier (P6)."""
    from copier.errors import UnsafeTemplateError

    text = str(exc).strip()
    action = "      Action : "
    if isinstance(exc, UnsafeTemplateError):
        return (f"ÉCHEC [{command}] Le gabarit {source} exécute du code ({text.splitlines()[0]}) : "
                f"refusé (ADR-0001).\n{action}vérifier --source ; NapkinStack n'active jamais ces fonctions.")
    if text.startswith("Validation error for question '"):
        question, _, detail = text.removeprefix("Validation error for question '").partition("': ")
        return (f"ÉCHEC [{command}] Réponse refusée pour {question} : {detail.strip()}\n"
                f"{action}relancer avec une valeur conforme.")
    if text.startswith("Destination repository is dirty"):
        return (f"ÉCHEC [{command}] Arbre de travail modifié dans {where} : une mise à jour part d'un "
                f"état commité (PDR-0001).\n{action}commiter ou remiser (git stash), puis relancer.")
    if match := DOWNGRADE.search(text):
        return (f"ÉCHEC [{command}] Version cible {match[2]} antérieure à celle du projet ({match[1]}) : "
                f"pas de retour arrière (PDR-0001).\n{action}utiliser nstack {match[1]} ou plus récent.")
    if text.startswith("Updating is only supported in git-tracked subprojects"):
        return (f"ÉCHEC [{command}] {where} n'est pas un dépôt git : la fusion s'appuie sur "
                f"l'historique.\n{action}git init, commit, puis relancer.")
    if text.startswith("Cannot update: version from last update not detected"):
        return (f"ÉCHEC [{command}] Le projet ne vient pas d'une version publiée (_commit de {ANSWERS}) : "
                f"aucune base de fusion.\n{action}créer le projet depuis un tag vX.Y.Z.")
    if isinstance(exc, OSError) or text == "Local template must be a directory.":
        detail = [line.split("|", 1)[-1].strip() for line in text.splitlines() if line.strip()][-1]
        return (f"ÉCHEC [{command}] Gabarit {source} en version {ref} inaccessible : {detail}\n"
                f"{action}vérifier --source et --ref (tag vX.Y.Z), et l'accès au réseau.")
    return f"ÉCHEC [{command}] Copier : {text}"


def init(destination: Path, answers: dict[str, str | None], source: str, ref: str) -> int:
    import copier
    from copier.errors import CopierError

    from napkinstack.doctor import CHECKLIST

    destination = destination.resolve()
    if destination.exists() and (not destination.is_dir() or any(destination.iterdir())):
        print(f"ÉCHEC [init] {destination} n'est pas vide : nstack init crée un projet neuf.\n"
              "      Action : choisir un dossier absent ou vide.")
        return 1
    data = {question: value for question, value in answers.items() if value is not None}
    try:
        copier.run_copy(source, destination, data=data, vcs_ref=ref, quiet=True, unsafe=False)
    except (CopierError, ValueError, OSError) as exc:
        print(_explain(exc, "init", destination, source, ref))
        return 1

    created = _answers(destination)
    version = created.get("_commit", ref)
    for args in (("init", "--quiet", "--initial-branch=main"), ("add", "--all"),
                 ("commit", "--quiet", "--message", f"Création du projet, NapkinStack {version}")):
        result = _git(destination, *args)
        if result.returncode:
            print(f"ÉCHEC [init] Projet généré dans {destination}, mais `git {args[0]}` a échoué :\n"
                  f"      {result.stderr.strip()}\n"
                  "      Action : corriger (identité : git config user.name et user.email), "
                  "puis git add --all && git commit.")
            return 1

    print(f"Projet créé dans {destination}, NapkinStack {version}, commit initial sur main.")
    print("\nÉtapes suivantes :")
    print(f"  1. cd {destination} && pre-commit install")
    print(f"  2. Créer le dépôt GitHub {created.get('github_repo')}, y pousser main, puis appliquer "
          "ces réglages :")
    for _, reglage, _ in CHECKLIST:
        print(f"     - [ ] {reglage}")
    print("  3. Vérifier le poste et GitHub, en lecture seule : nstack doctor (jeton : voir le README)")
    return 0


def update(root: Path, ref: str) -> int:
    import copier
    from copier.errors import CopierError

    if not (root / ANSWERS).is_file():
        print(f"ÉCHEC [update] {ANSWERS} introuvable dans {root} : ce dossier n'est pas un projet "
              "créé par nstack init.\n      Action : lancer la commande à la racine du projet, "
              "ou préciser --root.")
        return 1
    previous = str(_answers(root).get("_commit"))
    if previous == ref:
        print(f"Déjà à jour : NapkinStack {ref}.")
        return 0
    branch = f"nstack/update-{ref}"
    if _git(root, "rev-parse", "--verify", "--quiet", f"refs/heads/{branch}").returncode == 0:
        print(f"ÉCHEC [update] La branche {branch} existe déjà dans {root}.\n"
              "      Action : la fusionner ou la supprimer (git branch -D), puis relancer.")
        return 1
    try:
        copier.run_update(root, vcs_ref=ref, overwrite=True, skip_answered=True, defaults=True,
                          conflict="inline", quiet=True, unsafe=False)
    except (CopierError, ValueError, OSError) as exc:
        print(_explain(exc, "update", root, str(_answers(root).get("_src_path")), ref))
        return 1

    if not _git(root, "status", "--porcelain").stdout.strip():
        print(f"Déjà à jour : rien ne change entre NapkinStack {previous} et {ref}.")
        return 0
    current = str(_answers(root).get("_commit"))
    switch = _git(root, "switch", "--create", branch)
    if switch.returncode:
        print(f"ÉCHEC [update] Branche {branch} impossible à créer : {switch.stderr.strip()}\n"
              "      Action : les changements restent dans l'arbre de travail ; créer la branche "
              "à la main, puis commiter.")
        return 1
    conflicts = _git(root, "diff", "--name-only", "--diff-filter=U").stdout.splitlines()
    if conflicts:
        print(f"ÉCHEC [update] NapkinStack {previous} → {current} : conflits avec les adaptations "
              f"du projet, marqués sur la branche {branch} dans :")
        for path in conflicts:
            print(f"  - {path}")
        print("      Action : dans chaque fichier, garder la bonne version entre <<<<<<< et >>>>>>>, "
              "puis git add --all && git commit.\n      Le hook check-merge-conflict et la CI "
              "refusent tout marqueur restant.")
        return 1
    for args in (("add", "--all"), ("commit", "--quiet", "--message", f"NapkinStack {previous} → {current}")):
        result = _git(root, *args)
        if result.returncode:
            print(f"ÉCHEC [update] Mise à jour posée sur {branch}, mais `git {args[0]}` a échoué :\n"
                  f"      {(result.stdout + result.stderr).strip()}\n"
                  "      Action : corriger, puis git add --all && git commit.")
            return 1

    print(f"Branche {branch} : NapkinStack {previous} → {current}, fusionné avec les adaptations "
          "du projet.")
    print(f"\nÉtape suivante : git push -u origin {branch}, puis ouvrir la PR ; la CI la valide.")
    return 0
