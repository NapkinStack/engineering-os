# Product Decision Records

An important **product** decision: a user goal, an expected behaviour, a trade-off, a
structuring business rule, a UX or business decision.

The PDR describes **what the product must do and why**, never its implementation.

- Form: [the one every project receives](../../skeleton/.nstack/forms/pdr.md)
- Naming: `NNNN-user-oriented-title.md`

## Mandatory sections

| Section | Why |
|---|---|
| **Prior art** — ≥ 2 references | On an interface, a convention's value comes from the user already knowing it |
| **Dated success criterion** | Makes the decision falsifiable, and therefore useful |
| **Removal condition** | Without it, a feature is permanent by default, even unused |

> The **FDR** format does not exist in this OS. For genuinely complex features, the
> *Detailed functional design* section of the PDR is enough
> (`skeleton/.nstack/handbook/06-decisions.md` §4).

## Index

| No. | Title | Status | Criterion to check on |
|---|---|---|---|
| [0001](./0001-create-a-project-and-receive-updates.md) | Create a project and receive NapkinStack's updates | Accepted, clarified (private repositories) | 2026-12-31 |
| [0002](./0002-frame-and-bound-a-project.md) | Frame and bound a project | Accepted, clarified (delivery work; the criterion is effective work; what a session reads of the cycle), extended (discovery) | 2026-12-31, in the pilot project |
| [0003](./0003-approve-a-change-on-evidence-of-its-behaviour.md) | Approve a change on evidence of its behaviour | Accepted, clarified (what changes a module); measured on the pilot 2026-09-24 | 2026-12-31, in the pilot project |
| [0004](./0004-ask-the-right-question-to-the-right-person.md) | Ask the right question, to the right person, at the right moment | Accepted (2026-09-18), direction only; its criterion met on M9's log; built in part by M11c, its stage axis by M11j | 2026-10-31, on M9's log |
| [0005](./0005-work-on-the-framework-while-using-it.md) | Work on the framework while using it, and never be judged in silence | Accepted (2026-09-18), implemented in v0.4.0, clarified (a pin taken during review) | 2027-03-31 |
| [0006](./0006-work-where-the-forge-cannot-guard.md) | Work on a repository the forge cannot guard | Accepted (2026-09-20), implemented in v0.5.0, clarified (a record with no gap) | 2027-03-31, on a probe repository and the pilot |
| [0007](./0007-frame-a-project-when-framing-buys-something.md) | Frame a project when framing buys something | **Accepted (2026-09-22)**, clarified 2026-09-24 (a bound on the work, and criticality); built in v0.7.0 | 2027-03-31, on a probe repository and the pilot |
| [0008](./0008-configure-the-repository-in-one-gesture.md) | Configure the repository in one gesture, without handing over the keys | **Accepted (2026-09-22)**; the print mode in v0.7.0; clarified 2026-10-24 (D150): the forge allows no credential that administers and cannot commit — the apply mode built run by the person, never delegated (D151) | 2027-03-31, on two repositories and the forge's audit log |
| [0009](./0009-say-why-a-change-may-merge.md) | Say why a change may merge, and what that does not prove | Proposed (2026-09-20), planned for M13 | 2027-06-30, on twenty of the pilot's pull requests |
| [0010](./0010-the-framework-imposes-the-form.md) | The framework imposes the form, the project writes the content | **Accepted (2026-09-22)**, from the pilot's findings; built in v0.7.0; a fifth rule of the standard (2026-10-15) | 2027-03-31, on the pilot and one other project |
| [0011](./0011-ceremony-follows-consequence.md) | Ceremony follows consequence | **Accepted (2026-09-24)**; five of its six acceptance criteria built in v0.7.0, the sixth with M13 | 2027-03-31, on the pilot |
| [0012](./0012-a-project-s-tree-is-the-project-s.md) | A project's tree is the project's | **Accepted (2026-10-12)**, the handbook kept in the project. Built in v0.7.0: one folder for the framework's files, the contracts module created by the first contract; clarified (one register of decisions) | 2027-03-31, on a project created after it |
| [0013](./0013-checks-run-where-the-team-works.md) | Checks run where the team works; the forge is an operator | **Accepted (2026-10-20)**, from #189; the how in ADR-0006 | 2027-03-31, on the third project and one project with no forge CI |
| [0014](./0014-a-human-finds-what-the-words-mean-where-they-read-them.md) | A human finds what the words mean, where they read them | **Accepted (2026-10-20)**, from #191; built in D131 | 2027-03-31, two people new to nstack on a downstream project |
| [0015](./0015-a-contributor-sees-who-holds-a-deliverable.md) | A contributor sees who holds a deliverable | **Accepted (2026-10-21)**, from #212; the how in ADR-0007 | 2027-03-31, the third project with a second contributor, and one project off GitHub |
| [0016](./0016-a-cycle-s-progress-is-shown-where-the-decider-looks.md) | A cycle's progress is shown where the decider looks, and kept nowhere else | **Accepted (2026-10-21)**, from #220; the how in ADR-0008 | 2027-03-31, the decider follows two cycles of the third project from the forge alone |
| [0017](./0017-a-change-s-runs-show-what-their-logs-said.md) | A change's runs show what their logs said | **Accepted (2026-10-21)**, from #224; the how in ADR-0009; clarified 2026-10-24 (#245, #246) | 2027-03-31, the third project's end-to-end runs |
| [0018](./0018-git-is-required-the-forge-is-the-project-s-choice.md) | Git is required; the forge is the project's choice | **Accepted (2026-10-21)**, from #223; the how in ADR-0010 | 2027-06-30, a first project off GitHub |
| [0019](./0019-the-project-s-success-is-recorded-where-a-cycle-closes.md) | The project's success is recorded where a cycle closes | **Accepted (2026-10-25)**, the second step of D155's view of the project; built as D159 | 2027-03-31, two closures of the third project |
| [0020](./0020-a-closure-reads-the-decisions-whose-criterion-is-due.md) | A closure reads the decisions whose criterion is due | Proposed (2026-10-26), from #279 | 2027-03-31, two closures of the third project |
