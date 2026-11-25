"""
Fitness function 3 — Pull request scope and size.

  P1  one pull request = one module                  BLOCKING  (.nstack/handbook/02-modules.md §7)
  P2  review budget respected                        WARNING   (.nstack/handbook/05-workflow.md §4)
      — lock files, generated names, and what .gitattributes marks linguist-generated left out

A module is touched when the pull request changes it beyond its description — the same
count as `nstack pr-check`'s (D34): editing a manifest, an AGENTS.md, a README or docs/
changes no module, unless the manifest moves its criticality or its user-facing surface (D184),
and contracts/ is a module like any other.

The `cross-module` label lifts P1, the `over-budget` label documents P2: both are visible,
so the exceptions are countable (.nstack/handbook/10-measurement.md §3).

Usage :  nstack pr-scope [--root ROOT] [--base BASE]
The budget is the project's: `review_budget_lines` and `review_budget_files` in its answers
(`nstack config`), 400 and 15 by default; MAX_LINES and MAX_FILES in the environment override them
for a run (#529). The answers are read at the base, the project's merged word: a pull request
never sets the budget it is measured by (D289). The source taken is said.
In CI :  PR_LABELS comes from the pull_request event.
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

from napkinstack.fitness.manifests import changed_files
from napkinstack.pull_request import touched_modules

GENERATED = re.compile(r"(package-lock\.json|yarn\.lock|pnpm-lock\.yaml|Cargo\.lock|go\.sum|uv\.lock"
                       r"|\.generated\.|/generated/|(?:^|/)\.(?:claude|agents)/skills/)")  # skills: D252


def _git(root: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=root, capture_output=True, text=True).stdout


def declared_generated(root: Path, paths: list[str]) -> set[str]:
    """The paths the project's .gitattributes marks `linguist-generated` — the convention GitHub
    folds in its diffs (#497): a tool's output the fixed pattern cannot know, declared where a
    reviewer sees it. Read as GitHub reads it: any value but `false` (or `-linguist-generated`) is
    generated. Read at HEAD, the commit measured, never a working tree's edit; a git before 2.40
    has no --source and reads the working tree."""
    if not paths:
        return set()
    for source in (["--source", "HEAD"], []):
        found = subprocess.run(["git", "check-attr", *source, "-z", "--stdin", "linguist-generated"], cwd=root,
                               input="\0".join(paths) + "\0", capture_output=True, text=True)
        if found.returncode == 0:
            break
    out = found.stdout.split("\0")
    return {path for path, _, value in zip(out[0::3], out[1::3], out[2::3])
            if value not in {"unspecified", "unset", "false"}}


def run(root: Path, base: str) -> int:
    if subprocess.run(["git", "rev-parse", "--verify", "--quiet", base], cwd=root,
                      capture_output=True).returncode:
        print(f"FAIL [pr-scope] base '{base}' not found: the change cannot be measured.\n"
              "      Action: fetch the history (fetch-depth: 0), or pass an existing commit.")
        return 1
    from napkinstack import config

    budget, sources, unread = {}, [], False
    for name, setting in (("MAX_LINES", "review_budget_lines"), ("MAX_FILES", "review_budget_files")):
        if os.environ.get(name):
            value, source = os.environ[name], f"{name} in the environment"
            action = f"set it to a whole number, or unset it for the project's {setting}"
        else:
            try:
                answer, where = config.value(root, setting, at=base)
            except config.Unreadable as error:
                # The pull request that fixes the file is measured at the base too: refusing would be
                # a dead end. P2 is a warning; the defaults measure it, said.
                if not unread:
                    print(f"WARNING [pr-scope] {error} at {base}: the defaults measure this change.\n"
                          "      Action: fix the file's YAML in a pull request; the ones after its merge are "
                          "measured by the project's answers.")
                unread = True
                answer, where = config.SETTINGS[setting].default({}), "default"
            value, source = str(answer), (setting if where == "default" else f"{setting} in {where}")
            action = f"nstack config {setting} <a whole number above 0>"
        if not config.whole(value):
            print(f"FAIL [pr-scope] {source}: '{value}' is not a whole number above 0.\n      Action: {action}.")
            return 1
        budget[name] = int(value)
        sources.append(source + (", by default" if source == setting else ""))
    files = changed_files(root, base)
    if not files:
        print("No file changed.")
        return 0
    labels = {label.strip() for label in os.environ.get("PR_LABELS", "").split(",") if label.strip()}
    fork = _git(root, "merge-base", base, "HEAD").strip() or base
    modules = touched_modules(root, fork, files)
    print(f"Files changed   : {len(files)}")
    print(f"Modules touched : {len(modules)}" + "".join(f"\n  - {folder}" for folder in modules))

    status = 0
    if len(modules) > 1 and "cross-module" in labels:
        print("\nWARNING [P1] Cross-module PR allowed by label.\n"
              "  Counted as an exception. A rising rate means a boundary is decaying.")
    elif len(modules) > 1:
        print(f"\nFAIL [P1] This PR changes {len(modules)} modules.\n"
              "  One PR = one module (.nstack/handbook/02-modules.md §7).\n"
              "  A contract change goes through an expand/contract sequence,\n"
              "  never a single PR (.nstack/handbook/03-contracts.md §4).\n"
              "  If the exception is justified: add the 'cross-module' label.")
        status = 1

    lines = changed = 0
    rows = [row.split("\t", 2) for row in _git(root, "-c", "core.quotepath=off", "diff", "--numstat",
                                                  f"{base}...HEAD").splitlines()]
    declared = declared_generated(root, [path for _, _, path in rows])
    for added, removed, path in rows:
        if GENERATED.search(path) or path in declared:
            continue
        changed += 1
        lines += (int(added) if added.isdigit() else 0) + (int(removed) if removed.isdigit() else 0)
    max_lines, max_files = budget["MAX_LINES"], budget["MAX_FILES"]
    print(f"\nReview budget : {lines}/{max_lines} lines, {changed}/{max_files} files ({'; '.join(sources)})")
    if (lines > max_lines or changed > max_files) and "over-budget" in labels:
        print("WARNING [P2] Over budget, justified by label.")
    elif lines > max_lines or changed > max_files:
        print("WARNING [P2] Over the review budget.\n"
              "  A project's throughput is its VERIFICATION throughput, not its generation rate.\n"
              "  Split it up, or add the 'over-budget' label with a justification\n"
              "  (generation, mechanical migration, mass rename). A tool's output whose name gives\n"
              "  nothing away: mark it linguist-generated in .gitattributes (.nstack/handbook/05-workflow.md §4).")
    return status
