# PDR-0013 — Checks run where the team works; the forge is an operator

- **Status**: Proposed (2026-10-20). The maintainer decided its direction — *"a user can do
  their development in-house; GitHub is an operator"* — and accepted its five points as framed
  (*"c'est ok"*); one is refined here, the record kept in git rather than on the forge alone.
  Accepted by approving the pull request that brings it
- **Date**: 2026-10-20
- **Decision makers**: NapkinStack maintainers (`@NapkinStack/maintainers`)
- **Modules affected**: `nstack` (a command that runs and records the checks, `pr-check`), the
  skeleton's kernel (§7, *Done*), `07-governance.md`, the install guide

> The PDR describes **what the product must do and why**, never its implementation.
> The how belongs to an ADR.

---

## User problem

A project's decider wants every change judged by the framework's checks before it merges. The
framework says how: the forge's CI runs them, and their verdicts gate the merge. When the forge
cannot run them — its runner is down or slow, its hosted minutes are spent, or the team works
off it — the project is left with nothing between "wait" and "merge on faith".

Observed on 2026-10-20 (#189): the third project's runner left runs queued for an hour; eight
pull requests merged on checks the agent ran on the workstation and pasted as a comment. The
comment named a head by hand, nothing tied it to the commit that merged, nothing read it, and
once it covered heads it had not run on ("the other modules are unchanged since …"). The
forge's verdicts arrived an hour after the merges, read by nobody. Every project in that state
rebuilds the same convention, unchecked.

The framework assumed the forge is where checks run. It is one place they can run.

## Goal

A team whose forge cannot run the checks runs them where it works, and the change carries a
record of that run — bound to its commit, travelling with the repository — that the framework
reads as it reads the forge's checks, when the decider said it may.

## Out of scope

- **Proving the run was honest.** A record made on a workstation is made by whoever runs it; it
  makes a false claim traceable — who, which commit, which output — not impossible. The forge's
  CI is not proof either; it is a machine the team does not control.
- **Replacing the forge's CI** where it runs. Where it runs, it stays the judge.
- **Satisfying a forge's required checks.** The record never takes their names (below).
- **Signing.** PDR-0009 keeps its record signable later; this one does too, and signs nothing now.
- **A service, a runner of our own, a dashboard.**

---

## Prior art

> **Mandatory section.** Minimum two named references.
> (`skeleton/.nstack/handbook/06-decisions.md` §2)

| Product / reference | Solution chosen | What we keep from it |
|---|---|---|
| [Arcanist (Phabricator, now Phorge)](https://we.phorge.it/book/phorge/article/arcanist_lint_unit/) | `arc diff` runs lint and unit tests on the developer's machine and attaches their results to the revision, shown to the reviewer | **That a local run is evidence when it is attached to what is reviewed** |
| [git-appraise](https://github.com/google/git-appraise) | Code review — requests, comments, CI results (`refs/notes/devtools/ci`) — stored in git notes, so it travels with the repository and needs no particular forge | **The record lives in git, bound to the commit**: the forge is an operator, not the store |
| [GitHub commit statuses](https://docs.github.com/en/rest/commits/statuses) | Any system — Jenkins, Buildkite — posts a state and a context name on a commit; a ruleset may require a context | **Where people look on GitHub**, and the trap: a status named like a required check satisfies it |
| [Gerrit `Verified` label](https://gerrit-review.googlesource.com/Documentation/config-labels.html) | A vote on the change, by CI or by a person, that a submit rule requires | **That who may vote is the project's rule**, written in its configuration |
| [Dagger](https://docs.dagger.io/) | The same pipeline runs on a laptop and in CI | **One list of checks**, never a local copy that drifts from CI's |

**The convention the user already knows:** a CI result on the commit — green or red, with its
log behind it.

**Why depart from it:** only where it cannot run. The record looks like a CI result where the
forge shows one, and says where it ran.

---

## Options considered

| Option | What the user experiences | Cost | Chosen? |
|---|---|---|---|
| Do nothing | Each project pastes outputs by hand; nothing ties them to a commit | 0 | No: #189 |
| A. A section of the pull request body | Text the author edits; it can name any commit | Low | No: a body is not bound to a commit |
| B. A status on the forge, named like the CI's checks | Required checks turn green without CI | Low | **No: it would make the forge's barrier a formality** |
| **C. A record bound to the commit, kept in git, shown on the forge under its own name, standing in for CI only where the decider said so** | One command; the commit carries what ran, where, by whom, and its output | Medium | **Yes** |

## Decision

**Option C**, in five points.

1. **One command runs exactly what CI runs**, from the same list — the fitness functions, the
   scope and budget, the hooks and secrets, each changed module's checks, the pull request's own
   rules. On a clean tree at the head commit: a tree with uncommitted changes is refused, since its
   result would describe no commit.
2. **The record is bound to that commit and kept in git**, so it travels with the repository
   whatever forge holds it — or none. It names the commit, each check and its verdict, the
   workstation's identity as git and the engine know it, the session (`Agent-Session`) when an
   agent ran it, the engine's version and whether it is published (PDR-0005), and the output. A
   new commit has no record until the command runs on it.
3. **On a forge, it is shown under a name of its own** — *nstack / local checks*, never a CI
   check's name. It cannot satisfy a required check by resemblance; a decider who wants it to
   gate a protected branch makes that name required themselves, at the forge — their gesture,
   never the framework's or the agent's.
4. **The decider says, in the repository, whether recorded local checks stand in for CI** in
   this project — a line in a file the decider owns, reviewed like any change. Until they do, a
   record is information: `pr-check` shows it and requires the forge's checks as before. Once they
   do, `pr-check` accepts a record of the head in their place, and says it did.
5. **Its words are its own.** A change whose checks ran on the forge is *checked*; one whose
   checks ran and were recorded on a workstation is *attested*. The record, the summary of
   PDR-0009 and every message say which — as *guarded / unguarded* (PDR-0006) and
   *framed / unframed* (PDR-0007) are never left to silence.

---

## Expected behaviour

**Nominal journey.** The runner is down. The agent finishes a change, commits, and runs the
command: every check runs as CI would; the record is written for the head and pushed with it;
the forge shows *nstack / local checks — attested, 5 of 5*. The project's file says recorded
checks stand in; `pr-check` reads the record of the head and passes, saying *attested on a
workstation*. The merge proceeds on the project's usual rule.

**Not opted in.** Same run: the record is shown, `pr-check` still asks for the forge's checks,
and says a record exists for the head.

**Edge cases.** A push after the run: the new head has no record, and `pr-check` says so. A
check that failed: the record says failed, and stands in for nothing. A dirty tree: refused,
nothing written. No forge token: the record is written in git; the forge's display is skipped
and said. A record naming a check CI does not run, or missing one CI runs: refused as
incomplete.

**Business rules.**

- A record names one commit and is never moved to another.
- The list of checks is CI's own; there is no second list to keep in step.
- *Attested* is never written *checked*, anywhere.
- The decider's line, not the agent, decides whether a record stands in.

**Acceptance criteria** *(testable)*:

- [ ] Given a clean tree at a head, when the command runs, then each of CI's checks runs, and a
      record naming that commit, each verdict and its output is kept in git.
- [ ] Given uncommitted changes, when the command runs, then it refuses and writes nothing.
- [ ] Given a record of a commit, when a new commit is pushed, then `pr-check` finds no record
      for the new head.
- [ ] Given a project that did not opt in, when a record of the head exists, then `pr-check`
      shows it and still requires the forge's checks.
- [ ] Given a project whose decider opted in, when every check of the record passed, then
      `pr-check` accepts it and says *attested*.
- [ ] Given a forge, when the record is shown there, then its name is not a CI check's name.
- [ ] Given a record missing a check CI runs, then `pr-check` refuses it as incomplete.

---

## Success criterion

By 2027-03-31: on the third project, twenty consecutive pull requests merged while its runner
was down carry a record of their merged head, with no checks pasted by hand; and one project
judged with no forge CI at all — its checks attested only — passes `pr-check` on the same
rules as a checked one.

## Removal condition

If the forge's CI becomes always available to every project that uses the framework — no
quota, no runner to keep — the command stays as a convenience and the opt-in falls into disuse;
it is removed when no project has used it for two minor versions.

## Impacts

- **The kernel** (§7, *Done*): "local checks green" gains its evidence — a record of the head.
- **`07-governance.md`**: a section beside *when the forge cannot enforce any of it* — *when the
  forge cannot run the checks*.
- **PDR-0009**: its record of a change says, for each verdict, whether it was checked or
  attested.
- **Projects**: nothing changes until a decider opts in; a project that never does sees one new
  command and its record shown, nothing refused.
- **The how** — the git notes' ref and format, the command's name, the decider's file, the forge
  display — is an ADR's, before the first pull request that builds it.
