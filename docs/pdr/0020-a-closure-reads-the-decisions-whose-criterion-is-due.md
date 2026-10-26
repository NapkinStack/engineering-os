# PDR-0020 — A closure reads the decisions whose criterion is due

- **Status**: Accepted (2026-10-26, by the agent the maintainer delegated the decision to:
  *you can decide as an expert*), option A with points 5 to 8 clarified at acceptance, built as
  D168; proposed the same day (D167), from #279
- **Date**: 2026-10-26
- **Decision makers**: NapkinStack maintainers (`@NapkinStack/maintainers`)
- **Modules affected**: the engine (the plan's checks), the decision forms, the framing
  playbook's closure, the decisions handbook

> The PDR describes **what the product must do and why**, never its implementation.
> The how belongs to an ADR.

---

## User problem

Every decision record carries a success criterion with its date, and a removal condition (the PDR
and ADR forms). The framing playbook asks a cycle's closure to *read again every decision anchored
to this cycle, and every one whose criterion's date has passed: met, missed, or superseded — say
which in the record*. Nothing checks it. A closure that skips it passes `nstack plan` and
`nstack fitness`, and the decisions stay unread with nothing to show it.

The third project missed it twice in a row. One cycle stopped and one closed, and neither read
the five records whose criteria pointed at them. A later review of the documents found it by
hand. The closure that did read them read only the records written during that cycle.

A criterion nobody reads is a decision nobody can remove: the removal condition is only ever met
if someone looks.

## Goal

At a cycle's closure, the decider is told which decisions are due — anchored to that cycle, or
whose criterion's date has passed — and each one says, in its own record, when it was read and
what was found.

## Out of scope

- **Judging the criterion.** Whether a criterion is met is the decider's word. The engine says a
  reading is due, never what it should conclude.
- **Refusing a closure at once.** A rule that turns every project red on its next closure, for
  records written before the rule, would be paid by people who could not have known. A warning
  comes first.
- **The framework's own registers.** This repository reads its records by its own process; the
  rule is for the projects nstack frames.
- **Reminders between closures.** The closure is the moment the playbook already sets; a calendar
  is not.

---

## Prior art

| Product / reference | Solution chosen | What we keep from it |
|---|---|---|
| [AWS Prescriptive Guidance — the ADR process](https://docs.aws.amazon.com/prescriptive-guidance/latest/architectural-decision-records/adr-process.html) | Records are reviewed at set points and their status updated | **A decision is read again at a set moment**, and its record says it |
| OKRs (John Doerr, *Measure What Matters*) | Key results scored when the period ends | **A criterion is scored when its period ends**, by the person who owns it |
| Fitness functions (Ford, Parsons, Kua, *Building Evolutionary Architectures*) | An architectural decision checked by an automated function | **What can be checked is checked**: here, that the reading happened, never its verdict |
| GOV.UK Tech Docs Template — page expiry (`last_reviewed_on`, `review_in`) | A page past its review date shows a banner, computed at build | **Computed, never remembered** — but on a calendar of its own, and a date bumped without reading clears it: here the moment is the closure, and the line carries a verdict |
| MADR 4 — *Confirmation* | The record says how compliance with the decision will be confirmed | Kept as it is: the criterion says *what*; nothing in MADR says *when* it is read, which is this gap |
| adr-tools, Log4brains | Statuses and supersession; no reading is asked | **A record is never rewritten**: a decision that no longer holds is superseded by a new one |
| Agents reviewing stale records (skills that audit a register for drift) | A model reads the register on request | Refused as the barrier: not deterministic, and asked only by who remembers to |

**The convention the user already knows:** a review date on a decision, and its outcome written
beside it.

---

## Options considered

| Option | What the user experiences | Cost | Chosen? |
|---|---|---|---|
| Do nothing | The playbook's sentence, missed when nobody remembers it | 0 | No |
| **A. Each record says when it was read; the plan warns when a reading is due** | At a closure, `nstack plan` names the decisions due; each gets one line, *Read at <cycle>'s closure, <date>: met \| missed \| superseded*, and the warning goes | Low | **Recommended** |
| B. The closure lists the decisions it read, in the cycle's front matter | One list per closure, as the success records (PDR-0019) — but a decision's life is then scattered across cycle files, and the record itself never says it was read | Low | No |
| C. A refusing rule from the start | The same as A, but red on the next closure of every existing project | Low, and paid by the wrong people | No |

## Decision

**Option A.**

1. **A reading is due** for an accepted decision record of the project (`docs/pdr/`, `docs/adr/`)
   when a cycle is closed or stopped and the record's success criterion names that cycle, or a
   date on or before the day it ended.
2. **The record says it was read**, in a line of a fixed shape in its success criterion section:
   *Read at <cycle>'s closure, <date>: met | missed | superseded*, with a date on or after the
   closure.
3. **`nstack plan` warns**, naming each record due, the closure it is due at and the line to
   write. It never fails, in the first version that carries it. Whether it becomes a refusal is a
   decision of its own, taken on what the warning found.
4. **The forms show the line**, commented, under the success criterion. The framing playbook's
   closure points to the warning instead of asking the agent to remember.
5. **The warning is a rule of the plan, C10** *(clarified at acceptance)*: shown with the plan's
   checks, so `nstack fitness` and CI show it on the closure's pull request, as C9's warning is —
   not only in `nstack plan`'s view.
6. **What is read is exact** *(clarified at acceptance)*: the success criterion section only; a date
   written `YYYY-MM-DD`; a cycle named by its file (`03-the-window`) or as *cycle 03*. A date written
   otherwise is not read, and the forms say so. Nothing is inferred from prose.
7. **A reading answers what was due at its closure** *(clarified at acceptance)*: a criterion naming
   a later date is due again at the closure that passes it.
8. **A record is never rewritten** *(clarified at acceptance)*: the reading line is its one
   addition. A *missed* criterion is presented to the decider, whose answer is a decision of its
   own — a new record superseding it, or the removal condition applied.

---

## Expected behaviour

**Nominal journey.** Cycle 03 closes on 2026-11-07. The project's ADR-0003 has a criterion that reads *by 2026-11-07,
…*. `nstack plan` warns: *ADR-0003's criterion is due at 03-the-window's closure (2026-11-07):
read it, and write "Read at 03-the-window's closure, 2026-11-08: met | missed | superseded" in its
success criterion*. The decider reads it, says *met*; the line is written in the closure's pull
request; the warning goes.

**Edge cases.** A record whose criterion names no date and no cycle is never due. A record read
at one closure and due again at a later one, because its criterion names two dates, needs one
line per reading. A superseded or abandoned record is not due: its status already says what
became of it.

**Acceptance criteria** *(testable)*:

- [ ] Given a closed cycle and an accepted record whose criterion names a date before its end,
      with no reading line, then `nstack plan` warns, naming the record, the cycle and the line.
- [ ] Given the same record with a reading line dated on or after the closure, then no warning.
- [ ] Given a record whose criterion names the closed cycle, then the same warning.
- [ ] Given a record whose criterion names no date and no cycle, or a superseded record, then no
      warning.
- [ ] Given any of these, then `nstack plan` and `nstack fitness` still pass.

---

## Success criterion

By 2027-03-31: on the third project, two consecutive closures with no decision left unread that
was due, and the warning named at least one the closure would otherwise have missed.

## Removal condition

Removed if, after three closures on projects that carry it, the warning never named a record the
closure had not already read: the playbook's sentence was enough.

## Impacts

- **The engine**: the plan reads the projects' decision records' success criterion sections and
  warns.
- **The skeleton**: the PDR and ADR forms show the reading line; the framing playbook's closure
  and the decisions handbook say where it is written.
- **Projects**: a warning at their next closure for records due and unread; nothing turns red.
