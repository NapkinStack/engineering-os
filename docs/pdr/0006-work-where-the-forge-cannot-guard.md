# PDR-0006 — Work on a repository the forge cannot guard

- **Status**: Proposed (2026-09-20)
- **Date**: 2026-09-20
- **Decision makers**: NapkinStack maintainers (`@NapkinStack/maintainers`)
- **Modules affected**: the project skeleton (its workflows, README and checklist), `nstack
  doctor` and `nstack init`, `PRODUCT.md` §3

> The PDR describes **what the product must do and why**, never its implementation.
> The how belongs to the implementation plan and, where structuring, to an ADR.

---

## User problem

One person, working with agents, on a private repository of their own. This is the most
common shape of the work NapkinStack exists for, and it is the shape the framework serves
worst today.

**What GitHub allows them.** On a private repository under the Free plan, nothing can refuse
anything. Rulesets and protected branches are ["available in public repositories with GitHub
Free"](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/about-rulesets)
and in private ones only from a paid plan; [code
owners](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-code-owners)
follow the same rule; merge queues and pre-receive hooks are out of reach; secret scanning
and push protection are public-only. Actions still run — 2,000 minutes a month — but a
failing check blocks no merge, because making a check required needs the same paid plan.
Checked again on 2026-09-20, with the escape routes closed one by one: **no permission, no
fork, no deploy key produces a "may push a branch but may not merge" identity.** `Contents:
write` is repository-wide and merges pull requests; a private repository cannot be forked
into a Free organisation. The community asks GitHub for a free barrier in several open
discussions; today there is none.

**What the framework answers them.** `nstack doctor` reports seven gaps and repeats that the
GitHub Team plan is required. Every line is true and the whole is useless: it reads as a
verdict on the person rather than on their plan, it can never become compliant however much
they do, and it gives no next step that costs nothing.

**And the silence is the real cost.** When an agent pushes straight to `main` on a Friday
evening, nothing refuses it — that is the plan's limit, and no framework can change it — but
nothing *says* it either. The commit is found later, by someone chasing a bug. The framework
that promises "an unmergeable pull request rather than debt in `main`" (`PRODUCT.md` §3) has,
for this user, neither the refusal nor the record.

## Goal

A person working alone with agents, on a repository the forge cannot guard, gets the
framework's value, an exact statement of what holds and what does not, and no violation of
the flow that happens in silence.

## Out of scope

- **Inventing a barrier the forge does not have.** Verified on 2026-09-20: there is none to
  invent. A decision that pretended otherwise would be the defect this product exists to
  refuse.
- **An agent-side hook** that intercepts the agent on the workstation. Refused in the options
  below, on invariants P2 and P3.
- **Changing what "published" means**, or the channels a project installs the framework from:
  that is ADR-0002's, clarified separately.
- **Telemetry.** Nothing is collected, here as everywhere.
- **Forges other than GitHub**, and paying on the user's behalf.

---

## Prior art

> **Mandatory section.** Minimum two named references.
> (`skeleton/docs/os/06-decisions.md` §2)

**How is this problem solved elsewhere?**

| Product / reference | Solution chosen | What we keep from it |
|---|---|---|
| [GitHub rulesets, `Evaluate` mode](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/about-rulesets) (Enterprise) | A ruleset that runs and **records** violations without blocking, so a team sees what a rule would refuse before enforcing it | **The shape.** When you cannot prevent, record — and GitHub itself ships that as a distinct, named mode rather than as a weak barrier |
| AWS Config and the preventive/detective vocabulary of security engineering | Controls are split by what they do: prevent, detect, correct. A detective control is a first-class deliverable, not a failed preventive one | **The vocabulary**, and the permission to ship a record as a deliverable — provided it is named as one |
| [pre-commit](https://pre-commit.com/) | Local hooks, and the field's standing warning that a hook is bypassable; the real gate lives in CI | Our invariant P3, applied to ourselves: what is bypassable is never sold as a guarantee |
| [Claude Code's own documentation](https://code.claude.com/docs/en/memory) | *"Claude treats them as context, not enforced configuration. To block an action regardless of what Claude decides, use a PreToolUse hook instead."* | The vendor of the agent draws the line itself: instruction is not enforcement |
| [GitHub Spec Kit](https://github.com/github/spec-kit), BMAD-METHOD, Agent OS, Task Master | None of them says a word about the forge's plan, or about what happens when nothing can refuse. Spec Kit's gates — *"the LLM cannot proceed without either passing the gates"* — are markdown checkboxes the model ticks about its own work | **The gap this decision fills**, and the counter-example: a gate that judges itself is what our P5 exists to forbid |

**The convention the user already knows:** a tool tells you what it enforces and what it only
observes — `terraform plan` before `apply`, a linter's warning beside its error, a dry run
before the real one.

**Why depart from it:** on one point only. The tools above describe a *mode the user chooses*;
here the mode is imposed by the repository's plan, and the user often does not know it. So
the state is not an option to select: it is **read and named by the tool, on every
diagnosis**, and it changes what the tool claims about itself.

---

## Options considered

| Option | What the user experiences | Cost | Chosen? |
|---|---|---|---|
| Do nothing | Seven gaps, a plan to buy, no path that costs nothing; a direct push to `main` stays invisible | 0 | No. It serves worst the user most exposed to an unsupervised agent |
| A. Name the state | The diagnosis separates what is enforced from what is not and names the three exits; nothing else changes | Very low | Half of it. The Friday evening push is still silent |
| **B. Name the state, and record what nothing can refuse** | The same, plus a run that fails and names any commit that reached `main` outside a pull request — on every repository, guarded or not | Low — one workflow, no new permission | **Yes** |
| C. B, plus a hook on the workstation that stops the agent | Looks like a barrier, is bypassable, needs an adapter per agent | Medium, and it costs the product its honesty | No. It breaks P2 (portable rules) and P3 (enforcement in CI), and it is exactly the claim we hold against others |
| D. Require a guarded repository | The framework refuses to serve an unguarded one | Low | No. Most of the value — the method, the checks, the sheet, the boundaries — holds without the forge, and refusing would push people to claim a compliance they do not have |

## Decision

**Option B.** The product learns two words, states one rule, and ships one record.

**Guarded, or unguarded.** A repository is **guarded** when the forge refuses on its own —
the rules the checklist asks for are in force. It is **unguarded** when nothing there refuses,
for either of two reasons the diagnosis keeps apart: a setting **out of reach on this plan**,
which the project can do nothing about, and a setting **not yet in place**, which it can. A
public repository can be guarded at no cost, on any plan; a private one needs a plan that
enforces rules. The state is read by the tool, never declared by the project, and never
guessed: what cannot be read is "not verified", and "not verified" is never "guarded".

**The diagnosis answers in three blocks** — what is enforced here, what nothing enforces here,
and what it would take to change that, with its price. On an unguarded repository, a project
that has done everything its plan allows is told so, and the word *unguarded* appears on
every diagnosis for as long as it holds. A project is therefore never asked to buy a plan in
order to stop being reported as faulty; it is asked to know where it stands.

**What nothing can refuse is recorded.** Every project receives a check that fails when a
commit reaches `main` outside a pull request, on any repository — on an unguarded one because
nothing else will ever say it, on a guarded one because an administrator can still step
around the rules. It needs no write access, so it changes nothing about what the project's
automation is allowed to do.

**And the record is never sold as a barrier.** It names itself for what it is in its own
output: this did happen, nothing here could refuse it, and you are being told rather than
protected. The rule that binds this decision to [PDR-0005](0005-work-on-the-framework-while-using-it.md)
is the same sentence one step further:

> A project may be judged by rules nobody published, provided it is never judged in silence.
> A project may run where nothing can refuse, provided it is never **walked around** in
> silence.

---

## Expected behaviour

**Nominal journey.** Someone creates a project on their own private repository, free plan.
`nstack init` prints the checklist and marks the settings their plan cannot reach, naming the
three exits: make the repository public, where everything works at no cost; move to a plan
that enforces rules; or continue, knowing what holds. They do what they can, run the
diagnosis, and read: *unguarded — these checks run and tell the truth; nothing here refuses a
merge*. They work with their agent behind pull requests, and their test sheets are signed by
a second agent session, which the checks verify. Weeks later an agent pushes straight to
`main`; a run fails within the minute, names the commit, and says nothing here could have
refused it. They see it that evening instead of the following Monday.

**Nominal journey, guarded repository.** Nothing changes, beyond the new check, which passes
on every commit that arrived through a pull request.

**Edge cases and degraded states.** A repository whose settings cannot be read — no token, or
a token without the permission — is "not verified", never "guarded". A repository made public,
or moved to a plan that enforces rules, becomes guarded on the next diagnosis with no action
of the project's. **The record says nothing about what predates it**: the commit that created
the project, and everything a repository already held when it adopted the framework, are not
reported — a record that greets a new project by failing on its own arrival teaches people to
ignore it. A repository that was unguarded and became guarded keeps the record: it is what
catches a bypass.

**Business rules.**

- The state is read, never declared, and what cannot be read is never favourable.
- A detective control names itself as one, wherever it speaks.
- The three exits are stated with their cost, including the one that costs nothing.
- No output claims a barrier the repository does not have.

**Permissions:** unchanged, and deliberately so. The record reads what the forge already
exposes to a read-only automation token, so the rule that the project's automation writes
nothing (G10) stands untouched.

**Acceptance criteria** *(testable)*:

- [ ] Given a private repository on a plan that enforces nothing, when the diagnosis runs,
      then it names the repository unguarded, separates what is enforced from what is not,
      and names the three exits with their cost.
- [ ] Given that repository with every setting its plan allows in place, when the diagnosis
      runs, then it reports success, and the word *unguarded* still appears.
- [ ] Given a guarded repository, when the diagnosis runs, then the word *unguarded* appears
      nowhere.
- [ ] Given a repository whose settings cannot be read, when the diagnosis runs, then the
      state is "not verified" and never "guarded".
- [ ] Given a commit that reached `main` outside a pull request, when the record runs, then
      it fails, names the commit, and says that nothing here could refuse it.
- [ ] Given a commit that reached `main` through a merged pull request, when the record runs,
      then it passes.
- [ ] Given the commit that created the project, or any commit older than the record itself,
      when the record runs, then it passes.
- [ ] Given any output of the tool on an unguarded repository, then no sentence presents the
      record, the hooks or the checks as something that blocks a merge.
- [ ] Given the project creation on an unguarded repository, then the checklist marks the
      settings out of reach and names the exits.

---

## Success criterion

> **Mandatory section.** Without a date nobody comes back to check, and the decision folder
> becomes a graveyard.

> We will consider this was the right call if, before **2027-03-31**, on a **private
> repository of the free organisation created from the published version**: the diagnosis
> names it unguarded and reports success once every reachable setting is in place; a
> deliberate direct push to `main` is reported by the record in the same run; and over the
> pilot's first two cycles **no output of any command presents a barrier the repository does
> not have** — measured the way M9 and M10h measured, by probes whose expected outcome is
> written before they run.

How it is observed: the probe repository and its runs; the diagnosis output on both a guarded
and an unguarded repository, kept as evidence; the pilot's own runs read for any sentence that
overstates what holds.

If the criterion is not met: a record that cannot fire on a real direct push is a check that
guards nothing and goes; a diagnosis still read as a verdict on the person is a wording
problem and is rewritten, not removed.

---

## Removal condition

> **Mandatory section.** A feature with no removal condition is permanent by default,
> including when nobody uses it.

This decision will be removed if, over the pilot's first two cycles, **the record fires only
on legitimate flows** — noise a team learns to ignore is worse than nothing — or if a reader
takes *unguarded and compliant* for *protected*: the first person who says so ends that
wording. The two words go with it if the distinction turns out to be one nobody needs: a
framework that has to explain its own vocabulary before being useful has already failed.

---

## Impacts

- **Existing users**: none today beyond the pilot and the validation project, both guarded.
  They gain the record, which passes on every commit that came through a pull request.
- **Modules and contracts**: none.
- **Decisions**: **PDR-0005** is extended in spirit, not changed — its rule about silence now
  has a second half. **PDR-0001**'s checklist keeps its content and gains marks for what a
  plan cannot reach. **ADR-0002** untouched; the channels a project installs from are
  clarified separately. **PDR-0003** unchanged and newly relevant: its verifier may be an
  agent session, which is how a person working alone still gets a sheet signed by someone
  other than the author.
- **Support and documentation**: `PRODUCT.md` §3 gains the user this decision serves and §7
  the state; the project's own README says what its plan enforces; the handbook names the two
  words where it describes the checks.
- **Data**: nothing is collected. The state is read from the forge at diagnosis time and kept
  nowhere.
