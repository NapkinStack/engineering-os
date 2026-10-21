# ADR-0008 — Show the plan as milestones and issues, applied by CI

- **Status**: Proposed (2026-10-21)
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
   (ADR-0007), and the forge's objects carrying its marker; computes the display the files call
   for; applies the difference; prints what it made, changed, restored and left. `--dry-run`
   prints without applying. Exit 0 whatever the forge answers: a refusal is said.
2. **Which cycles.** The accepted one, and the closed and stopped ones (their milestones closed):
   the history stays readable. A proposed cycle is not shown — nothing is decided.
3. **A cycle is a milestone.** Title `Cycle <NN> — <goal>`; due on its `end`; description: the
   goal, the one-line progress of D138, and the marker `<!-- nstack:cycle <file stem> -->`. Closed
   when the cycle is closed or stopped.
4. **A deliverable is an issue** in its cycle's milestone. Title `<id> — <title>`; body: the module,
   the acceptance criteria as a checklist, the state, who holds it (ADR-0007), the pull requests
   whose description names it, a line saying the issue is generated from the cycle file and
   edited there, and the marker `<!-- nstack:deliverable <file stem>/<id> -->`. Labels:
   `deliverable` and `state: <state>`, made by the engine with their colours if absent. Assigned to
   the holder when the hold's person is a handle the forge can assign. Closed `completed` when
   accepted, `not_planned` when dropped or deferred; reopened if the file says otherwise.
5. **Finding its own objects.** Milestones and issues are listed (all states, paged) and kept
   only if their body carries the marker; the marker is the identity — never the title. An
   object without the marker is never changed.
6. **A hand edit.** Each object's fields are compared with what the files call for; a difference
   is rewritten and said: *restored D31's title, edited on the forge — the plan is edited in
   docs/project/cycles/03-the-window.md*. A display object whose deliverable left the file is
   closed `not_planned` and said, never deleted.
7. **Where it runs.** A workflow of its own in the skeleton, `Plan on the forge`, on every push to
   the default branch, with `issues: write` and `contents: read` and nothing else, one run at a
   time (a `concurrency` group): the display follows the merged plan only. A person may run
   `nstack board` by hand with a token to see it at once; nobody needs to.
8. **Pull requests named.** Read with the forge's search, one query per run
   (`is:pr "Deliverable:"` in the repository), parsed for `Deliverable: D<n>`; the ten newest per
   deliverable are listed.
9. **Off GitHub, no token, a refusal**: said; exit 0.

- **Expected user value**: the decider follows a cycle from the forge's milestone, at all times,
  with nobody maintaining it, and a hand edit never becomes a second truth.
- **How we will observe it**: PDR-0016's criterion.

## Success criterion

On the third project, after the update that brings it: one milestone per accepted, closed or
stopped cycle, one issue per deliverable, every accepted deliverable's issue closed — made by CI
with no person's gesture; a title edited on the forge restored at the next merge, and said.

## Consequences

- A new verb, a new workflow with the one write right it needs, the project's handbook page.
- Labels `deliverable` and `state: …` appear in the project, made by the engine; G11's list is
  unchanged (they are the display's, not the method's exceptions).
- A display object whose marker a person removes is no longer the display's: the next run makes a
  new one and leaves the old as it is — said in the run's output.
- One search call per run; no other rate-limited API.

## Rejected alternatives

See *Options considered*. Mirroring the plan into a GitHub Project's Roadmap is left for when the
milestone is found not enough (PDR-0016); other forges follow #223.
