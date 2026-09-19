# PDR-0005 — Work on the framework while using it, and never be judged in silence

- **Status**: Accepted (2026-09-18, by the maintainer; the success criterion is observed on
  2027-03-31); implemented in v0.4.0 (M10g): every judging run names the framework that
  judges, CI installs an unpublished pin from the repository and says so, `doctor` never
  calls it compliant (L1, L7), and `CONTRIBUTING.md` names the contributor's loop.
- **Date**: 2026-09-18
- **Decision makers**: NapkinStack maintainers (`@NapkinStack/maintainers`)
- **Modules affected**: the project skeleton (its workflow), `nstack` checks, `CONTRIBUTING.md`

> The PDR describes **what the product must do and why**, never its implementation.
> The how belongs to the implementation plan and, where structuring, to an ADR.

---

## User problem

A tech lead uses NapkinStack on a real project and hits a defect in the framework itself: a
check that fires where it should not, a rule that contradicts another, a message that
promises what the check does not hold. That is not a hypothesis. One day of real use on the
validation project produced eight such findings.

Two things then stand between them and a fix.

**The first is undocumented, and it already works.** To see whether a change to the
framework actually helps, you have to judge a real project with an unpublished engine. The
engine can already do it — `nstack <verb> --root <the project>` judges another tree, and
`nstack init --source <a local checkout>` already accepts a path, which is how this
repository's own platform tests run. Nothing anywhere says so. A contributor has to
discover it, or give up.

**The second is closed.** A project cannot be judged by an unpublished framework at all: its
CI reads `_commit` from `.copier-answers.yml` and resolves `napkinstack==<version>` from
PyPI, so a branch simply fails. A fix therefore cannot be tried in the place it matters —
the project that exposed the defect — before a release exists.

The consequence is the one `PRODUCT.md` P6 names for checks, arriving one level up: what
cannot be fixed gets worked around. A team that cannot try a fix upstream adapts its own
project around the defect, and the framework never learns.

## Goal

A contributor can judge a real project with an unpublished framework in one documented
command; and a project may be pinned to an unpublished framework, provided it can never be
silent about being judged by one.

## Out of scope

- **Replacing PyPI.** ADR-0002 stands unchanged: PyPI is the only **published** channel, a
  published version is a `vX.Y.Z` tag, and publication is refused otherwise. This decision
  adds a marked path for what is *not* published; it removes nothing.
- **An installer that clones the framework** into a fixed directory, the way an agent
  distributes itself. Refused, with its reason in the decision below.
- **Editable installs of the engine inside a project**, and any mechanism that lets a
  project's own tree carry framework code.
- **Going back to an earlier version**: already excluded by PDR-0001.
- **The resolution mechanism itself** — how CI decides between the registry and the forge.
  `PDR-0001` puts distribution in an ADR's hands; this document states the guarantee, and an
  ADR records the mechanism if it turns out structuring.
- **Forges other than GitHub**, a web interface, a service.

---

## Prior art

> **Mandatory section.** Minimum two named references.
> (`skeleton/docs/os/06-decisions.md` §2)

**How is this problem solved elsewhere?**

| Product / reference | Solution chosen | What we keep from it |
|---|---|---|
| [pre-commit](https://pre-commit.com/) | `repo:` accepts anything `git clone` understands, including a local path, and [`try-repo`](https://deepwiki.com/pre-commit/pre-commit/2.1.5-try-repo) exists **only** to try a hook repository from a local checkout before proposing it upstream — it even clones uncommitted changes | **The model.** The contributor's path is named, separate from the user's path, and belongs to the tool rather than to folklore |
| Bundler — `gem "rails", github: "rails/rails"` | An application may run on an unreleased framework, and the exact ref is written into the lockfile, where everyone reading the project sees it | **The condition.** Running on something unpublished is allowed, and it is recorded where it cannot be missed |
| [Hermes Agent](https://github.com/NousResearch/hermes-agent/blob/main/website/docs/getting-started/installation.md) (Nous Research) | The installer clones a full git checkout into a fixed directory, and the contributing guide tells contributors to work from that same checkout | The ambition — one gesture to use and to contribute. **Not the mechanism**: see the deviation below |
| [GitHub Spec Kit](https://github.com/github/spec-kit) | The documented install *is* the git install: `uvx --from git+<repository> specify init` | That installing from the forge is the field's default in this niche, not an exotic path |
| [uv](https://docs.astral.sh/uv/pip/packages/) | `uv tool install git+<repository>@<ref>`, `uvx --from git+<repository>@<ref>`, `--editable` | The machinery, already there. Nothing has to be written for the mechanism itself |

**The convention the user already knows:** you install a tool from the forge, and when your
project runs on an unreleased version of something, the ref is written down where every
reader of the project sees it.

**Why depart from it:**

Only on one point, and it follows from what NapkinStack is. The other tools are used; this
one **judges**. A linter running from a branch produces slightly different advice. A
framework running from a branch produces a different verdict on whether a project is
compliant — and the project can then claim compliance under rules its own author wrote.

Bundler records the ref in a file. That is enough for a library. It is not enough for a
referee, because a file is read by whoever chooses to read it, while a verdict is read by
everyone. So the ref is not only recorded: **the tool says it, out loud, on every run that
it judges.**

The Hermes model — the installer clones, and you work in that clone — is rejected for the
same reason. Hermes *is* the thing you run and shape; it is yours, and mutable by design.
NapkinStack is the thing that tells you no. A referee whose rulebook each player edits
locally has stopped being a referee.

---

## Options considered

| Option | What the user experiences | Cost | Chosen? |
|---|---|---|---|
| Do nothing | The contributor rediscovers an undocumented path or gives up; a fix cannot be tried on the project that exposed the defect | 0 | No. Eight findings in one day, and every one of them needed that path |
| A. Document the contributor loop only | The loop is named and supported; a project still cannot be pinned to an unpublished framework | Very low | Half of it. Keeps the second problem closed |
| B. Document the loop, and let the escape hatch declare itself | The loop is named; a project may be pinned to a ref, and both the tool and the diagnosis say so on every run | Low — the mechanism exists in `uv`, the paths exist in the engine | **Yes** |
| C. An installer that clones, and a development mode | One gesture to use and to contribute, as the field mostly does | High, and it dissolves the property the product sells | No |

## Decision

**Option B**, in two halves that answer two different needs, and one rule that binds them.

**The contributor's path is named and supported.** Judging a real project with an unpublished
framework is a documented, tested gesture: the engine already judges another tree, and
already accepts a local checkout as the template source. It becomes a section of
`CONTRIBUTING.md` rather than a discovery, and it is exercised where the platform tests
already exercise it, so it cannot rot.

**A project may be pinned to an unpublished framework.** What its CI resolves follows what
the project recorded: the registry for a published version, the forge for anything else.

**And it can never be silent about it.** This is the rule, and the decision is worth nothing
without it:

> A project judged by an unpublished framework is told so, by the tool, on every run that
> judges it — not only in a file that someone may read. The diagnosis reports it as a named
> gap, and so is a template source that exists on one machine only.

A project may therefore be judged by rules that nobody has published. It may not be judged
by them **quietly**, and it can never present that state as compliance. The escape hatch
exists, it is one line to take, and it announces itself for as long as it is held open.

---

## Expected behaviour

**Nominal journey — the contributor.** A team hits a defect while working. They clone the
framework, change it, and judge their own project with the changed engine, in one command
they read in `CONTRIBUTING.md`. They see the effect on their real repository before
proposing anything, and their pull request upstream carries that evidence.

**Nominal journey — the project.** Nothing changes for a project on a published version,
beyond one line naming the version that judged the run. A project that pins a ref keeps
working, and every one of its runs says which unpublished framework judged it.

**Edge cases and degraded states.** A ref that no longer exists on the forge fails loudly at
resolution rather than falling back to a published version — a silent fallback would judge
the project by rules nobody asked for. A template source that is a path on one machine is
reported for what it is: something no one else can reproduce.

**Business rules.** The three of the decision above.

**Permissions:** unchanged. Pinning a ref is a change to a tracked file, so it goes through
the same approval as everything else.

**Acceptance criteria** *(testable)*:

- [ ] Given a project on a published version, when any check runs, then its output names the
      framework version that judged it.
- [ ] Given a project whose recorded version is not a published tag, when any check runs,
      then the output says the framework is unpublished and names the ref.
- [ ] Given that same project, when the diagnosis runs, then it reports the unpublished
      framework as a named gap, and never reports the project as fully compliant.
- [ ] Given a project whose template source is a path on one machine, when the diagnosis
      runs, then it reports it.
- [ ] Given a ref that does not exist, when CI resolves the framework, then it fails and
      names the ref, and no published version is used in its place.
- [ ] Given `CONTRIBUTING.md`, then the contributor loop is written there, and the commands
      it names are the ones the platform tests already run.

---

## Success criterion

> **Mandatory section.** Without a date nobody comes back to check, and the decision folder
> becomes a graveyard.

> We will consider this was the right call if, before **2027-03-31**, **at least two defects
> of the framework are fixed by the person who hit them**, each one verified against their
> own project before the fix was published — **and** no project is found being judged by an
> unpublished framework without saying so in its own output.

How it is observed: the pull requests upstream, which carry the evidence produced against a
real project; and the checks' output on any project pinned to a ref.

If the criterion is not met: the first half failing means the loop was documented and nobody
used it — the problem was not discoverability, and the section goes. The second half failing
is more serious: it means the escape hatch can be held open quietly, and the decision is
superseded rather than adjusted.

---

## Removal condition

> This decision will be removed if the escape hatch is used to avoid a rule rather than to
> propose a change — a project pinned to a ref across more than one release with no pull
> request open upstream — or if the contributor's loop turns out to need machinery beyond
> what the engine and `uv` already do, since the whole argument for it is that it costs
> almost nothing.

---

## Impacts

- **Existing users**: none today. Once built, a project on a published version behaves as it
  does now, plus one line naming the version that judged it.
- **Modules and contracts**: none.
- **Decisions**: **ADR-0002 stands** — PyPI remains the only published channel and a
  published version remains a `vX.Y.Z` tag. **PDR-0001** is extended, not contradicted: it
  left distribution to the ADRs and never said whether a project may be judged by something
  unpublished. This document answers that, and leaves the mechanism to an ADR if it proves
  structuring.
- **Support and documentation**: `CONTRIBUTING.md` gains the contributor loop. The project
  checklist gains nothing: this is not a GitHub setting.
- **Data**: nothing is collected. The framework version comes from a file the project
  already carries.
