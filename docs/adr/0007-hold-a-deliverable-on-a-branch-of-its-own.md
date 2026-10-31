# ADR-0007 — Hold a deliverable on a branch of its own

- **Status**: Accepted (2026-10-21, by the maintainer, approving #214); built in D137. Clarified while
  building: the verb that gives a hold back is `nstack unclaim` — `release` already makes a
  module's artefacts; a deliverable `in-progress` may be taken too, as K3 accepts it
- **Date**: 2026-10-21
- **Decision makers**: NapkinStack maintainers (`@NapkinStack/maintainers`)
- **Scope**: project — the engine (`nstack claim`, `nstack unclaim`, `plan`, `pr-check`), a
  Copier question, the skeleton's `CONTRIBUTING.md`, handbook, kernel and glossary
- **Reversibility**: easy — the holds are branches under one prefix, deleted in one command;
  a project that never claims sees nothing refused

---

## Context

PDR-0015 decided *what*: a contributor takes a `ready` deliverable in one gesture a second
taker cannot also win, on any forge and with any agent; everyone sees who holds what and since
when; a stale hold is taken over, recorded and told; `pr-check` refuses a pull request for a
deliverable another session holds. This record says *how*.

## Problem

Where a hold lives so that git itself refuses a second one; what counts as work on it; how a
take-over and a release are recorded; how a forge shows it; what `pr-check` compares — with
no service, and no forge required.

## Constraints

- No forge required, any agent (PDR-0013, PDR-0015).
- **A deliverable is delivered by several pull requests**, each on its own branch, and the
  branches are deleted on merge (`nstack settings` sets it): on the third project, D28 was
  delivered by more than ten branches `d28-…`. The hold cannot be a work branch.
- Agents may share one forge identity (ADR-0004): the committer does not tell two agents apart;
  the `Agent-Session` trailer does.
- Nothing is authenticated beyond what the forge already guards: a hold makes a claim traceable,
  not true — as an attested record (ADR-0006).
- No dependency beyond git and what the engine has.

---

## Prior art

| Reference | What it does | What we take |
|---|---|---|
| [git push, non-fast-forward](https://git-scm.com/docs/git-push#_note_about_fast_forwards) | A remote refuses a ref update that does not descend from the ref's current value | **The refusal**: the second of two different claims is rejected by the remote, atomically |
| [git-bug](https://github.com/git-bug/git-bug) | Issues stored as chains of commits under refs of their own, pushed and merged like code | **An event log as commits** on a ref, readable with `git log` |
| [git-appraise](https://github.com/google/git-appraise) | Review data kept in git, no server | **Coordination data travels with the repository** |
| [GitHub Agent HQ](https://github.blog/news-insights/company-news/pick-your-agent-use-claude-and-codex-on-agent-hq/) | An assigned agent opens a draft pull request at once | **The display**: a draft pull request from the first work branch |
| [Linear agents](https://linear.app/developers/agents) | A delegate agent, an accountable person; sessions go `stale` | **Person and session on every hold**; staleness from activity |

---

## Options considered

| Option | For | Against | Chosen? |
|---|---|---|---|
| The work branch is the hold | One branch | A deliverable has many branches, deleted on merge: the hold would vanish after the first | No |
| A git note on the cycle file's commit | Beside the cycle | Notes merge line by line (`cat_sort_uniq`): two claims both survive — nothing refused | No |
| The forge's assignee on an issue | Native display | Forge-bound; two self-assignments both succeed | Display only, later |
| A custom ref (`refs/nstack/…`) | Out of the branch list | Some forges and rulesets refuse or hide refs outside `refs/heads`; invisible to a person | No |
| **A branch per hold, `nstack/hold/<cycle>/<D>`, whose commits are its events** | Every forge accepts and shows it; the remote refuses the second claim; history kept | One branch per held deliverable in the list | **Yes** |

## Decision

1. **The hold.** A branch `nstack/hold/<cycle>/<id>` — `<cycle>` the accepted cycle's file name
   without `.md`, `<id>` the deliverable (`nstack/hold/03-the-window/D30`). Its commits are its
   events, each an empty commit on the previous one; it is never merged.
2. **An event.** Subject `Hold <id>: <event>`; trailers `Hold-Event:` (`claim`, `renew`,
   `take-over`, `release`), `Hold-Person:` (the accountable person — a handle such as `@alice`,
   or `Name <email>`; by default git's user), `Agent-Session:` (the session, when an agent), and for a take-over
   `Hold-Previous:` (the person and session it was taken from), and `Hold-Id:`, random, so two
   runs in one second are two commits. The hold's state is its last event. One person is one
   whether named by a handle or by git: `@alice` is `Alice <alice@example.org>` — said, not
   proven.
3. **`nstack claim <id> [--session S] [--person P]`.** Refuses a deliverable that is not `ready`
   or `in-progress` in the accepted cycle. Fetches the hold's branch: absent or last event
   `release`, it commits a `claim` on it and pushes; held by the same person from a session on the hold, or with no session on either side, it commits a `renew` (clarified for D185: another session of that person is another holder, as D181 reads an agent's independence; it takes the hold with `--take-over` on the person's word, stale or not); held by another, refused — *held by P, session S, since T, last worked on W*. Then it
   creates the first work branch `d<n>-<slug>` from the remote's default branch as it is now, with one empty commit naming the
   deliverable, pushes it, and with a token opens a **draft pull request** whose description
   holds `Deliverable: <id>`; without one, it says the display is skipped.
4. **The race.** Two claims made at once are two different commits on the same parent: the
   remote takes the first and refuses the second (non-fast-forward); the second `claim` then
   fetches and reports the holder. Never `--force`: the engine never forces a hold's branch, the
   kernel tells an agent never to, and where the forge allows it `nstack settings` blocks forced
   pushes and deletion on `nstack/hold/**/*` (G20) — a ruleset's `**` stops at a slash, and a hold
   is two levels down; a forced push is the one way past the refusal.
5. **Work on a hold.** Its last activity is the newest of: its last event, and the tip of any
   remote branch named `d<n>-…` for its id. A hold is **stale** when that is older than the
   project's limit: a Copier answer `hold_days` (7 at init), the decider's, changed by hand as
   `checks` (D134). Between two pull requests, with no branch in flight, the holder renews by
   claiming again.
6. **Take-over and release.** `nstack claim <id> --take-over` commits a `take-over` on the hold
   only when it is stale — otherwise refused, saying when it will be. With a token, a claim that
   makes no new work branch — a take-over, or a claim after a release — comments on the open pull
   requests of this repository's work branches `d<n>-…`, asked branch by branch so that a
   fork's is never one: who holds it now, and from whom. `nstack unclaim <id>` commits a `release`; by
   another than the holder or the charter's decider, refused unless stale; another session of the holder's person is another than the holder (clarified for D185). The previous holder's
   branches are never touched.
7. **`plan`.** After its rules, a *Holds* section for the accepted cycle: each deliverable free,
   held (person, session, since, last worked on) or stale. Read from the remote; unreachable, it
   says *holds not read* — never a failure; no remote, the local holds are read and said local. A hold of a deliverable `accepted` or
   `dropped` is shown ended.
8. **`pr-check`, rule K5.** A pull request naming a deliverable that has a hold matches it when
   one of its commits carries a session of the hold's events, or one of its commits' authors or
   committers, or its opener's account, is the hold's person — by email, or a GitHub account
   by handle or noreply address, never by a display name; otherwise K5 fails, naming the holder. No hold: nothing is asked — claiming is the
   way to be protected, not a new toll (PDR-0015, impacts). Under GitHub Actions the hold's branch
   is fetched by name from the checkout's remote.

- **Expected user value**: two contributors' agents never deliver one deliverable twice; a hold
  nobody works on stops blocking after the project's limit, without the decider.
- **How we will observe it**: PDR-0015's criterion — on a project with two contributors, no
  deliverable delivered by two pull requests; every delivering pull request preceded by its hold.

## Success criterion

On a project with two contributors: two claims of one deliverable at the same second leave one
hold and one refusal naming it; a stale hold is taken over without the decider; no pull request
passes `pr-check` for a deliverable another session holds; the same on a repository with a
bare git remote and no forge.

## Consequences

- Two verbs (`claim`, `unclaim`), a section of `plan`, rule K5, a Copier question
  (`hold_days`); `CONTRIBUTING.md` gains *Working with several contributors* (PDR-0015, point 7);
  the kernel, `05-workflow.md`, `09-platform.md`, the glossary (*hold*) and `RULES.md` follow.
- The forge's branch list shows one `nstack/hold/…` branch per held deliverable. `nstack settings`
  blocks forced pushes and deletion on that prefix and nothing else: a ruleset restricting
  branch creation must allow it, or no one can claim.
- A work branch of a deliverable is named `d<n>-…`, as the third project already does; a branch
  named otherwise is not counted as work on the hold.
- Anyone who may push may write an event: the hold is traceable, not authenticated.

## Rejected alternatives

See *Options considered*. A forge assignee as a second display is left for when a project asks
for it; signing events waits for PDR-0009's signing, the trailers kept stable.
