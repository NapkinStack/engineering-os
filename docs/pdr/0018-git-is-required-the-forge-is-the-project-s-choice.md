# PDR-0018 — Git is required; the forge is the project's choice

- **Status**: Proposed (2026-10-21). Asked by the maintainer: *how tied is nstack to GitHub — a
  prerequisite? is a git repository mandatory?*, then *analyse the market and the solutions, to
  decide in an expert and clean way* (#223)
- **Date**: 2026-10-21
- **Decision makers**: NapkinStack maintainers (`@NapkinStack/maintainers`)
- **Modules affected**: the engine (`init`, `doctor`, `settings`, the forge displays), the Copier
  questions, the skeleton's CI and handbook

> The PDR describes **what the product must do and why**, never its implementation.
> The how belongs to an ADR.

---

## User problem

A team whose code is not on GitHub — GitLab, Forgejo or Gitea, a bare server. nstack's truth is in
git: attested checks in notes (ADR-0006), holds as branches (ADR-0007), the plan in files; the
forge is called an operator (PDR-0013). The product still assumes GitHub:

- `nstack init` requires `github_repo` (`organisation/name`): a project elsewhere answers a
  question that does not apply to it.
- The skeleton's CI is GitHub Actions only; a project elsewhere has no CI but `nstack attest`, and
  is not told so.
- `nstack doctor` (G1–G20) and `nstack settings` read GitHub's settings only; elsewhere nothing
  says which protections are not verified.
- The displays — an attested record's status, a hold's draft pull request, the plan's milestones
  (ADR-0008) — are GitHub's.

What already works with any git remote: init, update, the fitness functions, pr-scope, pr-check
(`--body-file`), attest, claim, plan — a bare remote is in the platform's tests.

## Goal

A team on any forge, or on none, creates and runs a project without an answer that does not apply,
is told plainly what nstack verifies for it and what it cannot, and has its checks judged — with
GitHub kept as the default and its support unchanged.

## Out of scope

- **A layer over every forge's API.** Adapters are narrow, built when a project needs one.
- **GitLab CI, Forgejo protections, other displays — in this step.** Each comes with the first
  project that asks for it; until then, said.
- **Dropping git.** The method's records are git objects.

---

## Prior art

| Product / reference | Solution chosen | What we keep from it |
|---|---|---|
| [Renovate platforms](https://docs.renovatebot.com/modules/platform/) | One `platform` setting — github, gitlab, forgejo, gitea, bitbucket, azure — each a narrow adapter | **The forge named once; adapters narrow** |
| [git-forge](https://github.com/Leleat/git-forge) | One CLI over every forge's issues and pull requests, their common features only — archived 2026-08 | **Not a lowest-common-denominator layer** |
| [Forgejo Actions](https://forgejo.org/docs/v17.0/user/actions/github-actions/) | Familiar to GitHub Actions, "not designed to be compatible"; most workflows run with small changes | **GitHub's workflows reused there — tested, not assumed** |
| [GitLab protected branches](https://docs.gitlab.com/ee/user/project/repository/branches/protected/) | Protections through an API; approvals and code owners on paid tiers | **A second protections adapter is possible, later** |
| git-bug, git-appraise | Coordination data in git, no forge | **The core stays forge-free** — nstack's line already |

**The convention the user already knows:** a tool that asks once which platform hosts the code.

---

## Options considered

| Option | What the user experiences | Cost | Chosen? |
|---|---|---|---|
| Do nothing | Off GitHub: a GitHub question, no CI, silence on protections | 0 | No |
| A. Every forge first-class now — CI, protections, displays | Complete, for forges nobody uses yet | High, and maintained blind | No |
| **B. The forge named once; honest everywhere; checks attested by default off GitHub; adapters when a project needs one** | The right question at init; what is and is not verified said; judged checks from day one | Low now | **Yes** |

## Decision

**Option B.**

1. **The forge is named once**: an answer `forge` — `github` (the default), `gitlab`, `forgejo`,
   `gitea`, `other`, `none` — asked at init. The repository's `organisation/name` is asked only
   where a forge has one; `github_repo` stays GitHub's answer, unchanged for the projects that
   have it.
2. **Off GitHub, the checks are attested by default**: the answer `checks` starts `attested` —
   `nstack attest` runs the CI's checks where the team works (PDR-0013) — and the GitHub
   workflows are not written into a project that cannot run them.
3. **Honest everywhere**: `nstack doctor` says, off GitHub, that the forge's protections are not
   verified — and what they would be, as the checklist names them — instead of reading GitHub;
   `nstack settings` says it has nothing to apply there; the displays say "not shown". A
   project's state is never called guarded when nothing was read.
4. **Adapters when asked**: GitLab CI generated from the one list of checks the engine already
   holds, Forgejo and Gitea reusing the GitHub workflows once tested on a real runner, protections
   and displays per forge — each in a workstream of its own, when a project names it.
5. **Nothing changes on GitHub**: a project with `github_repo` keeps every check, display and
   setting it has; its update writes `forge: github`.

---

## Expected behaviour

**Nominal journey.** `nstack init` on a team that hosts on GitLab: *forge? gitlab*, the repository's
path asked as GitLab's; the project is created with `checks: attested` and no `.github/`; `nstack
doctor` says *forge gitlab: its protections are not read by this version — what they should be:
…*; `nstack attest` records the checks; `nstack claim` holds a deliverable on the GitLab remote.

**Edge cases and degraded states.** A project with no remote (`none`): every command that would
reach a forge says it has none. A project on GitHub updating: `forge: github` added, nothing else
changes. A project that changes forge: its `forge` answer changed by hand in a pull request, as
`checks` is (D134).

**Business rules.** The answer `forge` is the decider's; GitHub stays the default.

**Permissions.** No forge credential is ever asked to know the forge.

**Acceptance criteria** *(testable)*:

- [ ] Given `nstack init` with `forge: gitlab`, then no GitHub question is asked, no `.github/`
      workflow is written, and `checks` is `attested`.
- [ ] Given a project with `forge` other than `github`, then `nstack doctor` reports the forge's
      protections as not verified, naming what they should be, and never as guarded.
- [ ] Given such a project, then `nstack settings` and the displays say there is nothing they can
      apply or show, and exit 0.
- [ ] Given a project on GitHub updating, then `forge: github` is written and every GitHub check,
      display and setting behaves as before.
- [ ] Given `forge: none`, then `nstack attest`, `nstack claim` and `nstack plan` work on the local
      repository and say they reach no forge.

---

## Success criterion

> We will consider this was the right call if **a project created on GitLab or Forgejo runs its
> first cycle with nstack — its checks attested, its deliverables held — and its decider never
> answers a GitHub question** is observed before **2027-06-30**.

How it is observed: the first project off GitHub; its answers file; its attested records.

If the criterion is not met: ask that project what stopped it; build the adapter it names.

---

## Removal condition

> This feature will be removed if **no project off GitHub has been created with nstack by
> 2027-12-31** — the `forge` question then costs every user a step for nobody.

---

## Impacts

- **Existing users**: on GitHub, nothing changes; an update writes `forge: github`.
- **Modules and contracts**: none.
- **Support and documentation**: `INSTALL.md` (choosing the forge), `07-governance.md` (what is
  verified where), the glossary (*forge*).
- **Data**: none collected.
- **The how** — the Copier questions and their conditions, `doctor`'s wording off GitHub, which
  skeleton files depend on the forge — goes to an ADR.
