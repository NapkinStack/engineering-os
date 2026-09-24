# Product Decision Records

An important **product** decision: a user goal, an expected behaviour, a trade-off, a
structuring business rule, a UX or business decision.

The PDR describes **what the product must do and why**, never its implementation.

- Template: [`_TEMPLATE.md`](./_TEMPLATE.md)
- Naming: `NNNN-user-oriented-title.md`

## Mandatory sections

| Section | Why |
|---|---|
| **Prior art** — ≥ 2 references | On an interface, a convention's value comes from the user already knowing it |
| **Dated success criterion** | Makes the decision falsifiable, and therefore useful |
| **Removal condition** | Without it, a feature is permanent by default, even unused |

> The **FDR** format does not exist in this OS. For genuinely complex features, the
> *Detailed functional design* section of the PDR is enough
> (`skeleton/docs/os/06-decisions.md` §4).

## Index

| No. | Title | Status | Criterion to check on |
|---|---|---|---|
| [0001](./0001-create-a-project-and-receive-updates.md) | Create a project and receive NapkinStack's updates | Accepted, clarified (private repositories) | 2026-12-31 |
| [0002](./0002-frame-and-bound-a-project.md) | Frame and bound a project | Accepted, clarified (delivery work; the criterion is effective work), extended (discovery) | 2026-12-31, in the pilot project |
| [0003](./0003-approve-a-change-on-evidence-of-its-behaviour.md) | Approve a change on evidence of its behaviour | Accepted, clarified (what changes a module); measured on the pilot 2026-09-24 | 2026-12-31, in the pilot project |
| [0004](./0004-ask-the-right-question-to-the-right-person.md) | Ask the right question, to the right person, at the right moment | Accepted (2026-09-18), direction only; its criterion met on M9's log; built in part by M11c, its stage axis by M11j | 2026-10-31, on M9's log |
| [0005](./0005-work-on-the-framework-while-using-it.md) | Work on the framework while using it, and never be judged in silence | Accepted (2026-09-18), implemented in v0.4.0 | 2027-03-31 |
| [0006](./0006-work-where-the-forge-cannot-guard.md) | Work on a repository the forge cannot guard | Accepted (2026-09-20), implemented in v0.5.0 | 2027-03-31, on a probe repository and the pilot |
| [0007](./0007-frame-a-project-when-framing-buys-something.md) | Frame a project when framing buys something | **Accepted (2026-09-22)**, clarified 2026-09-24 (a bound on the work, and criticality); planned for **M11j**, before v0.7.0 | 2027-03-31, on a probe repository and the pilot |
| [0008](./0008-configure-the-repository-in-one-gesture.md) | Configure the repository in one gesture, without handing over the keys | **Accepted (2026-09-22)**, planned for **M11k**, before v0.7.0; absorbs D61, whose half is done (M11f) | 2027-03-31, on two repositories and the forge's audit log |
| [0009](./0009-say-why-a-change-may-merge.md) | Say why a change may merge, and what that does not prove | Proposed (2026-09-20), planned for M13 | 2027-06-30, on twenty of the pilot's pull requests |
| [0010](./0010-the-framework-imposes-the-form.md) | The framework imposes the form, the project writes the content | **Accepted (2026-09-22)**, from the pilot's findings; planned for **M11l**, before v0.7.0 | 2027-03-31, on the pilot and one other project |
| [0011](./0011-ceremony-follows-consequence.md) | Ceremony follows consequence | **Accepted (2026-09-24)**; five of its six acceptance criteria met by M11a to M11f, the sixth with M13 | 2027-03-31, on the pilot |
