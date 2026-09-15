"""Point d'entrée unique `nstack` (chantier C1, PDR-0001)."""

from __future__ import annotations

import argparse
import os
import subprocess
from pathlib import Path

from napkinstack import __version__, skills
from napkinstack.fitness import boundaries, manifests

PACKAGE = Path(__file__).resolve().parent


def _root(value: str) -> Path:
    root = Path(value).resolve()
    if not root.is_dir():
        raise argparse.ArgumentTypeError(f"racine introuvable : {value}")
    return root


def _script(relative: str, *args: str, root: Path) -> int:
    env = {**os.environ, "NSTACK_ROOT": str(root)}
    return subprocess.run(["bash", str(PACKAGE / relative), *args], cwd=root, env=env).returncode


def _fitness(root: Path) -> int:
    results = [manifests.run(root), boundaries.run(root), skills.run(root, check_only=True)]
    return 1 if any(results) else 0


def _add(sub, name: str, help_: str, func) -> argparse.ArgumentParser:
    parser = sub.add_parser(name, help=help_)
    parser.add_argument("--root", type=_root, default=Path.cwd(),
                        help="racine du projet (défaut : dossier courant)")
    parser.set_defaults(func=func)
    return parser


def _init(args: argparse.Namespace) -> int:
    from napkinstack import project  # Copier ne se charge que pour init et update

    answers = {"project_name": args.project_name, "github_repo": args.github_repo,
               "owner_team": args.owner_team}
    return project.init(args.destination, answers, args.source or project.SOURCE,
                        args.ref or project.default_ref())


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="nstack", description="Moteur NapkinStack.")
    parser.add_argument("--version", action="version", version=f"nstack {__version__}")
    sub = parser.add_subparsers(dest="command", required=True, metavar="commande")
    _add(sub, "manifests", "manifests, cycles de vie, dépréciations (M1–M9)",
         lambda a: manifests.run(a.root))
    _add(sub, "boundaries", "graphe déclaré contre graphe réel (B1–B5)",
         lambda a: boundaries.run(a.root))
    sk = _add(sub, "skills", "génère ou vérifie les skills (S1–S4)",
              lambda a: skills.run(a.root, check_only=a.check))
    sk.add_argument("--check", action="store_true", help="vérifier sans écrire")
    _add(sub, "fitness", "manifests + frontières + skills",
         lambda a: _fitness(a.root))
    nm = _add(sub, "new-module", "crée un module et ses garde-fous",
              lambda a: _script("scaffold/new-module.sh", a.name, a.owner, a.criticality, root=a.root))
    nm.add_argument("name")
    nm.add_argument("owner")
    nm.add_argument("criticality", choices=["prototype", "standard", "eleve", "critique"])
    ps = _add(sub, "pr-scope", "une PR = un module, budget de revue (P1–P2)",
              lambda a: _script("fitness/pr_scope.sh", a.base, root=a.root))
    ps.add_argument("--base", default="origin/main")
    ini = sub.add_parser("init", help="crée un projet à partir du squelette (PDR-0001)")
    ini.add_argument("destination", type=Path, help="dossier du projet, absent ou vide")
    ini.add_argument("--project-name", help="nom du projet (demandé si absent)")
    ini.add_argument("--github-repo", help="dépôt GitHub, organisation/nom (demandé si absent)")
    ini.add_argument("--owner-team", help="équipe GitHub du socle, organisation/équipe (demandé si absent)")
    ini.add_argument("--source", help="gabarit : URL ou chemin (défaut : dépôt NapkinStack)")
    ini.add_argument("--ref", help="version du squelette, tag vX.Y.Z (défaut : celle de nstack)")
    ini.set_defaults(func=_init)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)
