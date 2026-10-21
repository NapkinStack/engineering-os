# Architecture Decision Records

A structuring **technical or architectural** decision — costly to reverse, or one that
will constrain the decisions after it.

- Form: [the one every project receives](../../skeleton/.nstack/forms/adr.md)
- Naming: `NNNN-verb-phrase-title.md`, e.g. `0001-adopt-postgres.md`
- A replaced decision is **superseded**, never rewritten quietly.

## Mandatory sections

| Section | Check |
|---|---|
| **Prior art** — ≥ 2 named references + the convention identified | Review; to automate |
| **Deviation** — when departing from the convention | Review; to automate |
| **Dated success criterion** — when building something bespoke | Review; to automate |
| **Rule to automate** — which fitness function follows from it | Review |

See `skeleton/.nstack/handbook/06-decisions.md`.

## Index

| No. | Title | Status | Criterion to check on |
|---|---|---|---|
| [0001](./0001-adopt-copier-to-generate-and-update-projects.md) | Adopt Copier to generate and update projects | Accepted | Validated at the prototype (2026-09-15) |
| [0002](./0002-distribute-napkinstack-on-pypi.md) | Distribute NapkinStack on PyPI | Accepted, clarified (two channels) | Validated at the v0.1.0 release (2026-09-15) |
| [0003](./0003-adopt-english-as-the-repository-language.md) | Adopt English as the repository language | Accepted; shrunk to the rule in force (2026-09-24) | Observed at the v0.2.0 to v0.4.0 releases, where the record holds the observation; the pilot's `init` to confirm |
| [0004](./0004-give-agents-their-own-github-identity.md) | Give agents their own GitHub identity, behind a human approval | Accepted, clarified (who verified; an approval covers what it read; two powers) | The pilot project, before 2026-12-31 |
| [0005](./0005-run-a-project-s-module-checks-in-one-job.md) | Run a project's module checks in one job | Accepted (2026-10-15) | Twenty pull requests of the third project, before 2026-12-31 |
| [0006](./0006-attest-checks-in-git-notes-bound-to-the-commit.md) | Attest checks in git notes, bound to the commit | Accepted (2026-10-20), the how of PDR-0013; built in D129 | Twenty pull requests of the third project, before 2027-03-31 |
| [0007](./0007-hold-a-deliverable-on-a-branch-of-its-own.md) | Hold a deliverable on a branch of its own | Accepted (2026-10-21), the how of PDR-0015; built in D137 | Two contributors on one project, and one bare git remote, before 2027-03-31 |
| [0008](./0008-show-the-plan-as-milestones-and-issues-applied-by-ci.md) | Show the plan as milestones and issues, applied by CI | Accepted (2026-10-21), the how of PDR-0016, after an independent review | The third project's next two cycles, before 2027-03-31 |
