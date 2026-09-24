# ADR-0003 — Adopt English as the repository language

- **Status**: Accepted (2026-09-16); shrunk to the rule in force on 2026-09-24 (M11h)
- **Date**: 2026-09-16
- **Decision makers**: NapkinStack maintainers (`@NapkinStack/maintainers`)
- **Scope**: project (engine and skeleton)
- **Reversibility**: costly — machine values and file names propagate into every
  generated project

> **Corrected in place.** This record once carried the migration it decided: the French
> values it replaced, the casing it unified, and a log of observations at each release. That
> history is in the M7 plan (`docs/governance/plans/2026-09-16-english-migration.md`) and in
> git; what follows is the rule. Records of this repository are corrected in place until
> v1.0 (`PRODUCT.md` §5).

---

## Context

NapkinStack ships prose as well as code: a handbook, playbooks and a kernel that every
generated project receives and owns. Its maintainers' working language is not English. The
question is which language the framework itself is written in, and whether a project
inherits that choice.

## Problem

Which language is canonical for this repository — code, documentation, machine values and
the skeleton it delivers — and does a generated project inherit it?

## Constraints

- A project owns its skeleton and merges new versions with `nstack update` (PDR-0001):
  every line NapkinStack ships that a project rewrites conflicts at every update.
- uv is the only prerequisite: a language decision must not add tooling.
- Machine values — `criticality`, `lifecycle`, rule identifiers, file names — propagate into
  every project's manifests; changing them is breaking.

---

## Prior art

**Dominant convention of the field:** an open-source framework is written in English —
source, identifiers, documentation and the artefacts its generators produce — regardless
of where its maintainers are from. Localisation, where it exists, covers end-user-facing
strings only; it never covers the source, the machine values or the scaffolding.

| Reference | What it does | Applicable here? |
|---|---|---|
| Django | English source and documentation; `django-admin startproject` generates English scaffolding; i18n catalogues translate end-user strings only | Yes: a framework whose generator produces a project |
| Ruby on Rails | English source, documentation and generators; localisation is the application's own concern | Yes: same generator model |
| Vue.js | Written by a Chinese-speaking author; the framework is English, the Chinese documentation a downstream translation | Yes: the maintainers' language is not the project's language |
| Kubernetes | English canonical source and documentation; localised docs never govern API values | Yes: machine values stay English |

**Why the convention is not enough:** not applicable — the convention is adopted.

---

## Options considered

1. **English everywhere, a single source** — one source to maintain, contributable without a
   second language. Chosen.
2. **English code, documentation in the maintainers' language** — leaves English identifiers
   documented in another language, which is the inconsistency to avoid.
3. **A bilingual skeleton, a `language` question at init** — doubles the prose to keep in
   step forever, for no user who asked.
4. **Do nothing** — each generated project would carry the mixed state, and fixing it later
   costs a merge in every one of them.

---

## Decision

**English everywhere, one source, no localisation mechanism.**

| Element | Rule |
|---|---|
| This repository | English, in every file: code, identifiers, documentation, machine values, messages, commit messages, pull requests |
| A project's own content | Its team's language — its ADRs, runbooks, module READMEs, `responsibility` fields |
| Localisation mechanism | None |
| Git history | Not rewritten. What is left in another language is quoted history — an old pull request title, a machine value as it was |
| Where the rule lives | `AGENTS.md` and `CONTRIBUTING.md`; review holds it |

The boundary is the one Django draws: the framework speaks English, what you write in your
project is yours.

### Deviation from the convention

None.

---

## Success criterion

*(Convention adopted: not mandatory.)* It holds while a generated project contains no word of
another language, and this repository none outside quoted history. Observed at the v0.2.0,
v0.3.0 and v0.4.0 releases on projects generated from the published tag; a search for accented
letters alone is not enough to observe it, since it cannot see an unaccented word.

---

## Consequences

**Positive:** one source, no translation to keep in step; contributing needs no second
language; one casing convention for machine values.

**Negative and accepted debt:**

- The maintainers write every commit, pull request and document in a second language.
  Permanent friction, accepted as the cost of being contributable.
- A team translating its skeleton pays a conflict at every `nstack update`, on every
  translated line. Not documented in the product until a team asks.

**Impacts on other modules or contracts:** `lifecycle` and `criticality` are contract values
of every `MANIFEST.yaml`, read by `nstack manifests`.

**Rule to automate:** none. A check would rest on accented letters — blind to unaccented words,
noisy on typography and proper nouns — while a stray sentence is visible in review and costs a
one-line fix. *High cost, low risk* → the automation backlog, with a trigger: the first outside
contribution written in another language.

---

## Rejected alternatives

- **Bilingual documentation, or a `language` question in `copier.yml`**: doubles the prose to
  maintain forever. A project owns its skeleton and can already translate it, at a cost this
  ADR states rather than hides.
- **A CI check rejecting non-English text**: brittle by construction, see *Rule to automate*.
- **Rewriting git history**: published history is never rewritten. The journal records what
  happened, including the language it happened in.
