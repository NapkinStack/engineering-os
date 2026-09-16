# Periodic reviews

> Three meetings. Each one produces a **decision**, never a mere observation.
> (`skeleton/docs/os/10-measurement.md` §5)

## Boundary review — monthly

What to look at:

- the rate of pull requests carrying the `cross-module` label, and on which pair of
  modules
- fitness function violations over the period
- overdue contractions (deprecated versions not removed)
- signals reported in pull requests: "I had to look at another module's implementation"

Output: *Architecture* issues, or nothing. When several signals converge on the same pair
of modules, the answer is **merge or re-split** — never add one more contract.

| Date | Signals | Decision |
|---|---|---|
| | | |

## Decision review — quarterly

List the ADRs and PDRs whose success criterion has come due. For each one: **confirmed**,
**superseded**, or **feature removed**.

Without this ritual, `docs/adr/` becomes a graveyard — which is worse than no
documentation at all, because it inspires false confidence.

| Date | Decision | Criterion | Verdict |
|---|---|---|---|
| | | | |

## Automation backlog review — quarterly

See `automation-backlog.md`. It can be held with the previous one: both address the same
subject from two sides — what should have left the prompt, and what should have left the
product.
