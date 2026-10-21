# PDR-0016 — A cycle's progress is shown where the decider looks, and kept nowhere else

- **Status**: Proposed (2026-10-21). Asked by the maintainer: *can't we see progress properly in
  GitHub, as a timeline in Jira?* (#220), under two rules they set as absolute the same day — the
  repository is the single source of truth; no manual intervention on a forge
- **Date**: 2026-10-21
- **Decision makers**: NapkinStack maintainers (`@NapkinStack/maintainers`)
- **Modules affected**: the engine (a display of the plan), the skeleton's CI on the default
  branch, the project's handbook page

> The PDR describes **what the product must do and why**, never its implementation.
> The how belongs to an ADR.

---

## User problem

A decider follows the project from where they already are — the forge, often on a phone. nstack
keeps the plan in the repository (`docs/project/cycles/`), and since D138 says it in one line in
`nstack plan`; nothing of it appears on the forge. To see a cycle's progress they open a YAML
front matter, run a command, or ask the agent.

The tools they know show it on the forge: Jira's timeline, Linear's cycles, GitHub's milestones
and Projects. Those tools hold the plan themselves — the board **is** the truth, edited by hand —
which nstack refuses: a board and a file that disagree are two truths, and a board kept by hand
is the manual work that slows adoption.

## Goal

Every accepted cycle and its deliverables are visible on the forge — progress, end date, who
holds what, the pull requests — at all times, with no person maintaining it, and never as a
second truth: the forge shows what the repository says, and nothing else.

## Out of scope

- **Planning on the forge.** Creating or changing a deliverable stays a change of the cycle
  file, reviewed in a pull request. A display edited by hand is overwritten, and said.
- **A board for every forge now.** GitHub first; another forge when the work on forges other than GitHub (#223)
  names it — until then, said "not shown".
- **A timeline across cycles (GitHub Projects' Roadmap) in this step.** It needs an organisation
  permission and a project made once; decided after the milestone has been lived with.
- **Measuring people.** Who holds a deliverable is shown; nothing ranks anyone.

---

## Prior art

| Product / reference | Solution chosen | What we keep from it |
|---|---|---|
| [GitHub milestones](https://docs.github.com/en/rest/issues/milestones) | A title, a description, a due date, open and closed issues — the forge draws the progress bar | **The cycle as a milestone**: its end date, a bar for free |
| [GitHub Projects](https://docs.github.com/en/issues/planning-and-tracking-with-projects) | Boards, tables, a Roadmap by iteration or dates; fields set through the GraphQL API | **Later, if asked**: one iteration per cycle |
| [gh-roadmap](https://github.com/zazabe/gh-roadmap) | A markdown roadmap applied to issues and Projects — and pulled back | **Apply from files**; not the pull back: one truth |
| Jira, Linear | The tool is the plan; boards edited by hand | **The views people know**, not where the truth lives |
| nstack's own displays (ADR-0006, ADR-0007) | A record or a hold in git, shown on GitHub one way, refusals said | **The same contract**: git's truth, the forge's view |

**The convention the user already knows:** a milestone with its progress bar and due date, its
issues ticked off as they close.

---

## Options considered

| Option | What the user experiences | Cost | Chosen? |
|---|---|---|---|
| Do nothing | `nstack plan`, or the agent | 0 | No |
| A. Plan on the forge (Projects as the truth), the repository follows | The board they know — and two truths, kept by hand | High, and against the rules | No |
| **B. The repository's plan applied to the forge, one way, by CI on every merge** | A milestone per cycle, an issue per deliverable, always current, never touched | Medium | **Yes** |
| C. B, plus a Project and its Roadmap | A timeline across cycles | High: an organisation permission, GraphQL | Later, if B is not enough |

## Decision

**Option B.**

1. **A cycle is a milestone**: its goal as description, due on its end date; closed when the
   cycle is closed or stopped.
2. **A deliverable is an issue in it**: its title, its acceptance criteria, its module, a label
   for its state, its holder (assigned when the forge knows the person), the pull requests that
   name it. Closed when accepted or dropped; reopened if its state goes back.
3. **Applied by the engine, on every merge to the default branch**, by the project's CI — no
   person runs it, no click is asked; a person may run it by hand to see it at once. Nothing on
   the forge is ever read back as the plan.
4. **A display edited by hand is overwritten** at the next run, and the run says what it
   overwrote. An issue or a milestone the display did not make is never touched.
5. **Said, never failed**: no forge, no token, a refusal — the run says what was not shown; it
   never fails a merge.

---

## Expected behaviour

**Nominal journey.** The decider accepts D30 in the cycle file; the pull request merges; a
minute later, on their phone, the milestone *Cycle 03 — the window* reads 10 of 15 closed, due
7 November, and D30's issue is closed.

**Edge cases.** Someone renames D31's issue on GitHub: the next run puts the title back and says
so. A deliverable dropped: its issue is closed as not planned. A private repository on a free
plan: milestones and issues are available on every plan. A project off GitHub: "not shown".

**Acceptance criteria** *(testable)*:

- [ ] Given an accepted cycle, then a milestone with its goal and end date exists, and one issue
      per deliverable in it, after one run.
- [ ] Given a deliverable accepted in the file, then its issue is closed at the next run.
- [ ] Given an issue of the display edited on the forge, then the next run restores it and says so.
- [ ] Given an issue the display did not make, then no run changes it.
- [ ] Given no token or no GitHub remote, then the run says "not shown" and exits successfully.
- [ ] Given the project's CI, then the display runs on every merge to the default branch with no
      person's gesture.

---

## Success criterion

By 2027-03-31: on the third project, the decider follows two consecutive cycles from the forge's
milestone alone, without opening the cycle file or asking the agent, and no display issue was
ever edited by hand without the next run saying it.

## Removal condition

Removed if the forge's display and the cycle file are found to disagree after a run — the one
thing it must never do — and it cannot be made to hold.

## Impacts

- **The engine**: a display of the plan, and its run in CI.
- **The skeleton**: the default branch's workflow runs it, with the one write permission it needs;
  the project's handbook page says where progress is seen.
- **Projects**: one milestone per accepted cycle and its issues appear after the update; nothing
  to set by hand.
- **The how** — the marker that tells a display issue from others, labels, the CI permission,
  the order of calls — goes to an ADR.
