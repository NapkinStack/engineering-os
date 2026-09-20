# PDR-0008 — Configure the repository in one gesture, without handing over the keys

- **Status**: Proposed (2026-09-20)
- **Date**: 2026-09-20
- **Decision makers**: NapkinStack maintainers (`@NapkinStack/maintainers`)
- **Modules affected**: `nstack` (a new command beside `doctor`), the skeleton's README and
  checklist, ADR-0004

> The PDR describes **what the product must do and why**, never its implementation.
> The how belongs to the implementation plan and, where structuring, to an ADR.

---

## User problem

The framework's barriers are the forge's settings, and the forge's settings are not copied
with a project. So every new project starts with **thirteen settings applied by hand**, from a
checklist printed by `nstack init` and checked read-only by `nstack doctor`. Measured on
2026-09-20: that list is the largest manual block of the whole journey, and it is the only one
an agent cannot take off the person's hands — by ADR-0004, the agent holds no administration
right at all.

Three consequences, all observed rather than supposed.

**It is slow where slowness buys nothing.** Thirteen settings, in four different pages of the
forge's interface, repeated at every new project. Nothing about them is a decision: they are
the same list every time, and `doctor` already knows what each one should be.

**One of them cannot even be done at the right moment.** D26, found in M9: GitHub offers a
status check as *required* only once it has seen it run, so a fresh repository cannot select
the five checks the framework needs. The documented workaround is to open a first pull request
for nothing, wait for the checks, then come back and select them.

**And on some plans, part of the list is impossible** — seven of the thirteen on a private
repository with no paid plan (PDR-0006). A person applying the list by hand discovers that one
setting at a time.

The person who wants their agent to do this cannot let it: the credential that configures a
repository is the credential that can *unconfigure* it, and an agent that can remove the rule
that constrains it is not constrained.

## Goal

The forge's settings become one gesture that is reliable, aware of the repository's visibility
and plan, and safe enough that a person may let their agent perform it — without any moment
where the agent can both weaken a rule and merge under it.

## Out of scope

- **Making this mandatory.** The checklist stays valid applied by hand, and `doctor` stays the
  read-only reference. Nothing in the framework depends on this command having been run.
- **Keeping settings in sync over time**, reverting drift, or watching the repository. This is
  a setup gesture, not an agent that holds a permanent right.
- **Giving the framework's own agent an administration right.** ADR-0004 is unchanged: the
  session that writes code never holds administration.
- **Forges other than GitHub**, and anything that costs money on the user's behalf.

---

## Prior art

> **Mandatory section.** Minimum two named references.
> (`skeleton/docs/os/06-decisions.md` §2)

**How is this problem solved elsewhere?**

| Product / reference | Solution chosen | What we keep from it |
|---|---|---|
| [github/safe-settings](https://github.com/github/safe-settings) | *"Policy-as-Code for GitHub Organizations… Centrally manage and enforce repository settings, branch protections, teams"*, from a settings file, applied by an App | **That settings belong in a file and are applied by a tool**, not typed into a form once per project |
| [Terraform's GitHub provider](https://registry.terraform.io/providers/integrations/github/latest/docs) | Repository settings and rulesets declared as code, applied with the operator's own credential | **The separation we need**: the description of the desired state travels with the project; the right to apply it stays with a human |
| [Allstar](https://github.com/ossf/allstar) | Policies with actions `log`, `issue`, `fix` — where `fix` *"reverts the setting"* | **The limit we do not cross.** Continuous correction needs a permanent right; we take the one-shot and leave the standing power alone |
| [Minder](https://github.com/mindersec/minder) | Remediation as *"a REST call flipping a repo setting"* or *"creating a pull request with a proposed fix"*, with `ActionOpt` = On / Off / **DryRun** | **The dry run as the default**, and remediation as an explicit opt-in rather than a background behaviour |
| Separation of duties, as [SLSA](https://slsa.dev/spec/v1.2/source-requirements) and the [OSPS Baseline](https://baseline.openssf.org/versions/2026-02-19.html) state it for review | The party that performs an action is not the party that authorises it | **The rule of this decision**, moved one level down: the identity that configures the barrier is not the identity that works behind it |

**The convention the user already knows:** a tool shows you the plan, then applies it —
`terraform plan` before `terraform apply`, `--dry-run` before the real thing.

**Why depart from it:** the tools above hold a standing credential and keep a repository in
its declared state forever. That is right for infrastructure and wrong here, because the thing
being configured is the barrier that constrains the very agent that would hold the credential.
So the gesture is **one-shot, scoped and self-checking**, and the standing state is verified by
a read-only diagnosis that needs no power at all.

---

## Options considered

| Option | What the user experiences | Cost | Chosen? |
|---|---|---|---|
| Do nothing | Thirteen settings by hand per project, a pull request opened for nothing to unlock D26, and a plan's limits discovered one at a time | 0 | No. Measured as the journey's largest manual block |
| A. Print the exact calls | The tool prints what to apply; the person pastes it into their own shell | Very low | **Yes, as the default.** No credential goes anywhere near the agent |
| **B. A, plus an apply mode with a credential that cannot commit** | The person may let their agent run it, with a temporary administration-only credential the tool refuses to use if it can also push code | Low | **Yes, as an opt-in** |
| C. A GitHub App of ours that configures repositories | One click, a standing right, nothing to paste | High, and it is a service to run | No. A permanent administration right on other people's repositories, held by us, for a gesture that happens once |
| D. Give the framework's agent administration | The agent does everything | Low | No. It is the cage-and-key problem: an agent that can remove the rule that constrains it is not constrained (ADR-0004) |

## Decision

**Options A and B: one command, two modes, and a rule that makes the second one safe.**

**The command computes a difference and applies it, never a rewrite.** It reads the
repository's current settings, compares them with the checklist `doctor` already knows,
and produces the smallest set of changes that closes the distance. It **adds and
strengthens**; it never deletes a ruleset, never removes a required check, never adds a bypass
actor, and never lowers a setting that is already stricter than the checklist asks. A
repository that is already compliant gets no change at all.

**It is aware of the plan and of the visibility.** What the repository's plan cannot enforce is
not attempted and not reported as a failure: it is named, with its cost, in PDR-0006's words.
A private repository on a free plan is configured as far as it can be, told it is unguarded,
and told the two exits.

**Print is the default; applying is a choice.** By default the command prints exactly what
would be done, in a form the person can run themselves with their own credential — nothing
enters the agent's session. A person who prefers may let the command apply it, and then:

> **The identity that configures the repository may never commit to it, and the command
> verifies this before acting.**

The credential it is given must be able to administer the repository and must **not** be able
to push to it. The command reads the calling identity's own permissions on the repository and
**refuses to act** when that identity can also write code. This is not a promise in prose: it
is a check, run first, that fails closed. So there is no moment at which one identity can both
weaken a barrier and merge under it — which is the only reason the standing rule of ADR-0004
can safely have an exception at all.

**The right is temporary by construction.** The command stores nothing, logs no credential,
and ends by telling the person to revoke what they granted. Nothing in the framework asks for
that credential again; the read-only diagnosis needs none of it.

**And it proves what it did.** It prints the changes it made, then runs the diagnosis, so the
end state is established by the same read-only check anyone else can run — not by the command's
own account of itself.

---

## Expected behaviour

**Nominal journey, by hand.** After `nstack init`, the person runs the command. It prints the
calls that would bring the repository to the checklist, marks what their plan cannot reach, and
they paste it into their shell. The diagnosis then reports the repository compliant, or
unguarded with the settings that are out of reach named.

**Nominal journey, delegated.** The person creates a short-lived credential that can administer
the repository and cannot push, hands it to their agent, and asks for the setup. The command
verifies the credential's shape, applies the difference, prints it, runs the diagnosis, and
reminds them to revoke. The agent never held a right to change code.

**Edge cases and degraded states.** A credential that can also push: refused before anything is
attempted, naming what to change. A credential that cannot administer: refused, naming the
permission. A setting the plan forbids: not attempted, named with its cost. A required check
the forge refuses to name before it has run (D26): applied if the forge accepts it, and
otherwise named as the one step that remains, with its reason. A repository already stricter
than the checklist: left alone, and said so. A partial failure: what succeeded is printed,
what failed is named with the forge's own error, and the diagnosis reports the real state.

**Business rules.**

- Nothing is ever lowered, removed, or bypassed.
- The configuring identity cannot be a committing identity, and this is checked, not assumed.
- Print is the default; applying is explicit.
- The end state is established by the read-only diagnosis, never by the command's own claim.

**Permissions:** the framework's own agent keeps no administration right (ADR-0004). The
credential used by this command is the user's, supplied for one run, and the command refuses it
if it carries the power to write code.

**Acceptance criteria** *(testable)*:

- [ ] Given a repository and no credential, when the command runs, then it prints the calls
      that would close the distance to the checklist, and changes nothing.
- [ ] Given a credential that can administer and can also push, when the command is asked to
      apply, then it refuses before any call, and names what to change.
- [ ] Given a credential that can administer and cannot push, when the command is asked to
      apply, then the repository's settings reach the checklist, and the diagnosis says so.
- [ ] Given a repository already compliant, when the command runs, then it makes no call and
      reports that nothing was needed.
- [ ] Given a repository whose ruleset is stricter than the checklist, when the command runs,
      then that setting is left as it is.
- [ ] Given a private repository on a plan that enforces nothing, when the command runs, then
      it applies what the plan allows, names the rest as out of reach with its cost, and never
      reports the repository as guarded.
- [ ] Given a run that applied changes, when it ends, then it prints each change made and
      reminds the person to revoke the credential.
- [ ] Given any run, then no credential appears in its output or in any file it writes.

---

## Success criterion

> **Mandatory section.** Without a date nobody comes back to check, and the decision folder
> becomes a graveyard.

> We will consider this was the right call if, before **2027-03-31**, **a new repository
> reaches every setting its plan allows in one gesture and under five minutes**, measured on a
> public repository and on a private one, from the published version — and if the five required
> checks are in place **without a pull request opened for nothing** (D26). And if, over the
> pilot and the validation project, **no credential granted for a setup is ever used for
> anything else**, which the forge's own audit log shows.

How it is observed: the two setup runs with their printed changes and the diagnosis that
follows; the repositories' rulesets read back through the API; the audit log for the life of
each granted credential.

If the criterion is not met: a gesture that still takes a pull request for nothing means the
forge's API does not accept a check it has not seen, and D26 stays a documented step rather
than a solved one; a credential found doing anything beyond setup means the shape is wrong and
the apply mode goes, leaving the printed form.

---

## Removal condition

> **Mandatory section.** A feature with no removal condition is permanent by default,
> including when nobody uses it.

The **apply mode** will be removed if the check that the configuring identity cannot commit
turns out not to hold on some credential shape the forge offers — a single case where the
refusal can be walked around is enough, because the whole safety of the mode rests on it. The
**command itself** will be removed if the forge's settings stop being applicable through its
API, or if a project is found using it to weaken a repository, which its own no-lowering rule
should make impossible.

---

## Impacts

- **Existing users**: none today; the checklist keeps working by hand. The pilot and the
  validation project can adopt it or not.
- **Modules and contracts**: none.
- **Decisions**: **ADR-0004** is clarified, not changed — the framework's agent still never
  holds administration, and this decision names the second, disjoint power and the rule that
  keeps them apart. **PDR-0001**'s checklist keeps its content and gains an executable form.
  **PDR-0006** supplies the vocabulary for what a plan cannot reach. **D25 and D26** are
  answered in practice if the forge's API accepts a check it has not yet seen.
- **Support and documentation**: `nstack init`'s next steps name the command; the skeleton's
  README keeps the checklist word for word, and adds the gesture beside it; `CONTRIBUTING.md`
  is unchanged.
- **Data**: nothing is collected, nothing is stored. The credential lives in the environment of
  one run.
