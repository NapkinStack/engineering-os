# Contributing to NapkinStack

This repository develops the framework; it is also its first user. Read
[`PRODUCT.md`](PRODUCT.md) first, §5 in particular.

## A workstream's journey

```mermaid
flowchart LR
    C["Workstream<br/>workstreams.md"]:::tracking --> P["Detailed plan<br/>plans/"]:::tracking
    P --> T["A failing test<br/>platform/tests/run.sh"]:::code
    T --> I["Implementation<br/>test green"]:::code
    I --> V["Verifications<br/>hooks · fitness · fresh clone"]:::code
    V --> R["Pull request<br/>summary in 5 blocks"]:::review
    R --> CI["CI and review"]:::review
    CI --> M["Merge<br/>squash"]:::done

    classDef tracking fill:#374151,color:#fff
    classDef code fill:#1f2937,color:#fff
    classDef review fill:#1e3a8a,color:#fff
    classDef done fill:#065f46,color:#fff
```

**Legend** — light grey: tracking (`docs/governance/`) · dark grey: work on the branch ·
blue: review · green: merged into `main`.

## The rules of the batch

- **One workstream = one pull request**, never two together. In the issue and pull
  request templates, "the module" reads "the workstream".
- **The test first**: every check has a test that proves it fails (P5), seen red before
  the implementation; every failure names the rule, the place and the action (P6).
- **Review budget**: 400 lines and 15 files; beyond that, the `over-budget` label,
  justified in the pull request (mechanical migration, detailed plan, generation).
- **Pull request summary**: `DONE / VERIFIED / ASSUMED / NOT VERIFIED / RISKS`.
- **Documentation in the same batch**: a change of command, of status or of decision
  updates every page concerned, diagrams and their legends included.
- **Definition of Done**: [`docs/governance/workstreams.md`](docs/governance/workstreams.md).

## Publishing a version

```mermaid
flowchart LR
    V["Version PR<br/>uv version --bump"]:::human --> T["Tag vX.Y.Z<br/>on main"]:::human
    T --> C["Build<br/>tag = version, otherwise stop"]:::ci
    C --> A{"Approval<br/>pypi environment"}:::human
    A --> P["PyPI<br/>Trusted Publishing, attestation"]:::pypi

    classDef human fill:#065f46,color:#fff
    classDef ci fill:#1f2937,color:#fff
    classDef pypi fill:#1e3a8a,color:#fff
```

**Legend** — green: a maintainer's action · grey: `.github/workflows/release.yml` ·
blue: PyPI. Decision: [ADR-0002](docs/adr/0002-distribute-napkinstack-on-pypi.md).

1. Bump the version in a pull request: `uv version --bump patch` (or `minor`), then merge
   it.
2. Tag the merged commit: `git tag -a vX.Y.Z -m "NapkinStack vX.Y.Z" <commit>`, then
   `git push origin vX.Y.Z`.
3. Approve the deployment in GitHub Actions ("Review deployments").

No secret is stored: GitHub proves its identity to PyPI at every publication. A published
version is never replaced; a mistake is fixed by the next version, and a faulty version is
yanked on PyPI.

A skeleton file renamed between two versions comes back, under its new name, in every
project that had deleted it: `nstack update` sees a new file. Rename only when the gain is
worth that cost, and say so in the version pull request.

Leak barriers and exceptions (`cross-module`, `over-budget`): the same as in the projects,
described in [`skeleton/CONTRIBUTING.md`](skeleton/CONTRIBUTING.md).
