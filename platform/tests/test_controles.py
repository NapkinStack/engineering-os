"""
Contrôles des fitness functions : chaque règle prouve qu'elle échoue (P5) et se nomme (P6).

Un module conforme sert de base ; chaque cas le dégrade d'une seule façon et vérifie que la
règle attendue est signalée, sans trace Python (D8). Lancé par platform/tests/run.sh.
"""

from __future__ import annotations

import copy
import datetime
import os
import subprocess
from pathlib import Path

import pytest
import yaml

from napkinstack import cli, skills
from napkinstack.fitness import boundaries, manifests

HIER = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()
CONFORME = {
    "module": {"name": "facturation", "responsibility": "Facture les clients.",
               "owner": "acme/facturation", "lifecycle": "active", "criticality": "standard"},
    "provides": [], "consumes": [], "data": {"owns": [], "shared": []},
    "commands": {"check": "true", "test": "true"},
    "docs": {"readme": "README.md", "agents": "AGENTS.md"},
}


def degrade(base=CONFORME, **changements):
    """Copie d'un manifest ; `section__cle=valeur`, `None` supprime la clé."""
    data = copy.deepcopy(base)
    for chemin, valeur in changements.items():
        cible, cles = data, chemin.split("__")
        for cle in cles[:-1]:
            cible = cible[cle]
        if valeur is None:
            cible.pop(cles[-1], None)
        else:
            cible[cles[-1]] = valeur
    return data


def ecrire_module(racine: Path, nom: str, manifest=CONFORME, sources: dict[str, str] | None = None) -> Path:
    dossier = racine / "modules" / nom
    (dossier / "tests").mkdir(parents=True)
    for fichier in ("AGENTS.md", "README.md"):
        (dossier / fichier).write_text("x\n", encoding="utf-8")
    texte = manifest if isinstance(manifest, str) else yaml.safe_dump(manifest, allow_unicode=True)
    (dossier / "MANIFEST.yaml").write_text(texte, encoding="utf-8")
    for chemin, contenu in (sources or {}).items():
        (dossier / chemin).parent.mkdir(parents=True, exist_ok=True)
        (dossier / chemin).write_text(contenu, encoding="utf-8")
    return dossier


def verifier(code: int, sortie: str, regle: str, echec: bool) -> None:
    assert f"[{regle}]" in sortie, sortie
    assert code == (1 if echec else 0), sortie


def test_manifest_conforme(tmp_path, capsys):
    ecrire_module(tmp_path, "facturation")
    assert manifests.run(tmp_path) == 0, capsys.readouterr().out


CAS_MANIFESTS = {
    "M1 dossier sans manifest": (lambda r: (r / "modules" / "orphelin").mkdir(parents=True), "M1", True),
    "M2 champ manquant": (lambda r: ecrire_module(r, "facturation", degrade(module__owner=None)), "M2", True),
    "M2 manifest en liste (D8)": (lambda r: ecrire_module(r, "facturation", "- une\n- liste\n"), "M2", True),
    "M2 section module en texte (D8)": (lambda r: ecrire_module(r, "facturation", degrade(module="texte")), "M2", True),
    "M2 section commands en texte (D8)": (lambda r: ecrire_module(r, "facturation", degrade(commands="make")), "M2", True),
    "M3 cycle de vie": (lambda r: ecrire_module(r, "facturation", degrade(module__lifecycle="unknown")), "M3", True),
    "M3 criticité": (lambda r: ecrire_module(r, "facturation", degrade(module__criticality="severe")), "M3", True),
    "M4 deux phrases": (lambda r: ecrire_module(r, "facturation", degrade(module__responsibility="Facture. Relance.")), "M4", False),
    "M5 déprécié sans date": (lambda r: ecrire_module(r, "facturation", degrade(module__lifecycle="deprecated")), "M5", True),
    "M5 date dépassée": (lambda r: ecrire_module(r, "facturation", degrade(
        module__lifecycle="deprecated", module__deprecation={"removal_date": HIER})), "M5", True),
    "M6 contrat déprécié sans date": (lambda r: ecrire_module(r, "facturation", degrade(
        provides=[{"contract": "factures-api", "version": "v1", "stability": "deprecated"}])), "M6", True),
    "M6 date dépassée": (lambda r: ecrire_module(r, "facturation", degrade(provides=[
        {"contract": "factures-api", "version": "v1", "stability": "deprecated", "removal_date": HIER}])), "M6", True),
    "M7 verbe manquant": (lambda r: ecrire_module(r, "facturation", degrade(commands={"check": "true"})), "M7", True),
    "M8 runbook absent": (lambda r: ecrire_module(r, "facturation", degrade(module__criticality="high")), "M8", True),
    "M9 AGENTS.md absent": (lambda r: (ecrire_module(r, "facturation") / "AGENTS.md").unlink(), "M9", True),
    "M9 tests absent": (lambda r: (ecrire_module(r, "facturation") / "tests").rmdir(), "M9", True),
}


@pytest.mark.parametrize(("preparer", "regle", "echec"), CAS_MANIFESTS.values(), ids=CAS_MANIFESTS.keys())
def test_manifests(tmp_path, capsys, preparer, regle, echec):
    preparer(tmp_path)
    code = manifests.run(tmp_path)
    verifier(code, capsys.readouterr().out, regle, echec)


CLIENTS = degrade(module__name="clients", module__owner="acme/clients")


def consomme(manifest, module):
    return {**manifest, "consumes": [{"contract": f"{module}-api", "version": "v1", "module": module}]}


def test_frontieres_conformes(tmp_path, capsys):
    ecrire_module(tmp_path, "facturation")
    ecrire_module(tmp_path, "clients", CLIENTS)
    assert boundaries.run(tmp_path) == 0, capsys.readouterr().out


CAS_FRONTIERES = {
    "B1 référence non déclarée": ({
        "facturation": (CONFORME, {"src/app.py": "from modules.clients.api import client\n"}),
        "clients": (CLIENTS, {})}, "B1", True),
    "B2 implémentation interne": ({
        "facturation": (consomme(CONFORME, "clients"), {"src/app.js": 'import { db } from "../clients/src/db";\n'}),
        "clients": (CLIENTS, {})}, "B2", True),
    "B3 dépendance circulaire": ({
        "facturation": (consomme(CONFORME, "clients"), {"src/app.py": "from modules.clients.api import client\n"}),
        "clients": (consomme(CLIENTS, "facturation"), {"src/app.py": "from modules.facturation.api import facture\n"})},
        "B3", True),
    "B4 dépendance inutilisée": ({
        "facturation": (consomme(CONFORME, "clients"), {}), "clients": (CLIENTS, {})}, "B4", False),
    "B5 table d'un autre module": ({
        "facturation": (degrade(data={"owns": ["factures"], "shared": []}), {}),
        "clients": (CLIENTS, {"src/requete.py": 'SQL = "SELECT * FROM factures"\n'})}, "B5", True),
}


@pytest.mark.parametrize(("modules_", "regle", "echec"), CAS_FRONTIERES.values(), ids=CAS_FRONTIERES.keys())
def test_frontieres(tmp_path, capsys, modules_, regle, echec):
    for nom, (manifest, sources) in modules_.items():
        ecrire_module(tmp_path, nom, manifest, sources)
    code = boundaries.run(tmp_path)
    verifier(code, capsys.readouterr().out, regle, echec)


def test_frontieres_manifest_illisible_sans_trace(tmp_path, capsys):
    ecrire_module(tmp_path, "facturation")
    ecrire_module(tmp_path, "clients", "- une\n- liste\n")
    ecrire_module(tmp_path, "stock", degrade(module__name="stock", consumes="clients"))
    assert boundaries.run(tmp_path) == 0, capsys.readouterr().out


def ecrire_skills(racine: Path, correspondance) -> None:
    (racine / "playbooks").mkdir()
    (racine / "playbooks" / "tests.md").write_text("# Tests\n", encoding="utf-8")
    (racine / ".nstack").mkdir()
    texte = correspondance if isinstance(correspondance, str) else yaml.safe_dump(correspondance, allow_unicode=True)
    (racine / ".nstack" / "skills.yaml").write_text(texte, encoding="utf-8")


TESTS = {"source": "playbooks/tests.md", "description": "Stratégie de test."}
CAS_SKILLS = {
    "S2 source introuvable": {"skills": {"tests": TESTS, "absente": {**TESTS, "source": "playbooks/absent.md"}}},
    "S2 description vide": {"skills": {"tests": {**TESTS, "description": ""}}},
    "S2 correspondance en liste (D8)": "- tests\n",
    "S2 entrée en texte (D8)": {"skills": {"tests": "playbooks/tests.md"}},
}


@pytest.mark.parametrize("correspondance", CAS_SKILLS.values(), ids=CAS_SKILLS.keys())
def test_skills(tmp_path, capsys, correspondance):
    ecrire_skills(tmp_path, correspondance)
    code = skills.run(tmp_path, check_only=True)
    verifier(code, capsys.readouterr().out, "S2", True)


def depot(racine: Path, fichiers: dict[str, int]) -> str:
    """Dépôt git à deux commits ; rend la base. Les fichiers portent n lignes."""
    env = {**os.environ, "GIT_AUTHOR_NAME": "test", "GIT_AUTHOR_EMAIL": "test@example.invalid",
           "GIT_COMMITTER_NAME": "test", "GIT_COMMITTER_EMAIL": "test@example.invalid"}

    def git(*args: str) -> str:
        return subprocess.run(["git", *args], cwd=racine, env=env, check=True,
                              capture_output=True, text=True).stdout.strip()

    git("init", "-q", "--initial-branch=main")
    (racine / "README.md").write_text("base\n", encoding="utf-8")
    git("add", "-A")
    git("commit", "-q", "-m", "base")
    base = git("rev-parse", "HEAD")
    for chemin, lignes in fichiers.items():
        (racine / chemin).parent.mkdir(parents=True, exist_ok=True)
        (racine / chemin).write_text("ligne\n" * lignes, encoding="utf-8")
    git("add", "-A")
    git("commit", "-q", "-m", "changement")
    return base


DEUX_MODULES = {"modules/a/x.txt": 1, "modules/b/y.txt": 1}
CAS_PR = {
    "P1 deux modules": (DEUX_MODULES, {}, "FAIL [P1]", 1),
    "P1 label cross-module": (DEUX_MODULES, {"PR_LABELS": "cross-module"}, "WARNING [P1]", 0),
    "P2 hors budget": ({"modules/a/x.txt": 3}, {"MAX_LINES": "1"}, "WARNING [P2] Over the review budget.", 0),
}


@pytest.mark.parametrize(("fichiers", "variables", "attendu", "code_attendu"), CAS_PR.values(), ids=CAS_PR.keys())
def test_pr_scope(tmp_path, capfd, monkeypatch, fichiers, variables, attendu, code_attendu):
    base = depot(tmp_path, fichiers)
    monkeypatch.delenv("PR_LABELS", raising=False)
    for nom, valeur in variables.items():
        monkeypatch.setenv(nom, valeur)
    code = cli.main(["pr-scope", "--root", str(tmp_path), "--base", base])
    sortie = capfd.readouterr().out
    assert attendu in sortie, sortie
    assert code == code_attendu, sortie
