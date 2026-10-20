# PDR-0014 — A human finds what the words mean, where they read them

- **Status**: Proposed (2026-10-20). Asked by the maintainer: *a lexicon of the product, for a
  human — even if the AI understands, it makes things hard to follow* (#191); the direction
  below was proposed to them and agreed before this record
- **Date**: 2026-10-20
- **Decision makers**: NapkinStack maintainers (`@NapkinStack/maintainers`)
- **Modules affected**: the skeleton's handbook (a glossary page out of `00-overview.md` §6),
  `RULES.md`, the kernel, the engine's messages, a check

> The PDR describes **what the product must do and why**, never its implementation.
> The how belongs to an ADR.

---

## User problem

A project's decider, a verifier, a teammate: humans read what nstack and its agent write —
command output, pull request bodies, cycle pages, the agent's reports. The agent knows the
vocabulary; the human meets *deliverable*, *oracle*, *workstream*, *guarded*, *framed*, `T5`,
`K3`, `P1` and has nowhere to look but the agent.

Observed (#191): the glossary exists — 21 terms in `00-overview.md` §6 — linked from nowhere;
terms met every day are not in it (*decider*, *verifier*, *workstream*, *kernel*, *guarded*,
*framed*, *published*, the criticality levels, a deliverable's states, the labels); a rule's
code is printed without a path to its meaning. Over one day of a downstream project, its
decider asked the agent several times to "explain simply".

## Goal

Every word and code the framework puts in front of a human is defined in one place the human
is pointed to from where they read it, in plain words, and stays defined as the framework
changes.

## Out of scope

- **A glossary in another language.** The repository is English (ADR-0003); the agent explains
  in the human's language, from the same definitions.
- **A documentation site, tooltips, a search.** A file in the project, linked.
- **Renaming the vocabulary.** Words are defined as they are; a word found confusing is a
  separate request.
- **A project's own vocabulary** — its domain's words belong to its charter.

---

## Prior art

| Product / reference | Solution chosen | What we keep from it |
|---|---|---|
| [Kubernetes glossary](https://kubernetes.io/docs/reference/glossary/) | One entry per term, short and long definitions, reused where the word is read | **One source, reached from where the word is** |
| [Sphinx `glossary` and `:term:`](https://www.sphinx-doc.org/en/master/usage/restructuredtext/directives.html#directive-glossary) | Terms defined once; a reference to an undefined term warns at build | **A check keeps the glossary true** |
| [Vale vocabularies](https://vale.sh/docs/keys/vocab) | Accepted and rejected words, enforced in prose | **One word per concept** — a rejected variant is caught |
| [Domain-driven design, ubiquitous language](https://martinfowler.com/bliki/UbiquitousLanguage.html) | One vocabulary shared by people, code and output | **The engine's messages use the glossary's words** |

**The convention the user already knows:** a glossary at the end of a manual, and an error
code with a link to its explanation.

---

## Options considered

| Option | What the user experiences | Cost | Chosen? |
|---|---|---|---|
| Do nothing | Asks the agent, every time; answers not kept | 0 | No |
| A. More terms in `00-overview.md` §6 | A longer table nobody is pointed to | Low | No: found by those who already know |
| **B. A glossary page, pointed to from the kernel, the forms and every rule code printed; a check keeping it and the words used in step; the agent told to use it** | Every word and code they meet leads to one plain sentence | Medium | **Yes** |
| C. B, as a site with tooltips | The same, in a browser | High | Not now: no reader outside the repository yet |

## Decision

**Option B.**

1. **One glossary page** in the project, `.nstack/handbook/glossary.md`, replacing
   `00-overview.md` §6. Each entry: the term, one sentence in plain words, *where you meet it*,
   and a realistic example. Grouped: who (postures), the work (discovery to acceptance), the
   rules, the records, the states. Rule codes are **not** copied there: the glossary points to
   `RULES.md`, which stays their source.
2. **Pointed to from where a human reads.** The kernel's first lines name it; each form names
   it once; every message that prints a rule's code says where its meaning is.
3. **Kept in step by a check.** A word the framework uses as one of its terms — in the handbook,
   the playbooks, the forms, the engine's messages — and not defined fails; a defined term no
   longer used is reported. Which words are terms is the glossary's own list, not a guess.
4. **The agent speaks it.** The kernel tells the agent, facing a human: use the glossary's word,
   and explain a term or a code at its first mention — in the human's language.

---

## Expected behaviour

**Nominal journey.** A decider reads `FAIL [T5] scenario S2: failed`. The line says where `T5`
is explained; `RULES.md` says it in a sentence; *scenario* and *test sheet* are in the
glossary, with an example. The agent's report, in the decider's language, says *the test sheet
(the scenarios a verifier runs)* the first time.

**Edge cases.** A new term added to a playbook without an entry fails the check, naming the file
and the word. A term removed everywhere is reported, its entry to delete. A project that edits
its glossary keeps its edits through `nstack update`, as any handbook page it owns.

**Acceptance criteria** *(testable)*:

- [ ] Given the skeleton, then `.nstack/handbook/glossary.md` exists and `00-overview.md` points to
      it instead of holding §6.
- [ ] Given every term the #191 audit found missing, then each has an entry.
- [ ] Given a message of the engine that prints a rule's code, then it names where the code is
      explained.
- [ ] Given a term of the glossary's list used in the handbook and not defined, then the check
      fails naming the file and the word.
- [ ] Given the kernel, then it names the glossary and tells the agent to explain a term at first
      mention.

---

## Success criterion

By 2027-03-31: a person new to nstack reads a cycle page, a `pr-check` output and an agent's
report from a downstream project and says what each framework word and code means, using only
what the project contains — on two people, without asking the agent.

## Removal condition

None while the framework has a vocabulary of its own. The check is removed if it reports more
noise than terms for two minor versions.

## Impacts

- **The skeleton**: a new handbook page; `00-overview.md` §6 replaced by a pointer; the kernel
  gains two lines; the forms one each.
- **The engine**: messages with a rule code gain a pointer; a check (in `fitness`, as `skills`).
- **Projects**: `nstack update` brings the page and the pointers; the check judges the
  framework's own files, not a project's prose.
- **The how** — the list's format, the check's place and messages — goes to the plan of the
  workstream that builds it.
