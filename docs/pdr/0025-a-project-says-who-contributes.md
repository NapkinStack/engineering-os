# PDR-0025 — A project says who contributes: its members, or anyone through a fork

- **Status**: Proposed (2026-11-25, D292), from the maintainer's request that NapkinStack be set up
  for efficient collaboration, both within one organisation and on an open project. Its first
  measurement is done (*User problem*). Two facts are measured before it is accepted
  (*Decision*, 5), and nothing is built before that
- **Date**: 2026-11-25
- **Decision makers**: NapkinStack maintainers (`@NapkinStack/maintainers`)
- **Modules affected**: the decider's settings, `nstack settings` and `nstack doctor`, the
  contributing guide, pr-check's K3

> The PDR describes **what the product must do and why**, never its implementation.
> The how belongs to an ADR.

---

## User problem

NapkinStack serves the members of an organisation well. They have write access, so they can
claim, attest, approve, and have an agent under an App of their own. A project that also wants
outside contributors gets nothing from NapkinStack. A project that wants none can only write that
wish in its contributing guide, and nothing enforces it.

This was measured on 2026-11-25, on a public test project of the organisation (NapkinStack/flet,
v0.34.11). The contributor was a small AI agent on an account with no access, told only to
"contribute a useful change via a pull request from your fork".
- **Forge and CI, what held:**
  - the fork's workflows waited for a person's approval (G9);
  - they then ran without secrets;
  - pr-check refused the sheet the agent wrote after its first red check: its own account as
    verifier, the template's example scenario, `passed` with no evidence.
- **The contributing guide spoke only to members.** The agent never followed it, made a change
  unrelated to the cycle's open deliverable, and met the rules only at its first red check.
- **K3 sent it to `nstack claim`**, which needs write access.
- **Approving a fork's workflows from one run's page released that run only.**

- **The template's example scenario, copied verbatim, passed as a scenario**, and the template's
  text left in the description was never named.

These gaps are #542 (the path from outside, K3, the approval of a fork's runs, what the verifier
owns) and #543 (the template's example and its leftover text). They hold whatever the project
chooses, and they are repaired first. This PDR is about the choice itself.

## Goal

The decider states once, among the project's answers, whether contributions come from its members
only or also from outside. The forge enforces that choice, and the contributing guide gives each
contributor the path that matches it.

## Out of scope

- A bot that lets an outsider hold a deliverable by a comment, in the style of `@rustbot claim`.
  A member can already hold a deliverable for someone (`nstack claim --person`), and leaving it
  unheld is acceptable. A bot would be built only if the volume of outside contributions ever asks
  for one.
- Telling an AI's change from a person's. The rules judge the change and its verification, never
  who typed it. This matches what Kubernetes requires: a person who understands the change and
  defends it.
- A contributor agreement or a sign-off rule (DCO, CLA). That is the decider's legal choice. When
  the decider makes it, the project uses an established app.

## Prior art

| Product / reference | Solution chosen | What we keep from it |
|---|---|---|
| GitHub, [2026-02-13](https://github.blog/changelog/2026-02-13-new-repository-settings-for-configuring-pull-request-access/) | A repository setting restricts the opening of pull requests to collaborators, or turns pull requests off. Its API exposes `pull_request_creation_policy` (`all` read on our repositories) | **The forge enforces `members`**, instead of a sentence in a guide |
| GitHub, [2026-06-17](https://github.blog/changelog/2026-06-17-limit-open-pull-requests-for-users-without-write-access/) and [2026-10-28](https://github.blog/changelog/2026-10-28-pull-request-limits-exempt-contributors-by-age-or-history/) | A limit on the open pull requests of an account without write access, with exemptions by age or history | Not in this decision: whether a repository can set it through the API is unmeasured; a follow-up if `open` is taken |
| GitHub | The workflows of a first-time contributor's fork wait for a maintainer's approval | Already in the checklist (G9) |
| [Rust's triagebot](https://forge.rust-lang.org/triagebot/issue-assignment.html), Probot's issue-assigner | An outsider claims an issue by a comment, and a bot assigns it | Not taken now (*Out of scope*) |
| tldraw (2026) | Closes outside pull requests automatically, after a wave of low-quality AI ones | The extreme of `members`, enforced by the forge here instead |

**The convention the user already knows**: a public repository either takes pull requests from
anyone, through a fork, or says it does not and the forge holds to it.

## Options considered

1. **Say nothing**, as today: `members` is a sentence nothing enforces, and `open` has no path.
2. **Derive the mode from the repository's visibility**: visibility says who may read the code,
   not whether outside code is wanted. A public repository may want none.
3. **Repair #542 and #543 only, and let the forge's own setting be the choice**: the smallest
   change. But the forge's setting would then be the only record of a decision about the project.
   NapkinStack keeps such decisions in the repository and treats the forge as a display of them.
   The contributing guide also needs the choice to say the right path, and it is written from the
   repository.
4. **One answer of the decider's, `contributors: members | open`, kept with the project's answers,
   shown in the contributing guide, and displayed on the forge** (chosen).

## Decision

**1. One answer, `contributors`, the decider's**, kept with the project's other answers and changed
the same way: by a pull request a human approves.

**2. Absent means not asserted.** A project that has not answered keeps today's behaviour. Nothing
is checked, nothing is changed on the forge, and the guide stays as it is. Only an explicit answer
is enforced. An update therefore changes nothing for a project already receiving outside pull
requests.

**3. `members`**: the forge restricts the opening of pull requests to the project's collaborators.
The person who applies the forge's settings sees that change before it is made, as for every
setting. The contributing guide says that issues are welcome and that pull requests come from
members.

**4. `open`**: pull requests stay open to all, and a fork's workflows wait for a person's approval
(G9, already asked). The contributing guide carries the path from outside, from #542.

**5. Measured before acceptance**, because a wrong answer would make the decision harmful:
- whether the forge's setting can be applied, not only read, through its API;
- whether a GitHub App installed on the repository, an agent's identity, can still open a pull
  request under `members`. If it cannot, `members` would stop the project's own agents, and the
  decision is reconsidered.

**6. The answer and the forge can disagree** when a person changes the forge's setting by hand. The
forge's settings check reads the forge and names the drift, as it does for every setting.

**7. Off GitHub**, the answer shapes the contributing guide only. The forge's part is said *not
verified* until the forge offers the setting.

## Expected behaviour

- On a project answering `members`, an account without access cannot open a pull request. The
  forge says so, and the guide points to issues. The project's agents still open theirs.
- On a project answering `open`, an outsider who reads the guide opens a pull request on a `ready`
  deliverable, fills its sheet from the acceptance criteria, and leaves the results to a member.
- Changing the answer is a pull request a human approves, like any setting.

## Success criterion

We will consider this was the right call if, before **2026-12-31**:
- on the test project answering `open`, an outside contributor delivers its cycle's deliverable
  with pr-check green after at most one verification round;
- on the same project answering `members`, the forge refuses a pull request from an account
  without access, and an agent's pull request, under its App, passes.

How it is observed: the same rehearsal as on 2026-11-25, run again with the guide and the setting
built.

If the criterion is not met: the setting is removed, and the guide's path from #542 stays.

## Removal condition

Removed if no project answers `open` by **2027-06-30**, or if the forges converge on a contribution
policy that a repository declares in a file of its own, which NapkinStack would then generate
instead.

## Impacts

- **Projects**: nothing until they answer. An explicit `members` on a public project closes pull
  requests to outsiders, which is a visible change. The person applying the forge's settings sees
  it before it is made.
- **The engine and the skeleton**: a new setting, an item of the forge's checklist, and the
  contributing guide's section for each mode. The how belongs to an ADR, once the two measurements
  of *Decision* 5 are made.
