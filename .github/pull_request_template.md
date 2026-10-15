# <title: the workstream's number, then what it changes, from the behaviour's point of view>

## Workstream

<Its number and its row in `docs/governance/workstreams.md` — the number taken when the branch
is brought current with `main` (D98). One workstream, one pull request.>

## What it changes

<The behaviour, not the list of files: the diff already says what changed; this section says
why. A change with a shape — a flow, who reads what, a before and an after — is drawn: one
Mermaid diagram with its legend, in place of the prose it shows.>

## What a project receives

<What `nstack update` merges into a project, and what the engine does differently — or
"nothing: this repository only". Whether anything a green project had turns red.>

## Definition of Done

- [ ] The behaviour is covered by a test that failed before — committed first, seen red (P5)
- [ ] Every failure names the rule, the place and the action (P6)
- [ ] `uv run bash platform/tests/run.sh` green, on a committed tree
- [ ] `uv run nstack fitness` green
- [ ] Affected documentation updated, diagrams and legends included; no dead reference
- [ ] The workstream's row updated in the register; its plan deleted, if it had one
- [ ] Brought current with `main` as the last thing before opening
- [ ] No private project named, no path of a workstation, no link into an assistant's session

## Summary

```
DONE           what was changed, one sentence per change
VERIFIED       the checks actually run, with their result
ASSUMED        the assumptions taken for lack of information
NOT VERIFIED   what was not tested, and why
RISKS          possible side effects, debt introduced, follow-ups needed
```
