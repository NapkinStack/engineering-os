# PDR-0019 — The project's success is recorded where a cycle closes

- **Status**: Proposed (2026-10-25). Asked by the maintainer: *a synthesised view of the whole
  breakdown, in progress, waiting, closed, and the project's overall progress*; the view across
  cycles was built as D155, and this record is its second step
- **Date**: 2026-10-25
- **Decision makers**: NapkinStack maintainers (`@NapkinStack/maintainers`)
- **Modules affected**: the engine (the plan's checks and its view of the project), the cycle
  form, the framing playbook, the project's handbook page

> The PDR describes **what the product must do and why**, never its implementation.
> The how belongs to an ADR.

---

## User problem

A decider asks how far the project is, not the cycle. nstack has no backlog to measure it
against, by design (PDR-0010): framing bounds one cycle at a time. What says the project is
finished is the charter's success criteria (PDR-0002) — and nothing records where each one
stands. Since D155, `nstack plan` counts them and says every cycle in one line; whether a
criterion is met, or being observed, is still written in a closure's prose, if at all.

The third project's criteria show what is at stake: *"from the day [the product] installs on the
decider's Fedora, the decider records every meeting with it for two consecutive weeks"*. Such a
criterion is neither met nor unmet for weeks: it is being observed, from a day someone has to
record.

## Goal

At any moment, the decider reads in one line how many of the charter's success criteria are met,
and which are being observed and since when — recorded by the decision that moved them, read from
the repository, kept nowhere else.

## Out of scope

- **A percentage of the project.** No total exists to divide by; a figure that looks like one
  would be invented.
- **Changing the charter to record progress.** The charter changes only through a decision (C9);
  a criterion's state is the life of the project, not its founding text.
- **A state set by anyone at any time.** A criterion moves when the decider says so, at a cycle's
  closure — where the framing playbook already asks *which success criteria moved*.
- **A health status written by hand** (Linear's *on track, at risk*). The cycle's circuit breaker
  already says when a cycle is late, and it is computed.
- **Showing it on the forge.** The milestone display (PDR-0016) is unchanged; a view across cycles
  on the forge stays *later, if asked*.

---

## Prior art

| Product / reference | Solution chosen | What we keep from it |
|---|---|---|
| [Linear — project and initiative updates](https://linear.app/docs/initiative-and-project-updates) | A person posts an update with a health (*on track, at risk, off track*); progress "cannot be predicted from quantitative data alone" | **A person's word records progress**, at a moment set for it — here the closure |
| [Shape Up — hill charts](https://basecamp.com/shapeup/4.0-appendix-01) | Scopes moved by hand from *unknown* to *known* to *done*; no ticket counts | **No count of work pretends to be progress**; a state between not started and done |
| OKRs (John Doerr, *Measure What Matters*) | Key results scored at the end of a period | **The criterion is scored at the end of a period**, not continuously |
| BMAD — `sprint-status.yaml` | A status file beside the plan | Refused: a second file that drifts from the first |

**The convention the user already knows:** a goal's key results, reviewed when a period ends.

---

## Options considered

| Option | What the user experiences | Cost | Chosen? |
|---|---|---|---|
| Do nothing | The criteria counted (D155); their state in a closure's prose | 0 | No |
| A. A state on each criterion, in the charter | One place — but the founding text rewritten at every closure, and C9 warns each time | Low, and against C9 | No |
| **B. The closure records the criteria it moved, in the cycle's front matter** | The latest record of each criterion is its state; `nstack plan` says *N of M met*, and which are observed since when | Low | **Proposed** |
| C. A status file of the project | One more file, kept by hand | Low, and a second truth | No |

## Decision

**Option B**, proposed.

1. **A closed or stopped cycle may record the criteria it moved**: each by its number in the
   charter's list, as `met` or `observing`, with the day observation started for the latter.
2. **A criterion's state is its latest record**, in the order of the cycles; one never recorded is
   *not yet*.
3. **`nstack plan` says it**: *N of M success criteria met*, then each one observed and since
   when, in the project's line.
4. **Checked like the rest of the plan**: a number outside the charter's list, or an unknown
   state, is refused with its place and its fix. A cycle that records nothing is valid.
5. **When every criterion is met**, the view says the project is finished — what the framing
   playbook already asks the closure to tell the decider.

---

## Expected behaviour

**Nominal journey.** Cycle 03 closes; the decider has installed the product on their Fedora on
2026-11-08. The closure records criterion 1 as `observing` since 2026-11-08. `nstack plan` reads
*0 of 3 success criteria met · 1 observed since 2026-11-08*. At cycle 04's closure, the two weeks
held: criterion 1 is recorded `met`; the line reads *1 of 3 met*.

**Edge cases.** The charter changes through a PDR and loses a criterion: a record naming a number
no longer in the list is refused, and says the PDR that changed the list is where it is fixed. A
criterion recorded `met` then found to fail: a later closure records it `observing` again — the
latest record wins.

**Acceptance criteria** *(testable)*:

- [ ] Given a closed cycle recording criterion 1 as met, then `nstack plan` says *1 of N met*.
- [ ] Given two closures recording the same criterion, then the later one is its state.
- [ ] Given a criterion recorded as observing with its day, then the line names it and the day.
- [ ] Given a record naming a criterion outside the charter's list, or an unknown state, then the
      plan check fails, naming the cycle file, the record and the fix.
- [ ] Given no cycle recording anything, then the view says *0 of N met* and every check passes.
- [ ] Given every criterion met, then the view says the project's criteria are all met.

---

## Success criterion

By 2027-03-31: on the third project, at two consecutive cycle closures, the decider records the
criteria that moved, and says the project's line answered *where is the project?* without opening
a file or asking the agent.

## Removal condition

Removed if, after three closures on projects that use it, no criterion was ever recorded: the
prose of the closure was enough.

## Impacts

- **The engine**: the plan's checks read the record; the project's view says it.
- **The skeleton**: the cycle form shows the record, commented, beside `outcome`; the framing
  playbook's closure says where the criteria that moved are written; the project's handbook page
  says how the line reads.
- **Projects**: nothing changes until a closure records something; no existing file turns red.
