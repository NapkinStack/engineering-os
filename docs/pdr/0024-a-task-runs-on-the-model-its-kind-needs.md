# PDR-0024 — A task runs on the model its kind needs

- **Status**: Proposed (2026-11-24, D280), from the maintainer's request to spend fewer tokens
  where a smaller model does the work as well, on any agent tool. Its first step is a
  measurement on a project, before anything is built
- **Date**: 2026-11-24
- **Decision makers**: NapkinStack maintainers (`@NapkinStack/maintainers`)
- **Modules affected**: the AI-context handbook, the tooling profile, the skills generator

> The PDR describes **what the product must do and why**, never its implementation.
> The how belongs to an ADR.

---

## User problem

An agent working in a project spends most of its tokens reading: it finds where a rule is
written, which files call a function, and what a log says. It does that reading on the model it
was started with, which is the strongest and most costly one, chosen for the hard part of the
work. NapkinStack says nothing about it. Its tooling profile has a row, *Specialised agents —
independent review, isolated investigation*, that no project fills.

Every major agent tool now lets a repository declare an agent of its own with its model, but none
of them in the same way:

| Tool | Declared in the repository | Its model |
|---|---|---|
| Claude Code | `.claude/agents/*.md` | `model:` `haiku`, `sonnet`, `opus`, an id, or `inherit`; delegated by its description |
| Cursor | `.cursor/agents/*.md`, and reads `.claude/agents/` | `model:` an id or `inherit`; falls back when the plan refuses it |
| Gemini CLI | `.gemini/agents/*.md` | `model:`, `inherit` by default |
| GitHub Copilot | `*.agent.md` | `model:`, inherited by default |
| OpenAI Codex | `.codex/agents/*.toml` | `model`, `model_reasoning_effort`; delegated on request |
| AGENTS.md, Agent Skills | — | no model field |

Model ids are each vendor's own; only `inherit` is shared.

## Goal

A task that a smaller model does as well runs on one, on whichever tool the project uses,
without the framework naming a model anywhere but the tooling profile, and with no loss of the
guarantees a verification gives.

## Out of scope

- Routing every task automatically, or a fleet of specialised agents: one agent first, measured.
- The verifier, a security review, framing, design, a decision, and the code a change ships:
  they stay on the strongest model the project uses. A cheaper verifier would cheapen what
  verification proves.
- Choosing models for the project: the decider does, in the tooling profile.

## Prior art

| Product / reference | Solution chosen | What we keep from it |
|---|---|---|
| Anthropic, *Optimizing for cost and intelligence* and *Choosing a model* | Delegate independent, high-volume, checkable work to a smaller model. A strong model directing smaller subagents cost about a third less for about the same score. Keep the strong model for hard decisions and dependent chains, and tune effort before adding a second model | **The split by kind of task**, and **measure before widening** |
| OpenAI Codex, *Subagents* | A small model for fast, narrowly scoped, repeatable work: exploration, tests, triage, summaries. A reviewer or a security agent on the strong model, at high effort | The same split, from a second vendor |
| Claude Code, Cursor, Gemini CLI, Copilot | One agent file per agent, in Markdown with a front matter of `name`, `description` and `model`, in the repository | **The file is the adapter**: one per tool, generated from one source |
| NapkinStack's tooling profile | Tools are adapters; capabilities are declared; a tool's name lives in one file | **A tier is a capability**; the model that serves it is a tool choice |

**The convention the user already knows**: an agent file in the repository, read by the tool,
with its model in its front matter.

## Options considered

1. **Say nothing**, as today: every read is paid at the strongest model's price.
2. **Name models in the kernel or the playbooks**: tied to one vendor, and stale at each
   release.
3. **Two tiers named by kind of task, mapped to each tool's model in the tooling profile, and
   one generated read-only agent** (chosen): neutral, measurable, and removable.

## Decision

**1. Two tiers, by kind of task.**
- *light*: reading that a person could check, such as finding files, symbols, call sites and
  where a rule is written; an inventory; a summary of an output.
- *strong*: everything else, and always the verifier, a security review, framing, design, a
  decision and the code a change ships.

**2. The tooling profile maps each tier to a model, per tool.** The *Specialised agents* row
names the tool and the model of each tier; the decider fills it. With no model named, the tier
is `inherit`, so nothing changes until the decider chooses.

**3. One agent, generated: an explorer, read-only, on the *light* tier.** It is generated from one
neutral source for each tool that reads agent files from the repository, alongside the skills.
It searches and reports paths with lines; it never edits, reviews or verifies.

**4. Built only once measured.** The first step is a hand-written explorer on one project,
measured against the same kind of task without it (*Success criterion*). Points 2 and 3 are
built if the measurement holds.

## Expected behaviour

- An agent that has to read widely to find something hands the search to the explorer, and
  gets back the answer with file and line, without reading every file itself.
- Nothing in the kernel names a model. A project that changes tool or vendor changes one row of
  its tooling profile, and the generated agent files follow.
- A tool that reads no agent file from the repository loses nothing: the explorer is only a
  file it ignores.

## Success criterion

We will consider this was the right call if, on the project that measures it, before
**2026-12-15**, over at least 20 comparable lookup tasks, both of the following hold:
- the tokens of the strongest model fall by at least 25% for the same kind of task;
- there is no more re-searching by the main agent, and no verifier finding traced to a wrong or
  missing answer from the explorer.

How it is observed: the coordinator of the project records, for each lookup task, the tokens of
the session's main model and of the explorer, and whether its answer was used as given, and
compares them with as many such tasks before.

If the criterion is not met: not built; this PDR is rejected with the measurement.

## Removal condition

Removed if the agent tools converge on a model field of their own that a repository can declare
once for all of them, or if a smaller model's reading costs a verification more than it saves.

## Impacts

- **Projects**: nothing until the measurement holds. Then a row of their tooling profile to fill,
  and an explorer agent file per tool, generated with the skills.
- **The engine**: `nstack skills` generates the agent files.
- **The skeleton**: `04-ai-context.md` says the two tiers, and the tooling profile carries the
  mapping.
