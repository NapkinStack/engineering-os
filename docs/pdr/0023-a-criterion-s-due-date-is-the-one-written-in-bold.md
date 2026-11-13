# PDR-0023 — A criterion's due date is the one written in bold

- **Status**: Proposed (2026-11-10), option B chosen by the decider who assigned the defect;
  accepted when a maintainer approves the pull request that carries it. It amends PDR-0020 §1
  and §6 on one point, what a date of the criterion is; the rest of PDR-0020 stands
- **Date**: 2026-11-10
- **Decision makers**: NapkinStack maintainers (`@NapkinStack/maintainers`)
- **Modules affected**: the engine (the plan's rule C10), the decision forms, the framing
  playbook's closure, the decisions handbook, `RULES.md`, the glossary

> The PDR describes **what the product must do and why**, never its implementation.
> The how belongs to an ADR.

---

## User problem

PDR-0020 makes a closure read the decisions whose criterion is due, and reads as due *any* date
written `YYYY-MM-DD` in the success criterion section (§1, §6). A criterion carries other dates
than the one it is due by. On a project, C10 warned that a record was *due at cycle 07's closure*
because its criterion cited the record it amends, with the amendment's date; another, due
*before* a date months later, was named due at the closure its amendment date reached.

The decider is then told to read a decision that is not due, writes a reading line that answers
nothing, and learns to dismiss the warning — the one thing the rule exists to prevent. The only
way out today is to move the amendment out of the criterion, which is where a reader looks for
it.

## Goal

A closure is told a decision is due only by the date the criterion says it is due by.

## Out of scope

- **Reading the words around a date.** *Before*, *by*, *amended*, *see*: PDR-0020 §6 infers
  nothing from prose, and this keeps it so.
- **Rewriting existing records.** A record whose due date is plain stops being read as due;
  the closure that reaches it says so (Decision, 4), and its author bolds it.
- **Cycles named in the criterion.** A cycle named by its file or as *cycle 03* stays due as
  PDR-0020 says.
- **The reading line.** Its date stays plain: it records a reading, not a deadline.

---

## Prior art

| Product / reference | Solution chosen | What we keep from it |
|---|---|---|
| PDR-0020's own forms | The sentence *observed before **\<YYYY-MM-DD\>***, its date already in bold | **The form already marks the due date**: the rule reads the mark the form shows |
| Front matter of static sites (Jekyll, Hugo: `date`, `expiryDate`) | A date that drives behaviour is in a field of its own, never found in prose | **A date that acts is marked as such**; another date is text |
| GOV.UK Tech Docs Template (`review_in`) | The review date is a named field | The same: the deadline is where the tool is told to look |
| iCalendar, `DUE` (RFC 5545) | A due date is its own property, apart from `DTSTAMP`, `LAST-MODIFIED` | **A due date and an edit date are never the same field** |

**The convention the user already knows:** a deadline set apart from the text around it. A
field would be the strongest; the forms are prose sentences, and their due date is already bold.

---

## Options considered

| Option | What the user experiences | Cost | Chosen? |
|---|---|---|---|
| Do nothing | Amendment and reference dates warned as due; the warning dismissed | 0 | No |
| A. Only a date after *before* or *by* | Most criteria read as written — but prose inferred, which PDR-0020 §6 refuses; *on*, *until*, *at the latest* missed | Low | No |
| **B. Only a date written in bold, `**YYYY-MM-DD**`** | The form's date is due, as it is shown; any other date is text. A plain due date in an older record stops being named until bolded | Low | **Chosen** |
| C. Keep the rule; amendments moved out of the criterion | Nothing changes in the engine; every author must know to keep the section clean | 0, paid by every author | No |

## Decision

**Option B.** It amends PDR-0020 §1 and §6 on what a date of the criterion is:

1. **A date of the criterion** is a date written in bold, alone between the markers:
   `**2027-01-31**`. A plain date — an amendment's, a reference's, a remark's — is not read.
   A bold run holding other words, `**before 2027-01-31**`, is not one either: the rule stays
   exact.
2. **Everything else in PDR-0020 stands**: the criterion section only, a cycle named by its file
   or as *cycle 03*, comments not read, a reading line per closure, a warning and never a
   refusal.
3. **The forms, the handbook, the playbook, `RULES.md` and the glossary say it**, where they
   state the rule.
4. **A plain due date is reported, not read.** A criterion with no bold date and no cycle named,
   holding a plain date a closure reached with no reading after it, gets a C10 warning of its
   own: no due date C10 can read, put it in bold. A date written *amended YYYY-MM-DD* is left
   out — the one phrase read, only to keep an amendment quiet; it never makes a date due. An update never silences a warning a project used to get.

---

## Expected behaviour

**Nominal journey.** Cycle 07 closes on 2026-11-07. A record's criterion reads *(PDR-0004,
amended 2026-11-02) … before **2027-01-31***. `nstack plan` names nothing for it; the closure
whose end reaches 2027-01-31 names it.

**Edge cases.** A criterion with only an amendment date, or only plain dates, is never due by a
date. A criterion with a bold date and a named cycle is due at both, as before. A plain due date
in a record written before this decision stops being read as due: the closure that reaches it
warns that the criterion has no due date C10 can read, and says to bold it.

**Acceptance criteria** *(testable)*:

- [ ] Given a closed cycle and a criterion with *amended YYYY-MM-DD* the closure reached and a
      bold date it did not reach, then no warning.
- [ ] Given a criterion with only an amendment date the closure reached, then no warning.
- [ ] Given a criterion with a bold date the closure reached, then C10 warns, as PDR-0020 says.
- [ ] Given a plain date, or a bold run holding words, then no warning that it is due.
- [ ] Given a plain date the closure reached, with no bold date and no cycle named, then C10
      warns that the criterion has no due date it can read; with an amendment date only, nothing.

---

## Success criterion

We will consider this was the right call if, on the project that met it and one other, no
closure warns of a decision for a date that was not its due date, and no due decision goes
unread for a date left plain, before **2027-03-31**.

How it is observed: the C10 warnings of their closures, against the records' criteria.

If the criterion is not met: supersede — a due date as a field of its own.

## Removal condition

This decision is removed with PDR-0020's rule C10, or superseded if a due date gets a field of
its own.

## Impacts

- **Projects**: a criterion whose due date is plain stops being read as due; the closure that
  reaches it says to bold it; amendment and reference dates stop being named. No check turns red: C10 is a warning.
- **The engine**: the plan's rule C10 reads only bold dates.
- **The skeleton**: the PDR and ADR forms' comment, `06-decisions.md` §5, `framing.md`'s
  closure, `RULES.md` and the glossary say it.
- **This repository**: its own records are outside C10 (PDR-0020, *Out of scope*); their plain
  dates are left as they are.
