# PDR-0004 — Ask the right question, to the right person, at the right moment

- **Status**: Accepted (2026-09-18, by the maintainer; the success criterion is observed on
  M9's log). The direction only: the design waits on what M9 records.
- **Date**: 2026-09-18
- **Decision makers**: NapkinStack maintainers (`@NapkinStack/maintainers`)
- **Modules affected**: the project skeleton (playbooks, handbook), `nstack` checks,
  governance

> The PDR describes **what the product must do and why**, never its implementation.
> The how belongs to the implementation plan and, where structuring, to an ADR.

---

## User problem

A project has moments, and each moment has its own questions and its own competent
speaker. When an idea is born, the questions are users, market, what "finished" means; no
one should be asked about a database yet. Once two modules exist and a contract is drawn
between them, the questions are boundaries, versions, consumers. Once a user-facing
deliverable is ready, the questions are evidence: who verifies, against what sheet, with
what proof.

The framework hands out the same procedure whatever the moment. `nstack init`, then the
discovery playbook, then the framing playbook — and from there, which questions get asked
depends on the agent's judgement and on the maintainer noticing what is missing. Those are
the two things this framework exists to stop depending on.

Two failures follow, and both were observed in M9 before this document was written.

**A question nobody asked.** The discovery dropped the success criterion that would have
produced real evidence, and moved to a rehearsal with no deployment and no real user.
PDR-0003 requires a test sheet run by a verifier with evidence on the head commit. Nothing
in the framework raised the obvious consequence — with no deployment and no real user,
what now counts as a *verified* deliverable? The maintainer raised it, reading the
handover. Had they not, a cycle would have closed green while proving only that the
paperwork moved.

**A question asked when the repository already holds the answer.** Every question put to a
human that a check could have answered is a tax paid by the one user the framework claims
to serve: the tech lead who has thirty minutes, not an afternoon.

## Goal

At any moment of a project's life, the team's agent can ask the framework what stage the
project is in, what it should ask next, and who should be asked — and gets a deterministic
answer grounded in facts the repository already holds.

## Out of scope

- **An AI inside `nstack`** (`PRODUCT.md` §6, as in PDR-0002): the engine returns facts,
  the team's agent asks the questions and writes the answers.
- **A catalogue of personas.** A hat exists only when a stage triggers it *and* it asks
  what no other hat would ask. Without that rule this becomes a role-play framework with
  the ceremony its users complain about.
- **Expertise held in the engine or in a model**: it lives in versioned playbooks, in
  generic markdown, readable by any agent (P2).
- **Estimation, velocity, portfolio management**: excluded by PDR-0002 and still excluded.
- **Blocking anything.** Routing advises; enforcement stays where PDR-0003 and the fitness
  functions already put it.
- **The design itself**: the stages, the hats, the command and its output. This document
  fixes the direction and what must be observed before any of it is built
  (`PRODUCT.md` §7: nothing is built before it has served once).

---

## Prior art

> **Mandatory section.** Minimum two named references.
> (`skeleton/docs/os/06-decisions.md` §2)

**How is this problem solved elsewhere?**

| Product / reference | Solution chosen | What we keep from it |
|---|---|---|
| [GitHub Spec Kit](https://github.com/github/spec-kit) | A constitution once per project, then `specify` → `plan` → `tasks` → `implement` for every feature | The artefact chain: each phase produces a document the next one reads, so the agent never works from the conversation |
| [BMAD-Method v6](https://github.com/bmad-code-org/BMAD-METHOD) | Dedicated agents (analyst, PM, architect) and **scale-adaptive planning**, which routes work to a quick track, a standard track or an enterprise track | Routing itself: that one procedure for every case is the wrong shape. And the warning — its own users report the ceremony of twelve personas |
| [AWS Kiro](https://kiro.dev/blog/introducing-kiro/) | `requirements.md` in EARS notation, `design.md`, `tasks.md`, plus steering rules and hooks | EARS as a way to write acceptance criteria that are testable rather than agreeable |
| [Agent OS](https://buildermethods.com/agent-os) | Three layers — standards, product, specs — and six phases the human invokes by command, including discovery of an existing codebase's patterns | The separation between what is durable (standards, product) and what is the current piece of work |

**The convention the user already knows:** the human chooses the phase, or the persona,
and runs the matching command. Spec Kit, Kiro, BMAD and Agent OS all work this way.

**Why depart from it:**

The convention assumes the user already knows the method well enough to pick the right
command — which is exactly what a tech lead adopting a framework does not yet have.
BMAD routes, but on the size of the work, not on the moment of the project; Agent OS has
phases, but the human selects them.

None of them reads the repository to answer *which moment is this*. They cannot: their
state lives in prose. NapkinStack's does not. `doctor` reports what is missing, `plan`
validates the charter and the cycles, `manifests` and `boundaries` report the module graph.
The state of a NapkinStack project is already machine-readable, and nothing yet uses that
to decide what to ask.

The departure costs the user nothing to learn — every command still works when called
directly — and removes the one step that required them to know the method in advance.

---

## Options considered

| Option | What the user experiences | Cost | Chosen? |
|---|---|---|---|
| Do nothing | The agent asks what it judges useful; the maintainer catches what is missing, when they catch it | 0 | No — the M9 failure is not an accident of one session |
| A stage map in the playbooks only | The agent reads the state with the existing commands and picks its own questions | Low | As the **form**: the map and the hats live in playbooks |
| A deterministic answer from the engine — stage, hat, questions, recipient | The agent asks the framework where the project stands and gets facts, not a guess | Medium | **The direction**, shape to be designed |
| A full per-domain persona catalogue, written up front | A hat for product, architecture, QA, security, CI, data, each with its interview | High | No — it is the failure mode the prior art documents. Hats are earned one at a time, on a recorded need |

## Decision

NapkinStack routes the interview on **three orthogonal axes**. Two exist; one is new.

| Axis | The question it answers | Today |
|---|---|---|
| **Stage** | Where is the project in its life? | Absent — derivable from facts the checks already return |
| **Hat** | Which field do the questions come from: product, architecture, verification, operations? | Absent |
| **Posture** | Who speaks with respect to the decision: framer, challenger, author, verifier, approver, decider? | PDR-0002 |

Four rules bound the direction, and they are what this document commits to.

1. **The stage is derived, never declared.** It comes from facts the repository holds. The
   framework never states a stage without naming the facts that establish it, so a wrong
   answer is visible and arguable rather than authoritative.
2. **The expertise lives in playbooks**, versioned, reviewed and testable — never in the
   engine, never in a model, never in an agent-specific persona file (P2).
3. **The recipient is read, not guessed.** A project already declares who decides and who
   owns what: `decider` in the charter, `owner_team` in a manifest, `CODEOWNERS` on a path.
   A question about scope goes to the decider, a question about a contract to both owners.
4. **Routing exists to ask fewer questions.** Any question a check could have answered is a
   design failure, not a feature. This is the rule that separates the direction from the
   ceremony its prior art is criticised for.

**Not decided here**, and deliberately: the list of stages, the list of hats, whether the
answer comes from a new command or from the existing ones, its output, and whether any of
it ever blocks. Those are designed after M9, from what M9 records.

---

## Expected behaviour

**Nominal journey.** A session starts. The agent asks the framework where the project
stands. It receives the stage with the facts that establish it, the hat to wear, the
playbook to load, the open questions that belong to this stage, and, for each, the person
who answers it. It asks them one at a time, writes the answers into the project's
documents, and the next session reads those documents rather than the conversation.

**Edge cases and degraded states.** A project whose state matches no stage, or two stages
at once, is reported as such and the agent falls back to the current playbooks: an unknown
stage must never invent one. A project generated before this exists keeps working
unchanged.

**Business rules.** The four rules of the decision above.

**Permissions:** unchanged. Routing proposes; PDR-0002's decider decides and PDR-0003's
approver approves.

**Acceptance criteria** *(testable — the oracle of this decision is M9's log)*:

- [ ] Given M9 Tasks 4 to 9, when a question is put to the maintainer, then the validation
      log records the stage, the hat, the recipient, and whether the repository could have
      answered it from facts a check already returns.
- [ ] Given the M9 log at Task 9, when the stages are listed, then every one of them is
      established by facts an existing check returns — or it is not a stage.
- [ ] Given the M9 log at Task 9, when a hat is proposed, then at least one recorded
      question is one that no other hat would have asked.

---

## Success criterion

> **Mandatory section.** Without a date nobody comes back to check, and the decision
> folder becomes a graveyard.

> We will consider this was the right call if the M9 log (Tasks 4 to 9) records **at least
> three questions the framework should have raised and did not**, each attributable to a
> stage that facts an existing check returns would have established — observed before
> **2026-10-31**.

How it is observed: the validation log of `NapkinStack/tool-library`, issue 1, which
already records every question and every point of friction as it happens.

If the criterion is not met: the problem is the maintainer's vigilance rather than the
framework's shape, and this direction is abandoned rather than built. Fewer than three, or
questions that no stage would have produced, means routing would have added a step instead
of removing one.

---

## Removal condition

> This direction will be removed if a stage cannot be established without asking the user
> which stage they are in — at which point the framework is asking a question in order to
> know which question to ask — or if, after one pilot cycle, the routed interview is longer
> than the unrouted one it replaced.

---

## Impacts

- **Existing users**: none today. Once built, a project generated before it keeps working:
  routing advises, it does not block, and every command still runs when called directly.
- **Modules and contracts**: none. The facts come from checks that already exist.
- **Support and documentation**: the stage map joins the postures, in
  `skeleton/docs/os/05-workflow.md` §10, which is today the only place in the deliverable
  where the model of who speaks is described; the kernel does not grow (P4, 250 lines). A
  hat is a playbook, subject to the same review as any other.
- **Data**: nothing is collected. Every fact used is already in the repository, and no
  model is called (`PRODUCT.md` §6).
