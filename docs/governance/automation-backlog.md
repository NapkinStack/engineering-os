# Automation backlog

> Any rule that still lives in the prompt while being mechanically checkable is a
> **debt**. This file makes it visible and dated.
>
> Without this backlog, the kernel grows at every incident and turns back into the
> unreadable document it replaces (`skeleton/.nstack/handbook/07-governance.md` §9).

| Rule | Where it lives | Risk if violated | Cost to automate | Trigger | Deadline |
|---|---|---|---|---|---|
| Mandatory ADR sections: prior art, deviation, dated criterion | The ADR index, review | Medium | Low | The first real project | Post-pilot review |
| A contraction issue opened as soon as the expand lands | `03-contracts.md` §4, by hand | Medium | Low | The first versioned contract | Post-pilot review |
| External dependency declared in the manifest | The security playbook, review | Medium | Medium | The first module with dependencies | Post-pilot review |
| English is the repository's only language (ADR-0003) | `AGENTS.md`, review | Low | High — detection rests on accented letters: blind to English borrowings, false-positive on typographic punctuation and proper nouns | First outside contribution written in another language | Post-pilot review |
| Review budget adjusted per module, by criticality | `05-workflow.md` §4 | Low | Low | A module whose budget is genuinely different | Post-pilot review |

## Rules already automated

Listed once, with the check that holds each one:
[`skeleton/.nstack/handbook/RULES.md`](../../skeleton/.nstack/handbook/RULES.md).

## Review

Quarterly (`skeleton/.nstack/handbook/10-measurement.md` §5). For each row: **automate**, **remove the rule**, or
**renew with a new deadline**.
