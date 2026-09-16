---
goal: "<One sentence: the outcome of this cycle>"
status: proposed          # proposed | accepted | closed | stopped — the decider accepts
appetite_weeks: 2         # the time the decider WANTS to spend, not an estimate
start: 2026-01-05         # YYYY-MM-DD
end: 2026-01-19           # start + appetite: the circuit breaker's date
deliverables:
  - id: D1
    title: "<An outcome a user can observe>"
    module: "<module name>"
    state: proposed       # proposed | ready | in-progress | accepted | deferred | dropped
    acceptance:           # given · when · then, required from ready on: the test sheet starts here
      - "Given <context>, when <action>, then <observable result>"
# outcome: completed      # closed: completed | shipped — stopped: reframed | stopped
# ended_on: YYYY-MM-DD
---

# Cycle NN — <title>

> Copied to `NN-<slug>.md` at framing (`playbooks/framing.md`). One accepted cycle at a
> time; no automatic extension.

## Goal

<Why this outcome, now.>

## Deliverables

<Notes the front matter cannot hold: order, dependencies, open points.>

## Out of scope

<What this cycle deliberately does not do.>

## Later

<Ideas that came up during the cycle. They enter a cycle only through a new framing.>

## Closure

<Written at the end: what was delivered, which success criteria moved, what was deferred,
where the next framing starts.>
