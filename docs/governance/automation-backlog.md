# Automation backlog

> Any rule that still lives in the prompt while being mechanically checkable is a
> **debt**. This file makes it visible and dated.
>
> Without this backlog, the kernel grows at every incident and turns back into the
> unreadable document it replaces (`skeleton/docs/os/07-governance.md` §9).

| Rule | Where it lives | Risk if violated | Cost to automate | Trigger | Deadline |
|---|---|---|---|---|---|
| *example* — a contract change must be preceded by an ADR | kernel §6 | Medium | Low | The 2nd inter-team contract | YYYY-MM-DD |
| Mandatory ADR sections: prior art, deviation, dated criterion | The ADR index, review | Medium | Low | The first real project | Post-pilot review |
| A contraction issue opened as soon as the expand lands | `03-contracts.md` §4, by hand | Medium | Low | The first versioned contract | Post-pilot review |
| External dependency declared in the manifest | The security playbook, review | Medium | Medium | The first module with dependencies | Post-pilot review |
| English is the repository's only language (ADR-0003) | `AGENTS.md`, `CONTRIBUTING.md`, review | Low | High — detection rests on accented letters: blind to English borrowings, false-positive on typographic punctuation and proper nouns | First outside contribution written in another language | Post-pilot review |

## Rules already automated — removed from the prompt

| Rule | Automated by | Date |
|---|---|---|
| One PR = one module | `nstack pr-scope` (`src/napkinstack/fitness/pr_scope.py`) | |
| Declared graph = real graph, contracts included | `nstack boundaries` | 2026-09-19 |
| Consumers of a removed version = 0 | `nstack boundaries` B6: a consumed version nobody provides fails | 2026-09-19 |
| Backward compatibility of contracts | `nstack compat` V1, with the project's comparator | 2026-09-19 |
| Deprecation dates not passed | `nstack manifests` | |
| Runbook required when criticality is high | `nstack manifests` | |
| No secret in the repository | gitleaks (hook and CI), push protection | 2026-09-13 |
| No update conflict marker left | `check-merge-conflict --assume-in-merge` (hook and CI) | 2026-09-15 |
| Forge settings matching the checklist | `nstack doctor`, read-only | 2026-09-15 |

## Review

Quarterly, with the decision review. For each row: **automate**, **remove the rule**, or
**renew with a new deadline**.
