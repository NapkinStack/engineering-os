"""
Fitness function 3 — Pull request scope and size.

  P1  one pull request = one module                  BLOCKING  (docs/os/02-modules.md §7)
  P2  review budget respected                        WARNING   (docs/os/05-workflow.md §4)

A module is touched when the pull request changes it beyond its description — the same
count as `nstack pr-check`'s (D34): editing a manifest, an AGENTS.md, a README or docs/
changes no module, and contracts/ is a module like any other.

The `cross-module` label lifts P1, the `over-budget` label documents P2: both are visible,
so the exceptions are countable (docs/os/10-measurement.md §3).

Usage :  nstack pr-scope [--root ROOT] [--base BASE]
In CI :  PR_LABELS comes from the pull_request event; MAX_LINES and MAX_FILES override the
         budget.
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

from napkinstack.fitness.manifests import changed_files
from napkinstack.pull_request import touched_modules

GENERATED = re.compile(r"(package-lock\.json|yarn\.lock|pnpm-lock\.yaml|Cargo\.lock|go\.sum|uv\.lock"
                       r"|\.generated\.|/generated/)")


def _git(root: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=root, capture_output=True, text=True).stdout


def run(root: Path, base: str) -> int:
    if subprocess.run(["git", "rev-parse", "--verify", "--quiet", base], cwd=root,
                      capture_output=True).returncode:
        print(f"FAIL [pr-scope] base '{base}' not found: the change cannot be measured.\n"
              "      Action: fetch the history (fetch-depth: 0), or pass an existing commit.")
        return 1
    budget = {}
    for name, default in (("MAX_LINES", 400), ("MAX_FILES", 15)):
        value = os.environ.get(name) or str(default)
        if not value.isdigit():
            print(f"FAIL [pr-scope] {name} '{value}' is not a number.\n      Action: set it to a whole "
                  f"number, or unset it for {default}.")
            return 1
        budget[name] = int(value)
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
              "  One PR = one module (docs/os/02-modules.md §7).\n"
              "  A contract change goes through an expand/contract sequence,\n"
              "  never a single PR (docs/os/03-contracts.md §4).\n"
              "  If the exception is justified: add the 'cross-module' label.")
        status = 1

    lines = changed = 0
    for row in _git(root, "diff", "--numstat", f"{base}...HEAD").splitlines():
        added, removed, path = row.split("\t", 2)
        if GENERATED.search(path):
            continue
        changed += 1
        lines += (int(added) if added.isdigit() else 0) + (int(removed) if removed.isdigit() else 0)
    max_lines, max_files = budget["MAX_LINES"], budget["MAX_FILES"]
    print(f"\nReview budget : {lines}/{max_lines} lines, {changed}/{max_files} files")
    if (lines > max_lines or changed > max_files) and "over-budget" in labels:
        print("WARNING [P2] Over budget, justified by label.")
    elif lines > max_lines or changed > max_files:
        print("WARNING [P2] Over the review budget.\n"
              "  A project's throughput is its VERIFICATION throughput, not its generation rate.\n"
              "  Split it up, or add the 'over-budget' label with a justification\n"
              "  (generation, mechanical migration, mass rename).")
    return status
