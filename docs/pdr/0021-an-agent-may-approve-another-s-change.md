# PDR-0021 — An agent may approve another's change, where the project says so

- **Status**: Proposed (2026-10-28, D174), from the maintainer's reading of the third project
  before a second contributor joins it
- **Date**: 2026-10-28
- **Decision makers**: NapkinStack maintainers (`@NapkinStack/maintainers`)
- **Modules affected**: the engine (`doctor`, the settings it prints), the project's answers, the
  code owners file, the pull request template and the bug form, the governance and measurement
  handbooks

> The PDR describes **what the product must do and why**, never its implementation.
> The how belongs to an ADR.

---

## User problem

ADR-0004 makes a human code owner's approval the barrier an agent cannot cross, and defers
letting an agent's approval count, for modules of criticality `prototype` and `standard` only, to
a measurement: *over the pilot's last 20 pull requests carrying a sheet, the human found nothing
the verifier had missed* (PDR-0003). On the third project, read on 2026-10-28:

- **394 pull requests merged, 175 of them with a filled test sheet**, since 2026-10-12.
- **No approval written on any of them**, and one with a review at all. Its ruleset requires
  no approval: the decider's *go* is given in the session, and the decider says they no longer
  read what the verifier did, and that the gesture is no use, only a brake.
- **The measurement was never taken**: nothing in a project gives the approver a place to say
  what they found beyond the verifier, and a criterion that asks a human what they found in a
  review they do not make can never be met.

So the barrier ADR-0004 describes is not where the work happens, and the deferred decision waits
on a number nobody can produce. Meanwhile the same project is about to take a second contributor,
with their own agent. With no approval required, either one's agent may merge anything once the
checks are green: the holds (K5) keep two people off one deliverable, but nothing makes one
contributor's work pass under another's eyes before it merges.

## Goal

A project chooses who may approve a change to its `prototype` and `standard` modules: a human,
as today, or another contributor's agent — independent, expert for the module, under an identity
no author holds; everything else keeps a human approver; and whether the choice holds is
measured on what escapes, not on reviews nobody makes.

## Out of scope

- **`high` and `critical` modules.** ADR-0004's bound is kept: a human approves them.
- **The project's own rules.** The charter, the cycles, the decision records, the framework's
  files and the project's answers — this one included — keep a human approver: an agent never
  approves the change that would let agents approve more.
- **An author approving its own work**, through any identity (`05-workflow.md` §10). A
  contributor alone has nobody else's agent: their changes wait for a human.
- **Merging.** Approving and merging stay two acts; auto-merge joins them (`07-governance.md` §7).
- **Judging whether an approver is expert.** The approval declares its profile; whether the
  profile fits the module is the project's to judge.

---

## Prior art

| Product / reference | Solution chosen | What we keep from it |
|---|---|---|
| GitHub rulesets — *required approving reviews*, *Code Owners*, *approval of the most recent push* | Approvals from accounts with write access count; a code owner review is required only on the paths the code owners file names; the last pusher's approval does not count. Reported in practice, not documented: an App's approval counts once it may write contents, and never on a pull request it opened; an App is never a code owner | **The forge enforces it, path by path**: the paths a human must approve are the ones the code owners file names; nothing is lowered |
| OpenSSF OSPS Baseline — *at least one non-author human approval* (level 2) | A human approves every change | **Kept as the default**: a project that answers nothing approves as today, and a project that targets the Baseline keeps it |
| SLSA Source Track L4 — *two-party review* | Two trusted reviewers, their review attested | **Trust is in the reviewer's identity**, not its nature: a reviewer counts because the author cannot hold its identity |
| Google's owners and *readability* (*Software Engineering at Google*, ch. 9) | A change needs an owner's approval and a reviewer certified for its language | **Expertise is declared per area**: here, the approver's profile for the module |
| Escaped defects (*Accelerate*'s change failure rate; defect escape rate in QA) | Quality measured by what reaches users broken | **Measured on what escapes**, a number the work itself produces |

**The convention the user already knows:** a pull request needs one approval from someone other
than its author before it merges.

**Why depart from it** *(only where the project chooses)*: the convention assumes the approver
reads. On the third project the human does not, and the verifier already runs the sheet; the
approval then carries no judgement, and an independent expert agent's carries more.

---

## Options considered

| Option | What the user experiences | Cost | Chosen? |
|---|---|---|---|
| Do nothing | A required human approval nobody gives with judgement, or no approval at all — and a second contributor's agent merging unseen | 0 | No |
| Keep waiting on PDR-0003's measurement | The same, until a number that cannot be produced | 0 | No |
| **A. The project chooses; another contributor's agent approves `prototype` and `standard` modules; the forge keeps the rest for a human; escapes are measured** | One answer, changed in a pull request a human approves; then the other contributor's agent verifies and approves | Medium | **Recommended** |
| B. An agent's approval counts everywhere | No place left where a human must look, `high` and `critical` included | Low | No |

## Decision

**Option A.**

1. **The project answers who approves** its `prototype` and `standard` modules: `human`, the
   default and today's behaviour, or `agent`. The answer is the decider's word, changed by a pull
   request a human approves.
2. **On `agent`, the forge requires one approval on every change**, and keeps a human's where it
   must through the code owners file: it names a human owner for every `high` and `critical`
   module, for the framework's files, the project's answers and its records (`docs/`), and no
   default owner for the rest. The code owners review stays required; approvals are dismissed
   on a new push; the last pusher's approval does not count; nobody is on the bypass list.
   Nothing is lowered: a project moving to `agent` changes its code owners file in a pull
   request a human approves.
3. **An agent's approval counts** when it comes from an identity of its own — never one an
   author of the change holds — and says, in the approval, the session it ran in and its profile
   for the module, in a few words. Where the module asks for a sheet, the approver is the
   verifier who ran it; where it asks none, the approver reviews the change on its oracle and
   its checks.
4. **What escapes is measured**: the bug form asks for the pull request that brought the defect,
   or says it is unknown. The share of approved pull requests named by a defect found within 30
   days of their merge, per module and per answer, tells whether the answer holds. PDR-0003's
   measurement, *what the human found beyond the verifier*, is replaced by it.
5. **ADR-0004's deferred decision is taken here**, within its bound, for the projects that
   answer `agent`; for the others, ADR-0004 stands as written. Where PDR-0008 calls an approval
   necessarily human, it now reads: human, except on `agent` within this bound.

---

## Expected behaviour

**Nominal journey.** Two contributors, each with an agent under an identity of its own; the
project answers `approval: agent`. Alice's agent delivers a deliverable in a `standard` module.
Bob's agent runs the sheet and approves, saying *session bob-v7 — the module's language and its
test tools*. The forge counts it; the pull request merges on green.

**Edge cases.** Bob's agent pushing a fix to Alice's change, then approving it: the approval does
not count, the last push is its own. A change to the contracts module (`high`) waits for its human
owner, whatever the agents said. A change to the code owners file or the project's answers waits
for a human. A project answering `human` sees no change. Alice alone, with no other contributor:
her changes wait for a human.

**Acceptance criteria** *(testable)*:

- [ ] Given `approval: agent`, then `doctor` asks for one required approval, the code owners
      review, dismissal on push, the last push's approval, no bypass, and a code owners file
      naming a human for every `high` and `critical` module, the framework's files, the answers
      and `docs/`, with no default owner; and names each that is missing.
- [ ] Given `approval: human`, or no answer, then `doctor` asks what it asks today.
- [ ] Given a project created with `agent`, then its code owners file is as point 2 says.
- [ ] Given the bug form, then it asks for the pull request that brought the defect, or unknown.
- [ ] Given the pull request template, then the approver's line asks for its session and profile.

---

## Success criterion

By 2027-04-30: on the third project with two contributors answering `agent`, at least 40 pull
requests approved by the other contributor's agent, at most 2 of them named by a defect found
within 30 days of their merge, and none merged without an approval.

## Removal condition

Removed — the answer `agent` withdrawn, ADR-0004 back as written — if more than 2 in 40 of those
pull requests are named by a defect within 30 days, or a change merged that point 2 keeps for a
human without one.

## Impacts

- **The engine**: `doctor` and the settings it prints read the answer.
- **The skeleton**: the answer, asked at `nstack init`; the code owners file on `agent`; the
  pull request template's approver line; the bug form's pull request field; the governance
  handbook (§7, the verifier's place in §3), the measurement handbook and the contributing guide.
- **Projects**: nothing on `human`, the default. On `agent`, one identity per contributor's
  agent, the code owners file, and the forge's settings `doctor` names.
- **Records**: ADR-0004's deferred decision, PDR-0003's measurement and PDR-0008's *necessarily
  human* point here, each with a clarification when this record is accepted.
