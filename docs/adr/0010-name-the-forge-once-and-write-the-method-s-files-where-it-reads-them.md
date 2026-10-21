# ADR-0010 — Name the forge once, and write the method's files where it reads them

- **Status**: Proposed (2026-10-21)
- **Date**: 2026-10-21
- **Decision makers**: NapkinStack maintainers (`@NapkinStack/maintainers`)
- **Scope**: project — the Copier questions, the skeleton's files and their conditions, the engine
  (`init`, `doctor`, `settings`, `pr-check`, `new-module`, the forge displays)
- **Reversibility**: easy — `forge: github` renders today's project; another value changes which
  files are written and what is said, nothing recorded elsewhere

---

## Context

PDR-0018 decided *what*: the forge named once, GitHub the default; off GitHub, the checks attested,
the method's files where the forge reads them, the project said unguarded on every diagnosis, T2
and the record of commits on main said to be limited, no link to github.com, adapters when asked.
This record says *how*.

## Problem

The questions and their conditions; which skeleton files depend on the forge and where the
ownership file and the pull request form go on each; how the engine knows the forge; what `doctor`
says and how it exits off GitHub; what `pr-check`, `settings` and the displays say.

## Constraints

- Nothing changes for a project on GitHub (PDR-0018 §6).
- No Copier migration: the template keeps none (`copier.yml`); answers are added with defaults.
- The answers file is the single source: the engine reads `forge` there, never guesses it from a
  remote, and says when the remote disagrees.
- No manual step: a `forge` answer changed in a pull request is followed by the next update.

---

## Prior art

| Reference | What it does | What we take |
|---|---|---|
| [GitHub](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-code-owners), [GitLab](https://docs.gitlab.com/ee/user/project/codeowners/), [Gitea](https://docs.gitea.com/usage/code-owners) code owners | GitHub reads `.github/`, the root, `docs/`; GitLab the root, `docs/`, `.gitlab/`; Gitea and Forgejo the root, `docs/`, `.gitea/` — each the first it finds | **The root is read by all three** |
| [GitLab description templates](https://docs.gitlab.com/ee/user/project/description_templates.html) | `.gitlab/merge_request_templates/Default.md` is the default merge request description | **GitLab's place for the pull request form** |
| Gitea and Forgejo issue and pull request templates | `.gitea/pull_request_template.md` (and `.github/`) | **Theirs** |
| [Copier `when`](https://copier.readthedocs.io/en/stable/configuring/#advanced-prompt-formatting) and templated file names | A question asked only when another answer allows it; a file rendered only when its name renders non-empty | **Conditions in the template, nothing in code** |
| [Renovate `platform`](https://docs.renovatebot.com/modules/platform/) | One setting selecting a narrow adapter | **One answer, read everywhere** |

---

## Options considered

| Option | For | Against | Chosen? |
|---|---|---|---|
| Guess the forge from the remote's URL | No question | A mirror, a proxy, no remote yet at init; the truth outside the repository | No — said when they disagree |
| Separate skeletons per forge | Clear | Every page duplicated; drift | No |
| **One skeleton, files and questions conditioned on `forge`** | One source; Copier renders and removes on update | Conditions to keep tested | **Yes** |
| The ownership file at the root for every forge | One place | Moves every GitHub project's `.github/CODEOWNERS` | No — GitHub unchanged; the root off GitHub |

## Decision

1. **The questions.** `forge` — `github` (default), `gitlab`, `forgejo`, `gitea`, `other`, `none` —
   asked first. `github_repo` asked only `when: forge == "github"`, its validator unchanged.
   `repository` — the path at the forge, `group/sub/name` accepted — asked only for `gitlab`,
   `forgejo`, `gitea` and `other`. `owner_team`'s help names the forge's own terms. `checks` keeps
   `forge` as its default on GitHub, and `attested` everywhere else, said in its help. `update`
   with defaults writes `forge: github` into an answers file that has none.
2. **The files, by forge** — the rendered names are conditioned in the skeleton:

   | File | `github` | `gitlab` | `forgejo`, `gitea` | `other`, `none` |
   |---|---|---|---|---|
   | Workflows, Dependabot, issue forms (`.github/…`) | written | — | — | — |
   | Ownership file | `.github/CODEOWNERS` | `CODEOWNERS` | `CODEOWNERS` | `CODEOWNERS` |
   | Pull request form | `.github/pull_request_template.md` | `.gitlab/merge_request_templates/Default.md` | `.gitea/pull_request_template.md` | `docs/pull_request_template.md` |

   A link to github.com — the issue forms' discussions, the contracts module's `contact` — is
   written only on GitHub; elsewhere the contact is the module's owner.
3. **The engine reads `forge`** from the answers file — a missing answer is `github` — through one
   function every command uses. The ownership file is the first of `.github/CODEOWNERS`,
   `CODEOWNERS`, `docs/CODEOWNERS` that exists; `new-module` and L6 use it.
4. **`doctor` off GitHub.** No G rule is read. One line per checklist group says what the forge's
   protections should be — as information — and a line says the repository is **unguarded**, the
   forge's protections not read by this version; a remote whose host contradicts `forge` is said.
   The exit is that of the workstation's rules alone: the forge's state is said, never a permanent
   *not verified*.
5. **`pr-check` off GitHub** prints, beside T2's result: *T2 compared the verifier with the change's
   agent sessions only — no person is recognised as an author off GitHub*. A project with `forge:
   none` has each review rule say it has no carrier.
6. **The record of commits on main.** Off GitHub its workflow is not written; `doctor` says the
   record does not run.
7. **`settings` and the displays.** `nstack settings` says it has nothing to apply off GitHub, exit
   0. The hold's draft pull request, the board, the attested status: "not shown — forge <name>".
8. **`init`'s next steps** name the forge's repository and, off GitHub, say that checks are attested
   (`nstack attest`) and the repository unguarded; never a GitHub setting.

- **Expected user value**: a team on GitLab or Forgejo answers only its own questions, keeps
  ownership and the test sheet working, and is told what nstack verifies for it.
- **How we will observe it**: PDR-0018's criterion.

## Success criterion

`nstack init` with each `forge` value renders the files of the table and asks only the questions
of §1; an update of a GitHub project changes nothing but `forge: github`; changing `forge` and
updating adds and removes the forge's files.

## Consequences

- Copier conditions in `copier.yml` and in skeleton file names; tests rendering each forge.
- `doctor`, `pr-check`, `landed`, `settings`, `hold`, `board`, `attest`'s display, `new-module`,
  `init` read one answer; the contracts module's template's `contact`.
- The handbook: `INSTALL.md` (choosing the forge; github.com as a supplier), `07-governance.md`
  (unguarded off GitHub), the glossary (*forge*).

## Rejected alternatives

See *Options considered*.
