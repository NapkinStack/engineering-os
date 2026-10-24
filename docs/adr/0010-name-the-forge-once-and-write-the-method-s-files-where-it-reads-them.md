# ADR-0010 — Name the forge once, and write the method's files where it reads them

- **Status**: Accepted (2026-10-21), after an independent review (#239) that reshaped it: a forge
  changed through `nstack update --forge`, the ownership file carried, Gitea and Forgejo's syntax
  said, the test sheet without a pull request, `_exclude` instead of templated names, GitHub
  Enterprise Server, one forge-neutral list of protections
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
  remote, and says when a known public host disagrees.
- No manual step, and Copier's own rule: an answers file is never edited by hand for an answer
  that conditions files — Copier renders the old copy with the current answers, so a hand edit
  adds and removes nothing.

---

## Prior art

| Reference | What it does | What we take |
|---|---|---|
| [GitHub](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-code-owners), [GitLab](https://docs.gitlab.com/ee/user/project/codeowners/), [Gitea](https://docs.gitea.com/usage/code-owners) code owners | GitHub reads `.github/`, the root, `docs/`; GitLab the root, `docs/`, `.gitlab/` (gitignore patterns, Premium for approval); Gitea and Forgejo the root, `docs/`, `.gitea/` — **Go regular expressions**, not gitignore patterns | **The root, for GitHub and GitLab syntax; Gitea and Forgejo said** |
| [GitLab description templates](https://docs.gitlab.com/ee/user/project/description_templates.html) | `.gitlab/merge_request_templates/Default.md` | **GitLab's place for the pull request form** |
| [Copier `_exclude`](https://copier.readthedocs.io/en/stable/configuring/#exclude), [questions and `when`](https://copier.readthedocs.io/en/stable/configuring/#questions), `copier update --data` | Exclusion patterns rendered by Jinja; a question asked only when another allows; an update given new answers as data renders the old copy with the old ones | **Conditions in `_exclude`; a forge changed through an update with data** |
| `MOVED_FILES` and `_carry` (this engine, D88) | A file the template moved is carried with the project's lines, a conflict marked | **The ownership file carried when the forge changes** |
| [Renovate `platform`](https://docs.renovatebot.com/modules/platform/) | One setting selecting a narrow adapter | **One answer, read everywhere** |

---

## Options considered

| Option | For | Against | Chosen? |
|---|---|---|---|
| Guess the forge from the remote's URL | No question | A mirror, a proxy, no remote at init; the truth outside the repository | No — a known public host's contradiction is said |
| Separate skeletons per forge | Clear | Every page duplicated; drift | No |
| Templated file and directory names | Copier supports it | Renames `skeleton/.github/`, which fifteen tests read; variables outside `.jinja` files | No |
| **One skeleton; files excluded by a rendered `_exclude`; a moved file's content included from one place** | One source per content; Copier renders and removes on update | Conditions to keep tested per forge | **Yes** |
| A forge changed by editing the answers file (D134's way) | No command | Copier renders the old copy with the new answer: nothing added or removed — and refuses it | No — `nstack update --forge` |

## Decision

1. **The questions.** `forge` — `github` (default), `gitlab`, `forgejo`, `gitea`, `other`, `none` —
   asked first. `github_repo` asked only `when: forge == "github"`, its validator unchanged; every
   file using it is conditioned on GitHub. `repository` — the path at the forge, `group/sub/name`
   accepted by its validator — asked only for `gitlab`, `forgejo`, `gitea`, `other`.
   `owner_team`'s help and validator accept the forge's terms (GitLab's subgroups). `checks`
   defaults to `forge` on GitHub and `attested` elsewhere — the engine no longer forces it at init.
   `update` with defaults writes `forge: github` into an answers file that has none, and says how to
   change it.
2. **The files, by forge**, excluded by a rendered `_exclude`; a moved file's content held once and
   included where the forge reads it:

   | File | `github` | `gitlab` | `forgejo`, `gitea` | `other` | `none` |
   |---|---|---|---|---|---|
   | Workflows, Dependabot, issue forms | `.github/…` | — | — | — | — |
   | Ownership file | `.github/CODEOWNERS` | `CODEOWNERS` | `CODEOWNERS`, said not read by the forge (its syntax differs) | `CODEOWNERS` | `CODEOWNERS` |
   | Pull request form | `.github/pull_request_template.md` | `.gitlab/merge_request_templates/Default.md` | `.gitea/pull_request_template.md` | `docs/pull_request_template.md` | `docs/pull_request_template.md` |

   A link to the project's forge — the issue forms' discussions, the contracts module's `contact` —
   is written only on GitHub; elsewhere the contact is the module's owner. The suppliers' addresses
   (the hooks' sources, the engine's) stay: PDR-0018 leaves them out of scope.
3. **Changing forge.** `nstack update --forge <name> [--repository <path>]` passes the answers to
   Copier as data — the old copy rendered with the forge its files were written for — and runs at
   the current version too; its branch is the decider's pull request. The ownership file and the
   pull request form are carried to their new place as `_carry` does: the project's lines kept, a
   conflict marked. `SECURITY.md`, a seat Copier never rewrites, is merged the same way into the
   new forge's text (clarified 2026-10-24, from #249's verification). `--repository` is required
   off GitHub. A `forge` edited by hand is said by
   `update` and `doctor`, which name the command.
4. **The engine reads `forge`** from the answers file — a missing answer is `github` — through one
   function every command uses. The ownership file is the first of `.github/CODEOWNERS`,
   `CODEOWNERS`, `docs/CODEOWNERS` that exists; `new-module`, L6 and the update's carrying use it.
   The displays take the repository from `github_repo` and the API from `GITHUB_API_URL`, so GitHub
   Enterprise Server is GitHub; the remote's URL is read only to say a contradiction, and only for
   known public hosts (github.com, gitlab.com, codeberg.org, gitea.com).
5. **`doctor` off GitHub.** No G rule is read. One forge-neutral list of protections — a pull
   request required, one approval, the code owners' review, no force push nor deletion of the main
   branch, squash only, secrets refused at push — is said as information, bound to `INSTALL.md` by a
   test; a line says the repository is **unguarded**, the forge's protections not read by this
   version. `checks: forge` off GitHub is said as a contradiction: no CI is shipped. The exit is
   that of the workstation's rules alone.
6. **`pr-check` off GitHub** says, beside T2: *the verifier compared with the change's agent
   sessions only — no person is recognised as an author off GitHub*. With `forge: none` there is no
   pull request: the test sheet lives in `docs/pull_request_template.md`, filled and passed to
   `attest --body-file`; without one, T1 to T5 say "no carrier" and do not fail, and L6 says no forge
   reads the ownership file.
7. **The record of commits on main**: off GitHub its workflow is not written; `doctor` says the
   record does not run.
8. **`settings` and the displays**: `nstack settings` says it has nothing to apply off GitHub, exit
   0; the hold's draft pull request, the board, the attested status say "not shown — forge <name>".
9. **`init` and `update`'s words**: `init` takes `--forge` and `--repository`, refuses
   `--github-repo` off GitHub, and its next steps name the forge's repository and, off GitHub, say
   that checks are attested and the repository unguarded; `update`'s last line says *attest* off
   GitHub, never "CI validates it".
10. **D134 bounded**: an answer changed by hand in a pull request stays the way for answers that
    condition no file (`checks`, `hold_days`); `forge` and `repository` change through §3.

- **Expected user value**: a team on GitLab or Forgejo answers only its own questions, keeps
  ownership and the test sheet working, and is told what nstack verifies for it.
- **How we will observe it**: PDR-0018's criterion.

## Success criterion

`nstack init` with each `forge` value renders the files of the table and asks only the questions
of §1; an update of a GitHub project changes nothing but `forge: github`; `nstack update --forge`
adds and removes the forge's files and carries the project's ownership lines.

## Consequences

- `_exclude` conditions and one included content per moved file; tests rendering each forge, an
  update of a GitHub project, and a forge change carrying a module's ownership line.
- The skeleton's pages naming GitHub or `.github/CODEOWNERS` — `CONTRIBUTING.md`, `AGENTS.md`,
  `SECURITY.md` (a seat, made a template), the handbook's `README.md`, `05-workflow.md`,
  `09-platform.md`, `INSTALL.md`'s GitHub sections — said per forge.
- `doctor`, `pr-check`, `landed`, `settings`, `hold`, `board`, `attest`'s display, `new-module`,
  `init` read one answer; the contracts module's template's `contact`.
- The handbook: `INSTALL.md` (choosing the forge; github.com as a supplier), `07-governance.md`
  (unguarded off GitHub), the glossary (*forge*).

## Rejected alternatives

See *Options considered*.
