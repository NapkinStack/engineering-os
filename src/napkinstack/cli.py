"""Single entry point `nstack` (workstream C1, PDR-0001)."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from napkinstack import assurance, attest, board, hold
from napkinstack import (compat, discovery, doctor, landed, modules, provenance, settings,
                         pull_request, skills)
from napkinstack.fitness import boundaries, hygiene, manifests, plan, pr_scope
from napkinstack.project import ANSWERS


def _here() -> Path:
    """The project the current folder belongs to: the nearest folder, this one or above, holding
    the project's answers — as git and cargo find their root (D130). Outside any project, the
    current folder, as before."""
    here = Path.cwd()
    return next((folder for folder in (here, *here.parents) if (folder / ANSWERS).is_file()), here)


def _root(value: str) -> Path:
    root = Path(value).resolve()
    if not root.is_dir():
        raise argparse.ArgumentTypeError(f"root not found: {value}")
    return root


def _modules(args: argparse.Namespace) -> int:
    found = modules.listing(args.root, args.changed_since, args.with_contract_sides)
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
    parser.add_argument("--root", type=_root, default=_here(),
                        help="project root (default: the nearest folder holding .copier-answers.yml, "
                             "this one or above; else the current folder)")
    parser.set_defaults(func=func)
    return parser


def _init(args: argparse.Namespace) -> int:
    from napkinstack import project  # Copier is only loaded for init and update

    answers = {"project_name": args.project_name, "forge": args.forge, "github_repo": args.github_repo,
               "repository": args.repository,
               "owner_team": args.owner_team}
    return project.init(args.destination, answers, args.source or project.SOURCE,
                        args.ref or project.default_ref())


def _update(args: argparse.Namespace) -> int:
    from napkinstack import project

    if args.forge:
        return project.change_forge(args.root, args.forge, github_repo=args.github_repo,
                                    repository=args.repository, session=args.session)
    if args.github_repo or args.repository:
        print("FAIL [update] --github-repo and --repository name the repository of a forge change.\n"
              "      Action: give --forge with them.")
        return 1
    return project.update(args.root, args.ref or project.default_ref(), args.session)


class _Version(argparse.Action):
    """The version, as the first line of a judging run says it: a version installed from
    anywhere but the registry is no published version (PDR-0005)."""

    def __call__(self, parser, namespace, values, option_string=None):
        version, origin = provenance.engine()
        print(f"nstack {version}" + (f" — UNPUBLISHED: {origin}" if origin else ""))
        parser.exit()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="nstack", description="NapkinStack engine.")
    parser.add_argument("--version", action=_Version, nargs=0, help="the engine's version, and where it came from")
    sub = parser.add_subparsers(dest="command", required=True, metavar="command")
    _add(sub, "manifests", "manifests, lifecycles, deprecations, what a release assembles (M1-M11)",
         lambda a: manifests.run(a.root))
    _add(sub, "boundaries", "declared graph against real graph, release artefacts included (B1-B9)",
         lambda a: boundaries.run(a.root))
    _add(sub, "plan", "the discovery, the charter and the cycles (C1-C8), and who holds what",
         lambda a: plan.run(a.root) | hold.show(a.root))
    sk = _add(sub, "skills", "generates or checks the skills (S1-S4)",
              lambda a: skills.run(a.root, check_only=a.check))
    sk.add_argument("--check", action="store_true", help="check without writing")
    _add(sub, "hygiene", "no path from one person's machine in a tracked file (H1)",
         lambda a: hygiene.run(a.root))
    _add(sub, "fitness", "manifests + boundaries + skills + plan + hygiene",
         lambda a: _fitness(a.root))
    _add(sub, "doctor", "diagnoses the workstation and the GitHub settings, read-only",
         lambda a: doctor.run(a.root))
    _add(sub, "settings", "prints the calls that would bring the GitHub settings to the checklist; changes nothing",
         lambda a: settings.run(a.root))
    nm = _add(sub, "new-module", "creates a module and its guardrails, with no imposed stack",
              lambda a: modules.create(a.root, a.name, a.owner, a.criticality, a.user_facing))
    nm.add_argument("name", help="module name, kebab-case")
    nm.add_argument("owner", help="GitHub team, organisation/team, or a user when the project has "
                                  "no organisation")
    nm.add_argument("criticality", choices=list(assurance.CRITICALITIES),
                    help="what a failure of this module costs — prototype: nothing, it is "
                         "thrown away and nothing depends on it · standard: real code, no "
                         "money and no personal data · high: a day of work · critical: a "
                         "key, an order, money, or someone's personal data. The decider "
                         "settles it (.nstack/handbook/05-workflow.md §7)")
    nm.add_argument("--user-facing", action="store_true",
                    help="a user sees this module: from standard up, its pull requests carry a "
                         "test sheet (.nstack/handbook/05-workflow.md §7)")
    for verb, help_text in (("bootstrap", "prepares one module, or all of them (commands.bootstrap)"),
                            ("check", "format, lint, types of one module, or all (commands.check)"),
                            ("test", "tests of one module, or of all of them (commands.test)"),
                            ("e2e", "end-to-end scenarios of one module, or of all (commands.e2e)"),
                            ("clean", "removes what one module's commands left in its folder, or all "
                                      "modules' (commands.clean)")):
        vb = _add(sub, verb, help_text, lambda a, v=verb: modules.run_verb(a.root, v, a.module))
        vb.add_argument("module", nargs="?", help="module name (default: all)")
    cp = _add(sub, "compat", "a frozen contract version changes only with a proof (V1, commands.compat)",
              lambda a: compat.run(a.root, a.module, a.base))
    cp.add_argument("module", nargs="?", help="module holding the contracts (default: all)")
    cp.add_argument("--base", default="origin/main")
    rl = _add(sub, "release", "makes one module's artefacts, or all of them, each into dist/<module> "
                              "(commands.release), with what follows a named module passed to it",
              lambda a: _release(a))
    rl.add_argument("module", nargs="?", help="module name (default: all, each after what it assembles)")
    rl.add_argument("arguments", nargs=argparse.REMAINDER, help="passed to the named module's command")
    rn = _add(sub, "run", "starts a module locally (commands.run), with what follows passed to it",
              lambda a: _run(a))
    rn.add_argument("module")
    rn.add_argument("arguments", nargs=argparse.REMAINDER, help="passed to the module's command")
    md = _add(sub, "modules", "the project's modules, or those with a file changed since a base", _modules)
    md.add_argument("--changed-since", metavar="BASE", help="only the modules with a file changed since BASE")
    md.add_argument("--with-contract-sides", action="store_true",
                    help="also the producer and the declared consumers of a contract version "
                         "this change touches (with --changed-since)")
    md.add_argument("--json", action="store_true", help="a JSON list, for CI")
    ps = _add(sub, "pr-scope", "one PR = one module, review budget (P1-P2)",
              lambda a: pr_scope.run(a.root, a.base))
    ps.add_argument("--base", default="origin/main")
    nc = _add(sub, "new-contract", "creates a contract — and, the first time, the module that holds them all",
              lambda a: modules.create_contract(a.root, a.name, a.owner))
    nc.add_argument("name", help="the contract's name, kebab-case")
    nc.add_argument("--owner", help="owner of the contracts module (default: the foundation's owner)")
    pc = _add(sub, "pr-check", "test sheet and cycle, read from the pull request description (T1-T5, K1-K5)",
              lambda a: pull_request.run(a.root, a.base, a.body_file))
    pc.add_argument("--base", default="origin/main")
    pc.add_argument("--body-file", type=Path, help="the description, when PR_BODY is not set")
    ld = _add(sub, "landed", "what reached this branch outside a pull request, recorded (W1)",
              lambda a: landed.run(a.root, a.span, landed.from_environment(a.root)))
    ld.add_argument("--span", default="HEAD~1..HEAD",
                    help="the commits to read, BEFORE..AFTER (default: the last commit)")
    at = _add(sub, "attest", "runs the CI's checks here and records the run on the commit, in git",
              lambda a: attest.run(a.root, a.base, a.body_file, a.labels, a.accept_identity))
    at.add_argument("--base", default="origin/main")
    at.add_argument("--body-file", type=Path, help="the pull request's description, for its checks")
    at.add_argument("--labels", default="", help="the pull request's labels, comma-separated")
    at.add_argument("--accept-identity", action="store_true",
                    help="record under an identity the project's history does not show yet — a first record of yours")
    cl = _add(sub, "claim", "takes a ready deliverable for a session, before its first change; "
                            "the shared remote refuses a second taker",
              lambda a: hold.claim(a.root, a.deliverable, a.session, a.person, a.take_over))
    cl.add_argument("deliverable", help="the deliverable's identifier, D<n>, in the accepted cycle")
    cl.add_argument("--session", help="the agent's session, written on the hold")
    cl.add_argument("--person", help="the person accountable, such as @alice (default: git's user)")
    cl.add_argument("--take-over", action="store_true",
                    help="take a hold nobody has worked on for hold_days — recorded, with its previous holder")
    rs = _add(sub, "unclaim", "gives a held deliverable back: by its holder, the decider, or anyone once stale",
              lambda a: hold.release(a.root, a.deliverable, a.session, a.person))
    rs.add_argument("deliverable", help="the deliverable's identifier, D<n>")
    rs.add_argument("--session", help="the agent's session, written on the release")
    rs.add_argument("--person", help="who releases it, such as @alice (default: git's user)")
    bd = _add(sub, "board", "shows the cycles and their deliverables on the forge, one way: milestones and issues",
              lambda a: board.run(a.root, a.dry_run))
    bd.add_argument("--dry-run", action="store_true", help="say what would change, change nothing")
    ds = _add(sub, "discover", "starts a discovery from an idea file, for the team's agent",
              lambda a: discovery.run(a.root, a.idea))
    ds.add_argument("idea", type=Path, help="the idea, a .md or .txt file")
    ini = sub.add_parser("init", help="creates a project from the skeleton")
    ini.add_argument("destination", type=Path, help="project folder, missing or empty")
    ini.add_argument("--project-name", help="project name (asked when absent)")
    ini.add_argument("--forge", choices=["github", "gitlab", "forgejo", "gitea", "other", "none"],
                     help="where the project's changes merge (asked when absent; github by default)")
    ini.add_argument("--github-repo", help="GitHub repository, organisation/name — on GitHub (asked when absent)")
    ini.add_argument("--repository", help="the repository's path at another forge, group/name or "
                                          "group/subgroup/name (asked when absent)")
    ini.add_argument("--owner-team", help="owner of the foundation: organisation/team, or a user "
                                          "when the project has no organisation (asked when absent)")
    ini.add_argument("--source", help="template: URL or path (default: the NapkinStack repository)")
    ini.add_argument("--ref", help="skeleton version: a tag vX.Y.Z, or a commit (default: the one of nstack)")
    ini.set_defaults(func=_init)
    up = _add(sub, "update", "merges a NapkinStack version onto a branch to review",
              _update)
    up.add_argument("--ref", help="target version: a tag vX.Y.Z, or a commit (default: the one of nstack)")
    up.add_argument("--session", help="the agent's session, written as the commit's Agent-Session trailer")
    up.add_argument("--forge", choices=["github", "gitlab", "forgejo", "gitea", "other", "none"],
                    help="moves the project to this forge, at its own version: its files, and the project's lines in them")
    up.add_argument("--github-repo", help="with --forge github: the repository, organisation/name")
    up.add_argument("--repository", help="with --forge at another forge: the repository's path, group/name")
    return parser


JUDGES = {"manifests", "boundaries", "plan", "skills", "hygiene", "fitness", "doctor", "settings", "pr-scope",
          "pr-check", "compat", "landed"}  # the commands whose verdict depends on the framework's rules


def _named_root(argv: list[str]) -> Path:
    """The root a command line names, read before the line is parsed: a command this engine
    does not know is refused by the parser, and the reason may be the engine's age (D90)."""
    for index, word in enumerate(argv):
        if word == "--root" and index + 1 < len(argv):
            return Path(argv[index + 1])
        if word.startswith("--root="):
            return Path(word.removeprefix("--root="))
    return _here()


def _release(a) -> int:
    """`release` passes what follows a named module to its command, as `run` does."""
    root, arguments = a.root, list(a.arguments)
    if "--root" in arguments[:-1]:
        at = arguments.index("--root")
        root, arguments = _root(arguments[at + 1]), arguments[:at] + arguments[at + 2:]
    return modules.run_verb(root, "release", a.module, arguments)


def _run(a) -> int:
    """`run` passes what follows the module to its command; `--root`, written there as the
    other verbs take it, is still the root."""
    root, arguments = a.root, list(a.arguments)
    if "--root" in arguments[:-1]:
        at = arguments.index("--root")
        root, arguments = _root(arguments[at + 1]), arguments[:at] + arguments[at + 2:]
    return modules.run_verb(root, "run", a.module, arguments)


# What git hands a hook to name its repository (D126): a hook of a linked worktree gets GIT_DIR,
# and every git the engine runs, in a module or a checkout of its own, would read that one.
# The engine names its project with --root; git finds the rest from where it runs.
GIT_LOCATION = ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_COMMON_DIR")


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    for name in GIT_LOCATION:
        os.environ.pop(name, None)
    if late := provenance.behind(_named_root(argv)):
        print(late, file=sys.stderr, flush=True)
    args = build_parser().parse_args(argv)
    if args.command in JUDGES:
        print(provenance.judged_by(args.root), flush=True)
        if said := plan.stage_line(args.root):
            print(said, flush=True)
    code = args.func(args)
    if code and args.command in JUDGES | {"attest"}:
        # Where a person reads what the codes and words above mean (D131).
        print("A rule's code is explained in .nstack/handbook/RULES.md; a word of the framework in "
              ".nstack/handbook/glossary.md.", flush=True)
    return code
