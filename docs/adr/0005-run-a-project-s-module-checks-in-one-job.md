# ADR-0005 — Run a project's module checks in one job

- **Status**: Accepted (2026-10-15)
- **Date**: 2026-10-15
- **Decision makers**: NapkinStack maintainers (`@NapkinStack/maintainers`)
- **Scope**: project (the skeleton's `Modules` workflow)
- **Reversibility**: easy — the workflow is the framework's, and a project receives the
  previous shape back through `nstack update`; no required check changes its name

---

## Context

`module-checks.yml` runs the standard verbs of the modules a change touches. Since D35 it has
three jobs: `Changed modules` lists them, a matrix job runs each one under its own name, and
`Module checks` — the check the ruleset requires (G4) — fails when one of them failed, because
no ruleset can require a name it does not know in advance.

The forge bills each job **rounded up to the next whole minute**. The framework's jobs are
short: most last about a minute, and the engine's install is most of it. Measured on the third
project, a private repository, before its organisation's hosted minutes ran out on
2026-10-14: 904 runs in about 48 hours; on a sample of 100 runs, 208 jobs billed about 1,935
minutes, of which the framework's fixed jobs were about 82 % and the modules' own commands
about 18 %. A pull request that changes one module bills seven jobs across the four
workflows; three of them are `Modules`, two of which do no module's work.

D105 let a project move its jobs to a runner of its own, which moved the cost without reducing
it. D103 asked for the cost to be measured before it was changed; it is measured. And D80 is
still open: a pull request that changes no module shows a job named
`matrix.module.name`, because the matrix never existed.

## Problem

How does a project run the checks of the modules a change touches at the least billed cost,
without losing a single verdict the workflow gives today?

## Constraints

- **The required check keeps its name**, `Module checks`: it is written in every project's
  ruleset (G4), and a rename would turn each one into a merge that nothing guards.
- **No verdict is lost**: the run on `main` stays — it judges the tree two pull requests
  produced together, which no pull request judged (D98 does not require a branch to be
  current); `compat` still runs after a failing step (D46); every module's evidence is still
  kept; `clean` still runs on a self-hosted runner, even after a failure (D106).
- **No stack** (P1): the workflow runs the verbs a module declares, nothing else.
- **One runner label for a project** (D105): nothing here may require a second.
- Testable where the platform tests run (P5): a step that decides a verdict is a script the
  oracle executes, as `install-engine.sh` already is.

---

## Prior art

**Dominant convention of the field:** a monorepo's continuous integration runs the projects
a change affects **in one job**, and fans out into parallel jobs only when one job is too slow.

| Reference | What it does | Applicable here? |
|---|---|---|
| [GitHub Actions billing](https://docs.github.com/en/billing/managing-billing-for-your-products/managing-billing-for-github-actions) | "GitHub rounds the minutes and partial minutes each job uses up to the nearest whole minute" | **Yes**: the cost model this decision answers. Three one-minute jobs cost three minutes, one three-minute job costs three; three thirty-second jobs cost three, one costs two |
| [Nx, GitHub integration](https://nx.dev/docs/features/ci-features/github-integration) | The generated workflow has one job; its last step runs `nx affected -t lint test build`, the affected projects listed from the git history | **Yes**: the shape — list what changed, run each one's targets, in one job |
| This framework, `install-engine.sh` | A decision CI takes lives in a script the oracle runs, not in YAML only a forge executes | **Yes**: where the loop goes |

**Why the convention is not enough:** it is enough. The matrix was chosen in D35 for the
required name, not for parallelism: the aggregate job was the cost of that choice, and one job
named `Module checks` pays the same need without it.

---

## Options considered

### Option 1 — One job, named `Module checks`, running a script of the framework
- Description: the job lists the changed modules (`nstack modules --changed-since …
  --with-contract-sides`) and calls `.nstack/check-modules.sh`, which runs, for each module in
  turn, `bootstrap`, `check`, `test`, then `compat` whatever happened before, then `e2e`, then
  `clean` on a self-hosted runner; it carries on to the next module after a failure, prints
  each module in its own log group, and fails at the end if any module failed. One evidence
  artefact holds every module's `.evidence/` under its folder. The criticality is printed by
  the engine.
- Advantages: three jobs become one, on pull requests and on `main`; D80 disappears with the
  matrix; the verdict logic is a script the oracle runs; the workflow no longer needs `yq`, so
  a self-hosted runner needs `git` alone.
- Drawbacks: modules run one after another — the wall clock is their sum; the pull request's
  page shows one line instead of one per module, and a failure is read in the job's log groups.
- Cost: low · **exit**: the previous workflow, from git history, through an update.

### Option 2 — Keep the matrix (do nothing)
- Three jobs per run, two of which do no module's work; D80 stays open.

### Option 3 — Drop the run on `main`
- Saves the whole workflow on every push. Loses the only judgement of the tree two pull
  requests make together, and of a commit pushed outside any pull request on a repository
  nothing guards (PDR-0006). A verdict lost: refused by the constraints.

### Option 4 — `concurrency` with `cancel-in-progress`
- Cancels a superseded run. The jobs last about a minute, so almost nothing is saved; on a
  `push` workflow it would cancel the record of a range (`Commits on main`) that is never read
  again. Refused.

### Option 5 — One runner per module (`runs_on` in the manifest)
- Proposed for a project whose single module builds for one operating system only. That
  project's need is met by `NSTACK_RUNS_ON`; a field for a project mixing operating systems,
  which none does, is configuration for a single use (`PRODUCT.md` §6). It would also forbid
  option 1.

---

## Decision

**Option 1.** The `Modules` workflow has one job, `Module checks`, on pull requests and on
`main`. The order of the verbs, the run of `compat` after a failure, the evidence and the
final `clean` are unchanged; they move from YAML into `.nstack/check-modules.sh`, which the
platform tests execute on a throwaway project with two modules, one of them failing.

### Deviation from the convention

None.

---

## Success criterion

*(Convention adopted: criterion not mandatory; one is set because the decision rests on a
measurement.)* Before **2026-12-31**, over twenty pull requests of the third project that
change one module, **the median number of jobs per pull request is five or fewer** across the
four workflows, counted through the forge's API — and **every module failure in those pull
requests is reported by `Module checks`**.

If that is not the case: a count above five means another job is paid for nothing, and is
measured next; a failure that `Module checks` did not report means the script lost a verdict,
and this decision is superseded by the matrix it replaced.

---

## Consequences

**Positive:**

- Two billed jobs fewer per pull request and per push to `main`, for every project, with no
  setting to change.
- D80 is closed: no job is named by an unresolved expression.
- The verdict of the module checks is executed by the oracle, not only by the forge.
- `yq` leaves the workflow; `INSTALL.md` asks a self-hosted runner for `git` alone.

**Negative and accepted debt:**

- Modules run sequentially. A change touches one module (P1), plus the two sides of a contract
  it changes; a project where that sum grows too long is the event that reopens this decision.
- One line on the pull request's page instead of one per module.
- The evidence artefact is one archive with a folder per module.

**Impacts on other modules or contracts:** none. The required check `Module checks` keeps its
name; no ruleset changes.

**Rule to automate:** the platform tests read the workflow — one job, named `Module checks`,
no `yq` — and run `check-modules.sh` on a project with two modules, the first failing its
tests: the second still runs, `compat` runs after the failure, and the job fails.

---

## Rejected alternatives

- **The matrix** (option 2): two jobs per run that judge nothing.
- **No run on `main`** (option 3): the tree two pull requests make together is judged by
  nobody, and a direct push to an unguarded repository by nothing but its record.
- **`concurrency`** (option 4): saves seconds, and can erase a record.
- **A runner per module** (option 5): configuration for a single use; the variable of D105
  already answers the project that asked.
- **Merging the `Governance` jobs as well**: `Fitness functions`, `PR scope and review budget`
  and `Hooks and secrets` are three required names in every ruleset; merging them is a
  breaking change for every project, for about two minutes per pull request.
- **Filtering the description's edits** out of `Pull request`: a job skipped by a condition
  counts as passed for a required check, so a skip would turn a refused sheet green.
