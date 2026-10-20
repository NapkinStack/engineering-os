# PDR-0015 — A contributor sees who holds a deliverable

- **Status**: Proposed (2026-10-20). Asked by the maintainer: *how do agents know what they
  must or may take, and how is the work shared out?* (#212); the market was surveyed and the
  direction below agreed with them before this record
- **Date**: 2026-10-20
- **Decision makers**: NapkinStack maintainers (`@NapkinStack/maintainers`)
- **Modules affected**: the engine (a new verb, `plan`, `pr-check`), the skeleton's
  `CONTRIBUTING.md` and handbook (`05-workflow.md`, `09-platform.md`, the glossary), the kernel,
  `RULES.md`

> The PDR describes **what the product must do and why**, never its implementation.
> The how belongs to an ADR.

---

## User problem

A project with two contributors or more, each working with an agent of their choice — a coding
agent on their workstation, or a forge's cloud agent. nstack tells every agent **what may be
taken**: a `ready` deliverable of the accepted cycle, in one module (K3; `09-platform.md`,
*pick up a ready deliverable*). It tells **who approves**: the module's owner. It never tells
**who has taken it**.

Nor is it written, in one place a newcomer reads, how several contributors share a project:
the pieces are in the handbook — postures (`05-workflow.md`), modules and owners (`02-modules.md`),
contracts (`03-contracts.md`), the newcomer's path (`09-platform.md`) — and `CONTRIBUTING.md`
speaks to one contributor. The maintainer had to ask the agent how a second contributor would
join, and whether their agent had to be Claude.

Observed (#212): a deliverable's `in-progress` is a line of the cycle file on `main`, changed by
a merged pull request — after the work, never before it. No field names who holds a
deliverable; `nstack plan` cannot say it; nothing stops two sessions from starting the same
deliverable, and `pr-check` accepts both pull requests. Unseen so far: the third project has
had one author.

## Goal

Before writing a line, a contributor — person or agent, on any forge — knows whether a
deliverable is free, takes it in one gesture that a second taker cannot also win, and everyone
sees who holds what and since when; a hold nobody works on is seen and released.

## Out of scope

- **A backlog, a board, priorities.** The cycle stays the one list of work; the decider orders
  it at framing.
- **Locking files or modules.** One deliverable is one module already; within a module, a
  conflict is git's to show at merge.
- **Assigning work to someone.** The decider chooses the deliverables; who takes one is the
  contributors' gesture, not a dispatch.
- **Measuring people.** A hold says who is accountable, not how fast they are.

---

## Prior art

| Product / reference | Solution chosen | What we keep from it |
|---|---|---|
| [GitHub Agent HQ](https://github.blog/news-insights/company-news/pick-your-agent-use-claude-and-codex-on-agent-hq/) | Assign an issue to Copilot, Claude or Codex; the agent opens a draft pull request | **A draft pull request shows the work from its start** — on a forge, as a display |
| [Linear agents](https://linear.app/developers/agents) | The agent is the issue's *delegate*; a human stays accountable; a session can go `stale` | **A person accountable for every agent's hold**, and **an abandoned hold is seen** — and handed on without an administrator |
| [Rust triagebot `claim`](https://forge.rust-lang.org/triagebot/issue-assignment.html) | Claim an issue by a comment; released by the holder or a team member | **Release by the holder or the decider**, never silently — and not its gap: with no expiry, dead claims pile up and wait for a team member |
| [Beads](https://pkg.go.dev/github.com/steveyegge/beads@v0.24.3) | A git-backed tracker; agents take the top unblocked task | **The record lives in git**, no service required |
| [Claude Code agent teams](https://www.morphllm.com/claude-code-agent-teams) | A shared task list; a claim under a file lock | **A second claim fails**, it is not merely discouraged |

**The convention the user already knows:** assigning oneself an issue, and a draft pull request
saying *I am on it*.

---

## Options considered

| Option | What the user experiences | Cost | Chosen? |
|---|---|---|---|
| Do nothing | Two agents on one deliverable; found at review | 0 | No |
| A. The forge's assignee on an issue per deliverable | Native on GitHub; nothing on another forge or for a workstation's agent; two assign themselves at once and both "win" | Low | Display only |
| B. A tracker built for agents (Beads, Linear) | One more tool, a second backlog beside the cycle; Beads is alpha, Linear proprietary | Medium | No |
| **C. A hold recorded in git, that git itself refuses twice; shown on the forge; read by `plan` and `pr-check`** | One gesture on any forge and with any agent; the second taker is told who holds it | Medium | **Yes** |

## Decision

**Option C.**

1. **Take.** `nstack claim D<n>` takes a `ready` deliverable of the accepted cycle for the
   current session, naming the person accountable for it. It refuses a deliverable that is not
   `ready`, outside the cycle, or already held — saying by whom and since when. Two contributors
   taking the same deliverable at the same moment: one wins, the other is refused; the shared
   remote decides, not a convention.
2. **Shown.** On a forge that has pull requests, the hold opens a draft pull request naming the
   deliverable, so a person sees it where they look.
3. **Seen.** `nstack plan` says, for each deliverable of the cycle: free, held — by which person
   and session, since when, last worked on when — or stale: held with no work for longer than
   the project allows (a week by default).
4. **Released, or taken over.** The holder releases it; the decider may release anyone's, at
   any time. A stale hold may be **taken over** by any contributor, in a gesture of its own —
   never automatically, never silently: the take-over is recorded (who, when, from whom), the
   previous holder is told where the forge allows it, and their work is kept for the new holder
   to start from. A hold that is not stale cannot be taken over. A deliverable merged or
   `dropped` frees itself. One absent person — the holder or the decider — never blocks a
   deliverable for longer than the project's limit.
5. **Checked.** `pr-check` refuses a pull request delivering a deliverable that another session
   holds, with a rule of its own, and says who holds it.
6. **Told.** The kernel tells an agent to take a deliverable before its first change, and to
   stop if it is held; the glossary defines *hold*.
7. **Written for a newcomer.** `CONTRIBUTING.md` gains *Working with several contributors*: how
   work is shared — by module, each with its owner; how a contributor joins — the forge's
   invitation, the module's `owner` and `CODEOWNERS`, nstack installed; that any agent reading
   `AGENTS.md` works, the generated skills being one tool's convenience; and taking a deliverable
   before the first change. A short section that points into the handbook, never a copy of it;
   it ships with the verb, so it never describes a command that does not exist.

---

## Expected behaviour

**Nominal journey.** Two contributors, two agents. Alice's agent runs `nstack claim D30`; it is
held by Alice, session `capture-d30-resume`, and a draft pull request appears. Bob's agent runs
`nstack plan`, sees D30 held and D31 free, and takes D31.

**Edge cases.** Bob's agent tries D30 a second later: refused, *held by Alice since 10:02*. Alice
stops for two weeks: `plan` says D30 is stale; Bob takes it over, starting from Alice's work, and
Alice is told — the decider was not needed. Bob tries to take over a hold Alice worked on
yesterday: refused, it is not stale. A project
with no forge: the hold and its refusal work the same; there is no draft pull request, and the
command says so.

**Acceptance criteria** *(testable)*:

- [ ] Given a `ready` deliverable nobody holds, when a session claims it, then it is held by that
      session and its accountable person, and `plan` says so.
- [ ] Given two sessions claiming one deliverable against one remote, then exactly one holds it
      and the other is told who does.
- [ ] Given a deliverable not `ready`, or outside the accepted cycle, then the claim is refused,
      saying why.
- [ ] Given a hold older than the project's limit with no work on it, then `plan` says it is stale.
- [ ] Given a pull request delivering a deliverable another session holds, then `pr-check` fails,
      naming the holder.
- [ ] Given the holder or the decider releasing it, then the deliverable is free again.
- [ ] Given a stale hold, when another contributor takes it over, then they hold it, the take-over
      is recorded with the previous holder, and the previous holder's work is kept.
- [ ] Given a hold that is not stale, then a take-over is refused, saying when it would become
      stale.
- [ ] Given a repository with no forge, then claiming, refusing and releasing behave the same.
- [ ] Given the skeleton's `CONTRIBUTING.md`, then it says how work is shared by module, how a
      contributor joins, that the agent is the contributor's choice, and to take a deliverable
      before the first change — each pointing to the handbook page that holds the detail.

---

## Success criterion

By 2027-03-31: on a project with two contributors or more, no deliverable is delivered by two
pull requests, and every pull request of a cycle's deliverable was preceded by its hold — on
the third project once it has a second contributor, and on one project off GitHub.

## Removal condition

Removed if, over two minor versions, projects with several contributors hold no deliverable
before working on it — the gesture then costs more than the collisions it prevents.

## Impacts

- **The engine**: a new verb (take, release), a section of `plan`, a rule of `pr-check`.
- **The skeleton**: `CONTRIBUTING.md` gains *Working with several contributors* and its first
  step becomes *take a ready deliverable*; `05-workflow.md` and `09-platform.md` say when to take
  a deliverable; the kernel tells the agent; the glossary gains *hold*; `RULES.md` the new rule.
- **Projects**: nothing changes for one contributor until they claim; the `pr-check` rule
  refuses only a pull request whose deliverable another session holds.
- **The how** — where the hold is recorded, how git refuses the second, what counts as work on
  a hold and how staleness is measured, how a take-over is recorded and told, the forge's
  display — goes to an ADR.
