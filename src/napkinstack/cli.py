"""Point d'entrée unique `nstack` (chantier C1, PDR-0001)."""

from __future__ import annotations

import argparse
from pathlib import Path

from napkinstack import __version__, skills
from napkinstack.fitness import boundaries, manifests


def _root(value: str) -> Path:
    root = Path(value).resolve()
    if not root.is_dir():
        raise argparse.ArgumentTypeError(f"racine introuvable : {value}")
    return root


def _add(sub, name: str, help_: str, func) -> argparse.ArgumentParser:
    parser = sub.add_parser(name, help=help_)
    parser.add_argument("--root", type=_root, default=Path.cwd(),
                        help="racine du projet (défaut : dossier courant)")
    parser.set_defaults(func=func)
    return parser


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
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)
