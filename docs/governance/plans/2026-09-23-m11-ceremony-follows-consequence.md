# NapkinStack M11 — Ceremony follows consequence — implementation plan

> **Location:** `docs/governance/plans/`, the repository's working context.
>
> **For the executing agent:** REQUIRED SUB-SKILL: use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to run this plan task by task. One workstream is
> one pull request, in the order of the roadmap, and each task is TDD: the failing test first,
> seen red for the right reason, then the code (P5). Steps use checkboxes (`- [ ]`).
> **The code blocks below are a design, not an extract from a prototype.** Two tasks carry a
> probe that must run before the blocks they cover are trusted: M11f task 0 (auto-merge on the
> forge) and M11g task 0 (the OSPS Baseline mapping). Until each probe is done, read the blocks
> it covers as a proposal.

**Goal:** make the framework cost what the consequence of a failure costs, and nothing more.
The proportionality is already promised — **three times, in three documents, in three shapes** — and executed
by a single threshold. This milestone turns the promise into rules a machine applies, and
removes the four mechanisms that charged the maximum price to every project regardless of what
it was building.

**Architecture:** two axes, two owners, no overlap.

| Axis | Unit | Declared in | Governs | Who decides |
|---|---|---|---|---|
| **Assurance** — what a failure of *this code* costs | the **module** | `criticality` in `MANIFEST.yaml` | the engine's checks: test sheet, verifier, e2e, runbook, contract tests | the **decider**, recorded in the module's creation ADR |
| **Exposure** — what a failure of *this project* costs others | the **project** | an OSPS Baseline target level | the forge's requirements: pull requests, status checks, human approval | the **decider**, at init or later |

*Exposure returned to M13 on 2026-09-24: M11g's probe found the OSPS mapping not clean. M11
ships the assurance axis alone.*

They never override each other. A project at the lowest exposure level can hold a `critical`
module and pays its assurance in full; a widely used project at level 3 can hold a `prototype`
module and pays no assurance for it. This separation is what makes both axes small.

**Tech stack:** Python 3.12+ standard library, PyYAML and pytest 9.1.1, as the rest of
`platform/`; the generated project comes from `nstack init --source .`, as
`platform/tests/run.sh` already does. **No new dependency**, and no vendoring of the OSPS
Baseline catalogue — M11g reads identifiers and maps to them, it does not copy them.

---

## Why now, and on what evidence

**From the pilot** (`NapkinStack/flet`, public, 23 pull requests in three days, driven by a
session that knows nothing of this repository):

| Measured | Where it comes from |
|---|---|
| **16 of the decider's 54 turns** were a bare "approved" / "merged" — 7 of them pure relay, carrying no judgement | no auto-merge: the agent waits to be told |
| **7 turns** of "I do not understand what you are asking me" | the routing PDR-0004 has not been built |
| **6 turns** of "you are the expert, decide" | same |
| **5 turns** asking to **simulate** evidence the world could not supply | C4 requires acceptance criteria on every deliverable, and law 2 requires an executable oracle; market research has neither |
| **6 verification rounds** on one read-only `high` module, **3 of the 11 defects introduced by the late rounds**, while the `critical` module does not exist yet | T4 invalidates every scenario at each fix, and nothing says one round is enough |
| `screening` declared **`high`** — read-only, holds no key, places no order | `criticality` is a positional argument with **no help text**, no criteria at hand, and no consequence printed before the choice |

**From the market** (September 2026):

- **DORA** names the central cost of AI-assisted delivery the **verification tax**, and finds AI
  is an *amplifier*: the return comes from the system around the agent, not the agent. LinearB
  measures AI-generated code waiting **4.6× longer** for a first review; Atlassian names the
  *efficiency paradox* — output backs up at the points that need human judgement.
- **GitHub Spec Kit** (111k stars, 30+ agents) is criticised on exactly two points: the process
  is heavy, and **the documents it produces govern by convention rather than by enforcement**.
  Scott Logic's review reports being *"around ten times faster"* with plain iterative prompting,
  and concludes it is *"too much process for a disposable prototype, a tiny bug fix, or a task
  already expressed by a precise failing test"*.
- **The OpenSSF OSPS Baseline** places *"at least one non-author human approval before merging"*
  (`OSPS-QA-07.01`) at **maturity level 3 of 3**. "No direct commit to the primary branch"
  (`OSPS-AC-03.01`) is level 1; "automated status checks must pass" (`OSPS-QA-03.01`) is level 2.
- **The EU Cyber Resilience Act** entered its reporting phase on **11 September 2026**; full
  compliance is due 11 December 2027. The Baseline is mapped to it.

**The conclusion that orders this plan.** Our first criticism is the market leader's first
weakness — that is our reason to exist, and it is kept. Our second weakness is *also* the market
leader's second weakness, unsolved by anyone: uniform ceremony. And our checklist imposes
`OSPS-QA-07.01`, a level-3 control, **from a project's first commit**. We ship the top tier as
the floor.

---

## Global constraints

- **P1 to P7 hold.** In particular **P5**: every rule this plan adds or moves gains a test that
  proves it fails when broken, seen red first. And **P4**: the kernel stays within 250 lines —
  M11c adds one routing line and must remove one elsewhere or stay under budget.
- **No new configuration for a single use (§6).** The only new project-level field is the OSPS
  target, and it is optional with a default that blocks nobody.
- **We report alignment, never conformity.** `doctor` says which Baseline controls it *observes*
  as satisfied. It does not certify, and the wording must make that impossible to misread.
- **Nothing here rewrites a published version's promise.** The `CHANGELOG` entries for v0.1.0 to
  v0.6.1 are untouched.
- **Records are corrected in place**, ADRs and PDRs included, and the exemption is declared in
  `PRODUCT.md` §5 with its end at v1.0 (M11h). The history stays in `workstreams.md` and in the
  `CHANGELOG`.
- **Precondition: v0.6.2 is published before M11a starts.** It carries D62–D65, already on
  `main`, plus D66. The pilot upgrades at its cycle boundary and must find the fixed messages.

## Decisions taken while planning

1. **The project-level knob is the OSPS Baseline level, not an invented one.** Three levels
   already exist, are machine-readable, are mapped to CRA and NIST, and carry a sentence with
   commercial value. Inventing `solo`/`team` was measured against the pilot's 23 pull requests
   and would have changed **none of them**; it was dropped.
2. **The criticality matrix of `05-workflow.md` §7 is the single source for *when*.** The
   framework describes proportionate requirements in **three** places: the four-level diagram of
   `07-governance.md` §6, the seventeen-row Definition of Done of `05-workflow.md` §7, and the
   thirteen-row reliability table of `08-quality.md` §7 — three shapes, and only the diagram
   carries `prototype`. The matrix says **when** a requirement applies; §6 points at it; §7 of
   `08-quality.md` keeps **what** an operable module holds and gives up the when.
3. **Human review leaves the criticality matrix.** Approval is exposure, not blast radius: it
   belongs to the OSPS axis. This removes any need to amend ADR-0004 — the four settings of
   `07-governance.md` §7 keep holding together at level 3, which is where they are required.
   *Since M11g's probe (2026-09-24), required at every level until M13 — D69 stays open.*
4. **Each matrix row is marked *machine* or *owed*.** A framework that pretends CI verifies UAT
   teaches people to ignore it. **Eight rows are executable; ten are owed** to a human and named
   as such. The count changed once during M11b: the e2e row was written as *machine* and moved to
   *owed* when building it showed a check could not tell an end-to-end suite from a unit suite
   renamed — see M11b task 4. *And once more in the coherence pass of 2026-09-24: "contract tests"
   were marked machine while no check requires them; the row became owed, and the check that does
   exist — a frozen version proved compatible, V1 — became its own machine row. Eight and eleven.*
5. **`high` and `critical` finally differ, without a new field.** `critical` adds: the sheet
   confirmed at head after the last fix, e2e present and green, and the runbook referenced by the
   sheet. The four values plus `user_facing` are enough; no `read_only` field is added.
   *As built: `critical` adds every scenario re-run at the head (M11d) and makes the owed rows
   `high` leaves to judgement due; e2e is owed at `high` already (M11b task 4), and nothing reads
   a runbook reference — the coherence pass aligned §7 on this.*
6. **The framework never asks for N verification rounds.** It asks for one sheet and one
   independent verifier. The six rounds came from T4 and from silence; the matrix says
   explicitly that further rounds are a project's own decision.
7. **Auto-merge is a correction, not an option.** It removes the human from the *merge*, never
   from the *approval*. ADR-0004 requires an approval; it never required a human to press merge.
8. **Market research is not a deliverable.** PDR-0010, accepted 2026-09-22, already gives it a
   home: a typed issue. No new artefact, no new field on cycles. *Superseded by M11e: such work
   is a spike, a deliverable whose product is knowledge — the door `05-workflow.md` §3 already
   had.*

---

## Roadmap

```mermaid
flowchart TD
    V62["v0.6.2<br/>D62-D66 published<br/>(precondition)"]:::done --> A
    A["M11a<br/>one matrix, prototype included<br/>machine vs owed"]:::done --> B["M11b<br/>the engine spends it"]:::done
    B --> C["M11c<br/>the choice returns to the decider"]:::done
    B --> D["M11d<br/>T4 stops being a ratchet"]:::done
    A --> E["M11e<br/>a criterion nobody can meet<br/>is a spike"]:::done
    F["M11f<br/>approval mechanics<br/>auto-merge, squash, D61"]:::done --> H
    C --> H["M11h<br/>PDR-0011, records<br/>corrected in place"]:::done
    D --> H
    E --> H
    H --> G["M11g<br/>OSPS probe: not clean<br/>returns to M13"]:::done
    H --> J["M11j<br/>unframed<br/>PDR-0007"]:::done
    H --> K["M11k<br/>settings, printed<br/>PDR-0008, D77, D78"]:::done
    K --> R["M11r<br/>settings, applied<br/>after a probe, D57"]
    R --> I
    H --> L["M11l<br/>the form<br/>PDR-0010"]:::done
    H --> M["M11m<br/>the pilot's boundary<br/>D68, D74, D75"]:::done
    H --> N["M11n<br/>identifiers stay home<br/>D79"]:::done
    L --> O["M11o<br/>every document<br/>has its moment"]:::done
    O --> I
    O --> Q["M11p<br/>levels of rules<br/>have a place"]:::done
    Q --> I
    N --> I
    G --> I["M11i<br/>v0.7.0 published<br/>two projects migrated"]
    J --> I
    K --> I
    L --> I
    M --> I

    classDef done fill:#065f46,color:#fff
```

**Legend** — green: merged, or closed by its probe · no fill: to do. Redrawn by M11h on 2026-09-24: M11h was taken
before M11g, which may evaporate on its probe, and M11j to M11m were added before the release.

M11f has no dependency and gives the largest immediate relief for the smallest change: it may be
taken first if the pilot's next cycle starts before M11a lands.

## File map

| File | What changes | Workstream |
|---|---|---|
| `skeleton/docs/os/05-workflow.md` §7 | the matrix gains `prototype`, loses *Human review*, marks each row *machine* / *owed*, states one round | M11a |
| `skeleton/docs/os/07-governance.md` §6 | the second description is removed; it points at the matrix | M11a |
| `skeleton/docs/os/08-quality.md` §7 | **the third table**: keeps *what* an operable module holds, gives up *when* it is required | M11a |
| `src/napkinstack/templates/module/MANIFEST.yaml` | the `criticality` comment points at the matrix, not at the diagram — it is what the agent reads when it chooses | M11a |
| `skeleton/playbooks/framing.md` | the criticality implied by the risks points at the matrix; the decision is the decider's | M11a, M11c |
| `skeleton/.github/pull_request_template.md` | the sheet's table gains the `Confirmed` column | M11d |
| `skeleton/README.md.jinja` | the CHECKLIST copy, word for word, with its test | M11f |
| `skeleton/.github/workflows/module-checks.yml` | already branches on criticality; the dead *"Not wired up (D9)"* step goes | M11b |
| `skeleton/docs/os/07-governance.md` §7 | approval is described by exposure level, not as an absolute | M13 (returned by M11g's probe) |
| `src/napkinstack/assurance.py` | **new**: the machine half of the matrix, read by every rule that spends it | M11b |
| `src/napkinstack/fitness/manifests.py` | M8 reads the matrix instead of a hard-coded threshold | M11b |
| `src/napkinstack/pull_request.py` | T1 and T4 read the matrix; T4 splits by scenario kind | M11b, M11d |
| `src/napkinstack/modules.py`, `cli.py` | `criticality` gains help text and printed consequences | M11c |
| `skeleton/AGENTS.md` | one routing line: the criticality is the decider's | M11c |
| `skeleton/playbooks/framing.md`, `05-workflow.md` §3 | a deliverable waiting on someone outside is a spike, or a dependency with a date | M11e |
| `src/napkinstack/fitness/plan.py` | C4's refusal names the spike and a dependency with a date | M11e |
| `src/napkinstack/doctor.py` | auto-merge, squash-only, branch deletion; OSPS levels in M13 | M11f |
| `skeleton/.github/CODEOWNERS.jinja` | unchanged — the default owner stays | — |
| `docs/pdr/0011-*.md` | new: ceremony follows consequence | M11h |
| `docs/adr/0005-*.md` | not written: the probe sent the scale to M13 | — |
| `docs/adr/0003-*.md` | shrunk to the rule in force | M11h |
| `AGENTS.md`, `PRODUCT.md` §2, §3, §5 | the M7 sentence, the fifth user, the honest claim, the records exemption | M11h |
| `docs/governance/workstreams.md` | D66 to D77 recorded, D78 by M11g | M11h, M11g |
| `CHANGELOG.md` | the v0.7.0 section, engine and project apart | M11i |

---

## Coherence map — everything that cites what this plan rewrites

Checked by search, not by memory. An executing agent that changes a section without walking this
list leaves the framework saying two things at once, which is the defect being removed.

**Cites `05-workflow.md` §7** (the matrix): `00-overview.md` glossary · `08-quality.md` §128 ·
`07-governance.md` §7 closing sentence · `playbooks/tests.md` · `.github/pull_request_template.md`
(twice) · `.github/workflows/module-checks.yml` (twice) · `templates/module/MANIFEST.yaml` ·
`fitness/manifests.py` (M10, twice) · `pull_request.py` (twice) · `modules.py`.

**Cites `07-governance.md` §6** (the diagram): `templates/module/MANIFEST.yaml:18` ·
`playbooks/framing.md:40`.

**Cites `07-governance.md` §7** (approval and the forge): `skeleton/AGENTS.md:27` ·
`skeleton/README.md.jinja:127` · `.github/CODEOWNERS.jinja` (twice) · `modules.py:63` ·
`10-measurement.md:93` · `docs/adr/0004-*.md` (twice). **M11g rewrites §7's framing, never its
number**, so every citation above keeps resolving; each is re-read once to confirm the sentence
it points at still says what the citing file claims.

**Two copies bound by a test:** `CHECKLIST` in `doctor.py`, printed by `nstack init`, read by
`project.py`, repeated word for word in `skeleton/README.md.jinja`.

**Identifiers, verified free before use:** M1 to M10 are taken, so the e2e rule is **M11**
(built and removed in M11b: it does not exist); G1 to G13 are taken, so the forge rules are
**G14, G15, G16**. Families the engine emits: B1-B8, C1-C7, G1-G16, H1, K1-K4, L1-L7, M1-M10,
P1-P2, S1-S4, T1-T5, V1, W1.

---

## M11a — One matrix, `prototype` included, each row named — PR 1

No behaviour change. This workstream makes the contract readable before any code spends it.

- [x] **Task 1.** In `05-workflow.md` §7, add the `prototype` column and remove the *Human
      review* row (it moves to `07-governance.md` §7 in M11g, as an exposure requirement).
- [x] **Task 2.** Mark every row. A row is **machine** when a check in this repository can fail
      on it today, **owed** otherwise. The seven machine rows: oracle green · lint, format,
      types · unit tests · contract tests · fitness functions · test sheet run by an independent
      verifier · e2e. The ten owed rows keep their place and gain one sentence: *"owed to a human;
      no check reads it."* *(As built: e2e moved to owed in M11b task 4, runbook and re-run at the
      head were added as machine.)*
- [x] **Task 3.** Add, under the matrix: **one round.** The framework asks for one sheet and one
      verifier who is not an author. Further adversarial rounds are a project's own decision,
      recorded in its own ADR — never a framework requirement.
- [x] **Task 4.** State what separates `high` from `critical`, in the matrix itself: `critical`
      adds the sheet **confirmed at head** after the last fix, **e2e present and green**, and the
      **runbook referenced** by the sheet.
- [x] **Task 5.** In `07-governance.md` §6, replace the four-level diagram's content with a
      pointer to the matrix, keeping the principle sentence (*"never impose the ceremony of a
      critical system on a small module"*) and the revision rule.
- [x] **Task 6 — the third table.** `08-quality.md` §7 holds a **thirteen-row reliability table**
      on the same three columns, also without `prototype`, and `modules.py:37` cites it as the
      authority for the runbook while the DoD matrix carries a runbook row too. **One fact, one
      home**: the matrix says *when* a runbook is required, `08-quality.md` §7 says *what it
      contains* and points at the matrix for the when. Its own columns gain `prototype`, or state
      in one sentence that operability starts at `standard`.
- [x] **Task 7 — the comment the agent actually reads.** `src/napkinstack/templates/module/
      MANIFEST.yaml:18` points the `criticality` field at `07-governance.md` §6. It is the line
      under the agent's cursor when it chooses (D70). It points at the matrix.
      `skeleton/playbooks/framing.md:40`, which derives the criticality from the risks, does the
      same.
- [x] **Task 8.** `platform/tests/` gains a case that fails when **any two** of the three
      documents describe different sets of criticality values — the defect this workstream exists
      to close, and it had three homes, not two.

**Done when:** one document says when, the others say what, `prototype` is in all of them, every
row says who judges it, and a test refuses a second description of the same fact.

## M11b — The engine spends the matrix — PR 2

- [x] **Task 1.** A single module holds the matrix as data, read by `manifests.py` and
      `pull_request.py`, so a change to the contract is one edit:

```python
# src/napkinstack/assurance.py — the matrix of docs/os/05-workflow.md §7, machine rows only.
MATRIX = {
    "prototype": {"sheet": False, "runbook": False, "e2e": False, "confirm_at_head": False},
    "standard":  {"sheet": "user_facing", "runbook": False, "e2e": False, "confirm_at_head": False},
    "high":      {"sheet": True, "runbook": True, "e2e": True, "confirm_at_head": False},
    "critical":  {"sheet": True, "runbook": True, "e2e": True, "confirm_at_head": True},
}
```

- [x] **Task 2.** T1 reads `MATRIX[...]["sheet"]` instead of a hard-coded set. Test first: a
      `prototype` module changed beyond its description must **not** be asked for a sheet, and a
      `standard` user-facing one must.
- [x] **Task 3.** M8 reads `["runbook"]`. Test first: a `standard` module with no runbook passes;
      a `high` one fails with the action naming the file to create.
- [x] **Task 4 — built, then removed. The rule does not ship.** A new rule `M11` was to require
      `commands.e2e` wherever the matrix asked for e2e. It was written, its test was seen red, and
      then **this repository's own `platform` module refused it for a good reason**: `platform`
      declares its entire oracle as `commands.test`, because its test suite *is* its end-to-end
      suite. The rule would have asked it to declare one command under two names.
      A check can read that an `e2e` verb exists; it cannot read that the verb runs end-to-end
      scenarios rather than the unit suite renamed. **A rule a one-line alias satisfies teaches the
      alias** — which is what P6 says of every contournable check. The e2e row moved to *owed*,
      with that reason written in `05-workflow.md` §7 where a reader will meet it.
      Ten minutes of dogfood against a rule the plan had already approved. Recorded, not hidden.
- [x] **Task 5.** Every message names the criticality that produced the requirement and what the
      neighbouring value would change (P6). Example: *"FAIL [T1] … required at criticality
      `high`. At `standard` this module would need a sheet only if it were user-facing."*
- [x] **Task 6 — the CI already knows.** `module-checks.yml` reads `.module.criticality` and
      branches on it already; it also runs `nstack e2e` unconditionally. Two consequences: the
      planned e2e rule would have added the **declaration** requirement, not the run, and the dead step *"Levels high and
      critical — not wired up yet (D9)"*, which prints a sentence and passes in **every generated
      project**, is removed. A step that cannot fail is the residue this milestone exists to
      remove; D9 stays open in the register, without a decorative step to stand for it.
- [x] **Task 7.** Run the real commands on a generated project, not only unit tests: one module
      per criticality value, and the four outcomes observed.

**Done when:** the four values produce four different regimes, each proven by a test that was
seen red, and no step in a generated project passes without being able to fail.

## M11c — The choice returns to the decider — PR 3 *(delivered)*

The defect: `cli.py:83` declares `criticality` with `choices=[...]` and **no `help`**, while its
neighbours `name` and `owner` have one. The agent types a word with no criteria at hand and
picks the prudent one.

- [x] **Task 1.** Help text on the argument, one line per value, phrased as a consequence:
      *"prototype: thrown away, nothing depends on it · standard: real code, no money, no
      personal data · high: a failure costs a day · critical: a key, an order, money, or
      someone's data."*
- [x] **Task 2.** `new-module` prints, **before creating**, what the chosen value will require
      and what the neighbouring values would change — the matrix rows that apply, not a link.
- [x] **Task 3.** `next_steps` gains one line: the creation ADR records the criticality **and one
      sentence of justification**. The ADR already goes through the decider's approval, so the
      choice becomes a reviewed act rather than a keystroke.
- [x] **Task 4.** One line in the kernel (`skeleton/AGENTS.md`), under the stopping rules: *"The
      criticality of a module is a product decision. You propose it with its consequence; the
      decider settles it."* Check the 250-line budget after the edit; if it exceeds, the sentence
      about session identity that `07-governance.md` §7 already carries in full is the one to
      shorten.
- [x] **Task 5.** `platform/tests/` asserts the help text exists and that the consequences are
      printed — a silent generator is the defect being fixed.

**Done when:** `nstack new-module --help` answers "which one do I pick?" without opening a
document, and the decision is recorded where a human approves it.

## M11d — T4 stops being a ratchet — PR 4

The defect: T4 requires every scenario's evidence to be produced on the head commit. A fix moves
the head, so **one blocker invalidates the whole sheet** and calls a full round. Cost is
O(rounds × scenarios) instead of O(scenarios + fixes). Measured: six rounds on one module.

- [x] **Task 1.** T4 splits by the scenario's declared kind.
      - **automated** — must be green at head. CI re-runs them; this costs nothing and stays.
      - **explored** and **human only** — the evidence keeps the commit it was produced on, and
        the sheet carries a **confirmation at head**: the verifier's line naming what changed
        since that commit and that it does not touch the behaviour the scenario covers.
- [x] **Task 2.** The sheet's table gains one column, `Confirmed`, empty for automated scenarios.
      Test first: a sheet with an explored scenario whose evidence predates the head and carries
      no confirmation must fail; the same sheet with a confirmation must pass.
- [x] **Task 3.** At criticality `critical`, the confirmation is required for **every** scenario,
      automated included — that is the `confirm_at_head` row of M11b's matrix, and it is where
      the two top values finally differ.
- [x] **Task 4.** The refusal message says which of the two paths applies, and gives the line to
      add (P6).
- [x] **Task 5.** `skeleton/.github/pull_request_template.md` carries the sheet's table for every
      project: it gains the `Confirmed` column, and the two places where it explains the sheet
      say what fills it. A rule whose form is not in the template is a rule nobody can satisfy on
      the first try.
- [x] **Task 6.** Rerun the pilot's own case as a fixture: a sheet of six scenarios, three fixes
      after the first verification, must pass with one confirmation block instead of three full
      re-runs.
- [x] **Task 7 — checked, and no record to correct.** PDR-0003 promises *scenarios written before
      the code, run by someone other than the author, each result backed by evidence*. It never
      promises evidence produced on the head commit — T4 is the engine's reading of it, not the
      decision. **PDR-0003 is untouched by this workstream**, and this line exists so that nobody
      later "fixes" a contradiction that does not exist.

**Done when:** fixing a blocker costs a confirmation, not a round, `critical` is the only value
that still pays the full price, and the template shows the form.

## M11e — A criterion nobody can meet gets met with counterfeit — PR 5 *(delivered)*

**Renamed while building it.** The plan said non-code work should *leave* the deliverables. It
should not: **the framework already had the right home for it, and the refusal did not mention
it.** `05-workflow.md` §3 says an exploratory task is a **spike** — *"the deliverable is
knowledge, not code"* — and `playbooks/framing.md` says a spike's criteria *"name what is
recorded and the threshold it is read against; a refuted result is still a delivered one."*

The pilot's D1, *"five private invitations, and we count who acts"*, was a legitimate spike. Its
criteria could have read *"we record how many of the five act within seven days; below two, the
demand is not shown"*, and **"nobody acted" would have been a delivered deliverable**. It did not
know that, so it answered a criterion it could not meet with five simulated proofs — merged and
reviewed like the rest. Sending the work to discovery or to an issue, as the plan proposed, would
have contradicted the framework's own answer and taught it as a second rule.

- [x] **Task 1.** C4's refusal names the door: write the criteria, **or make it a spike** — what
      will be recorded, the threshold, and a refuted result is a delivered one. And what has no
      criterion at all, because it waits on someone outside the project, is **a dependency with a
      date, not a deliverable**. The rule itself is unchanged.
- [x] **Task 2.** `playbooks/framing.md` step 2 gains the two questions to ask of every
      deliverable before writing its criteria, and the sentence that explains why one door is not
      enough: *a criterion nobody can meet is not met, it is answered with something that looks
      like proof.*
- [x] **Task 3.** `05-workflow.md` §3's diagnosis table gains the row it was missing — *it waits
      on someone outside the project* — and the spike row now says what a spike's criteria hold.
- [x] **Task 4.** The pilot's D1 is the fixture: the refusal must name knowledge, the spike, the
      refuted result, the dependency with a date, and what a criterion nobody can meet is answered
      with.

**Done when:** the framework stops offering one door to work that has two, and says which.

## M11f — Approval mechanics: the relief that weakens nothing — PR 6

Seven of the decider's sixteen approval turns carried no judgement: they existed because nobody
had enabled auto-merge and the agent waited to be told. This workstream removes the relay, not
the approval.

- [x] **Task 0 — probe, before any block below is trusted.** On a throwaway repository: enable
      auto-merge, approve a pull request with CI pending, confirm it merges on green; then push a
      commit to an approved and armed pull request and confirm G13 dismisses the approval and the
      merge waits. Rewrite the tasks below from what actually ran.
- [x] **Task 1.** A checklist rule — provisionally **G14** — auto-merge enabled on the
      repository, with `doctor` reading `allow_auto_merge`. Not blocking: a project that wants
      the agent to merge by hand keeps that.
- [x] **Task 2.** **G15**, squash-only merges, and **G16**, branch deletion on merge (D61, absorbed
      by PDR-0008). Both readable through the API **without the Administration permission**, so
      both are verified rather than merely written. The pilot's repository currently shows 22
      branches for 23 merged pull requests and four commits on `main` for two workstreams.
- [x] **Task 3.** The skeleton documents the one-gesture approval — as built, in
      `07-governance.md` §7, the README carrying only the checklist lines: the human approves from their own terminal, under their own identity, without a
      browser round-trip. The agent still never approves.
- [x] **Task 4.** `doctor`'s output names the three new rules with the exact setting to change.
- [x] **Task 5 — the checklist has two copies and a test that binds them.** `CHECKLIST` lives in
      `doctor.py`, is printed by `nstack init`, read by `project.py`, and **repeated word for word
      in `skeleton/README.md.jinja`**, with a test that verifies it. G14 to G16 land in both, and
      the test is the guard — it must be seen red before the README is edited.
- [x] **Task 6.** The CI replay test asserts the message text for each of the three.

**Done when:** an approval is one gesture and the merge follows by itself, with every barrier of
ADR-0004 intact.

## M11g — The exposure level, anchored on the OSPS Baseline — PR 7

- [x] **Task 0 — probe, before any block below is trusted.** Read `ossf/security-baseline`'s
      YAML catalogue and its Gemara mappings. Confirm that G1 to G13 and the five required checks
      map onto stable control identifiers, and that the three levels' membership is readable as
      data. **If the mapping is not clean, this workstream stops and returns to M13 as originally
      planned** — the rest of M11 does not depend on it. Record the outcome either way.
      **Done 2026-09-24: not clean** — [the probe's record](../audits/2026-09-24-osps-baseline-probe.md).
      Identifiers are stable and levels readable, but six of our sixteen rules have no control,
      four compose one, and task 3 would have to give the six a level of our own making. **M11g
      stops; tasks 1 to 6 return to M13.** The probe also found **D78**: `OSPS-AC-03.02`, level
      1, protects the primary branch from deletion, and our checklist never asks for it.
- [ ] **Task 1.** A mapping table, in the repository, from our rule identifiers to OSPS control
      identifiers, with the level each control belongs to. Our identifiers stay ours; theirs are
      referenced, never copied.
- [ ] **Task 2.** An optional project field, `assurance_level`, default **1** — the universal
      floor the Baseline itself recommends. It is a Copier answer in `.copier-answers.yml`,
      already owned by the code owner and therefore never merged without a human.
- [ ] **Task 3.** `doctor` reports two things and never confuses them: **the level attained**,
      from what it observes, and **the target**, from what is declared. A rule blocks only when
      its control belongs to the target level or below. `G2` and `G3` — the non-author human
      approval, `OSPS-QA-07.01` — become blocking at target 3, reported below it.
- [ ] **Task 4.** The wording is audited for one failure mode: `doctor` must never read as a
      certification. It says *"observed as satisfied"*, names what it cannot see, and links the
      Baseline rather than restating it.
- [ ] **Task 5.** `07-governance.md` §7 is rewritten: the four settings that close the
      self-approval door are described as **what level 3 requires**, with the honest statement of
      what a project below level 3 does not have. No amendment to ADR-0004 is needed — its
      reasoning is unchanged and its scope becomes explicit.
- [ ] **Task 6.** `ADR-0005` records the choice: adopt an external, machine-readable, regulation-
      mapped scale rather than invent one. Prior art in the record: OSPS Baseline, the EU CRA
      timetable, the three-tier convention of agent governance (IAPP, CBRA), and the rejected
      alternative — our own `solo`/`team`, measured against the pilot's 23 pull requests and
      found to change none of them.

**Done when:** a project knows which level it is at, which it targets, what the next one costs,
and the framework stops charging level 3 to a project that has no users.

**Closed by its probe on 2026-09-24.** Tasks 1 to 6 are M13's, with the probe's table as their
starting point; M11 ships without the exposure axis, and D69 stays open.

## M11h — The records, corrected in place — PR 8

- [x] **Task 1.** **PDR-0011 — Ceremony follows consequence.** The product decision: two axes,
      two owners; the framework says what each level buys; a dated success criterion
      (**2027-03-31**) and a removal condition, per the PDR format.
- [x] **Task 2.** `PRODUCT.md` §3 gains a fifth user — *a solo founder before there is a product*
      — with a measurable criterion, because the plan is about serving them without betraying the
      other four. *Done as one user, not two:* PDR-0006 had promised §3 its user — one person
      with agents, on a repository the forge cannot guard — and it was never added. It is the same
      person, so it is one row, its criterion drawn from PDR-0006, PDR-0007 and PDR-0011.
- [x] **Task 3.** `PRODUCT.md` §2, *what it does not sell*, gains the honest sentence the market
      data supports: **NapkinStack costs on day one and pays from the first module someone else
      must review.** Stanford's measurement — 35-40% AI speedup on simple greenfield, under 10%
      on complex legacy — says plainly that we do not beat plain iterative prompting on a
      three-day greenfield MVP, and pretending otherwise is how trust is lost.
- [x] **Task 4.** `PRODUCT.md` §5 declares the records exemption: ADRs and PDRs of *this*
      repository are corrected in place until the framework has an outside user; the supersession
      rule of `06-decisions.md` §134 applies here **from v1.0**. An undeclared exemption is D57.
- [x] **Task 5.** `PDR-0007` is clarified in place: its sentence *"removes a bound on the work,
      never a check on the change"* is true of framing and false of criticality, which has always
      moved checks. One paragraph, dated.
- [x] **Task 6.** `ADR-0003` is shrunk to the rule in force — English everywhere including machine
      values, **no localisation mechanism**, git history not rewritten — and loses the migration
      narrative, the old value table and the correction log. `AGENTS.md:10-12` loses the M7
      sentence and keeps the rule. The skeleton needs no change: it contains **zero** occurrences.
- [x] **Task 7.** `workstreams.md` records **D66** (an update names only the target version's
      release page, so a project jumping versions lands where its conflict is not explained),
      **D67** (criticality declared on four values, spent on one threshold; proportionality
      promised in three documents and executed by nothing), **D68** (nothing says when to take an update),
      **D69** (the checklist imposes `OSPS-QA-07.01`, a level-3 control, from the first commit),
      **D70** (the criticality is chosen by the agent on a command line with no help, no criteria
      and no consequence shown), **D71** (T4's ratchet: one fix invalidates every scenario),
      **D72** (a deliverable that depends on people outside the project has no executable oracle;
      the framework demanded one and was paid in simulated evidence). *Done, with **D73 to D77**
      besides* — found at the pilot's cycle boundary — and the three accepted decisions no
      workstream carried (below, M11j to M11l).
- [x] **Task 8 — the two plans downstream.** **M12**'s catalogue enumerates the rules it attacks:
      it gains M11, G14, G15, G16, and its T1, T4 and M8 entries are rewritten to the new
      behaviour — a conformance suite that attacks the previous rules proves nothing. **M13**'s
      row in `workstreams.md` loses the OSPS mapping, which M11g has taken, and keeps the merge
      record (PDR-0009). *Done, with two corrections:* there is no rule **M11** to add — M11b
      built the e2e rule and removed it — and of G14 to G16 only **G15** refuses anything, so it
      alone gains a forge scenario. M13 keeps the mapping **conditionally**: M11g has not run, and
      its probe may send the mapping back.
- [x] **Task 9 — a measurement the documents are still waiting for.** `07-governance.md` §7 ends
      on an open condition: an agent's approval does not count *"until the test sheets show,
      module by module, that an independent verifier finds what a human would"*. The pilot
      produced the first data point — a delegated verifier found **8 real defects, 2 of which the
      author would have shipped**, forced 3 refusals to merge, and showed 5 of the author's
      fixtures proved nothing. The measurement is recorded beside the condition. **The rule does
      not change**: one data point on one module is not the module-by-module evidence the
      sentence asks for, and saying so is the point. *Done in PDR-0003, not beside the sentence:*
      `07-governance.md` is in the skeleton, and a figure from this framework's pilot has no place
      in every project's handbook (PDR-0010). The record the condition answers to is PDR-0003's
      success criterion, and that is where it is written.

**Done when:** every document says what is true now, the exemption that lets us do that is
written down, the register holds what was found, and no downstream plan still attacks a rule
that no longer exists.

**What M11h found that this plan had missed.** Three decisions accepted on 2026-09-22 —
PDR-0007, PDR-0008 and PDR-0010 — each said *"to be implemented in M11"*, and so did M11's row
in the register; this plan, written the next day, carried none of them, beyond D61's half of
PDR-0008 in M11f. On 2026-09-24 the maintainer decided they are built **in M11, before
v0.7.0**. They are M11j to M11l below; M11m gathers what the pilot's cycle boundary found.
Each is planned in detail when it starts — the decisions already carry testable acceptance
criteria, and those are the oracle.

## M11j — The unframed state (PDR-0007) — PR 10

A project with no accepted charter is **unframed**: K1 to K3 do not apply, every other rule
does, and every judging run names the state. Its oracle is PDR-0007's six acceptance criteria.
It builds PDR-0004's first axis, the stage, read from the repository and never declared.

**Done when:** a first delivery pull request on an unframed project merges with no charter,
no cycle and no label, while another rule still refuses something in that project.

**Done (2026-10-12).** Built against PDR-0007's six criteria, each seen red first:

- [x] `plan.stage()` reads the stage from `docs/project/charter.md`: unframed, framed, or
      unreadable. Never declared; `None` outside a project, so this repository has none.
- [x] The pull request check skips K1 to K3 when unframed; an unreadable charter is C1
      there too, never a silent fall back.
- [x] Every judging command names the stage on its second line; a framed project never
      reads "unframed".
- [x] `nstack doctor` says once what framing buys and the gesture that starts it — a stage,
      not a gap, outside its exit code.
- [x] `new-module` no longer announces a cycle rule to a project that has no cycle.
- [x] The handbook, the project folder's guide, the rule index and the framing playbook name
      the two stages; the framing playbook says when framing is worth it, and never to frame
      to make a check pass.

**Found on the way, not fixed here**: a project with no module shows a skipped CI job named
`matrix.module.name` — the matrix job's name is an expression that nothing resolves when the
matrix is empty. Seen on the third project's pull requests; for the register.

## M11k — The forge's settings in one gesture (PDR-0008), D57, D77 and D78 — PR 11

One command beside `doctor`: it computes the distance to the checklist and prints the calls
that close it; applying is a choice, and only with a credential that **cannot commit**, checked
first and failing closed. Its oracle is PDR-0008's eight acceptance criteria. **D77** is fixed
here, because the command and `doctor` share one checklist and one verdict: *not read* and
*not in place* get two exit codes, and the summary says which. **D78** too: the checklist
gains the protection of the default branch against deletion and force-push, which the command
then applies like any other setting — `OSPS-AC-03.02` puts it at level 1, and this repository's
own ruleset already has both. **D57** closes here too: the kernel says *"never with a human's
credentials"* without the exception PDR-0008 makes for a credential that cannot commit, and
one of the two has to say it.

**Done when:** a repository reaches the checklist in one gesture, no credential ever reaches
the output, and a script can tell a gap from what could not be read.

**Done (2026-10-12), as far as it could honestly go.** Planned in detail when it started, and
cut in two by what the forge's documentation said.

- [x] **Task 0 — read the forge before writing a call.** Every endpoint the command prints was
      read at the forge's REST documentation the same day. The read that mattered: nothing
      documented lets a command learn that a token **cannot** commit — the one check PDR-0008's
      apply mode rests on.
- [x] **Task 1 — `nstack settings`, print mode.** The same checks as `doctor`; the smallest set
      of calls, in the forge's own command line; one ruleset for the missing rules, never a
      rewrite of an existing one; what is stricter left and said; a bypass list left to a human;
      what a plan cannot enforce named, and the repository said unguarded. Criteria 1, 4, 5, 6
      and 8.
- [x] **Task 2 — D78.** G17 and G18: the main branch cannot be deleted nor rewritten. In the
      checklist, in its second copy, in the rule index, in the plan the command prints.
- [x] **Task 3 — D77.** `doctor` exits 1 on a gap, 2 when nothing read is missing and something
      could not be read.
- [x] **Task 4 — broken on purpose.** Three mutations of the command, each caught by the oracle:
      a bypass actor in the planned ruleset, a stricter actions policy planned open, merge
      commits kept.
- [x] **Task 5 — on a real project.** Run on the third project, private on a free plan, with no
      token: the plan printed a ruleset the forge would refuse and said nothing of it. It now
      says so. Fixed here, re-run there.

**Not done: the apply mode, and D57 with it — M11r.**

## M11r — The settings applied, once the forge has answered (PDR-0008) — PR 20

- [ ] **Task 0 — the probe, with the maintainer's own token.** A fine-grained token with
      Administration write and no Contents access, and a second one that can also push: what
      does the forge answer to each on the repository object, on a settings call, on a harmless
      write to the code? **Exit**: if nothing tells the two apart without attempting a write, the
      apply mode is not built and PDR-0008 says so; the print mode stands.
- [ ] **Task 1.** The check, first and failing closed; then the calls; then the diagnosis.
      Criteria 2, 3 and 7.
- [ ] **Task 2 — D57.** The kernel's "never with a human's credentials" and the one exception,
      in the place the probe shows it belongs.


## M11l — The form, not the content (PDR-0010) — PR 12

**Planned in detail on 2026-10-12**, the day the maintainer created a third project and read
it: of its 48 Markdown files, three mention the product, and its front page is a title, an
unwritten sentence and 249 lines of this framework's manual. PDR-0010's criteria name the
README alone; the reading showed the same defect in four more files, and two requirements the
decision implied without stating — **a diagram before prose**, and **documents that stay
current**. Both are written into the decision by this workstream, in place.

```mermaid
flowchart LR
    subgraph T["A file of the skeleton is one of two things"]
        M["METHOD<br/>the framework writes it<br/>every update merges it"]:::method
        S["SEAT<br/>the framework writes its form once<br/>the project writes the content<br/>no update touches it again"]:::seat
    end
    I["nstack init"]:::cmd --> M
    I --> S
    U["nstack update"]:::cmd --> M
    U -. "never" .-> S
    S --> C1["charter accepted<br/>the front page is written<br/>C8 refuses the form left empty"]:::event
    C1 --> C2["cycle closed<br/>the closure names what<br/>was brought current"]:::event
    C2 --> C2

    classDef method fill:#374151,color:#fff
    classDef seat fill:#065f46,color:#fff
    classDef cmd fill:#1f2937,color:#fff
    classDef event fill:#1e3a8a,color:#fff
```

**Legend** — grey: the method, the framework's and received through updates · green: a seat,
the product's from the first commit · blue: the two events that bring a seat current — one a
machine reads, one owed to the decider.

### Decisions taken while planning M11l

1. **The defect is the mixed file.** A file that holds the framework's words *and* waits for the
   project's is owned by nobody: the project does not delete what looks official, and the
   framework conflicts on what the project wrote. Each of the skeleton's files becomes method or
   seat, never both.
2. **Ownership is update behaviour, and Copier already has the word for it.** A seat is listed
   in `copier.yml` under `_skip_if_exists`: written at `init`, recreated if missing, never
   merged again. No engine code, no marker, no detection.
3. **Four seats, not twelve.** `README.md`, `modules/README.md`, `docs/adr/README.md`,
   `docs/pdr/README.md`, and nothing else moves. `contracts/README.md` shrinks to a pointer and
   stays method. `docs/project/README.md`, `CONTRIBUTING.md`, `SECURITY.md`, the templates, the
   playbooks, the kernel and `docs/os/` are method and say so. `CODEOWNERS`, `contracts/MANIFEST.yaml`
   and `docs/tooling-profile.md` are mixed too, merge cleanly today on both real projects, and
   are **left alone**: no observed defect, no change.
4. **The standard names no tool.** *"A diagram written as text in the file, with its legend,
   before the prose"* is the rule; the tooling profile maps it to Mermaid, the way it maps every
   other capability (P7).
5. **Currency gets one machine rule and one owed line, and no more.** Whether a README is *true*
   is not decidable. Whether it still holds its form's words under an accepted charter is: that
   is **C8**, the same family as D51. Everything after that is owed, named at the cycle's
   closure, and marked owed.
6. **No diagram is demanded of a decision record.** A charter gets one — who uses the product
   and what it talks to. An ADR or a PDR is most often a table of options; a compulsory diagram
   there produces decoration.
7. **The Feature form and the Spike form go.** Each names work a deliverable already claims
   (K3; and M11e made the spike a deliverable). What arrives unplanned and is not yet work is a
   **Request**. Four forms: Request, Bug, Architecture, Debt.
8. **D79 leaves this workstream and becomes M11n.** It rewrites the engine's messages and gains
   a rule index: another subject, another review. M11l keeps only the D79 items that sit in the
   files it already rewrites.
9. **No early v0.7.0.** The third project is re-created from the merged commit with `--ref`,
   the door PDR-0005 built for exactly this; it takes v0.7.0 by `nstack update` like the other
   two. M11i's order — after j, k, l, n — stands.

### File map

| File | Change |
|---|---|
| `copier.yml` | `_skip_if_exists`: the four seats |
| `skeleton/README.md.jinja` | The stub: name, sentence, one pointer line, four headings, a diagram's place |
| `skeleton/docs/os/INSTALL.md.jinja` | **New.** The manual, moved, unchanged in substance |
| `skeleton/modules/README.md` | The project's module map: a diagram's place, one pointer to `02-modules.md` |
| `skeleton/contracts/README.md` | Three lines and a pointer to `03-contracts.md` |
| `skeleton/docs/adr/README.md`, `skeleton/docs/pdr/README.md` | The index and a pointer to `06-decisions.md` |
| `skeleton/docs/os/06-decisions.md` | §9 planned / unplanned / the log; **§10, the project's documents** — the standard, once |
| `skeleton/docs/os/00-overview.md` §5 | Method and seat, the table the test reads |
| `skeleton/docs/os/README.md`, `09-platform.md` | The map and the trees name `INSTALL.md` |
| `skeleton/docs/tooling-profile.md` | One row: diagrams as text |
| `skeleton/docs/project/_CHARTER_TEMPLATE.md` | A context diagram's place |
| `skeleton/docs/project/cycles/_TEMPLATE.md` | Closure: the documents brought current |
| `skeleton/playbooks/framing.md` | Charter accepted → the front page written; closure → brought current |
| `skeleton/.github/ISSUE_TEMPLATE/` | `01-request.yml` replaces `01-feature.yml`; `04-spike.yml` removed; `05-debt.yml` → `04-debt.yml` |
| `skeleton/CONTRIBUTING.md` | Step 1 picks a deliverable, not an issue |
| `src/napkinstack/fitness/plan.py` | **C8** |
| `src/napkinstack/project.py`, `doctor.py` | The token line and the docstring name `docs/os/INSTALL.md` |
| `platform/tests/test_seats.py` | **New.** Seats bound to the handbook's table; a seat names the framework once; the manual whole; the standard once; the forms |
| `platform/tests/test_plan.py`, `run.sh` | C8; the checklist copy; the stub; an update that leaves a seat alone |
| `docs/pdr/0010-…`, `docs/governance/workstreams.md`, this plan | Corrected in place |

### Tasks

- [x] **Task 0 — probe: `_skip_if_exists` across an update.** In `run.sh`'s update block, where
      a template moves from v90.2 to v90.3: change the template's `README.md.jinja` between the
      two, and assert the project's `README.md` is byte-identical after `nstack update`, and
      that a seat deleted by the project comes back. **Seen red first** (today the README
      merges). If Copier's behaviour is not this, stop: decision 2 is wrong and the seats need
      another mechanism.
- [x] **Task 1 — the seats, bound.** `00-overview.md` §5 gains the method/seat table;
      `test_seats.py` asserts (a) the table's seats equal `copier.yml`'s `_skip_if_exists`,
      (b) every seat exists in the skeleton, (c) **a seat names the framework or its engine on
      at most one line**. (c) is red on all four files before they are rewritten.
- [x] **Task 2 — the checklist's second copy moves, test first.** `run.sh` reads
      `skeleton/docs/os/INSTALL.md.jinja` instead of `README.md.jinja`: red, the file does not
      exist. Then the manual moves **by `git mv` and a new stub**, so the diff shows no line of
      the manual changed but its opening paragraph. `init`'s third next step and `doctor`'s
      docstring name the new path.
- [x] **Task 3 — the stub.** Name, the sentence `doctor` L5 already reads, one line to
      `docs/os/INSTALL.md` that says it may be deleted, then *What it is* (a diagram's place,
      then three lines), *Run it*, *Contribute*, *Decisions*. `run.sh` asserts: fewer than 40
      lines, exactly one line naming `INSTALL.md`, no installation command.
- [x] **Task 4 — the folder files.** For each paragraph removed from `modules/`, `contracts/`,
      `docs/adr/` and `docs/pdr/` READMEs: found in the handbook first, moved there if absent
      (the naming rule of a decision file and the *Rule to automate* row are the two to check).
      `modules/README.md` becomes the module map — a diagram of the modules and the contracts
      between them, brought current by the pull request that creates or retires one.
- [x] **Task 5 — the standard, once (criterion 5).** `06-decisions.md` §10: a diagram of who
      writes which document and what brings it current; the table; three rules of form — a
      diagram with its legend before the prose, a source for every claim about the outside
      world, a date on every decision — and one of currency: every document names the event that
      brings it current. A test counts the standard's sentence in the skeleton (**one**) and
      refuses a tool's name in the section. The tooling profile gains its row. Kernel untouched:
      227 of 250.
- [x] **Task 6 — current (C8 and the owed line).** `test_plan.py`: an accepted charter beside a
      README still holding the stub's words is refused, naming the words; a proposed charter is
      not; a project with no README is not. Red, then C8. The charter template gains its
      diagram's place, owed like the rest of its prose (C2 reads the front matter). The cycle template's Closure
      gains *Documents brought current*; `framing.md` says who writes the front page, when, in
      which pull request. The matrix keeps "Affected documentation up to date" as **owed**: C8
      does not make it machine.
- [x] **Task 7 — planned and unplanned (criteria 3 and 4).** `06-decisions.md` §9: *planned
      work → the cycle's deliverables*, *unplanned work → a typed issue*, *what the project
      must remember → one named issue, the log*; "expected behaviour" reads the deliverable's
      acceptance criteria. The same words corrected where they are repeated (`00-overview.md`
      glossary, `06` §4, `08-quality.md` §9, `CONTRIBUTING.md` step 1). Forms as decision 7. A
      test lists the forms and refuses a `Deliverable` field in any of them.
- [x] **Task 8 — D79's share.** The two measurements from this framework's pilot leave
      `05-workflow.md` §7 and `07-governance.md` §7, or stay as a rule with no figure. The rest
      of D79 is M11n's.
- [x] **Task 9 — the records.** PDR-0010 corrected in place, dated: the seats, C8, the standard
      with its currency rule, its criteria ticked against what ran. `workstreams.md`: D59 and D60
      done, D79 to M11n, M11n listed. M11i gains two lines for its Migration paragraph — a
      running project keeps its seats and receives `INSTALL.md`; two forms disappear on update.
- [x] **Task 10 — a real project, both ways.** From the working tree: `init`, then `plan` with
      an accepted charter over the untouched stub (red on C8), the stub written (green),
      `doctor`. Then a copy of each project created on v0.6.2 takes `nstack update --ref` to
      this branch: its README byte-identical, `INSTALL.md` arrived, conflicts counted and named
      in the pull request — measured, not predicted (D73).

**Done when:** a project created from this commit opens on its own name and nothing else of
ours; its manual is one click away; a charter cannot be accepted over an empty front page; and
a project that already exists loses nothing it wrote.

**Done (2026-10-12).** As built, against what was planned:

- **A missing seat comes back** (task 0). Copier's `_skip_if_exists` recreates a file that is
  absent — unlike a method file a team deleted, which stays deleted. Kept: a project with no
  front page gets a form to write.
- **Only the front page was red on "names the framework once"** (task 1): the three folder
  files named the engine once or never. Their defect was method prose in a seat, which no
  count catches — they were rewritten on reading, and the test now holds the line.
- **The charter's diagram is owed, not checked** (task 6): C2 reads the front matter, never
  the prose. C8 reads exact lines of the form, not a `<…>` pattern: a front page may hold any
  tag.
- **Measured on copies of the two projects created on v0.6.2** (task 10), each taking this
  branch by `nstack update --ref`: **no conflict on either**, the four seats byte-identical,
  `docs/os/INSTALL.md` arrived whole, two forms removed and one added, 24 files touched. Each
  keeps its 249-line README until its team trims it; the third project's still holds the
  unwritten sentence, which C8 will refuse the day its charter is accepted.
- **A real project from the working tree**: the front page is 27 lines and names the framework
  nowhere; an accepted charter over it is refused with the three lines to write; written, the
  plan is compliant.

## M11n — The framework's own identifiers stay home (D79) — PR 14

Split from M11l on 2026-10-12. Engine output and skeleton comments cite this repository's
records — `(PDR-0005)`, `(ADR-0004)`, `(D46)` — which collide with a project's own numbering;
rule codes are defined in no document a project holds; `doctor` L4 refuses a file named
`PRODUCT.md`, which a product may now legitimately write. Planned in detail when it starts.

**Done when:** nothing a project reads or runs cites a record it cannot open, every rule code a
message prints is defined in one page of the handbook bound by a test, and L4 is retired.

**Done (2026-10-12).** Four cases, each seen red first (`test_identifiers.py`):

- **15 messages and 9 skeleton lines** cited `(PDR-…)`, `(ADR-…)` or `(D46)`. Each lost the
  reference and kept its reason; two gained a page of the handbook instead. The engine's
  comments and docstrings keep theirs: nobody outside reads them.
- **`docs/os/RULES.md`**: 66 codes in 12 families, one line each — what it refuses, where its
  reason is written — opened by a diagram of where each family judges. The test binds it both
  ways: a code printed and not defined, or defined and printed by nothing, is red.
- **L4 retired.** It refused a file named `PRODUCT.md`; the oracle now creates one and asserts
  `doctor` says nothing of it. The repository's own hook configuration lost the same comment:
  the two copies are bound by the suite.
- **Not done here, and said**: the handbook still names a forge's command line in
  `07-governance.md` §7. That is P7's subject, not D79's.

## M11o — Every document has its moment (PDR-0010, extended) — PR 15

Opened on 2026-10-12 by the maintainer's reading of M11l: *the README was one example* — other
files speak of the project, and some can only be written after a phase has ended. An
inventory of the 61 files of the skeleton and the 4 of the module scaffold found three more
mixed files and one rule that asked too early.

| File | Was | Becomes |
|---|---|---|
| `SECURITY.md` | The project's policy and the framework's rules | A fifth seat: the policy; the rules stay in `playbooks/security.md` |
| A module's `README.md` (`new-module`) | Four lines of the engine's commands | The verbs, and the place of a diagram |
| `docs/architecture/`, `docs/runbooks/` | Empty folders with no moment | A row of `06-decisions.md` §10: absent until a decision or an incident needs them |
| `README.md`'s sentence | Reported as a gap from the first minute (L5) | Asked for at the discovery's go (C8); **L5 retired** |
| The documentation standard | In the handbook, which no agent loads | `playbooks/documentation.md`, triggered by the kernel (228 of 250 lines) |
| `CONTRIBUTING.md`, `docs/project/README.md`, `contracts/*`, the templates, `docs/os/`, the playbooks | Method | Method — unchanged, and said so |
| `docs/tooling-profile.md`, `CODEOWNERS`, `contracts/MANIFEST.yaml` | Shared row by row | Unchanged: both real projects merge them without conflict |

- [x] **Task 1 — C8 by moment, seen red.** The sentence at a go; the whole front page at an
      accepted charter; the module map once a module holds code. Each refusal names its event.
- [x] **Task 2 — L5 retired**, with its count in the oracle; `RULES.md` loses the row (the
      binding test went red first).
- [x] **Task 3 — the fifth seat**, bound by the same test as the four.
- [x] **Task 4 — the module's page**, with a test that it names the framework once at most.
- [x] **Task 5 — the standard where agents load it**: the playbook, its skill entry, the
      kernel's trigger row; `06-decisions.md` §10 rewritten by phase and pointing at it.
- [x] **Task 6 — the playbooks say what each moment writes**: `discovery.md` at a go,
      `framing.md` at the charter's acceptance.
- [x] **Task 7 — the place of a diagram** in the ADR and PDR templates, as an invitation.
- [x] **Task 8 — the records**: PDR-0010 corrected a second time, this section.

**Done (2026-10-12).** The oracle refused the first version of the module-map rule: creating a
module turned a project red at once, against the promise that a scaffold stays green (D33).
The rule now reads a module's first file of code, like M7. **Not taken, and said**: the levels
of rules — what every project shares, what one project adds — which the maintainer raised the
same day and which is M11p's.

## M11p — The levels of rules have a place (PDR-0002) — PR 16

Raised by the maintainer on 2026-10-12, with security as the example: some rules are every
project's, others are this project's alone, and the framework must tell them apart. It
already did, in words — three levels, since PDR-0002 — and named no place for the middle one.

```mermaid
flowchart LR
    F["FRAMEWORK<br/>playbooks/security.md"]:::fw -->|"read with"| P["PROJECT<br/>docs/project/rules/security.md"]:::pr
    P -->|"read with"| M["MODULE<br/>its AGENTS.md"]:::mo

    classDef fw fill:#374151,color:#fff
    classDef pr fill:#1e3a8a,color:#fff
    classDef mo fill:#065f46,color:#fff
```

**Legend** — grey: received through updates · blue: the project's, new here · green: the
module's, unchanged. The same three boxes exist for every playbook.

- [x] **Task 1 — the place.** `docs/project/rules/<subject>.md`, the subject being a playbook's
      name; `always.md` for every task. Absent at creation; a form, `_TEMPLATE.md`, whose last
      column asks how each rule is checked.
- [x] **Task 2 — whoever loads a playbook is told.** One line in each of the nine trigger
      blocks, seen red first: a playbook loaded as a skill never shows the kernel's table.
- [x] **Task 3 — the kernel** loads the level and ranks it between the module and the
      playbook: 230 of 250 lines.
- [x] **Task 4 — the handbook.** `00-overview.md` §5 draws the three levels with one rule of
      each; `07-governance.md` §2 says where its decision tree lands at each level;
      `06-decisions.md` §10 gives the folder its moment — the charter's acceptance.
- [x] **Task 5 — the framing** proposes the project's first rules from the charter's
      constraints, and says why never in a playbook.

**Done (2026-10-12).** Nothing reads a project's rules: they are the project's, and a check
on their content would be the framework naming a domain. **Not done, and said**: the skills'
descriptions still open on "The project's … rules" for what are every project's; the playbook
they load now names the project's layer, which is what an agent acts on.

## M11q — Nothing created before its moment, and a decision to take — PR 18

Opened on 2026-10-12 by the maintainer reading the third project after its discovery: 68
files, about 6,570 lines of the framework's against 680 of the project's — *"il faut
distinguer ce qui est réellement utile … et les fichiers qui polluent"*.

- [x] **Task 1 — no folder created empty.** `docs/architecture/`, `docs/runbooks/` and two
      redundant placeholders leave the skeleton; a test, seen red, keeps the one a module's
      envelope needs. The handbook's trees say when each folder appears.
- [x] **Task 2 — the rest is a decision, not a cleanup.** **PDR-0012**, *proposed*: one folder
      for the framework's files, the contracts module created by the first contract, and the
      handbook's place left to the maintainer.
- [x] **Task 3 — what the third project taught, for the register**: D80 to D83.

**Done (2026-10-12), and corrected against what was announced.** The maintainer had been told
that not creating `contracts/` at `init` was a small change. It is not: nothing creates that
module afterwards, so it needs a command, and the oracle and `CODEOWNERS` assume the folder.
It went into PDR-0012 rather than being done by half.

## M11s — One folder for the framework (PDR-0012) — PR 21

PDR-0012 accepted by the maintainer on 2026-10-12, the handbook kept in the project.

- [x] **Task 1 — the move.** `playbooks/`, `docs/os/`, the six forms, the project folder's
      guide and the tooling profile go under `.nstack/`; 84 files that named an old address
      follow. The trees and tables of the handbook are redrawn by hand.
- [x] **Task 2 — a project is one from its creation.** `docs/project/` no longer exists before
      a discovery or a charter: the stage is read from the answers file as well.
- [x] **Task 3 — measured before it was written: a rename loses an adaptation.** On the pilot's
      copy, a line added to a page that moved was dropped in silence. A test reproduces it on a
      project created in the old layout, seen red; `nstack update` then carries each adapted
      file to its new place and names it (D84).
- [x] **Task 4 — every page named exists.** One test over the engine's messages and the files
      a project receives.
- [x] **Task 5 — the three real projects**, on copies: clean; one conflict shown where a line
      had been lost; one conflict in a file that does not move.

**Not done here: the contracts module created by the first contract — M11t.** It needs a
command, and the oracle and the code owners assume the folder.

## M11u — The addresses a project wrote follow the move (D85) — PR 22

Found the hour M11s was merged, by taking its update on the third project: the framework's
files had moved, and 100 mentions of their old addresses stayed in files the project owns —
seats no update touches, module files the scaffolding wrote, the charter, the cycle. Two were
dead links, on the front page and in the security policy.

- [x] **Task 1 — seen red** in the oracle's old-layout project: a link on the front page, a
      relative link in a decision index, two paths in the project's own notes.
- [x] **Task 2 — `nstack update` rewrites them**: an address named from the root, and a
      relative link resolved from the file that holds it; only an address that was the
      framework's, only when its new place exists; only for a project that crosses the move.
      The files rewritten are listed, and the change is in the update's pull request.
- [x] **Task 3 — the real projects again**, on copies: the third project, 100 old addresses
      to none, no dead link; the pilot, none left and no dead link, its one conflict unchanged.

**Why the update edits files it otherwise never touches.** A seat is the project's; so is a
module's manifest. But the line being changed is an address of the framework's, which the
framework moved: leaving it is leaving a dead link on a product's front page. The rewrite is
exact, listed, and reviewed like the rest of the update.

## M11t — The contracts module is created by the first contract (PDR-0012) — PR 23

- [x] **Task 1 — `nstack new-contract <name>`**, seen red: the contract's first version as a
      page to write, and the first time the module that holds every contract — manifest,
      owner, runbook, its line among the code owners. The scaffold moves from the skeleton to
      the engine's templates. A project is born without `contracts/`.
- [x] **Task 2 — green as created.** The first run turned the module red: a contract's page
      counted as content, and the rule on standard verbs asked for `check` and `test` before
      anything could be checked. A page at any depth is now description; the rule fires at the
      first schema or test, and a case holds that line too.
- [x] **Task 3 — an update must not take the module from under a contract.** The scaffold
      left the skeleton, so the merge deletes it. Seen red on a project holding a contract;
      the update restores the module and its owner for such a project, says so, and lets the
      empty one go for a project that holds none.
- [x] **Task 4 — the three real projects**, on copies: two with no contract lose the empty
      module; the one with a contract keeps it whole, and validates.

## M11v — What the third project found — PR 24

The defects a real discovery and a real framing left in the register, and one that was not
there yet. As M11m did for the pilot: each in the place the next reader looks.

- [x] **D86** — the release notes of an unpublished version named a description, not a
      reference: the link names the commit. A case, seen red.
- [x] **D82** — the discovery's intake asks in which language the project writes; the framing
      asks it when no discovery came first. The answer is the project's first rule.
- [x] **D83** — a legal or regulatory claim is read at its primary source, or is an assumption.
- [x] **D81** — a project's rule has no earliest moment: the handbook no longer says "not
      before the charter".
- [x] **D87**, new — whoever frames reads the rule before proposing a criticality; a lower
      value is a deviation, written with its reason and the event that ends it.
- [ ] **D80** — left open on purpose: both ways out cost more than the defect.

The four playbook lines are not checks, and say so (P1: no logic about a project's domain).
A case per line keeps it where it is.

## M11m — What the pilot's cycle boundary found — PR 13

- **D74**: `nstack update` no longer carries a foreign commit silently — it builds its branch
  from the default branch, or refuses and names the branch it would have carried; the test,
  seen red first, decides which.
- **D68**: the pilot's sentence, *"upgrading mid-cycle changes the judge while a cycle is being
  judged"*, where the handbook describes an update.
- **D75**: one question in `playbooks/verification.md` — is the entry point a real user calls
  exercised the way they call it? A playbook line, not a check (P1).

**Done when:** an update started from a feature branch cannot carry a foreign commit
silently, and the two sentences are where the next reader looks.

**Done (2026-09-24).** D74 refuses rather than switches: switching would
change a user's checkout without a word, the same shape as the defect. D68 lands in the
skeleton's README, where an update is described; D75 at the verifier's diff-reading step.

## M11i — v0.7.0, and the two projects that already exist — PR 9 and the release

- [x] **Task 1.** The `CHANGELOG` v0.7.0 section, **engine and project apart** (D63), with a
      **Migration** paragraph: what M11a to M11f and M11j to M11m change for a project — there is
      no target level in v0.7.0, M11g having returned it to M13. **Written from an update actually
      run against a copy of each real project before the tag, not predicted from the diff**
      (D73): our v0.6.1 note announced a conflict on the one project where it could not happen.
      And **both projects will turn red on G15 and G16**: each allows merge commits today.
      *As run, 2026-10-12, on a fresh copy of each: the pilot's update has one conflict, in a
      page it had adapted; the second project's merged clean — and its pull request was refused
      on P1 and T1 for old addresses rewritten in comments of its code (**D88**, fixed here: a
      module's code is left as written and named). G14 to G16 are gaps on both, read from the
      forge. The apply mode of `nstack settings` (M11r) is not in this version.*
- [x] **Task 2.** The release, with explicit consent, and the release page produced by the
      workflow rather than by hand — its second live run after v0.6.2.
      *Done 2026-10-12: tag `v0.7.0` on `581dea6`, published to PyPI by the workflow after the
      maintainer's approval, the release page taken from the changelog. Checked from the
      registry: `nstack 0.7.0`, and a project created by it is pinned to `v0.7.0` and green.*
- [ ] **Task 3.** `tool-library` takes the update and is observed, not coached.
- [ ] **Task 4.** The pilot takes it at its own cycle boundary. **Its `screening` module is
      declared `high`; the matrix now says what that buys and what `standard` would have bought.**
      Whether it revises the declaration is a measurement, not an instruction, and it is logged in
      this repository either way.

---

## Verification — every pull request

1. `uv run bash platform/tests/run.sh` — **from a committed tree**: Copier copies the working
   state and four root dotfiles are character devices in this sandbox.
2. `nstack fitness` on this repository, and **the real commands on a project generated from the
   working tree** — not only unit tests.
3. `pre-commit run --all-files`.
4. The pull request body carries DONE / VERIFIED / ASSUMED / NOT VERIFIED / RISKS.
5. CI green, then the decider approves in the browser, then the merge under the App with
   `--match-head-commit <full sha>` and `--delete-branch`, then **`main` is checked after the
   merge**.

## Risks

| Risk | Why it is real | What we do |
|---|---|---|
| **The OSPS mapping is not clean** | Their controls are written for projects, ours for changes; the granularity may not line up | M11g task 0 is a probe with an explicit exit: the workstream returns to M13 and the rest of M11 ships without it |
| **`prototype` becomes a hiding place** | A module declared `prototype` to escape a sheet | The value is declared in a reviewed file, printed in every run, and `nstack modules` lists how many sit at each value. Measured, then judged — not guessed at now |
| **Lowering the assurance floor reads as lowering quality** | It is the product's promise: quality does not depend on vigilance | The floor is never lowered on a module that declares what it is; only the *default target* of the project moves, anchored on an external standard, and `doctor` names the gap to the next level at every run — *M13's, since M11g's probe* |
| **`doctor` is read as a certification** | "OSPS level 2" is a sentence people will put in a sales deck | M11g task 4 audits the wording; the word *observed* appears in every line, and what cannot be seen is listed — *M13's, since M11g's probe* |
| **The kernel exceeds 250 lines** | M11c adds a routing line; the kernel is at **226 of 250**, so one line fits and the risk is only that M11c grows | Checked in the task; if it grows, the sentence duplicated from `07-governance.md` §7 comes out |
| **The two existing projects conflict on update** | Both are ours, both take the skeleton | M11i does them one at a time, and the `CHANGELOG`'s Migration paragraph is written before the tag, not after |

## Self-review

- **No placeholder, no TBD.** The two blocks that are not yet proven are marked as probes with a
  named exit (M11f task 0, M11g task 0).
- **Internal consistency.** Human review appears in exactly one axis (exposure — M13's since
  M11g's probe) and is
  removed from the other (M11a task 1). `confirm_at_head` is introduced in M11b's matrix and
  spent in M11d task 3. No rule is added without its failing test (P5). The three proportionality
  tables are reconciled by subject — when, what, and a pointer — rather than merged into one, and
  a test refuses a fourth description.
- **Coherence pass.** Every file citing the three sections this plan rewrites is listed in the
  coherence map, found by search. Three gaps the first draft had missed are closed: the third
  table (`08-quality.md` §7), the pull request template's sheet, and the CHECKLIST's second copy
  in the skeleton README.
- **Scope.** Nine workstreams at planning time, each tracing to a measured defect: D61, D66 to D72; M11h added four more (M11j to M11m), for three accepted decisions and D57, D68, D74, D75, D77,
D78 and D79. Nothing here
  serves a user of `PRODUCT.md` §3 that is not named, and the fifth user is added explicitly
  rather than assumed.
- **Ambiguity.** "One round" (M11a task 3) is a statement about what the *framework* requires,
  never a cap on what a project chooses — the sentence says so in both directions.
- **What this plan deliberately does not build:** our own security control catalogue (OSPS
  exists, in YAML, with tooling), runtime action guardrails (OPA, Cedar and NIST hold that
  ground, and P3 says CI anyway), a spec → plan → tasks pipeline (Spec Kit and Kiro have it, and
  it is what they are criticised for), our own ArchUnit, and a per-rule configuration file.
