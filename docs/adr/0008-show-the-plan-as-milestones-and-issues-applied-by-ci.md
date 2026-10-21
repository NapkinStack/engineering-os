# ADR-0008 — Show the plan as milestones and issues, applied by CI

- **Status**: Accepted (2026-10-21), after an independent review (#227) that reshaped §3–§10:
  the pull requests listed rather than searched, milestones keyed on the cycle's number and their
  title collisions said, deliverables keyed on their identifier, the holds read with the job's
  token and the run triggered by a claim, fields compared after normalising, writes paced
- **Date**: 2026-10-21
- **Decision makers**: NapkinStack maintainers (`@NapkinStack/maintainers`)
- **Scope**: project — the engine (a new verb), a workflow of the skeleton, the project's
  handbook page
- **Reversibility**: easy — the display is labelled issues and milestones the engine made; the
  workflow removed, they stay as a last picture, closed or deleted in one pass

---

## Context

PDR-0016 decided *what*: every cycle the decider accepted, and its deliverables, shown on the
forge — progress, end date, holder, pull requests — one way, applied by the project's CI on every
merge to the default branch; a display edited by hand overwritten and said; an issue it did not
make never touched; failures said, never a failed merge. This record says *how*.

## Problem

Which forge objects carry the plan; how the engine tells its own objects from everyone else's
without a store of its own; where the run happens and with what right; how a hand edit is found
and undone; what the run costs on a project with many pull requests.

## Constraints

- **The repository is the single source of truth** (the maintainer's rule, 2026-10-21): nothing
  read from the forge decides anything but whether the display must be rewritten.
- **No manual intervention**: no label, milestone or project made by a person; no setting to
  change for it to run.
- The workflow token is read-only by default (G10): a right the display needs is asked by its
  own job, and only it.
- A private repository on a free plan has milestones and issues: the display works there.
- No dependency beyond the engine's standard library.

---

## Prior art

| Reference | What it does | What we take |
|---|---|---|
| [GitHub milestones](https://docs.github.com/en/rest/issues/milestones) | Title, description, due date, state; the forge counts open and closed issues | **The cycle**: due on its end date, the bar for free |
| [GitHub issues](https://docs.github.com/en/rest/issues/issues) and labels | Title, body, labels, assignees, milestone, state with a reason (`completed`, `not_planned`) | **The deliverable**, closed as completed or not planned |
| [Terraform's GitHub provider](https://registry.terraform.io/providers/integrations/github/latest/docs/resources/repository_milestone) | Declared state applied to the forge; drift found and corrected at the next apply | **Plan, compare, apply; drift said** |
| [Release Please](https://github.com/googleapis/release-please), [Renovate's dependency dashboard](https://docs.renovatebot.com/key-concepts/dashboard/) | An issue or pull request a bot owns, found again by a marker in its body, rewritten at every run | **A marker in the body** to find one's own objects, no store |
| nstack's own displays (ADR-0006, ADR-0007) | A record or a hold shown one way; refusals said | **Same contract** |

---

## Options considered

| Option | For | Against | Chosen? |
|---|---|---|---|
| A store of issue numbers committed in the repository | Exact | The display writes into the truth: a commit per run, conflicts | No |
| Find own objects by title | Simple | A title edited by hand loses the object; a person's issue with the same title is taken | No |
| **A marker in the body (an HTML comment), and a label** | Invisible to a reader, survives a title edit, a person's issue never carries it | A marker deleted by hand makes the object a stranger: a new one is made, the old left | **Yes** |
| A GitHub Project as the board | A timeline | An organisation permission, a project made by hand; PDR-0016 leaves it for later | No, later |
| The display in the pull request workflows | Faster | A pull request's token must not write to the plan of a change not merged | No: on the default branch only |

## Decision

1. **The verb, `nstack board`.** Reads the cycle files (`docs/project/cycles/`), the holds
   (ADR-0007), the pull requests, and the forge's objects; computes the display the files call
   for; applies the difference; prints what it made, changed, restored, left and could not show.
   `--dry-run` prints without applying.
2. **Which cycles.** The accepted one, and the closed and stopped ones (their milestones closed):
   the history stays readable. A proposed cycle is not shown — nothing is decided.
3. **A cycle is a milestone**, keyed on its number `NN` (the file's leading digits), so that a
   renamed slug keeps its milestone. Title: the cycle file's own heading, `Cycle NN — <title>`
   (`# Cycle 03 — the window`), short enough for a phone's list; description: the goal, the
   one-line progress of D138 — the figure that counts, whatever else a person puts in the
   milestone — and the marker `<!-- nstack:cycle NN -->`. Due on `end`, sent as
   `<end>T00:00:00Z` and compared on its date alone: the forge shows *due by* the first day the
   cycle is over, deliberately the cycle form's own date. Closed when the cycle is closed or
   stopped. Two cycle files with the same `NN` are not shown, and said.
4. **A deliverable is an issue** in its cycle's milestone, keyed on its identifier `D<n>` alone —
   the identifier a pull request names (`Deliverable: D<n>`), so that a deliverable moved to
   another cycle keeps its issue and changes milestone. Title `<id> — <title>`; body: the module,
   the acceptance criteria as a checklist, the state, who holds it, the pull requests that name
   it, a line saying the issue is generated from the cycle file and edited there, and the marker
   `<!-- nstack:deliverable D<n> -->`. Labels `deliverable` and `state: <state>`: made by the engine
   if absent; a label of that name that already exists is a person's, used as it is, never
   recoloured. Assigned to the holder when the hold's person is a GitHub handle or noreply
   address the repository can assign (`GET /assignees/{login}`); the full list is sent, so an
   assignee added by hand is put back. Closed `completed` when accepted, `not_planned` when
   dropped or deferred, and every deliverable not accepted when its cycle is closed or stopped;
   reopened with `state_reason: reopened` if the file says otherwise; `state_reason` is compared
   too. An identifier used twice across the cycle files is not shown, and said.
5. **Finding its own objects.** Milestones and issues are listed (all states, paged) and kept
   only if their body carries the marker; the marker is the identity — never the title. An
   object without the marker is never changed. Where a person's milestone already holds the title
   a cycle needs — GitHub refuses two — the cycle is not shown and the run says which milestone
   stands in the way.
6. **A hand edit.** Fields are compared after normalising — line endings and trailing space in
   bodies, labels and assignees as sets, a due date on its date — so that nothing is reported that
   did not change; a difference is rewritten and said: *restored D31's title, edited on the forge
   — the plan is edited in docs/project/cycles/03-the-window.md*. A display issue whose
   deliverable left every shown cycle is closed `not_planned` and said, never deleted. A
   milestone's items the display did not make are counted and said (*2 items in Cycle 03 not from
   the plan*): GitHub's bar counts them, the description's line does not.
7. **Where and when it runs.** A workflow of its own in the skeleton, `Plan on the forge`:
   - on every push to the default branch — the plan changed — and to `nstack/hold/**` — a holder
     changed (ADR-0007) — and by hand (`workflow_dispatch`); it always reads the default branch's
     tip, whatever pushed, so a re-run never applies an older plan;
   - `permissions: {}` at the workflow, and at its one job `issues: write`, `pull-requests: read`,
     `contents: read` — nothing else; one run at a time (a fixed `concurrency` group, the latest
     waiting run kept);
   - the holds are fetched with the job's token for that one command (an extra header), the
     checkout keeping `persist-credentials: false`. Holds that cannot be read leave the assignees
     as they are, and the run says *holders not shown*.
8. **Pull requests named.** Listed newest first (`/pulls?state=all`, paged), until one is older
   than the earliest start of a shown cycle; each description read with the same rule K3 reads,
   `Deliverable: D<n>`. The ten newest per deliverable are shown. No search API: its 1,000-result
   cap and its free-text matching do not fit.
9. **Gently.** Writes are made one after another, a second apart; a secondary rate limit
   (403 or 429 with `retry-after`) stops the run with *partially shown, the rest at the next run*.
   A first run on a project with thirty deliverables makes about sixty writes — and its watchers
   get a notification for each new issue, said in the handbook.
10. **Said, never failed.** No GitHub remote, no token, issues disabled (410), a refusal: the run
    says what was not shown — in its output, in the job's summary and as a warning annotation —
    and exits 0. An unexpected answer is caught as a refusal, never a traceback.
11. **By hand.** A person may run `nstack board` with a token that may write issues; nobody needs
    to. The marker, not the creator, is the identity, so a hand run and CI agree.

- **Expected user value**: the decider follows a cycle from the forge's milestone, with nobody
  maintaining it, and a hand edit never becomes a second truth.
- **How we will observe it**: PDR-0016's criterion.

## Success criterion

On the third project, after the update that brings it: one milestone per accepted, closed or
stopped cycle, one issue per deliverable, every accepted deliverable's issue closed — made by CI
with no person's gesture; a title edited on the forge restored at the next merge, and said.

## Consequences

- A new verb, a new workflow with the one write right it needs, the project's handbook page.
- On a private repository, Actions minutes: one short job per merge and per claim.
- Labels `deliverable` and `state: …` appear in the project, made by the engine; G11's list is
  unchanged (they are the display's, not the method's exceptions).
- A display object whose marker a person removes is no longer the display's: for an issue, the
  next run makes a new one and leaves the old — said; for a milestone, its title stands in the
  way, and the run says so until the marker is put back or the milestone renamed.
- A handful of listing calls per run, within the job token's rate; writes are paced.

## Rejected alternatives

See *Options considered*. Mirroring the plan into a GitHub Project's Roadmap is left for when the
milestone is found not enough (PDR-0016); other forges follow #223.
