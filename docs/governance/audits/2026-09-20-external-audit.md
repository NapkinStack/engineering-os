# External audit of 2026-09-20 — what it found, what the market says, where each item goes

> An expert outside the project audited the public repository and compared it with the 2026
> field. This note is the reading of that audit: what it gets right, what it gets wrong
> against the code, and what the market evidence says — so that every recommendation is
> either placed in a decision, dated, or refused with its reason.
>
> Sources are named. Claims about other products were re-verified on 2026-09-20 against
> their own documentation, not from memory.

## The audit's verdict, and ours

Its central judgement — *"a conceptual architecture remarkably structured for its level of
maturity, but not yet tried by a real population of teams"* — is the same one `PRODUCT.md`
already makes. We accept it.

Its strongest actionable idea is the **adversarial conformance suite**: our probes exist
(11 in M9, 8 in M10h) but they live in issue comments, are run by hand, and are never
replayed. That becomes **M12**.

## What the market actually shows

Three questions were researched from the projects' own documentation.

**1. Does anything else install enforcement into the user's repository?** No. Of the five
agent frameworks surveyed — [Spec Kit](https://github.com/github/spec-kit),
[BMAD-METHOD](https://github.com/bmad-code-org/BMAD-METHOD),
[OpenSpec](https://github.com/Fission-AI/OpenSpec),
[GSD Core](https://github.com/open-gsd/gsd-core) and the [AGENTS.md](https://agents.md/)
convention — **none writes a workflow, a branch rule, a code-owners file or a required check
into the user's repository**. GSD installs `PreToolUse` hooks into the agent's runtime, and
authored rulesets for *its own* repository by hand. Claude Code's own documentation draws
the line: *"Claude treats them as context, not enforced configuration. To block an action
regardless of what Claude decides, use a PreToolUse hook instead."*

**2. Do the repository-posture tools block?** No. [OSSF
Scorecard](https://github.com/ossf/scorecard) reports and scores; [Allstar](https://github.com/ossf/allstar)
lists `block` under *"Proposed, but not yet implemented actions"*, and the OpenSSF retired
its hosted app in v4.6; Legitify, zizmor and poutine report; Backstage Tech Insights,
Cortex, OpsLevel, Compass and Port measure and notify. What blocks a merge on GitHub is a
ruleset, a required check, or a GitHub App posting a failing check run — which is where we
already are.

**3. Is there a machine-readable record of why a change may merge?** **No.** GitHub's rule
suites API is the only native record and is per-ref, opaque and unsigned; SLSA's Source
Track defines two-party review at L4 but *"no forge implements it"* and its reference tooling
has 18 stars; [in-toto](https://github.com/in-toto/attestation) has predicates for tests and
provenance but **none for review or approval**; [gittuf](https://github.com/gittuf/gittuf)
models review approvals and is in beta; Kosli gates deployments, not merges. The one project
whose stated purpose is exactly this has one star.

**Where the field is moving, and it is towards us.** SLSA Source Track L4 requires *"two
trusted persons to review all changes to protected branches"* — PDR-0003 and ADR-0004. The
[OpenSSF OSPS Baseline](https://baseline.openssf.org/versions/2026-02-19.html) requires *"at
least one non-author human approval"* (OSPS-QA-07.01), an enforcement mechanism against
direct commits (OSPS-AC-03.01) and automated tests before a commit is accepted
(OSPS-QA-06.01). GitHub itself now requires *"one more approval than the number you
configured"* when Copilot opens a pull request not attributed to a person, tags audit
entries with `actor_is_agent`, and signs its agent's commits.

**And where the field disagrees with us.** Every serious project ships a way to spend less
ceremony on small work, and the ones that did not were told to: Spec Kit's issue #1174,
*"this workflow behaves the same regardless of task complexity"*, was closed by a preset and
a TinySpec extension that classifies a change by size; GSD's own documentation says a
too-small phase gives *"a planning overhead that dwarfs the execution cost. The loop feels
bureaucratic rather than helpful"*, and ships `/gsd-fast` and `/gsd-quick`; BMAD leads with
*"the process sizes itself to the work"*; OpenSpec sells *"predictability without the
ceremony"*. Our `K1` applies uniformly, and PDR-0002 counts systematic `out-of-cycle` as a
failure rather than a state.

## The audit, item by item

**Right, and already true — no action.** That the enforcement philosophy is the core idea;
that the module is the unit of parallelism; that contracts are first-class with
expand/contract; that a 250-line kernel is a real constraint (226 today); that the prompt is
a transit zone; that independent verification addresses an agent's confirmation bias; that
no AI inside and no imposed stack are the right calls — the audit and this project agree,
and the code holds them.

**Wrong against the code.**

| The audit says | The repository says |
|---|---|
| The label *"vibe coding framework"* hurts the product | The word *vibe* appears **zero** times in the repository. `README.md` and `PRODUCT.md` §1 already say "engineering framework" |
| The oracle-before-generation rule may be too rigid for exploration | Already handled: `05-workflow.md` requalifies an exploratory task as a **spike** — *"the deliverable is knowledge, not code"* — with its own issue form |
| Criticality should become an adaptive mode | It already drives the test sheet, the integration and end-to-end steps and the runbook. What is missing is **routing**, which is PDR-0004, accepted 2026-09-18 |
| The pilot starts on v0.4.1 | Read before the decision of 2026-09-20: the pilot starts on v0.5.0 |
| Superpowers is a competing layer | It is a skills plugin for one agent; this repository's own sessions use it |

**Right, and taken.**

| Item | Where it goes |
|---|---|
| A guardrail red-team as a conformance suite, replayed per release | **M12**, with its own plan |
| Ceremony proportional to the work | **PDR-0007** — a project may be *unframed*, and the cycle rules then do not apply |
| Simplify the first hour | **PDR-0008** — the repository's settings become one command, and PDR-0004's routing (M11) |
| A machine-readable "why may this merge" record | **PDR-0009** — the merge record, after the pilot's first cycle |
| The product's own vocabulary | Three named states, one rule: *guarded or unguarded* (PDR-0006), *framed or unframed* (PDR-0007), *published or unpublished* (PDR-0005). Never in silence |
| Keep engineering semantics separate from GitHub's implementation | Held as a constraint in every decision below; no forge adapter is built before a project asks for one |

**Right, and dated — not now.**

| Item | Why it waits |
|---|---|
| `nstack context` and per-agent context bundles | An adapter per agent breaks P2, and compiling context pushes rules back into the prompt, against the product's own thesis. Reconsidered if the pilot asks for it |
| An agent firewall on the workstation | Refused in PDR-0006's options: bypassable, an adapter per agent, and the appearance of a barrier — the very claim this project holds against others |
| `nstack adopt` for existing repositories | The largest market claim in the audit, and a product of its own. It would be designed on zero real usage. After the pilot |
| A fitness function catalogue | `PRODUCT.md` §6 already forbids building checks before a need is observed |
| Installers for brew, npm, binaries | PDR-0001 keeps uv as the only prerequisite; the forge channel (ADR-0002, clarified) covers trying the tool |
| Forge adapters beyond GitHub | Not before a project needs one |
| A before/after benchmark | Built on our own runs it would be marketing. It needs the pilot's data |

**Taken from the audit's wording.** *"Don't make the agent smarter. Make the repository
harder to misuse."* It says in one line what `PRODUCT.md` §2 takes a paragraph to say.

## What this note does not do

It does not change a decision by itself. Each item above is either already true, refused
with its reason, or carried into a decision record that can be argued with on its own terms.
