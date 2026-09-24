# PDR-0011 — Ceremony follows consequence

- **Status**: Proposed (2026-09-24)
- **Date**: 2026-09-24
- **Decision makers**: NapkinStack maintainers (`@NapkinStack/maintainers`)
- **Modules affected**: `nstack pr-check` (T1, T4), `nstack manifests` (M8), `nstack
  new-module`, `nstack doctor`, the skeleton's handbook (`05-workflow.md` §7,
  `07-governance.md` §6 and §7, `08-quality.md` §7) and playbooks, `PRODUCT.md` §2 and §3

> The PDR describes **what the product must do and why**, never its implementation.
> The how belongs to the implementation plan and, where structuring, to an ADR.

---

## User problem

The framework has always promised proportionality. `07-governance.md` §6 said it in a
diagram, `05-workflow.md` §7 in a seventeen-row Definition of Done, `08-quality.md` §7 in a
thirteen-row reliability table — three shapes, and only the diagram knew `prototype`. The
engine executed none of them: one threshold, written in four places in the code (D67).

**What that cost, measured on the pilot** (`NapkinStack/flet`, 23 pull requests in its first
three days, driven by a session that knew nothing of this repository):

| Measured | Why |
|---|---|
| **16 of the decider's 54 turns** were a bare "approved" or "merged", 7 of them pure relay | nothing merged an approved pull request by itself |
| **6 verification rounds** on one read-only `high` module; **3 of its 11 defects introduced by the late rounds** | one fix invalidated every scenario (D71), and nothing said one round was enough |
| **5 turns** asking to simulate evidence the world could not supply | a criterion nobody can meet was required, and paid in counterfeit (D72) |
| `screening` declared **`high`** — it reads, holds no key, places no order | the agent chose the value on a command line with no help and no price shown (D70) |
| a level-3 control imposed from the first commit | the checklist requires a non-author human approval, which the OpenSSF OSPS Baseline places at the top of three levels (D69) |

The person who pays is the decider of a small project: every module costs what a critical
one costs, and the approvals they give carry no judgement. The person who is badly served is
the decider of a critical one: nothing distinguished `critical` from `high`, so the top value
bought nothing more.

## Goal

A project pays, per module and per project, what the consequence of a failure costs — and
nothing more — and every price is stated before it is chosen.

## Out of scope

- **Lowering what a module that declares its consequence pays.** A `critical` module pays in
  full, in every project, whatever its exposure.
- **Routing by the size of a change.** Refused by PDR-0007, for the same reason: it invites
  splitting a change to buy silence.
- **Inventing a scale for the project's exposure.** One exists, is machine-readable and is
  mapped to regulation; whether it maps cleanly onto our rules is a probe, recorded in its own
  ADR.
- **A cap on verification.** The framework asks for one round; a project that wants more
  decides it, in its own ADR.
- **Certifying anything.** The tool reports what it observes, never conformity.

---

## Prior art

| Product / reference | Solution chosen | What we keep from it |
|---|---|---|
| [DO-178C](https://en.wikipedia.org/wiki/DO-178C) Design Assurance Levels, ISO 26262 ASIL, IEC 61508 SIL | An objectives table indexed on the consequence of a failure, audited by humans | **The table.** Ours already existed; the difference is that CI executes its machine rows and the others are named as owed |
| [OpenSSF OSPS Baseline](https://baseline.openssf.org/) | Three maturity levels of controls for a project, machine-readable, mapped to the EU Cyber Resilience Act | **The scale for exposure**, if M11g's probe finds the mapping clean — a sentence a project can say to someone outside it |
| [GitHub Spec Kit](https://github.com/github/spec-kit), issue #1174 and Scott Logic's review | One process for every task, then a `lean` preset after the complaint *"this workflow behaves the same regardless of task complexity"* | **The warning.** The market leader's second weakness was ours too; its answer came late and by preset, ours is by declared consequence |
| DORA, *ROI of AI-assisted Software Development* (2026) | Names the **verification tax** and finds AI is an amplifier of the system around it | **Where the cost is.** It is in verifying and approving, so that is where proportionality has to act |
| [PDR-0003](0003-approve-a-change-on-evidence-of-its-behaviour.md) and [PDR-0007](0007-frame-a-project-when-framing-buys-something.md) | Evidence proportionate to criticality; framing paid when it buys something | **The same principle**, applied to the whole matrix rather than to one rule or one stage |

**The convention the user already knows:** a safety standard's level — you say what a failure
costs and the level tells you what you owe.

**Why depart from it:** on one point. Those standards are audited by people after the fact;
here every row a machine can read is refused before merge, and every row it cannot read says
so. A table that pretends CI verifies acceptance testing teaches people to ignore it.

---

## Options considered

| Option | What the user experiences | Cost | Chosen? |
|---|---|---|---|
| Do nothing | Every module and every project pays the top tier; the decider relays approvals | 0 | No — measured above |
| A. One project-wide switch, `solo` / `team` | A small project gets fewer rules | Low | No. Measured against the pilot's 23 pull requests, it would have changed **none** of them: the cost came from the module's value and the forge's settings, not from team size |
| **B. Two axes, two owners** | Each module pays for its declared consequence; each project for its declared exposure; neither overrides the other | Medium | **Yes** |
| C. A per-rule configuration file | Every rule tuned by the project | High | No. It moves the decision from *what a failure costs* to *which rule annoys me*, and it is configuration for a single use (`PRODUCT.md` §6) |

## Decision

**Option B. Two axes, two owners, no overlap.**

| Axis | Unit | Declared in | Governs |
|---|---|---|---|
| **Assurance** — what a failure of *this code* costs | the module | `criticality` in its manifest | the engine's checks: test sheet, verifier, confirmation at head, runbook |
| **Exposure** — what a failure of *this project* costs others | the project | a target level | the forge's requirements: pull requests, status checks, human approval |

**One matrix says when.** `05-workflow.md` §7 is the single source of what each criticality
requires, `prototype` included; the other documents say *what* a requirement holds and point at
it for *when*. Every row is **machine** — a check fails on it — or **owed** — a human owes it
and no check reads it. `critical` differs from `high` by what it adds: every scenario re-run at
the head after the last fix, e2e present and green, the runbook referenced by the sheet.

**One round.** The framework asks for one sheet and one verifier who is not an author. After a
fix, an explored scenario is **confirmed** at the head, not re-run from scratch; `critical`
re-runs everything, which is what the top value costs.

**The choice returns to the decider, with its price.** The criticality is the decider's, recorded
in the module's creation decision, and the tool prints what the chosen value costs and what its
neighbour would have cost before anyone pays for it.

**Human review belongs to exposure.** Approval by a non-author human protects the people who
depend on a project, not the code of one module; it leaves the criticality matrix. The four
settings of `07-governance.md` §7 keep holding together where they are required, so ADR-0004
needs no amendment. Which exposure scale, and from which level approval blocks, is M11g's to
settle in ADR-0005 — **after** its probe. Until then, the forge's checklist applies as today.

**The approval is one gesture.** Auto-merge removes the human from the merge, never from the
approval.

---

## Expected behaviour

**Nominal journey.** A decider creates a module and is shown the value's price and its
neighbour's; they choose, and the creation ADR records it. A pull request on a `prototype`
module needs no sheet; on a `standard` one, a sheet only when a user sees the change; on `high`
and `critical`, always. A fix after verification costs a confirmation of the explored scenarios
at the head, except on `critical`. The approval is given once, and the merge follows.

**Edge cases and degraded states.** An unknown criticality reads as the strictest until a
reader fixes it. A deliverable that waits on someone outside the project is a spike or a
dependency with a date, never a criterion to simulate. A module declared lower than its
consequence is visible — the value sits in a reviewed file and in every run's output — and is
measured, not guessed at.

**Business rules.**

- The two axes never override each other.
- The framework never asks for more than one round.
- Every row of the matrix names who judges it.
- Every price is shown before it is paid.

**Permissions:** unchanged. A criticality is changed in a reviewed file, by the code owner's
approval.

**Acceptance criteria** *(testable)*:

- [x] Given a `prototype` module changed beyond its description, when the pull request is
      checked, then no test sheet is required. *(M11b)*
- [x] Given a `critical` module, when the sheet was verified before the last fix, then every
      scenario must be re-run at the head; on `high`, an explored scenario confirmed at the head
      is enough. *(M11d)*
- [x] Given `nstack new-module`, when a criticality is chosen, then the price of that value and
      of its neighbour is printed, and the next steps ask the creation ADR for one sentence
      saying why this value and not its neighbour, settled by the decider. *(M11c)*
- [x] Given the handbook, when the requirements of a criticality are looked for, then one table
      holds them, and a test refuses a second description. *(M11a)*
- [x] Given a repository, when the diagnosis runs, then it reads whether auto-merge, squash-only
      and branch deletion are on. *(M11f)*
- [ ] Given a declared exposure target, when the diagnosis runs, then it reports the level
      observed and the target apart, and never reads as a certification. *(M11g, after its
      probe)*

---

## Success criterion

> We will consider this was the right call if, before **2027-03-31**: in the pilot, **no pull
> request needs a second adversarial round because the framework asked for one**, **no decider
> turn is a bare relay** of an approval already given, and every module created after v0.7.0
> has its criticality **recorded with a reason** in its creation decision — while every
> `critical` module still pays every machine row of the matrix.

How it is observed: the pilot's pull requests and their verification history; the decider's
turns, counted as the M11 plan counted them; the creation ADRs.

If the criterion is not met: rounds that persist mean the confirmation is not trusted —
adjust T4's wording before its rule. Relay turns that persist mean the approval is not yet one
gesture — a forge setting, not a decision. Criticalities chosen without a reason mean the price
is printed where nobody reads it — adjust where, not whether.

---

## Removal condition

This decision will be superseded if **two modules declared below `high` ship to a user a
defect that a machine row of the next value up would have refused** — the proportional floor
would then be in the wrong place. It is also superseded if, in a project with users, **more
than half its modules sit at `prototype`**: the value would have become a hiding place rather
than a statement.

---

## Impacts

- **Existing users**: the pilot's `screening` module is declared `high`; the matrix now says
  what that buys and what `standard` would have bought. Whether it revises the value is a
  measurement, not an instruction. `tool-library` sees fewer sheets asked on `standard` modules
  a user does not see.
- **Modules and contracts**: `criticality` keeps its four values; no field is added.
- **Decisions**: **PDR-0003** keeps its rule — a sheet and an independent verifier — and gains
  the matrix as the place its trigger is read. **PDR-0007** is clarified: criticality has always
  moved checks, framing never does. **ADR-0004** is unchanged. **ADR-0005** (M11g) records the
  exposure scale, or records that the probe sent it to M13.
- **Support and documentation**: `05-workflow.md` §7 is the matrix; `07-governance.md` §6 and
  `08-quality.md` §7 point at it; `PRODUCT.md` §2 says what the framework does not buy on day
  one, and §3 names the user it now serves.
- **Data**: nothing is collected.
