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
               "owner": "acme/facturation", "lifecycle": "Actif", "criticality": "standard"},
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
    "M3 cycle de vie": (lambda r: ecrire_module(r, "facturation", degrade(module__lifecycle="Inconnu")), "M3", True),
    "M3 criticité": (lambda r: ecrire_module(r, "facturation", degrade(module__criticality="haute")), "M3", True),
    "M4 deux phrases": (lambda r: ecrire_module(r, "facturation", degrade(module__responsibility="Facture. Relance.")), "M4", False),
    "M5 déprécié sans date": (lambda r: ecrire_module(r, "facturation", degrade(module__lifecycle="Déprécié")), "M5", True),
    "M5 date dépassée": (lambda r: ecrire_module(r, "facturation", degrade(
        module__lifecycle="Déprécié", module__deprecation={"removal_date": HIER})), "M5", True),
    "M6 contrat déprécié sans date": (lambda r: ecrire_module(r, "facturation", degrade(
        provides=[{"contract": "factures-api", "version": "v1", "stability": "deprecated"}])), "M6", True),
    "M6 date dépassée": (lambda r: ecrire_module(r, "facturation", degrade(provides=[
        {"contract": "factures-api", "version": "v1", "stability": "deprecated", "removal_date": HIER}])), "M6", True),
    "M7 verbe manquant": (lambda r: ecrire_module(r, "facturation", degrade(commands={"check": "true"})), "M7", True),
    "M8 runbook absent": (lambda r: ecrire_module(r, "facturation", degrade(module__criticality="eleve")), "M8", True),
    "M9 AGENTS.md absent": (lambda r: (ecrire_module(r, "facturation") / "AGENTS.md").unlink(), "M9", True),
    "M9 tests absent": (lambda r: (ecrire_module(r, "facturation") / "tests").rmdir(), "M9", True),
}


@pytest.mark.parametrize(("preparer", "regle", "echec"), CAS_MANIFESTS.values(), ids=CAS_MANIFESTS.keys())
def test_manifests(tmp_path, capsys, preparer, regle, echec):
    preparer(tmp_path)
    code = manifests.run(tmp_path)
    verifier(code, capsys.readouterr().out, regle, echec)
