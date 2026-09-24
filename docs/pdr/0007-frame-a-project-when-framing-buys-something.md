# PDR-0007 — Frame a project when framing buys something

- **Status**: Accepted (2026-09-22, by the maintainer; the success criterion is observed
  before 2027-03-31); to be implemented in **M11j**, before v0.7.0, with PDR-0008 (M11k) and
  PDR-0010 (M11l), which answer the same hour of a project's life; clarified 2026-09-24
- **Date**: 2026-09-20
- **Decision makers**: NapkinStack maintainers (`@NapkinStack/maintainers`)
- **Modules affected**: `nstack pr-check` (rules K1 to K3), `nstack plan`, the skeleton's
  handbook and playbooks, `PRODUCT.md` §3

> The PDR describes **what the product must do and why**, never its implementation.
> The how belongs to the implementation plan and, where structuring, to an ADR.

---

## User problem

Measured on 2026-09-20, on a project generated from the published v0.4.0: a person who wants
to commit their first file of code meets, in order, thirteen forge settings to apply by hand,
a module to declare, two commands to write — and then `FAIL [K1] the project is not framed:
no accepted charter and cycle`. Their first pull request cannot pass until a charter and a
cycle are accepted, or until every pull request carries the `out-of-cycle` label with its
justification.

**The artefacts are not the cost; the decisions are.** With an agent, writing a charter, a
cycle, a manifest or an ADR takes minutes — M9 measured a one-week appetite framed in about
53 minutes of effective work. What cannot be delegated is the decider's part: an appetite, an
end date, a list of deliverables with acceptance criteria, and two acceptances. That part is
the product, and it is worth its price **when there is something to bound** — several people,
a deadline, a decider who is not the person typing.

For one person and their agents, at the start of a project, there is nothing to bound yet.
The rule then buys nothing and costs a wall.

**And the field has already answered this question.** Every comparable project ships a way to
spend less ceremony on small work: BMAD leads with *"the process sizes itself to the work.
Small changes go straight to build"*; OpenSpec sells *"predictability without the ceremony"*
and concedes that *"for a one-character typo fix, the ceremony probably isn't worth it"*; GSD
Core's own documentation says a phase that is too small produces *"a planning overhead that
dwarfs the execution cost. The loop feels bureaucratic rather than helpful"*, and ships
`/gsd-fast` and `/gsd-quick`; Spec Kit was told the same in its issue #1174 — *"this workflow
behaves the same regardless of task complexity"* — and answered with a `lean` preset and a
TinySpec extension that routes by the size of the change.

We have the opposite posture: `K1` applies to every delivery pull request, and PDR-0002's
removal condition counts a project that labels more than one pull request in five
`out-of-cycle` as a project whose bounds are decoration. A project with no cycles is
therefore, today, **a failure state rather than a stage**.

## Goal

A project pays for framing when framing buys it something, and a project that has not framed
is in a named state — not in violation.

## Out of scope

- **Removing cycles, or weakening them where they apply.** PDR-0002 is unchanged for a framed
  project: the appetite, the end date, the circuit breaker and the deliverables keep every
  rule they have today.
- **Routing a change by its size** — a classifier that decides how much process a diff
  deserves. Considered and refused below.
- **Nagging.** The tool names the state and what framing would buy; it never asks twice.
- **The rules that have nothing to do with cycles**: boundaries, contracts, pull-request
  scope, the test sheet and its verifier, the hooks, the forge's settings. They apply in every
  state, unchanged.

---

## Prior art

> **Mandatory section.** Minimum two named references.
> (`skeleton/docs/os/06-decisions.md` §2)

**How is this problem solved elsewhere?**

| Product / reference | Solution chosen | What we keep from it |
|---|---|---|
| [BMAD-METHOD](https://github.com/bmad-code-org/BMAD-METHOD/blob/main/docs/plan/choose-a-planning-path.md) | A page whose whole purpose is to do less: *"These are independent tools, not stages"*, *"otherwise skip it"*, *"You don't need BMad for an obvious, low-risk edit"* | **That the lightest path is documented, not tolerated.** It is a supported state, named in the product |
| [GSD Core](https://github.com/open-gsd/gsd-core/blob/next/docs/how-to/handle-quick-and-fast-tasks.md) | Two commands beside the loop, and a spec rule that quick mode *"MUST skip research, plan checker, and verifier by default"* | **That the escape is part of the design**, with its own rules, rather than an exception to be justified each time |
| [Spec Kit](https://github.com/github/spec-kit/issues/1174) | A `lean` preset *"without the ceremony of the full templates"*, and TinySpec routing by change size after 22 reactions on the complaint | **The warning.** A framework that ignores this is told, publicly, and answers late |
| [Shape Up](https://basecamp.com/shapeup) (the source of PDR-0002's cycles) | Appetite, a fixed cycle, a circuit breaker — for a **team with a shaper, a betting table and builders** | **The condition of its own value.** Shape Up is a way for an organisation to decide what not to build; it never claimed to be the way one person spends a Sunday |
| [PDR-0004](0004-ask-the-right-question-to-the-right-person.md), accepted 2026-09-18 | Routing on three axes, the first being the project's **stage**, *derived from the committed repository alone* | **The vehicle.** This decision is the first use of that axis, and it keeps its rule: the stage is read, never declared |

**The convention the user already knows:** a tool that has modes tells you which one you are
in — `git status` before a commit, a linter's warning beside its error, a dry run before the
real one.

**Why depart from it:** on one point. The projects above let the *user* choose the light
path, change by change. Here the state is **read from the repository**, and it governs one
family of rules only. A user cannot opt out of a rule by declaring themselves small; they
can only be in a project that has not yet framed anything — a fact anyone can check.

---

## Options considered

| Option | What the user experiences | Cost | Chosen? |
|---|---|---|---|
| Do nothing | A wall on the first delivery pull request, or a justified label on every one of them | 0 | No. Measured, and the field's most common complaint about frameworks of this kind |
| A. Route by the size of the change | A small diff gets fewer rules | Medium | No. It invites splitting a change to buy silence, and it puts the framework in the business of judging a diff's importance — which criticality already does, by module and by risk rather than by line count |
| **B. Route by the project's stage** | A project with no accepted charter is **unframed**: the cycle rules do not apply, everything else does, and every judging run says so | Low | **Yes** |
| C. Both | Stage, plus a size classifier inside a framed project | High | No, not now. B removes the wall; A can be reconsidered if a framed project asks for it, with evidence |
| D. Make the charter part of `init` | Every project is framed from its first minute | Low | No. It moves the decision earlier, when the person has the least to decide with, and it makes the first gesture heavier — the opposite of the goal |

## Decision

**Option B.** One more state, read and never declared.

**A project is framed or unframed.** It is **framed** when `docs/project/` holds an accepted
charter; it is **unframed** otherwise. Nothing is declared: the state is read from the
committed repository, as PDR-0004's first rule requires, so two machines on one commit always
agree.

**In an unframed project, the cycle rules do not apply.** `K1`, `K2` and `K3` — an accepted
charter and cycle, the circuit breaker, a named deliverable — are the rules that bound work
inside a cycle. Where there is no cycle, they have nothing to say, and they say nothing. The
`out-of-cycle` label is not needed, because there is no cycle to be outside of.

**Everything else applies, unchanged.** The module boundaries, the contracts and their
compatibility, the pull-request scope, the test sheet and its independent verifier, the
hooks, the forge's own settings: an unframed project is judged by all of them. This decision
removes a *bound on the work*, never a *check on the change*.

**And the state is never silent.** Every run that judges names it, beside the framework that
judges and the repository's guarded state (PDR-0005, PDR-0006). The diagnosis says what
framing would buy — an appetite, an end date, a circuit breaker, a decider — and how to
start. It says it once, where the reader already is; it does not nag.

**In a framed project, nothing changes.** PDR-0002 keeps every rule, including its removal
condition: more than one pull request in five labelled `out-of-cycle` means the bounds are
decoration. That measurement is about a project that *has* bounds, and it stays.

**Framing is a one-way gesture, and an ordinary one.** A project frames when it has something
to bound; accepting a charter moves it into the framed state on the next run, with no
migration. A framed project that wants to stop is not a supported move: closing a cycle and
accepting no other leaves the charter in place, and the project stays framed with no cycle —
which `K1` names for what it is, a project between cycles (D47).

---

## Expected behaviour

**Nominal journey, unframed.** Someone creates a project, declares a module, writes code with
their agent, opens a pull request. The scope, the boundaries, the hooks and — when the module
is user-facing or of high criticality — the test sheet with its independent verifier all
apply. The cycle rules do not fire. The output of every judging run names the state:
*unframed — the cycle rules do not apply here*.

**Nominal journey, framed.** A charter is accepted, then a cycle. From the next run, delivery
work names its deliverable, the circuit breaker applies on the end date, and the project is
told so in the same line.

**Edge cases and degraded states.** A charter that exists but is only *proposed* leaves the
project unframed: acceptance is the act, not the file. A charter accepted with no cycle is a
framed project between cycles — `K1` applies and says which of the two is missing. A charter
that cannot be read (malformed front matter) is a failure of `C1`, never a silent fall back
to unframed.

**Business rules.**

- The state is read from the committed repository, never declared, never guessed.
- Only the cycle rules — `K1` to `K3` — depend on it.
- No output presents an unframed project as a project without rules.
- A project is never asked twice to frame.

**Permissions:** unchanged. Accepting a charter is a change to a tracked file and goes through
the same approval as everything else.

**Acceptance criteria** *(testable)*:

- [ ] Given a project with no accepted charter, when a delivery pull request is checked, then
      `K1`, `K2` and `K3` do not fire, and the output names the project unframed.
- [ ] Given that same pull request, when it is checked, then the scope, boundary, contract,
      test-sheet and hygiene rules apply exactly as they do in a framed project.
- [ ] Given a project with an accepted charter and an accepted cycle, when a delivery pull
      request is checked, then the cycle rules apply as they do today, and the word *unframed*
      appears nowhere.
- [ ] Given a project with an accepted charter and no cycle, when a delivery pull request is
      checked, then `K1` fires and names the cycle as the missing piece, not the charter.
- [ ] Given a charter whose status is `proposed`, when any judging command runs, then the
      project is unframed.
- [ ] Given an unframed project, when the diagnosis runs, then it says what framing would buy
      and the gesture that starts it, in one place and once.

---

## Success criterion

> **Mandatory section.** Without a date nobody comes back to check, and the decision folder
> becomes a graveyard.

> We will consider this was the right call if, before **2027-03-31**: on a project created
> from the published version and never framed, **a first delivery pull request is merged with
> no charter, no cycle and no `out-of-cycle` label**, while at least one other rule of the
> framework refuses something in that same project — and, in the pilot, **framing still
> happens** and the cycle rules fire exactly as they do today.

How it is observed: the unframed project's pull requests and the rule that refused; the
pilot's charter, cycles and `out-of-cycle` count, which PDR-0002 already measures.

If the criterion is not met: an unframed project where nothing else ever refuses means the
framework's value was in the cycles alone, and this decision is the wrong half of the
problem. A pilot that stops framing means the state became an escape, and the decision is
superseded rather than adjusted.

---

## Removal condition

> **Mandatory section.** A feature with no removal condition is permanent by default,
> including when nobody uses it.

This decision will be removed if **a project with more than one code owner stays unframed for
more than two months while merging delivery work** — the state would then be serving teams as
an exit from the bounds, which is exactly what PDR-0002 exists to prevent. It is also removed
if the two words turn out to explain nothing: a framework whose vocabulary has to be taught
before it is useful has already lost the person it was written for.

---

## Impacts

- **Existing users**: the pilot and the validation project are framed and see no change. A
  project that was blocked by `K1` with no charter is unblocked, and told where it stands.
- **Modules and contracts**: none.
- **Decisions**: **PDR-0002** is narrowed in its field of application, not weakened — its
  rules, its criterion and its removal condition are untouched for a framed project.
  **PDR-0004** gains its first implemented axis, the stage, and keeps its rule that the stage
  is derived from the repository. **PDR-0006** gains a sibling: a second state the tool names
  rather than hides. **PDR-0003** is unchanged, and is what still holds an unframed project to
  evidence.
- **Support and documentation**: the handbook's workflow and governance chapters name the two
  states; `playbooks/framing.md` says what framing buys and when it is worth it;
  `PRODUCT.md` §3's tech lead criterion is unchanged, and the fifth user of PDR-0006 gains a
  path that does not start with a charter.
- **Data**: nothing is collected. The state is read from the tracked files at each run.

---

## Clarification of 2026-09-24 — a bound on the work, and criticality

Added in M11h, without changing the decision.

**Observation:** the decision says it *"removes a bound on the work, never a check on the
change"*. That is true of framing, and it was written as if it were true of every axis the
framework reads. It is not true of criticality, which has always moved checks: a `prototype`
module has never needed a test sheet, and since PDR-0011 the matrix of `05-workflow.md` §7
says, row by row, which checks each value buys.

**Clarification:** the sentence describes **the stage** alone. Being unframed changes which
rules bound the work — K1 to K3 — and nothing else. Which checks judge a change is decided by
the module's declared criticality, on the other axis, in every state. An unframed project with
a `critical` module pays that module's checks in full; a framed one with a `prototype` module
does not pay them. The two never substitute for each other.
