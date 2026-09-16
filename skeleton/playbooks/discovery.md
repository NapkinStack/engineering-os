# Playbook — Discovery

> **Trigger.** Load this playbook when a project starts from an idea — a few lines, notes,
> a wish — before any charter: to test the idea, compare it with what exists, challenge it,
> and reach a decision.

---

## Your posture

You run stages 1 to 4 as the **framer**, stage 5 only as the **challenger** — never both in
the same session. The decider decides, at stage 6.

| You do | You never do |
|---|---|
| Ask one question at a time, only what you cannot infer | Agree to please; soften an objection |
| Give every market fact its source | State a fact you cannot source — write it as an assumption |
| Keep the document to what could change the decision | Fill a canvas, size a market, invent personas |
| End each round with a decision | Open a new direction before the round is decided |

`nstack discover <idea-file>` created `docs/project/discovery.md`: one section per stage.

---

## 1. Intake

Read the idea file entirely. Restate the idea in one paragraph — for whom, which problem,
what the product does — and ask the decider to correct it. Nothing else until it is right.

## 2. Research

With the research tools of `docs/tooling-profile.md`, look for:

- what users do today instead, including nothing;
- the direct and indirect alternatives, their positioning and their price;
- the business models of the field;
- the legal and regulatory constraints, for the countries concerned.

Each finding goes in the evidence table — the claim, for or against the idea, its source.
A claim without a source goes to *Assumptions*.

## 3. Define

With the decider: the users, their problem in their own words, and the success signals —
what will be observed, and by when, if the idea is right.

## 4. Shape

- **The value hypothesis** — why a user would switch from what they do today, in one or two
  sentences. A hypothesis to test first, not a list of features.
- **A short press release**, dated launch day: the user, the problem, the product, one
  quote. If it does not convince the decider, say so: that is a finding.
- **No-gos** — what the product deliberately will not do.

## 5. Challenge — in another session

A session that did not write stages 1 to 4, or a human. The challenger reads the idea file
and the document, then:

1. **Pre-mortem** — the product launched a year ago and failed: list the plausible reasons.
2. **The four risks** — *value*: will they use it, or buy it? *usability*: can they use it?
   *feasibility*: can it be built with the means at hand? *viability*: does it hold for the
   business — cost, law, operations? For each, the riskiest assumption and the cheapest
   test that could refute it.
3. **Counter-evidence** — search for what contradicts the value hypothesis: failed products,
   closed competitors, regulatory refusals.

Report the objections with their evidence, in section 5. Never rewrite stages 1 to 4.

## 6. Decide

Present to the decider, in this order: the objections, the riskiest assumptions, the value
hypothesis. The decider chooses:

| Decision | What follows |
|---|---|
| **go** | The framing writes the charter from this document (`framing.md`); the assumptions needing a test become spike deliverables of the first cycle |
| **clarify** | A new round on the open questions only; `round` goes up |
| **kill** | The document stays, with its reasons — the cheapest outcome of all |

Record `decision`, `decider` and `decided_on` in the front matter, the reasons in section 6,
then run `nstack plan`.

---

## Bounds

A round is one or two working sessions. A second `clarify` is the decider's explicit choice,
recorded in section 6 — never a default.
