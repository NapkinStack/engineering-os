# PDR-0018 — Git is required; the forge is the project's choice

- **Status**: Proposed (2026-10-21). Asked by the maintainer: *how tied is nstack to GitHub — a
  prerequisite? is a git repository mandatory?*, then *analyse the market and the solutions, to
  decide in an expert and clean way* (#223). Reshaped by an independent review (#236) before its
  acceptance
- **Date**: 2026-10-21
- **Decision makers**: NapkinStack maintainers (`@NapkinStack/maintainers`)
- **Modules affected**: the engine (`init`, `update`, `doctor`, `settings`, `pr-check`, `landed`,
  `new-module`, the forge displays), the Copier questions, the skeleton's CI, ownership file, pull
  request form and handbook, the module templates

> The PDR describes **what the product must do and why**, never its implementation.
> The how belongs to an ADR.

---

## User problem

A team whose code is not on GitHub — GitLab, Forgejo or Gitea, a bare server. nstack's truth is in
git: attested checks in notes (ADR-0006), holds as branches (ADR-0007), the plan in files; the
forge is called an operator (PDR-0013). The product still assumes GitHub as its **host**:

- `nstack init` requires `github_repo` (`organisation/name`) and asks `owner_team` in GitHub's
  terms; its next steps say *create the GitHub repository* and list GitHub's settings.
- The skeleton's CI is GitHub Actions only, and so are Dependabot and the issue forms; a project
  elsewhere has no CI but `nstack attest`, and is not told so.
- The method's own files sit where only GitHub reads them: the ownership file
  (`.github/CODEOWNERS`, which `new-module`, L6 and the code owner review rely on) and the pull
  request's form (where the test sheet lives).
- Generated links point to GitHub: the issue forms' discussions, a contracts module's `contact`.
- Two checks of the method quietly stop off GitHub:
  - the record of commits reaching `main` outside a pull request (PDR-0006) runs only as a GitHub
    workflow reading GitHub's API — elsewhere it never runs, and nothing says so;
  - a test sheet's verifier is compared with the change's authors through GitHub's noreply
    addresses only — elsewhere no person is recognised as an author, and T2 passes any `@handle`
    silently; only agent sessions stay compared.
- `nstack doctor` (G1–G20) and `nstack settings` read GitHub's settings only; elsewhere `doctor`
  ends on a permanent *not verified*, and nothing says which protections are missing.
- The displays — an attested record's status, a hold's draft pull request, the plan's milestones
  (ADR-0008) — are GitHub's.

What already works with any git remote: init and update, the fitness functions, pr-scope,
pr-check (`--body-file`), attest, claim, plan — a bare remote is in the platform's tests.

GitHub is also a **supplier**, distinct from the host: the engine's source and the skeleton's
template, the pre-commit hooks' sources, PyPI. Hosting elsewhere does not remove the need to reach
github.com — the maintainer's literal question: hosting on GitHub is no prerequisite; reaching it is.

## Goal

A team on any forge, or on none, creates and runs a project without an answer that does not apply,
keeps the method's own files working, has its checks attested and said, and is told plainly — on
every diagnosis — what nstack verifies for it, what it cannot, and that its repository is
unguarded; GitHub stays the default, its support unchanged.

## Out of scope

- **A layer over every forge's API.** Adapters are narrow, built when a project needs one.
- **GitLab CI, other forges' protections and displays — in this step.** Each comes with the first
  project that asks for it; until then, said.
- **GitHub as a supplier** — the engine's source, the hooks' sources, PyPI: reaching github.com
  stays required; a mirror is the project's.
- **Dropping git.** The method's records are git objects.

---

## Prior art

| Product / reference | Solution chosen | What we keep from it |
|---|---|---|
| [Renovate platforms](https://docs.renovatebot.com/modules/platform/) | One `platform` setting — github, gitlab, forgejo, gitea, bitbucket, azure — each a narrow adapter | **The forge named once; adapters narrow** |
| [git-forge](https://github.com/Leleat/git-forge) | One CLI over every forge's issues and pull requests, their common features only — archived 2026-08 | **Not a lowest-common-denominator layer** |
| [Forgejo Actions](https://forgejo.org/docs/v17.0/user/actions/github-actions/) | Familiar to GitHub Actions, "not designed to be compatible" | **GitHub's workflows reused there — tested, not assumed** |
| [GitLab code owners](https://docs.gitlab.com/ee/user/project/codeowners/) and [protected branches](https://docs.gitlab.com/ee/user/project/repository/branches/protected/); Gitea and Forgejo's `CODEOWNERS` at the root, `docs/` or `.gitea/` | The ownership file read at places of each forge's own; approvals and code owners on paid GitLab tiers | **The method's files where the forge reads them** |
| Sourcehut, Gerrit | Review without pull requests (patches, changes) | **`none` and `other` name what the method then lacks** |
| git-bug, git-appraise | Coordination data in git, no forge | **The core stays forge-free** — nstack's line already |

**The convention the user already knows:** a tool that asks once which platform hosts the code.

---

## Options considered

| Option | What the user experiences | Cost | Chosen? |
|---|---|---|---|
| Do nothing | Off GitHub: GitHub questions, no CI, two checks silently off, a permanent *not verified* | 0 | No |
| A. Every forge first-class now — CI, protections, displays | Complete, for forges nobody uses yet | High, and maintained blind | No |
| **B. The forge named once; the method's files kept where the forge reads them; checks attested; honest everywhere, unguarded said; adapters when a project needs one** | The right questions at init; ownership and the test sheet working; what is and is not verified said | Low now | **Yes** |

## Decision

**Option B.**

1. **The forge is named once**: an answer `forge` — `github` (the default), `gitlab`, `forgejo`,
   `gitea`, `other`, `none` — asked at init. Off GitHub, the repository's path is a second answer,
   accepting a forge's subgroups; `github_repo` stays GitHub's answer, unchanged for the projects
   that have it, and `owner_team` is asked in the named forge's terms. In this step every forge but
   `github` behaves the same; the names exist so that an adapter later needs no new answer.
   `none`: no forge — no pull request, no review surface; the project runs alone, unguarded, and
   every review rule says it has no carrier.
2. **Off GitHub, the checks are attested**: the answer `checks` starts `attested`. This amends
   PDR-0013 §4 for one case: where no CI is shipped, there is nothing a record stands in for —
   the attested record is the only judge; `init` says so and names the answer the decider changes
   when the forge's CI arrives.
3. **The method's files where the forge reads them**: the GitHub workflows, Dependabot and the
   issue forms are not written off GitHub; the ownership file and the pull request's form — the
   method's, not GitHub's — are written where the named forge reads them, or at a forge-neutral
   place; `new-module` and L6 use that place. No generated link points to github.com.
4. **Honest everywhere, unguarded said** (PDR-0006): off GitHub the project is **unguarded** on
   every diagnosis — no output presents an attested record as something that blocks a merge.
   `nstack doctor` says the forge's protections are not read, names what they should be — as
   information, never as a step a person must take by hand — and exits as for a repository fully
   read, the state said rather than a permanent *not verified*. `pr-check` says when T2 compared the
   verifier with sessions only, never people. The record of commits reaching `main` says it does
   not run. `nstack settings` says it has nothing to apply; the displays say "not shown". `init`'s
   next steps name no GitHub repository and no GitHub setting.
5. **Adapters when asked**: GitLab CI generated from the one list of checks the engine already
   holds, Forgejo and Gitea reusing the GitHub workflows once tested on a real runner, protections
   applied by the engine (#221) and displays per forge — each in a workstream of its own, when a
   project names it.
6. **Nothing changes on GitHub**: a project with `github_repo` keeps every check, display and
   setting it has; its update writes `forge: github`. GitHub Enterprise Server is `github` where the
   engine reaches its API; where it does not, the displays say so.

---

## Expected behaviour

**Nominal journey.** `nstack init` for a team on GitLab: *forge? gitlab*, the repository's path in
GitLab's form, the owner in GitLab's terms; the project is created with `checks: attested`, its
ownership file and pull request form where GitLab reads them, no GitHub workflow; `init`'s next
steps say how to attest and that the repository is unguarded; `nstack doctor` says *forge gitlab:
unguarded — its protections are not read by this version; what they should be: …*; `nstack attest`
records the checks; `nstack claim` holds a deliverable on the GitLab remote.

**Edge cases and degraded states.** `forge: none`: every command that would reach a forge says
there is none, and each review rule says it has no carrier. A project on GitHub updating:
`forge: github` added, nothing else changes. A project already off GitHub with a placeholder
`github_repo` updating: it gets `forge: github` and is told to change it. A project mirrored on two
forges names the one where changes merge. A remote whose host contradicts the `forge` answer is
said by `doctor`. A `forge` answer changed in a pull request: the next update adds or removes the
forge's files.

**Business rules.** The answer `forge` is the decider's, changed by hand in a pull request, as
`checks` is (D134); GitHub stays the default.

**Permissions.** No forge credential is asked to know the forge.

**Acceptance criteria** *(testable)*:

- [ ] Given `nstack init` with `forge: gitlab`, then no question names GitHub, no GitHub workflow,
      Dependabot or issue form is written, `checks` is `attested`, and the next steps name no GitHub
      repository or setting.
- [ ] Given `forge: gitlab`, then the ownership file and the pull request's form are written where
      GitLab reads them, `nstack new-module` records the owner there, and L6 reads it there.
- [ ] Given `forge` other than `github`, then no generated file holds a link to github.com.
- [ ] Given such a project, then `nstack doctor` says it is unguarded, its protections not read
      and what they should be, and exits as for a repository fully read.
- [ ] Given such a project, then no output presents an attested record as something that blocks a
      merge.
- [ ] Given a pull request off GitHub, then `pr-check` says T2 compared the verifier with sessions
      only.
- [ ] Given such a project, then the record of commits reaching `main` is said not to run.
- [ ] Given such a project, then `nstack settings` and the displays say there is nothing they can
      apply or show, and exit 0.
- [ ] Given a project on GitHub updating, then `forge: github` is written and every GitHub check,
      display and setting behaves as before.
- [ ] Given `forge: none`, then `nstack attest`, `nstack claim` and `nstack plan` work on the local
      repository and say they reach no forge, and each review rule says it has no carrier.
- [ ] Given a `forge` answer changed in a pull request, then the next `nstack update` adds or
      removes the forge's files.

---

## Success criterion

> We will consider this was the right call if **a project created on GitLab or Forgejo runs its
> first cycle with nstack — its checks attested, its deliverables held, its ownership file read —
> and its decider never answers a GitHub question** is observed before **2027-06-30**.

How it is observed: the first project off GitHub; its answers file; its attested records.

If the criterion is not met: ask that project what stopped it; build the adapter it names.

---

## Removal condition

> This feature will be removed if **no project off GitHub has been created with nstack by
> 2027-12-31** — the `forge` question then costs every user a step for nobody.

---

## Impacts

- **Existing users**: on GitHub, nothing changes; an update writes `forge: github`.
- **Modules and contracts**: `new-module` writes the owner where the forge's ownership file is;
  the contracts module's template no longer links to GitHub off GitHub; the owner's validator
  speaks the forge's terms.
- **Support and documentation**: `INSTALL.md` (choosing the forge; reaching github.com as a
  supplier), `07-governance.md` (what is verified where; unguarded off GitHub), the glossary
  (*forge*).
- **Data**: none collected.
- **The how** — the Copier questions and their conditions, where each forge reads the ownership
  file and the pull request form, `doctor`'s wording and exit off GitHub, which skeleton files
  depend on the forge — goes to an ADR.
