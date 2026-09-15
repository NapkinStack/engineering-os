"""
Diagnostic d'un projet, en lecture seule : le poste et les réglages GitHub (PDR-0001).

Les workflows informent ; ce sont les réglages GitHub qui bloquent, et ils ne se copient
pas avec le projet. CHECKLIST est affichée par nstack init, vérifiée ici, et recopiée mot
pour mot dans le README du squelette (un test le vérifie).

GitHub se lit avec un jeton fourni par l'humain (GH_TOKEN, sinon GITHUB_TOKEN) : à grain
fin, limité au dépôt, permission Administration : lecture. Sans jeton, ou si l'API refuse
une lecture, le réglage est « non vérifié », jamais conforme. Aucune écriture.

Contrôles :
  L1  nstack installé à la version du projet (_commit de .copier-answers.yml)
  L2  git et pre-commit disponibles
  L3  hooks pre-commit installés
  L4  PRODUCT.md absent : contexte de développement de NapkinStack (R6)
  L5  README personnalisé : phrase de présentation écrite
  G1–G11  réglages GitHub de CHECKLIST

Usage :  nstack doctor [--root RACINE]
Sortie :  0 si tout est vérifié et conforme, 1 sinon.
"""

from __future__ import annotations

import fnmatch
import json
import os
import re
import shutil
import subprocess
import urllib.error
import urllib.request
from collections.abc import Callable
from pathlib import Path

import yaml

from napkinstack import __version__
from napkinstack.project import ANSWERS

OK, ECART, INCONNU = "OK", "ÉCHEC", "NON VÉRIFIÉ"
API_VERSION = "2026-03-10"
MARQUEUR = "<Une phrase : ce que fait ce projet.>"
JOBS = ("Fitness functions", "Périmètre et budget de revue", "Hooks et secrets")
ACTIONS_TIERCES = ("astral-sh/setup-uv",)  # actions hors GitHub des workflows du squelette
LABELS = ("cross-module", "hors-budget")
PUBLIEE = re.compile(r"v\d+(\.\d+)*((a|b|rc)\d+)?(\.post\d+)?(\.dev\d+)?")

RULESET = "Settings → Rules → Rulesets, branche main"
SECURITE = "Settings → Advanced Security"
ACTIONS = "Settings → Actions → General"

CHECKLIST = [  # (règle, réglage, action)
    ("G1", "Pull request obligatoire : aucun push direct sur main",
     f"{RULESET} : exiger une pull request avant la fusion"),
    ("G2", "Au moins 1 relecture approuvée", f"{RULESET} : au moins 1 approbation requise"),
    ("G3", "Revue des CODEOWNERS obligatoire", f"{RULESET} : exiger la revue des Code Owners"),
    ("G4", "Checks obligatoires : " + ", ".join(f"`{job}`" for job in JOBS),
     f"{RULESET} : exiger ces checks de statut"),
    ("G5", "Secret Protection et protection au push",
     f"{SECURITE} : activer Secret Protection et la protection au push"),
    ("G6", "Signalement privé de vulnérabilités (canal de `SECURITY.md`)",
     f"{SECURITE} : activer le signalement privé de vulnérabilités"),
    ("G7", "Actions autorisées : celles de GitHub, plus " + ", ".join(f"`{a}`" for a in ACTIONS_TIERCES),
     f"{ACTIONS} : n'autoriser que les actions de GitHub et " + ", ".join(f"{a}@*" for a in ACTIONS_TIERCES)),
    ("G8", "Actions épinglées par SHA obligatoires", f"{ACTIONS} : exiger l'épinglage des actions par SHA"),
    ("G9", "Approbation des workflows pour tout contributeur externe",
     f"{ACTIONS} : exiger l'approbation pour tous les contributeurs externes"),
    ("G10", "Jeton des workflows en lecture seule ; Actions ne crée ni n'approuve de PR",
     f"{ACTIONS} : permissions des workflows en lecture, sans création ni approbation de PR"),
    ("G11", "Labels " + " et ".join(f"`{label}`" for label in LABELS),
     "Issues → Labels : créer " + " et ".join(LABELS)),
]


class NonVerifie(Exception):
    """Réglage illisible : jeton, permission ou réseau."""


class GitHub:
    """Lectures de l'API REST de GitHub, mises en cache ; jamais d'écriture."""

    def __init__(self, repo: str, token: str, api: str) -> None:
        self.repo, self.token, self.api = repo, token, api.rstrip("/")
        self.cache: dict[str, tuple[int, object]] = {}

    def get(self, path: str, missing: bool = False):
        """JSON de /repos/<dépôt><path> ; None si `missing` et 404 ; NonVerifie sinon."""
        if path not in self.cache:
            request = urllib.request.Request(f"{self.api}/repos/{self.repo}{path}", headers={
                "Accept": "application/vnd.github+json", "Authorization": f"Bearer {self.token}",
                "X-GitHub-Api-Version": API_VERSION, "User-Agent": f"nstack/{__version__}"})
            try:
                with urllib.request.urlopen(request, timeout=10) as response:
                    self.cache[path] = (response.status, json.load(response))
            except urllib.error.HTTPError as error:
                self.cache[path] = (error.code, None)
            except (OSError, ValueError):
                self.cache[path] = (0, None)
        status, data = self.cache[path]
        if status == 200:
            return data
        if status == 404 and missing:
            return None
        if status == 0:
            raise NonVerifie(f"API GitHub injoignable ({self.api})")
        if status == 401:
            raise NonVerifie("jeton refusé (HTTP 401)")
        raise NonVerifie(f"lecture refusée (HTTP {status}) : dépôt inaccessible, ou permission "
                         "Administration : lecture absente du jeton")


def _regle(gh: GitHub, kind: str) -> dict | None:
    return next((rule for rule in gh.get("/rules/branches/main") if rule.get("type") == kind), None)


def _parametres(gh: GitHub, kind: str) -> dict:
    return (_regle(gh, kind) or {}).get("parameters") or {}


def _securite(gh: GitHub) -> bool:
    analysis = gh.get("").get("security_and_analysis")
    if analysis is None:
        raise NonVerifie("réglages de sécurité non visibles : permission Administration : lecture "
                         "absente du jeton")
    return all((analysis.get(key) or {}).get("status") == "enabled"
               for key in ("secret_scanning", "secret_scanning_push_protection"))


def _actions_autorisees(gh: GitHub) -> bool:
    if gh.get("/actions/permissions").get("allowed_actions") != "selected":
        return False
    selection = gh.get("/actions/permissions/selected-actions")
    patterns = selection.get("patterns_allowed") or []
    return bool(selection.get("github_owned_allowed")) and all(
        any(fnmatch.fnmatch(f"{action}@0", pattern) for pattern in patterns) for action in ACTIONS_TIERCES)


def _workflows(gh: GitHub) -> bool:
    permissions = gh.get("/actions/permissions/workflow")
    return (permissions.get("default_workflow_permissions") == "read"
            and permissions.get("can_approve_pull_request_reviews") is False)


VERIFICATIONS: dict[str, Callable[[GitHub], bool]] = {
    "G1": lambda gh: _regle(gh, "pull_request") is not None,
    "G2": lambda gh: _parametres(gh, "pull_request").get("required_approving_review_count", 0) >= 1,
    "G3": lambda gh: _parametres(gh, "pull_request").get("require_code_owner_review") is True,
    "G4": lambda gh: set(JOBS) <= {check.get("context") for check in _parametres(
        gh, "required_status_checks").get("required_status_checks", [])},
    "G5": _securite,
    "G6": lambda gh: gh.get("/private-vulnerability-reporting").get("enabled") is True,
    "G7": _actions_autorisees,
    "G8": lambda gh: gh.get("/actions/permissions").get("sha_pinning_required") is True,
    "G9": lambda gh: gh.get("/actions/permissions/fork-pr-contributor-approval").get(
        "approval_policy") == "all_external_contributors",
    "G10": _workflows,
    "G11": lambda gh: all(gh.get(f"/labels/{label}", missing=True) is not None for label in LABELS),
}


def _poste(root: Path, answers: dict) -> list[tuple[str, str, str, str]]:
    commit = str(answers.get("_commit") or "")
    projet = commit.removeprefix("v")
    installer = f'uv tool install "napkinstack=={projet}" --with-executables-from pre-commit'
    resultats = []

    if not PUBLIEE.fullmatch(commit):
        l1 = (INCONNU, f"Raison : le projet vient d'une version non publiée ({commit or 'inconnue'}).")
    elif projet != __version__:
        l1 = (ECART, f"nstack {__version__} installé, projet en {projet} (PDR-0001 R3).\nAction : {installer}")
    else:
        l1 = (OK, "")
    resultats.append(("L1", "nstack à la version du projet", *l1))

    absents = [outil for outil in ("git", "pre-commit") if shutil.which(outil) is None]
    resultats.append(("L2", "git et pre-commit disponibles", ECART if absents else OK,
                      f"Absents : {', '.join(absents)}.\nAction : installer git ; pre-commit vient avec "
                      f"{installer}" if absents else ""))

    if "git" in absents:
        l3 = (INCONNU, "Raison : git absent.")
    else:
        hook = subprocess.run(["git", "rev-parse", "--git-path", "hooks/pre-commit"], cwd=root,
                              capture_output=True, text=True)
        chemin = root / hook.stdout.strip()
        installe = (hook.returncode == 0 and chemin.is_file()
                    and "generated by pre-commit" in chemin.read_text(errors="replace"))
        l3 = (OK, "") if installe else (ECART, "Action : pre-commit install")
    resultats.append(("L3", "Hooks pre-commit installés", *l3))

    produit = (root / "PRODUCT.md").exists()
    resultats.append(("L4", "PRODUCT.md absent", ECART if produit else OK,
                      "PRODUCT.md décrit le développement de NapkinStack (PDR-0001 R6).\n"
                      "Action : le supprimer." if produit else ""))

    readme = root / "README.md"
    marque = readme.is_file() and MARQUEUR in readme.read_text(encoding="utf-8", errors="replace")
    resultats.append(("L5", "README personnalisé", ECART if marque else OK,
                      f"README.md contient encore « {MARQUEUR} ».\n"
                      "Action : écrire la phrase qui présente le projet." if marque else ""))
    return resultats


def _afficher(regle: str, reglage: str, statut: str, detail: str) -> None:
    print(f"  {statut:<11} [{regle}] {reglage}")
    for ligne in detail.splitlines():
        print(f"              {ligne}")


def run(root: Path) -> int:
    if not (root / ANSWERS).is_file():
        print(f"ÉCHEC [doctor] {ANSWERS} introuvable dans {root} : ce dossier n'est pas un projet "
              "créé par nstack init.\n      Action : lancer la commande à la racine du projet, "
              "ou préciser --root.")
        return 1
    answers = yaml.safe_load((root / ANSWERS).read_text(encoding="utf-8")) or {}

    resultats = _poste(root, answers)
    print("Poste")
    for resultat in resultats:
        _afficher(*resultat)

    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    print(f"\nGitHub : {answers.get('github_repo')}")
    if token:
        gh = GitHub(str(answers.get("github_repo")), token,
                    os.environ.get("GITHUB_API_URL") or "https://api.github.com")
    else:
        gh = None
        print("  Aucun jeton (GH_TOKEN ou GITHUB_TOKEN) : aucun réglage n'est lu.\n"
              "  Action : fournir un jeton à grain fin limité au dépôt, permission "
              "Administration : lecture, puis relancer.")
    for regle, reglage, action in CHECKLIST:
        if gh is None:
            statut, detail = INCONNU, ""
        else:
            try:
                statut, detail = (OK, "") if VERIFICATIONS[regle](gh) else (ECART, f"Action : {action}")
            except NonVerifie as raison:
                statut, detail = INCONNU, f"Raison : {raison}"
        resultats.append((regle, reglage, statut, detail))
        _afficher(regle, reglage, statut, detail)

    ecarts = sum(statut == ECART for _, _, statut, _ in resultats)
    inconnus = sum(statut == INCONNU for _, _, statut, _ in resultats)
    if not ecarts and not inconnus:
        print("\nnstack doctor : conforme.")
        return 0
    print(f"\nnstack doctor : {ecarts} écart(s), {inconnus} non vérifié(s).\nLes workflows informent ; "
          "ce sont les réglages GitHub qui bloquent, et ils ne se copient pas avec le projet.")
    return 1
