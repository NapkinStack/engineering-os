# ADR-0006 — Attest checks in git notes, bound to the commit

- **Status**: Accepted (2026-10-20, by the maintainer, approving #196); built in D129.
  **Clarified 2026-10-26 (D166, #275)**: a passed module check is kept for the same commit, base
  and engine — decisions 2 and 3. **Clarified 2026-10-27 (D173, #295)**: an output over the cap
  is cut log group by log group, so that each module keeps its own results — decision 3.
  **Amended 2026-11-17 (D223, #406)**: a passed module check is kept while what it reads is
  unchanged — the digest of its inputs, not the commit and base — for seven days and twenty
  commits of the default branch at most; an automated sheet row stands on the same digest —
  decisions 2, 3 and 7
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
   a failure, and exits non-zero when one failed. *Clarified (D166)*: `Module checks` reads the tree
   and the base, never the description; when the commit's record passed it with the same base commit,
   the same engine — published, or named by a commit with no change of its own, tracked or not — and
   the same person, it is kept with that run's evidence, not run again, so a sheet filled after a
   first attest costs no second end-to-end run. Ignored files, the environment and the tools outside
   the tree are not compared. `--again` runs it.
   *Amended (D223, #406)*: the key is what the check reads, no longer the commit and the base. A
   pull request that merges the default branch in, for another module's change, moved both, and
   every end-to-end run of the change was paid again for nothing it reads; on a project of four
   authors that was the bottleneck. The **inputs** of `Module checks` at a commit are, as git's tree
   ids, never hashed by hand:
   - the folder of each module the check ran — the changed ones and, for a changed contract, its
     provider and its consumers, as the check selects them;
   - the folder of each module those consume from (`consumes[].module`): what their tests and
     end-to-end runs start or call. A module reaching another one's internals is already refused
     (`02-modules.md` §8): the declared graph is meant to be the whole of it;
   - the project's shared files — every tracked path outside the module folders: lockfiles,
     workspace manifests, scripts, `.nstack/`, workflows — and the `contracts/` and `platform/`
     modules, which every module reads: a contract version or a shared mechanism that moves
     re-runs every check (an independent verifier's finding, before the code merged);
   - the engine and the person, as before.

   Their digest, SHA-256 over those ids in a fixed order, is kept in the record. The check is kept
   when the digest at the new head equals the one a passed run recorded — whatever the commit — and
   the run is **fresh**: made at most seven days ago, and the default branch has moved by at most
   twenty commits between that run's base and this one's. Past either bound it runs again in full,
   so an input nobody declared costs at most that long. A digest that cannot be computed — a module
   folder unreadable, a `consumes` naming no module of the project — is no key: the check runs.
   Where the forge also runs `Module checks` on the default branch after each merge (the
   skeleton's `module-checks.yml` does, on push), an undeclared input is caught there within the
   day; that run is what the bound leans on, never what replaces it.
3. **The record.** One JSON line per run, appended to the note of `HEAD` under
   `refs/notes/nstack/checks`: `record: attested-checks/v1`, the commit, the time, the engine's
   version, its origin when unpublished, and whether it is published, the base and its commit, who ran it as git names them, the `Agent-Session` of the
   head's commit when there is one, and per check its name, commands, exit codes and output —
   each output capped at 64 KiB, head and tail kept and the cut said, with the SHA-256 of the
   whole. *Clarified (D173)*: an output with log groups — `Module checks` prints one per module —
   is cut within each group, a quarter from its head and the rest from its tail, the room a small
   group leaves going to the others; one cut across the whole hid the middle module's results. A check kept from an earlier run carries `kept_from`, that run's time. The latest line for
   a commit is its record. *Amended (D223)*: `Module checks` carries `inputs`, the digest of
   decision 2, and a kept one also `kept_commit`, the commit its run was made on.
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
   *Amended (D223)*: where checks are attested, T4 asks an automated sheet row run on another commit than the head to be
   run again. It stands, as a row whose commit has the head's tree already does (D93), when a
   record of that commit and the head's record hold the same `inputs` digest and the row's run
   is fresh as above. A row explored by hand is unchanged: a person's exploration follows the
   commit and is confirmed at the head (D71, D214); a module at criticality `critical` re-runs at
   the head whatever the digest.

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
