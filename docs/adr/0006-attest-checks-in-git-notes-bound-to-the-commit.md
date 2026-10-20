# ADR-0006 — Attest checks in git notes, bound to the commit

- **Status**: Accepted (2026-10-20, by the maintainer, approving #196); built in D129
- **Date**: 2026-10-20
- **Decision makers**: NapkinStack maintainers (`@NapkinStack/maintainers`)
- **Scope**: project — the engine (`nstack attest`, `pr-check`, `doctor`), the Copier
  questions, the skeleton's governance handbook
- **Reversibility**: easy — the record is a git ref of its own, deleted in one command; the
  opt-in defaults to the forge, and a project that never sets it sees nothing refused

---

## Context

PDR-0013 decided *what*: when the forge cannot run the checks, the team runs them where it
works; the run is recorded, bound to its commit, kept in git and shown on a forge under a name
of its own; it stands in for CI only where the decider says so, and is called *attested*. This
record says *how*.

## Problem

Where the record lives, how it reaches others, which checks it runs, where the decider's word is
written, and what `pr-check` does with it — without a second list of checks to keep in step with
the workflows, and without a forge being required.

## Constraints

- No forge required: the record travels with the repository (PDR-0013, point 2).
- No second list of checks: what the command runs is what the workflows run (point 1).
- A record names one commit and is never moved (business rule).
- Nothing changes for a project that does not opt in (impacts).
- No new dependency beyond git and what the engine has.

---

## Prior art

| Reference | What it does | What we take |
|---|---|---|
| [git notes](https://git-scm.com/docs/git-notes) | Data attached to a commit without changing it, under a ref of one's own (`refs/notes/<name>`), pushed and fetched like any ref; merge strategies, among them `cat_sort_uniq` for line-based notes | **The store**: bound to the commit, no forge, and concurrent writers merged line by line |
| [git-appraise](https://github.com/google/git-appraise) | CI results kept as one JSON line per run in `refs/notes/devtools/ci`, merged with `cat_sort_uniq` | **The format**: JSON lines, one per run, the latest one read |
| [Copier answers file](https://copier.readthedocs.io/en/stable/configuring/) | The project's answers to the template's questions, kept and reused by every update | **Where a project's choice lives**: beside `project_name` and `github_repo` |
| [GitHub commit statuses](https://docs.github.com/en/rest/commits/statuses) | A state and a context on a commit, shown where people look | **The display**, under its own context |

---

## Options considered

| Option | For | Against | Chosen? |
|---|---|---|---|
| A record committed as a file | Plain to read | Changes the commit it describes: never bound to it | No |
| A commit status only | Shown at once | Forge-only; lost with the forge; anyone with the right sets any state | Display only |
| **git notes, JSON lines, `refs/notes/nstack/checks`** | Bound to the commit, travels with the repository, line-merged | Not fetched by default; GitHub no longer shows notes | **Yes**, with the status as display |
| The decider's word in the charter | Already the decider's file | A charter changes only by PDR, and an unframed project has none | No |
| **The decider's word as a Copier answer, `checks`** | Every project has the file; updates keep it; reviewed in a pull request | One more question at `init` | **Yes** |

## Decision

1. **The list.** The engine holds one list of the checks — each with the name of its CI job
   (`Fitness functions`, `PR scope and review budget`, `Hooks and secrets`, `Test sheet and cycle`,
   `Module checks`) and the commands that job runs. A test binds it to the skeleton's workflows: a
   job or a command in one and not the other fails it, as D105's test binds the runners.
2. **The command, `nstack attest`.** At the root, on a clean tree — any uncommitted or untracked
   change refused, nothing written. It runs each check of the list in order, all of them even after
   a failure, and exits non-zero when one failed.
3. **The record.** One JSON line per run, appended to the note of `HEAD` under
   `refs/notes/nstack/checks`: `record: attested-checks/v1`, the commit, the time, the engine's
   version and whether it is published, who ran it as git names them, the `Agent-Session` of the
   head's commit when there is one, and per check its name, commands, exit codes and output —
   each output capped at 64 KiB, head and tail kept and the cut said, with the SHA-256 of the
   whole. The latest line for a commit is its record.
4. **Its travel.** `nstack attest` pushes the notes ref to the branch's remote when there is one,
   fetching and merging it first with `cat_sort_uniq`; no remote, it says the record is local.
   `pr-check` fetches the ref before reading it.
5. **Its display.** With a token that may write statuses, a commit status on the head: context
   `nstack / local checks`, state from the run, description `attested: n of n`. Without one, the
   display is skipped and said. The context is never a CI job's name.
6. **The decider's word.** A Copier question, `checks`: `forge` (default) or `attested`. Changed
   in a pull request, as the project's other answers. `doctor` names the state.
7. **`pr-check`.** `checks: forge` — a record of the head is shown, nothing else changes.
   `checks: attested` — a record of the head is required: every check of the list present and
   passed; missing, older than the head, incomplete or failed, `pr-check` fails with a rule of its
   own and says which. Its summary says *attested on a workstation, by …, at …*.

- **Expected user value**: a project whose forge cannot run the checks merges on evidence bound
  to the merged commit, with no hand-pasted output; a project off GitHub is judged the same way.
- **How we will observe it**: PDR-0013's criterion — twenty consecutive pull requests of the
  third project merged on records of their heads.

## Success criterion

The third project's next twenty pull requests merged while its runner is down each have a
record of their merged head in `refs/notes/nstack/checks`, and none carries checks pasted by
hand; one run of `nstack attest` on a repository with no remote writes and reads its record.

## Consequences

- A new command, a new rule of `pr-check`, a new Copier question, a section of
  `07-governance.md` (*when the forge cannot run the checks*), the kernel's *Done* naming the
  record.
- The notes ref is unprotected by the forge's branch rules: whoever may push may write a note.
  The record makes a claim traceable; it does not make it true (PDR-0013, out of scope).
- CI's own checkout does not fetch notes: CI never reads a record — where CI runs, it judges.

## Rejected alternatives

See *Options considered*. A record signed with the workstation's key is left to PDR-0009's
later signing, the shape kept compatible: one JSON object per run, stable field names.
