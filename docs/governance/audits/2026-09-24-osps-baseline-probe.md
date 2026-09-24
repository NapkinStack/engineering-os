# OSPS Baseline probe of 2026-09-24 — the mapping is not clean, and M11g returns to M13

> M11g opened on a probe, by design: before trusting any block of its plan, check that our
> checklist maps onto the OpenSSF OSPS Baseline's controls and that the Baseline's three levels
> can be read as data. The plan's exit was explicit — *"if the mapping is not clean, this
> workstream stops and returns to M13 … Record the outcome either way."* This is the record.
>
> Source read: `ossf/security-baseline`, releases **v2026.02.19** and **v2026.08.28**, and
> `main` at `70b4874` (2026-09-23). Every figure below was computed from the YAML catalogue
> (`baseline/OSPS-*.yaml`), not from its rendered pages.

## Verdict

```mermaid
flowchart LR
    Q1["Identifiers stable?"]:::ok --> Q2["Levels readable as data?"]:::ok
    Q2 --> Q3["G1 to G16 map onto controls?"]:::no
    Q3 --> V["Not clean:<br/>M11g returns to M13"]:::no

    classDef ok fill:#065f46,color:#fff
    classDef no fill:#7c2d12,color:#fff
```

**Legend** — green: the probe confirmed it · red: it did not, and that decides the exit.

| Question | Answer |
|---|---|
| Are the identifiers stable? | **Yes.** No identifier renamed or reused between v2026.02.19 and today; a retired requirement keeps its identifier and says *"Retired in …"* (BR-01.02, VM-05.01) |
| Is level membership readable as data? | **Yes, with two reservations.** Each requirement lists its levels. But the encoding changed between the two releases (`Maturity Level 1` became `maturity-1`), the catalogue is still marked `draft: true`, and two requirements apply at level 1 only (BR-07.01, VM-02.01), so levels are not strictly cumulative |
| Does our checklist map onto controls? | **No.** Six of our sixteen rules have no counterpart; four map together onto a single control; one maps partly. The plan's task 3 — *"a rule blocks only when its control belongs to the target level or below"* — has no answer for a rule with no control, except a level we would assign ourselves. That is inventing a scale again, which is exactly what ADR-0005 was to avoid |

## The mapping, rule by rule

67 assessment requirements in 10 families; the ones below are those our checklist touches.

| Our rule | OSPS requirement | Level | Fit |
|---|---|---|---|
| G1 pull request required | `OSPS-AC-03.01` no direct commit on the primary branch | 1 | clean |
| G2 at least one approval · G3 code owner review · G12 empty bypass list · G13 stale approvals dismissed | `OSPS-QA-07.01` a non-author human approval before a commit reaches the primary branch | 3 | **four rules, one control** — together they are what makes the approval real; none maps alone |
| G4 required checks (the five jobs) | `OSPS-QA-03.01` status checks pass · `OSPS-QA-06.01` an automated test suite runs before a commit is accepted | 2 | clean, one rule to two controls |
| G5 secret protection and push protection | `OSPS-BR-07.01` prevent storing unencrypted secrets | 1 only | clean |
| G6 private vulnerability reporting | `OSPS-VM-03.01` a private reporting channel | 2 | clean |
| G9 workflow approval for outside contributors | `OSPS-BR-01.03` untrusted code cannot reach privileged credentials | 1 | **partial** — one means to that end among several |
| G10 read-only workflow token | `OSPS-AC-04.01` a CI task with no permission declared gets the lowest | 2 | clean |
| G7 allowed actions · G8 SHA-pinned actions · G11 labels · G14 auto-merge · G15 squash only · G16 branch deleted on merge | — | — | **no counterpart** |

**Two findings the probe was not looking for.**

- **`OSPS-AC-03.02`, level 1, asks that deleting the primary branch be protected — and our
  checklist never asks for it.** This repository's own ruleset forbids deletion and force-push
  on `main` (verified through the API on 2026-09-24: rules `deletion` and `non_fast_forward`),
  and the register's step 0 says so; no rule G1 to G16 asks a generated project for either,
  and `doctor` reads neither. Recorded as **D78**.
- **G15 sits against a recommendation, not a requirement.** `OSPS-QA-01.02` requires a public
  record of every change, who made it and when; its *recommendation* adds *"avoid squashing or
  rewriting commits in a way that would obscure the author."* A squash merge on GitHub keeps
  the pull request's author as the commit's author and names the other authors in
  `Co-authored-by` trailers, so the requirement holds. The tension is worth knowing before
  anyone reads G15 as the Baseline's opinion: it is ours.

## What this changes

- **M11g stops here.** The mapping, the `assurance_level` field, the level-aware `doctor` and
  ADR-0005 return to **M13**, as the plan provided. M11 ships without the exposure axis.
- **D69 stays open.** The checklist still imposes a level-3 control — `OSPS-QA-07.01` — from a
  project's first commit. The facts are unchanged; what failed is the vehicle.
- **PDR-0011 is unaffected in substance.** Its exposure axis was always conditional on this
  probe; the forge's checklist applies as today, and the decision says so.
- **What M13 inherits** is this table, not a blank page: ten of our rules mapped — four of
  them composing one control, one only partly — six with no counterpart, and a catalogue still
  marked draft. A narrower path exists and is **not taken here** — mapping only the rules that
  have a control and saying nothing about the rest — because it would report a level for a
  project while leaving six of its rules outside any level, which is the reading the plan's
  risk table warns about: a sentence people put in a sales deck.
