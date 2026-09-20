"""Single entry point `nstack` (workstream C1, PDR-0001)."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from napkinstack import (__version__, compat, discovery, doctor, landed, modules, provenance,
                         pull_request, skills)
from napkinstack.fitness import boundaries, hygiene, manifests, plan, pr_scope


def _root(value: str) -> Path:
    root = Path(value).resolve()
    if not root.is_dir():
        raise argparse.ArgumentTypeError(f"root not found: {value}")
    return root


def _modules(args: argparse.Namespace) -> int:
    found = modules.listing(args.root, args.changed_since)
    if found is None:
        print(f"FAIL [modules] base '{args.changed_since}' not found in {args.root}.\n"
              "      Action: fetch the history (fetch-depth: 0), or pass an existing commit.")
        return 1
    print(json.dumps(found) if args.json else "\n".join(f"{m['name']}\t{m['folder']}" for m in found))
    return 0


def _fitness(root: Path) -> int:
    results = [manifests.run(root), boundaries.run(root), skills.run(root, check_only=True),
               plan.run(root), hygiene.run(root)]
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
    _add(sub, "manifests", "manifests, lifecycles, deprecations (M1-M10)",
         lambda a: manifests.run(a.root))
    _add(sub, "boundaries", "declared graph against real graph (B1-B7)",
         lambda a: boundaries.run(a.root))
    _add(sub, "plan", "the discovery, the charter and the cycles (C1-C7)", lambda a: plan.run(a.root))
    sk = _add(sub, "skills", "generates or checks the skills (S1-S4)",
              lambda a: skills.run(a.root, check_only=a.check))
    sk.add_argument("--check", action="store_true", help="check without writing")
    _add(sub, "hygiene", "no path from one person's machine in a tracked file (H1)",
         lambda a: hygiene.run(a.root))
    _add(sub, "fitness", "manifests + boundaries + skills + plan + hygiene",
         lambda a: _fitness(a.root))
    _add(sub, "doctor", "diagnoses the workstation and the GitHub settings, read-only (PDR-0001)",
         lambda a: doctor.run(a.root))
    nm = _add(sub, "new-module", "creates a module and its guardrails, with no imposed stack",
              lambda a: modules.create(a.root, a.name, a.owner, a.criticality, a.user_facing))
    nm.add_argument("name", help="module name, kebab-case")
    nm.add_argument("owner", help="GitHub team, organisation/team, or a user when the project has "
                                  "no organisation")
    nm.add_argument("criticality", choices=["prototype", "standard", "high", "critical"])
    nm.add_argument("--user-facing", action="store_true",
                    help="a user sees this module: its pull requests carry a test sheet")
    for verb, help_text in (("bootstrap", "prepares one module, or all of them (commands.bootstrap)"),
                            ("check", "format, lint, types of one module, or all (commands.check)"),
                            ("test", "tests of one module, or of all of them (commands.test)"),
                            ("e2e", "end-to-end scenarios of one module, or of all (commands.e2e)")):
        vb = _add(sub, verb, help_text, lambda a, v=verb: modules.run_verb(a.root, v, a.module))
        vb.add_argument("module", nargs="?", help="module name (default: all)")
    cp = _add(sub, "compat", "a frozen contract version changes only with a proof (V1, commands.compat)",
              lambda a: compat.run(a.root, a.module, a.base))
    cp.add_argument("module", nargs="?", help="module holding the contracts (default: all)")
    cp.add_argument("--base", default="origin/main")
    rn = _add(sub, "run", "starts a module locally (commands.run)",
              lambda a: modules.run_verb(a.root, "run", a.module))
    rn.add_argument("module")
    md = _add(sub, "modules", "the project's modules, or those with a file changed since a base", _modules)
    md.add_argument("--changed-since", metavar="BASE", help="only the modules with a file changed since BASE")
    md.add_argument("--json", action="store_true", help="a JSON list, for CI")
    ps = _add(sub, "pr-scope", "one PR = one module, review budget (P1-P2)",
              lambda a: pr_scope.run(a.root, a.base))
    ps.add_argument("--base", default="origin/main")
    pc = _add(sub, "pr-check", "test sheet and cycle, read from the pull request description (T1-T5, K1-K4)",
              lambda a: pull_request.run(a.root, a.base, a.body_file))
    pc.add_argument("--base", default="origin/main")
    pc.add_argument("--body-file", type=Path, help="the description, when PR_BODY is not set")
    ld = _add(sub, "landed", "what reached this branch outside a pull request, recorded (W1)",
              lambda a: landed.run(a.root, a.span, landed.from_environment(a.root)))
    ld.add_argument("--span", default="HEAD~1..HEAD",
                    help="the commits to read, BEFORE..AFTER (default: the last commit)")
    ds = _add(sub, "discover", "starts a discovery from an idea file, for the team's agent (PDR-0002)",
              lambda a: discovery.run(a.root, a.idea))
    ds.add_argument("idea", type=Path, help="the idea, a .md or .txt file")
    ini = sub.add_parser("init", help="creates a project from the skeleton (PDR-0001)")
    ini.add_argument("destination", type=Path, help="project folder, missing or empty")
    ini.add_argument("--project-name", help="project name (asked when absent)")
    ini.add_argument("--github-repo", help="GitHub repository, organisation/name (asked when absent)")
    ini.add_argument("--owner-team", help="owner of the foundation: organisation/team, or a user "
                                          "when the project has no organisation (asked when absent)")
    ini.add_argument("--source", help="template: URL or path (default: the NapkinStack repository)")
    ini.add_argument("--ref", help="skeleton version, tag vX.Y.Z (default: the one of nstack)")
    ini.set_defaults(func=_init)
    up = _add(sub, "update", "merges a NapkinStack version onto a branch to review (PDR-0001)",
              _update)
    up.add_argument("--ref", help="target version, tag vX.Y.Z (default: the one of nstack)")
    return parser


JUDGES = {"manifests", "boundaries", "plan", "skills", "hygiene", "fitness", "doctor", "pr-scope",
          "pr-check", "compat", "landed"}  # the commands whose verdict depends on the framework's rules


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command in JUDGES:
        print(provenance.judged_by(args.root), flush=True)
    return args.func(args)
