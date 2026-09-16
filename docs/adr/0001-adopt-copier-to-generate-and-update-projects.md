# ADR-0001 — Adopt Copier to generate and update projects

- **Status**: Accepted (2026-09-15, after the prototype)
- **Date**: 2026-09-15
- **Decision makers**: NapkinStack maintainers (`@NapkinStack/maintainers`)
- **Scope**: project (the engine and the project skeleton)
- **Reversibility**: easy for the generated projects, which contain only their own files
  and an answers file; costly for the engine, which would have to replace the tool

---

## Context

PDR-0001 (Proposed) fixes the behaviour: `nstack init` generates a project that owns its
skeleton; `nstack update` brings it, on demand, a new version merged with its adaptations;
the conflicts are left to the team; one NapkinStack version covers the engine and the
skeleton (R2); the workstation and CI run the version the project pins (R3). The tooling
is Python, installed by uv.

Today the skeleton is copied by hand and the only generator is
`platform/scaffold/new-module.sh`, which substitutes markers with `sed`.

## Problem

Which tool generates a project's skeleton and merges the versions that follow with the
local adaptations?

## Constraints

- **A three-way merge** between the original version, the new version and the project
  (PDR-0001, option A).
- **No code execution** coming from the template during an update: a project must not have
  to trust remote code in order to receive rules.
- **Python, installable by uv**; a permissive licence; active maintenance.
- **A single repository** until the need to split it is demonstrated (PDR-0001).

---

## Prior art

**Dominant convention of the field:** a template-based project generator (Cookiecutter,
Yeoman, GitHub repository templates). Only a minority of tools can update an already
generated project; among those, the three-way merge is the reference.

**References examined:**

| Reference | What it does | Applicable here? |
|---|---|---|
| Copier (MIT, v9.18.2 of 2026-09-07, Python ≥ 3.10) | `copy` then `update`: a three-way merge through `git merge-file`, conflicts marked, refusal when the tree is dirty or the version goes backwards, deleted files not recreated, code-executing features refused without `--trust` | **Yes**, covers every constraint |
| cruft (MIT) | Updates Cookiecutter projects, a diff to approve | No: no activity since 2024-12 (maintenance filter) |
| Cookiecutter (BSD-3) | Generation only | No: no update |
| Yeoman (Node) | Every rewrite of an existing file asks for approval, with no merge | No: no merge, and a Node runtime on top of uv |
| projen (Node) | Synthesised files, not modifiable | No: that is option C, rejected by PDR-0001 |
| GitHub repository templates | The initial copy | No: no update |

---

## Options considered

### Option 1 — Copier, driven by the engine
- Description: the skeleton is **the** Copier template of this repository
  (`_subdirectory`); its versions are the repository's tags; the engine calls the public
  API `run_copy` and `run_update`, never enabling `unsafe`.
- Advantages: a proven three-way merge; native refusals (dirty tree, downgrade, remote
  code); a single version for engine and skeleton; a standard answers file.
- Drawbacks: `update` downloads the template from GitHub; files containing variables take
  the `.jinja` suffix.
- Setup cost: low · maintenance: follow Copier's versions · **exit**: rewrite `init` and
  `update`; the generated projects stay intact.

### Option 2 — Cookiecutter and cruft
- Description: generation by Cookiecutter, updates by cruft.
- Advantages: Cookiecutter is very widely adopted.
- Drawbacks: cruft is no longer maintained (no activity since 2024-12).
- Exit cost: identical to option 1, with an abandonment risk already realised.

### Option 3 — Build the merge into the engine
- Description: generate the versions and call `git merge-file` ourselves.
- Advantages: no dependency.
- Drawbacks: reimplements Copier, edge cases included (deleted files, renames, skipped
  versions). Fails the proportionality filter (`skeleton/docs/os/06-decisions.md` §3).

### Option 4 — Do nothing
- Copy by hand: contrary to PDR-0001, which exists to get out of frozen copies.

---

## Decision

**Option 1.** Among the references examined, Copier is the only maintained tool that does
exactly what PDR-0001 describes, safety refusals included; this is adopting a convention,
not building something. It is driven by the engine, so that one NapkinStack version is
always the same for the engine and for the skeleton (R2, R3).

Rules of use:

1. **A single template in this repository: the project skeleton.** Copier recommends one
   template per repository, because tags are shared. The module envelope is therefore not
   a second Copier template; `new-module` stays an engine scaffold (D19, to be fixed
   separately).
2. **Versions = the repository's tags**, in the PEP 440 format Copier requires.
3. **No "unsafe" feature** (tasks, migrations, Jinja extensions): the engine never enables
   `unsafe`, and Copier refuses those features by default.
4. **Inline conflicts** (Copier's default): the `check-merge-conflict` hook, with
   `--assume-in-merge` as Copier recommends, and the project's CI refuse any remaining
   marker. Without that argument the hook ignores markers written outside a git merge
   (D20, observed by the prototype).
5. **The `.jinja` suffix only** on files that contain a variable; every other file is
   copied as is and stays readable and checkable.

### Deviation from the convention

None.

---

## Success criterion

*(Convention adopted: criterion not mandatory.)* Validation by the PDR-0001 prototype: its
acceptance criteria 1 and 4 to 7 pass with Copier, with no merge code specific to
NapkinStack.

**Observed on 2026-09-15**: criteria 1, 4, 6 and 7 validated, criterion 5 validated with
`--assume-in-merge`; Copier's native refusals confirmed (dirty tree, downgrade).

If that is not the case: supersede with an option documented in a new ADR.

---

## Consequences

**Positive:**

- No homemade merge mechanism to maintain.
- A project cannot execute code coming from the template during an update.
- Copier's answers file records the project's original version, with no format specific to
  NapkinStack.

**Negative and accepted debt:**

- `update` requires access to NapkinStack's public GitHub repository.
- A YAML file containing variables becomes a `.jinja` that the YAML hooks no longer check:
  the generated project, tested in CI, is checked in its place.
- Copier's versions follow Dependabot, like any dependency.

**Impacts on other modules or contracts:** `platform/` becomes the engine that drives
Copier; the skeleton is extracted into a subfolder; `new-module.sh` is kept.

**Rule to automate:** no new check. The refusal of "unsafe" features is native (Copier
exits with code 4) and will be exercised by the project generation test in NapkinStack's
CI, planned in the implementation plan. `skeleton/docs/os/07-governance.md` §2

---

## Rejected alternatives

- **cruft**: a good model, but no activity since December 2024; adopting an already
  abandoned tool creates immediate exit debt.
- **Yeoman**: file-by-file approval with no merge, and a Node runtime on top.
- **projen**: files that cannot be modified, contrary to the need to adapt the rules.
- **Building the merge**: reimplementing Copier costs more to maintain than following its
  versions.
- **Several Copier templates in this repository** (the skeleton and the module envelope):
  contrary to the tool's recommendation, since tags are shared.
