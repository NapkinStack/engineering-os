# PDR-0022 — Agents deliver alone; a person is asked only where it matters

- **Status**: Accepted (2026-11-01, by the maintainer: "ok on adopte cette philosophie dans tout
  nstack. go PDR-0022"), from the reading of #328 and of a delivered deliverable still shown as
  held on the third project. To be built by the next three workstreams
- **Date**: 2026-11-01
- **Decision makers**: NapkinStack maintainers (`@NapkinStack/maintainers`)
- **Modules affected**: the engine (`plan`, `claim`, `board`, `pr-check`, a new gesture), the
  framing playbook, the project and governance handbooks, the kernel

> The PDR describes **what the product must do and why**, never its implementation.
> The how belongs to an ADR.

---

## User problem

A project's progress is written by hand in a file a delivery must never touch (D183), under
`docs/`, which a human approves. On the third project, read on 2026-11-01:

- **About 36 of its last 152 merged pull requests look like keeping the plan**, by a rough match on
  their titles, which also counts legitimate changes of a cycle.
- **`nstack plan` says `0 of 24 accepted`** on a cycle where 9 deliverables have merges (D191), and
  an agent told the decider an acceptance was owed for each (#328).
- **A delivered deliverable stays held.** Its hold goes stale after 7 days and the plan then offers
  anyone a take-over of finished work. Its issue on the forge stays open.
- **A person cannot tell what needs them**: it is spread across the plan, the issues and the agents'
  summaries, so they read everything or nothing.

The same project's agents also show the opposite risk: one wrote in its notes an approval that does
not exist. Removing the person must never mean believing an agent's word.

## Goal

Where a person's judgement changes nothing, agents carry the work to its end, and the repository
holds the proof. A person sees one list of what needs them, and when it is empty they can walk away.

## Out of scope

- **Who approves a change.** PDR-0021 and ADR-0004 stand: `high`, `critical` and the project's rules
  keep a human.
- **What the decider decides**: the charter, a cycle and its scope, a deferral, a closure's outcome.
- **Deciding at merge.** Several pull requests may deliver one deliverable: a merge proves no criterion.
- **Reading an approval.** It lives on the forge. The plan does not depend on one to say progress.

---

## Prior art

Read 2026-11-01; most of it is vendors reporting on their own systems.

| Product / reference | Solution chosen | What we keep from it |
|---|---|---|
| [Vercel](https://vercel.com/blog/58-percent-of-prs-in-our-largest-monorepo-merge-without-human-review) | A classifier routes low-risk pull requests past human review; it reports 671 skipped, none reverted | **Effort follows consequence**, already our `criticality` (PDR-0011) |
| [Augment Cosmos](https://augmentcode.com/blog/solving-code-review-with-cosmos) | A risk analyser approves or routes, inside a service | The routing, **without the service**: here it is the repository's |
| [arXiv 2605.08017](https://arxiv.org/pdf/2605.08017) | Measures agents' pull requests: autonomous merges are 0.07% | The ground is not taken |
| [Linear's GitHub integration](https://linear.app/docs/github) | An issue moves to Done on its pull request's merge | **Progress nobody types**; not its assumption that one merge finishes the work |
| [Spec Kit, BMAD, OpenSpec](https://docs.bswen.com/blog/2026-08-07-ai-spec-frameworks-compared) | Documents and handoffs; the criticism is ceremony, and the lighter one gains | **The price of ceremony** (PDR-0011) |

**The convention the user already knows:** someone moves a card to Done.

**Why depart from it:** the mover is either a person spending attention on nothing, or a merge that
does not know whether the work is finished.

---

## Options considered

| Option | What the user experiences | Cost | Chosen? |
|---|---|---|---|
| Do nothing | A plan pull request per acceptance, or a plan that lies; finished work offered for take-over | 0 | No |
| Accepted at merge (#328's first proposal) | No gesture, and `accepted` on a part of a deliverable | Low | No |
| A bot commits the state after a merge | No gesture, a dependency on CI, noise on the default branch | Medium | No |
| **A. The agent records the delivery, checked by a rule; the state is computed; one list says what needs a person** | No plan pull request during a cycle; a person reads one list | Medium | **Yes** |

## Decision

**Option A, and the principle below binds all of NapkinStack.**

**The principle, invariant P8 of `PRODUCT.md`:** a person is asked only where their judgement changes
something. Whatever a rule can establish, an agent carries through and the repository proves; an
agent's word alone never counts as proof.

1. **An agent records a delivery**, with one gesture, no pull request and no file under `docs/`: for each
   criterion of the deliverable, what holds it. It lives with the deliverable's hold, so it needs no
   forge and survives a squash.
2. **A rule checks the record.** It is refused when the default branch records no merge of the
   deliverable, when all its merges were reverted, or when a criterion is left unanswered. It may come
   from a session on the hold, its person, or the decider. A holder gone: the hold goes stale, another takes
   it over and records.
3. **The state is computed, one way, everywhere.** `delivered` comes from that record: `plan`, `claim`,
   `board` and `pr-check` read the same answer. A delivered deliverable is not held, is never offered for
   take-over, and its issue closes. All its merges reverted afterwards: it reads as back in work, and says why.
4. **The cycle file keeps decisions**: scope, criteria, deferrals. The states are written there once,
   at the closure, in one pull request, from the records.
5. **The word stays `delivered`.** `accepted` is what the closure records, since an approval is not in the
   repository. Where the project waives approval (`framing.md` §3), the decider's word is quoted once, at
   that closure, for the cycle.
6. **A criterion only a person can try stays with them.** The cycle names its acceptance issue, as today; the
   deliverable waits and is listed until their answer is there.
7. **`nstack plan` opens with what needs a person**: a trial, a word owed, a cycle at its end, and later a
   change waiting for a human approver. Empty, it says *nothing needs you*, and only when that is certain
   (clarified for D194: a decision due is an agent's to read, P8, and only a missed one comes to a person).
8. **Joining costs one gesture.** Giving an agent its identity becomes a command and one click at the forge.
9. **The rest of NapkinStack is read against P8**: each manual gesture a playbook asks for is automated,
   removed, or kept with its reason.

---

## Expected behaviour

**Nominal journey.** An agent merges the last pull request of D30, then records it. `nstack plan` says
*1 of 12 delivered*, D30 is no longer held, its issue closes. The decider opens the plan: *nothing needs
you*. At the end of the cycle, one pull request writes every state.

**Edge cases.** A deliverable with three merges of five: the plan says so, and no record is made until each criterion
is held. An agent recording a deliverable with no merge: refused, and the message says why. A false record, each
criterion named and none really held: the rule cannot see it; the closure's reading can, and it is counted.
A shallow clone or an unreachable remote: the plan says it could not read, never that nothing is delivered.

**Acceptance criteria** *(testable)*:

- [ ] Given a deliverable with a merge and every criterion named, when an agent records it, then the plan
      says `delivered`, not held, with no pull request made.
- [ ] Given no merge, every merge reverted, or a criterion unanswered, then the record is refused with
      the rule, the reason and the action.
- [ ] Given a delivered deliverable, then its hold never goes stale, `claim` and `--take-over` refuse it,
      and `board` closes its issue.
- [ ] Given a delivered deliverable whose merges are all reverted, then it reads as back in work.
- [ ] Given a closure, then one pull request writes the states from the records.
- [ ] Given a trial, a word owed or a cycle at its end, then the plan opens with it; given none, it says
      *nothing needs you*; given what it cannot read, it says it cannot say.
- [ ] Given a new agent, then one command and one click give it a working identity, isolated from any
      other account on the workstation.

---

## Success criterion

By 2027-03-31, on the third project and one new project made by someone who is not a maintainer: no plan
pull request during a cycle apart from changes of scope; at most 1 false record in 40 at the closures; and
the new project's first agent working under its identity in under 15 minutes.

## Removal condition

Removed — states written by hand again — if more than 1 record in 20 is found false at a closure, or if a
decider says the list missed something that needed them, twice in a cycle.

## Impacts

- **The engine**: a gesture to record; the computed state in `plan`, `claim`, `board` and `pr-check`; the list.
  ADR-0007 gains the record's form; a command to give an agent its identity (ADR-0004).
- **The skeleton**: `framing.md` §4 and §5; the project and governance handbooks; the kernel's *Close*;
  D191's section of the plan gives way to the computed state.
- **Projects**: a minor version. States already written stay true; nothing to migrate by hand.
- **`PRODUCT.md`**: invariant P8.
