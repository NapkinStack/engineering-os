# platform

The project's internal platform. It exists to **reduce cognitive load**, not to control:
every time a team has to rebuild a mechanism already built elsewhere, that is a platform
failure.

## Contents

The engine's code lives in `src/napkinstack/` and runs through the `nstack` command
(`uv run nstack --help`). This folder holds the module's envelope: manifest, instructions,
runbook, tests and configuration.

| Path | Role |
|---|---|
| `src/napkinstack/fitness/` | The architecture checks, not bypassable |
| `src/napkinstack/modules.py` | Module creation and the standard verbs read from its MANIFEST |
| `src/napkinstack/templates/module/` | A module's template, with no imposed stack |
| `src/napkinstack/skills.py` | Generates the Claude Code skills from the playbooks |
| `src/napkinstack/project.py` | Project creation and update, through Copier |
| `src/napkinstack/doctor.py` | Read-only diagnosis of the workstation and the GitHub settings |
| `src/napkinstack/pull_request.py` | The rules read from the pull request description: test sheet, cycle |
| `src/napkinstack/fitness/plan.py` | The discovery, the charter and the cycles |
| `src/napkinstack/fitness/hygiene.py` | What a shared repository must not carry |
| `src/napkinstack/fitness/pr_scope.py` | One pull request, one module; the review budget |
| `src/napkinstack/discovery.py` | `nstack discover`: a discovery started from an idea file, no model called |
| `tests/run.sh` | The oracle: every guardrail proves it can fail |
| `tests/test_guardrails.py` | Rules M, B, S, P, H: one failing case per rule (pytest, run by `run.sh`) |
| `tests/test_pull_request.py` | Rules T and K: one failing case per rule |
| `tests/test_plan.py`, `tests/test_discovery.py` | Rules C: one failing case per rule; `nstack discover` |

## Fitness functions

| Command | Rules |
|---|---|
| `nstack manifests` | M1-M10: fields, lifecycles, deprecation dates, runbook, envelope, user-facing |
| `nstack boundaries` | B1-B5: declared graph vs real graph, internal imports, cycles, data access |
| `nstack pr-scope` | P1-P2: one PR = one module — changed beyond its description, `contracts/` included — review budget |
| `nstack plan` | C1-C7: charter, cycles, deliverables, closures, discovery |
| `nstack pr-check` | T1-T5, K1-K4: the test sheet and the cycle, read from the pull request description |
| `nstack hygiene` | H1: no path rooted in one person's home directory, in any tracked file |

```bash
uv run nstack fitness                      # manifests + boundaries + skills + plan + hygiene
uv run nstack pr-scope --base origin/main
uv run nstack modules --changed-since origin/main   # the modules a change touches, as CI lists them
uv run nstack init <folder>                # creates a project (PDR-0001)
uv run nstack update                       # updates a project, on a branch to review
uv run nstack doctor --root <project>      # workstation and GitHub settings, read-only
uv run nstack new-module <name> <owner> <criticality> --root <project>
uv run nstack check [module] --root <project>   # also test, bootstrap, e2e; run <module>
```

## Skills

```bash
uv run nstack skills           # generates .claude/skills/
uv run nstack skills --check   # S1, S2, S4 blocking in CI; S3 as soon as skills are generated
```

| Check | Verifies |
|---|---|
| S1 | Every playbook has an entry in `.nstack/skills.yaml` |
| S2 | Every entry points at an existing playbook, with a non-empty description |
| S3 | The generated skills match the current playbooks. Not applicable without `.claude/skills/`: a fresh clone, and therefore CI, has none |
| S4 | Name and description follow the [Agent Skills specification](https://agentskills.io/specification): a name of 1 to 64 characters `a-z0-9` and single hyphens, a description of at most 1024 characters. Also blocks generation |

The `description` is what triggers the skill: it says **what** and **when**, in the third
person, with no behavioural instruction — those live in the body of the playbook. A vague
description produces a skill that never triggers, or one that triggers all the time.

## Calibration

`boundaries.py` detects dependencies **textually**, which is deliberately simple and
therefore imperfect. Two settings at the top of the file:

- `SOURCE_SUFFIXES` — the extensions scanned
- `IMPORT_HINTS` — what looks like an import line in your language

A false positive is fixed by declaring the dependency. A false negative is fixed by
enriching the patterns — and deserves an issue, because it is a violation that was
getting through.

## Adding a fitness function

In order of return, the next ones to write are listed in
`skeleton/docs/os/07-governance.md` §3. A good fitness function is fast, deterministic,
and **explanatory when it fails**: one that only says "architecture violation" will be
worked around.
