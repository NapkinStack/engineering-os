# Architecture Decision Records

A structuring **technical or architectural** decision — costly to reverse, or one that
will constrain the decisions after it.

- Template: [`_TEMPLATE.md`](./_TEMPLATE.md)
- Naming: `NNNN-verb-phrase-title.md`, e.g. `0001-adopt-postgres.md`
- A replaced decision is **superseded**, never rewritten quietly.

## Mandatory sections

| Section | Check |
|---|---|
| **Prior art** — ≥ 2 named references + the convention identified | Review; to automate |
| **Deviation** — when departing from the convention | Review; to automate |
| **Dated success criterion** — when building something bespoke | Review; to automate |
| **Rule to automate** — which fitness function follows from it | Review |

See `skeleton/docs/os/06-decisions.md`.

## Index

| No. | Title | Status | Criterion to check on |
|---|---|---|---|
| [0001](./0001-adopt-copier-to-generate-and-update-projects.md) | Adopt Copier to generate and update projects | Accepted | Validated at the prototype (2026-09-15) |
| [0002](./0002-distribute-napkinstack-on-pypi.md) | Distribute NapkinStack on PyPI | Accepted | Validated at the v0.1.0 release (2026-09-15) |
| [0003](./0003-adopt-english-as-the-repository-language.md) | Adopt English as the repository language | Accepted | Observed at the v0.2.0 release (2026-09-16); the pilot's `init` to confirm |
