# Security

## Reporting a vulnerability

**Never open a public issue for a vulnerability.**

Use the forge's private reporting: on GitHub, the **Security** tab, then **Report a
vulnerability**. The report is visible only to the maintainers.

Target time to first response: **7 days**.

## The project's absolute rules

| # | Rule |
|---|---|
| S1 | No secret in the repository — not in clear text, not encoded, not in a test |
| S2 | All external input is hostile until explicitly validated |
| S3 | Least privilege by default, including for CI and for agents |
| S4 | Deny by default in authorisation |
| S5 | Never a homemade cryptographic or authentication mechanism |

Operational detail: `skeleton/.nstack/playbooks/security.md`.

## A known vulnerability in a dependency

The CI check `Hooks and secrets` audits, last, what `uv sync --locked` installs with `pip-audit`,
transitive dependencies included. A known vulnerability that a published version fixes fails
it, on every pull request, until the lock moves past it; Dependabot's security updates open that
pull request, outside the weekly cooldown and grouping of its version updates. One with no fix
yet is a warning on the check: no pull request could make it green. The published package
carries no lock, so a project installing it resolves current versions.

## An exposed secret

A secret exposed, even briefly, even in a commit since rewritten: **rotate it
immediately**. Removing it from history is not enough. That is an incident, not a fix.

## High-risk actions

Changing permissions, accessing secrets, exposing a new service, an irreversible
migration: never a silent execution. The risk named, the impact described, a safe
procedure and a rollback proposed, explicit confirmation asked for
(`skeleton/AGENTS.md` §5).
