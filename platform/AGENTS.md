# platform — local instructions

## Responsibility

Provides the standard verbs, the fitness functions and the module scaffolding.

## What this module does not do

It holds **no business logic** and depends on no module. Any business rule here would be
shared by every module, and would therefore make them inseparable.

## Invariants

- A fitness function must be **fast** (under 30 s), **deterministic** (no random false
  positive) and **explanatory**: a failure message naming the rule broken, the file, and
  the corrective action.
- The standard verbs **never change name**. Their content is free.
- A change here affects every module: the review budget applies strictly, and an ADR is
  expected for any new blocking rule.

## Known traps

- `boundaries.py` detects textually. Changing `IMPORT_HINTS` without testing against the
  real repository produces either noise or blind spots.
- The scaffolding writes into `.github/CODEOWNERS`: check there is no duplicate.

## Areas not to change without approval

`src/napkinstack/fitness/` — these are the guardrails themselves. Weakening them quietly
would amount to bypassing a quality gate.
