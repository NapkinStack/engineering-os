# Playbook — Framing

> **Trigger.** Load this playbook when you are asked to frame a project, to plan its next
> cycle, to re-frame the current one, or to write a cycle's closure.

---

## Your posture

You are the **framer**. You propose; the decider decides.

| You do | You never do |
|---|---|
| Interview the decider, one subject at a time | Decide in their place, or fill a gap with an invention |
| Propose the field's convention by default, and say so | Propose more than the need |
| List the open questions | Let a cycle be accepted with a blocking question open |
| Keep the first cycle small | Split into many modules on day one (`docs/os/02-modules.md` §3) |

The documents you write carry the project, not the conversation: every later session reads
them, and reads nothing else of what was said.

---

## 1. Frame the project: the charter

Start from what the decider gives you. When `docs/project/discovery.md` exists, its decision
must be **go**: the charter reuses its users, problem, success signals, no-gos and risks, and
you ask only what it leaves open. Otherwise — an idea alone — propose a discovery first
(`discovery.md`); a specification already challenged can be framed directly. Read the source
entirely, then interview, one subject at a time, asking only what you cannot infer:

| Subject | Ask | The charter records |
|---|---|---|
| Users | Who uses it, in what situation, with what problem? | The users and their problem |
| Outcome | What must be true for the project to be finished? | Success criteria, measurable and dated |
| Constraints | Law, money, security, data, platforms, deadlines | The constraints |
| Risks | What could make it fail, or cause harm? | The risks, and the criticality they imply |
| Vocabulary | The domain's words, and what each one means | The vocabulary |
| Not this project | What it will deliberately not do | Out of scope |

A domain that moves money, handles personal data or acts on someone's behalf raises the
criticality of the modules concerned, and the `security.md` playbook applies from the first
cycle: say so to the decider.

Write `docs/project/charter.md` from `docs/project/_CHARTER_TEMPLATE.md`, with
`status: proposed` and the open questions at the end.

## 2. Plan a cycle

1. **Goal** — one sentence, the one outcome of this cycle.
2. **Deliverables** — a finite list, `D1`, `D2`…, each an outcome a user can observe. Each
   gets acceptance criteria written *given · when · then*; they become its test sheet
   (`verification.md`).
3. **Unknowns** — a blocking unknown becomes a *spike* deliverable, whose output is
   knowledge (`docs/os/05-workflow.md` §3).
4. **Modules** — name each deliverable's module. Propose a new module only against the
   tree of `docs/os/02-modules.md` §3: one module is often enough to start.
5. **Appetite** — ask the decider how many weeks they **want** to spend, not how long it
   will take. When the deliverables do not fit, cut the scope; never stretch the appetite.
6. **Later** — everything else goes to the *later* list, visibly.

Write `docs/project/cycles/NN-<slug>.md` from `docs/project/cycles/_TEMPLATE.md`, with
`status: proposed` and `end` = `start` + the appetite, then run `nstack plan`.

## 3. Hand over to the decider

Present the charter, the cycle, the open questions, what went to *later*, and what you are
unsure of. The decider amends, then sets `status: accepted` — on the charter, then on the
cycle — in a pull request they approve. The modules accepted there are created with
`nstack new-module`, with `--user-facing` when a user sees them.

## 4. During the cycle

- **A new idea** goes to *later*. It enters the cycle only if the decider re-frames:
  swapping a deliverable out, or closing the cycle early.
- **An urgent fix** outside the cycle — an incident, a production defect — goes in a pull
  request with the `out-of-cycle` label and the line `Out of cycle: <reason>`.
- **A deliverable** moves `proposed` → `ready` (acceptance criteria written) →
  `in-progress` → `accepted` (its test sheet run, its pull request approved).

## 5. The end of a cycle

**Every deliverable accepted** — write the closure: what was delivered, which success
criteria moved, what was deferred; set `status: closed`, `outcome: completed`, `ended_on`.

**The end date reached first** — the circuit breaker: nothing is extended. Present the
three choices, with the state of every deliverable:

| The decider chooses | `status` | `outcome` |
|---|---|---|
| Ship what is accepted | `closed` | `shipped` |
| Frame a new cycle, with a new appetite | `stopped` | `reframed` |
| Stop the project | `stopped` | `stopped` |

The closure is where the next framing starts. When the charter's success criteria are met,
the project is finished: say so to the decider.
