# ADR-0003 — Adopt English as the repository language

- **Status**: Accepted (2026-09-16)
- **Date**: 2026-09-16
- **Decision makers**: NapkinStack maintainers (`@NapkinStack/maintainers`)
- **Scope**: project (engine and skeleton)
- **Reversibility**: costly — machine values and file names propagate into every
  generated project

---

## Context

This repository is written in French: documentation, code comments, some identifiers,
output messages, and part of the machine values. Two layers are already English, without
anyone deciding it: every directory name (`skeleton/`, `platform/`, `contracts/`,
`modules/`, `playbooks/`), every `nstack` command, and most of the conceptual vocabulary
used inside the French prose — *fitness function, playbook, kernel, oracle, context
firewall, expand/contract, quality gate, runbook, DoR/DoD*.

The seam shows. Two enumerations read by the same code, in the same file, follow two
different conventions: `criticality` is lower case and half-translated (`prototype`,
`standard`, `eleve`, `critique`), while `lifecycle` is capitalised and accented
(`Proposé`, `Déprécié`).

v0.1.0 is published on PyPI. **No project has been generated from it**; the pilot has not
started. The question is therefore asked at the only moment when its answer is free.

## Problem

Which language is canonical for this repository — code, documentation, machine values and
the skeleton it delivers — and does a generated project inherit that choice?

## Constraints

- v0.1.0 is published: changing machine values is breaking and requires a minor bump.
- A project owns its skeleton and merges new versions with `nstack update` (PDR-0001):
  every line NapkinStack ships that a project rewrites conflicts at every update.
- uv is the only prerequisite: a language decision must not add tooling.
- The maintainers' working language is French. Any decision makes them write in a second
  language, permanently.

---

## Prior art

> **Mandatory section.** Minimum two named references.

**Dominant convention of the field:** an open-source framework is written in English —
source, identifiers, documentation and the artefacts its generators produce — regardless
of where its maintainers are from. Localisation, where it exists, covers end-user-facing
strings only; it never covers the source, the machine values or the scaffolding.

**References examined:**

| Reference | What it does | Applicable here? |
|---|---|---|
| Django | English source and documentation; `django-admin startproject` generates English scaffolding; i18n catalogues translate end-user strings only, never the generated project | Yes: a framework whose generator produces a project |
| Ruby on Rails | English source, documentation and generators; localisation is the application's own concern, through its locale files | Yes: same generator model |
| Vue.js | Written by a Chinese-speaking author; the framework is English and the Chinese documentation is a downstream translation | Yes: the maintainers' language is not the project's language |
| Kubernetes | English canonical source and documentation; localised docs never govern API values | Yes: machine values stay English |
| Linux kernel | English required for code and commit messages, worldwide maintainers | Yes: contribution language |

**Why the convention is not enough:** not applicable — the convention is adopted.

---

## Options considered

### Option 1 — English everywhere, a single source
- Description: code, documentation, machine values, skeleton and governance journal in
  English. No localisation mechanism. A generated project writes its own content in
  whatever language its team uses.
- Advantages: matches the convention; one source to maintain; removes the two casing
  inconsistencies as a by-product; an outside contributor no longer needs French to read
  a rule whose identifier is already English.
- Disadvantages: about 64 500 words to rewrite; breaking for machine values.
- Setup cost: four pull requests. Maintenance cost: none beyond writing in English.
  **Exit cost:** the same work again, plus a second breaking version.

### Option 2 — English code and machine values, French documentation
- Advantages: half the volume.
- Disadvantages: leaves the repository bilingual to read. A contributor would meet an
  English identifier documented by a French paragraph — the exact inconsistency this
  decision exists to remove.

### Option 3 — Bilingual skeleton, a `language` question at init
- Advantages: a French-speaking team receives its method in its own language.
- Disadvantages: doubles 5 000 lines of prose to keep in permanent consistency, for zero
  current users. Maintenance cost grows with every future version.

### Option 4 — Do nothing
- Advantages: free today.
- Disadvantages: the cost does not stay flat. Once the pilot exists, every rename below
  becomes a three-way merge on a live repository, and every generated project pays it
  again. Doing nothing is only cheap until the next `nstack init`.

---

## Decision

**Option 1**, executed before the pilot starts.

The argument that settles it is timing, not taste. Options 1 and 4 differ mainly in
price, and the price of Option 1 is at its minimum exactly now: v0.1.0 is published but
nobody has generated a project from it, so every breaking rename costs nothing. The
window closes at the first `nstack init`.

| Element | Choice |
|---|---|
| Canonical language | English, for every file in this repository |
| `lifecycle` | Lower case: `proposed · active · maintenance · deprecated · retired` |
| `criticality` | Fully English: `prototype · standard · high · critical` |
| A project's own content | Its team's language — its ADRs, runbooks, module READMEs, `responsibility` fields |
| Localisation mechanism | None |
| Where the rule lives | `AGENTS.md` and `CONTRIBUTING.md`; review holds it |
| Version | v0.2.0, minor bump: a manifest valid in v0.1.0 is invalid in v0.2.0 |

The boundary is the one Django draws: the framework speaks English, what you write in
your project is yours. It applies here to a framework that ships prose as well as code.

### Deviation from the convention

None.

---

## Success criterion

*(Convention adopted: not mandatory.)* It will have been the right call if, after v0.2.0,
a `git grep` for accented letters returns nothing outside git history, and the pilot's
`nstack init` produces a project containing no French.

---

## Consequences

**Positive:**

- One source. No translation to keep in sync, and no drift to detect.
- Two casing conventions collapse into one; accented values leave YAML, Python
  comparisons and CI output, where they were a portability hazard for no benefit.
- Contributing no longer requires reading French — the stated purpose of the change.
- The audit that the decision forced found defects unrelated to language: four labels
  named by `pr_scope.sh` and the issue forms that did not exist on the repository, and a
  `cross-module` guardrail that could therefore never be lifted.

**Negative and accepted debt:**

- Breaking: a `MANIFEST.yaml` valid in v0.1.0 is invalid in v0.2.0. Accepted because no
  project has been generated.
- The maintainers write every commit, pull request and document in a second language.
  Permanent friction, accepted as the cost of being contributable.
- A team translating its skeleton pays a conflict at every `nstack update`, on every
  translated line. **Not documented in the product**: no user, no team onboarded, so
  nothing to maintain for a problem nobody has. To be written the day a team asks.
- Git history and past commit messages stay French and are not rewritten. New ones are
  English.

**Impacts on other modules or contracts:** `lifecycle` and `criticality` are contract
values of every `MANIFEST.yaml`, read by `nstack manifests`. The skill keys of
`.nstack/skills.yaml` change with the playbook file names.

**Rule to automate:** none for now, and the arbitration is explicit
(`skeleton/docs/os/07-gouvernance.md` §2). The rule is mechanically checkable in
principle, but soundly only at high cost: detection would rest on accented letters, which
misses English borrowings and false-positives on typographic punctuation and proper
nouns. Risk if violated is low — a stray French sentence is visible in review and costs a
one-line fix. So the branch taken is *high cost, low risk* → **automation backlog**, with
a trigger: the first outside contribution written in another language.

---

## Rejected alternatives

- **Bilingual documentation, or a `language` question in `copier.yml`**: doubles the prose
  to maintain forever, for zero users. The project owns its skeleton and can already
  translate it — at a cost this ADR states rather than hides.
- **Translating only the code and machine values**: leaves English identifiers documented
  in French, which is the defect, not the fix.
- **A CI check rejecting non-English text**: brittle by construction, see *Rule to
  automate*. Listed in the automation backlog instead of shipped badly.
- **Rewriting git history into English**: published history is never rewritten. The
  journal records what happened, including the language it happened in.
