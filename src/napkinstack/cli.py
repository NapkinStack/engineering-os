"""Single entry point `nstack` (workstream C1, PDR-0001)."""

from __future__ import annotations

import argparse
import os
import subprocess
from pathlib import Path

from napkinstack import __version__, doctor, modules, skills
from napkinstack.fitness import boundaries, manifests

PACKAGE = Path(__file__).resolve().parent


def _root(value: str) -> Path:
    root = Path(value).resolve()
    if not root.is_dir():
        raise argparse.ArgumentTypeError(f"root not found: {value}")
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
                        help="project root (default: current folder)")
    parser.set_defaults(func=func)
    return parser


def _init(args: argparse.Namespace) -> int:
    from napkinstack import project  # Copier is only loaded for init and update

    answers = {"project_name": args.project_name, "github_repo": args.github_repo,
               "owner_team": args.owner_team}
    return project.init(args.destination, answers, args.source or project.SOURCE,
                        args.ref or project.default_ref())


def _update(args: argparse.Namespace) -> int:
    from napkinstack import project

    return project.update(args.root, args.ref or project.default_ref())


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="nstack", description="NapkinStack engine.")
    parser.add_argument("--version", action="version", version=f"nstack {__version__}")
    sub = parser.add_subparsers(dest="command", required=True, metavar="command")
    _add(sub, "manifests", "manifests, lifecycles, deprecations (M1-M9)",
         lambda a: manifests.run(a.root))
    _add(sub, "boundaries", "declared graph against real graph (B1-B5)",
         lambda a: boundaries.run(a.root))
    sk = _add(sub, "skills", "generates or checks the skills (S1-S4)",
              lambda a: skills.run(a.root, check_only=a.check))
    sk.add_argument("--check", action="store_true", help="check without writing")
    _add(sub, "fitness", "manifests + boundaries + skills",
         lambda a: _fitness(a.root))
    _add(sub, "doctor", "diagnoses the workstation and the GitHub settings, read-only (PDR-0001)",
         lambda a: doctor.run(a.root))
    nm = _add(sub, "new-module", "creates a module and its guardrails, with no imposed stack",
              lambda a: modules.create(a.root, a.name, a.owner, a.criticality))
    nm.add_argument("name", help="module name, kebab-case")
    nm.add_argument("owner", help="GitHub team, organisation/team")
    nm.add_argument("criticality", choices=["prototype", "standard", "high", "critical"])
    for verb, help_text in (("bootstrap", "prepares one module, or all of them (commands.bootstrap)"),
                            ("check", "format, lint, types of one module, or all (commands.check)"),
                            ("test", "tests of one module, or of all of them (commands.test)")):
        vb = _add(sub, verb, help_text, lambda a, v=verb: modules.run_verb(a.root, v, a.module))
        vb.add_argument("module", nargs="?", help="module name (default: all)")
    rn = _add(sub, "run", "starts a module locally (commands.run)",
              lambda a: modules.run_verb(a.root, "run", a.module))
    rn.add_argument("module")
    ps = _add(sub, "pr-scope", "one PR = one module, review budget (P1-P2)",
              lambda a: _script("fitness/pr_scope.sh", a.base, root=a.root))
    ps.add_argument("--base", default="origin/main")
    ini = sub.add_parser("init", help="creates a project from the skeleton (PDR-0001)")
    ini.add_argument("destination", type=Path, help="project folder, missing or empty")
    ini.add_argument("--project-name", help="project name (asked when absent)")
    ini.add_argument("--github-repo", help="GitHub repository, organisation/name (asked when absent)")
    ini.add_argument("--owner-team", help="GitHub team owning the foundation, organisation/team "
                                          "(asked when absent)")
    ini.add_argument("--source", help="template: URL or path (default: the NapkinStack repository)")
    ini.add_argument("--ref", help="skeleton version, tag vX.Y.Z (default: the one of nstack)")
    ini.set_defaults(func=_init)
    up = _add(sub, "update", "merges a NapkinStack version onto a branch to review (PDR-0001)",
              _update)
    up.add_argument("--ref", help="target version, tag vX.Y.Z (default: the one of nstack)")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)
