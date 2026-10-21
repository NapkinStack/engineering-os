# PDR-0017 — A change's runs show what their logs said

- **Status**: Proposed (2026-10-21). Asked by the third project's decider, watching its
  end-to-end runs: *I sometimes see errors written in red on the interface … are the logs in
  place? do you analyse the logs during each test?* (#224)
- **Date**: 2026-10-21
- **Decision makers**: NapkinStack maintainers (`@NapkinStack/maintainers`)
- **Modules affected**: the engine (`nstack e2e`), the manifest's `commands`, the skeleton's
  playbooks (`tests.md`, `verification.md`), CI's module checks

> The PDR describes **what the product must do and why**, never its implementation.
> The how belongs to an ADR.

---

## User problem

A module's end-to-end scenarios pass or fail on what they assert. What the module **said** while
they ran — a warning, an error in its log, a red message on its screen — is read by nobody:

- `verification.md` asks for evidence of each scenario and says nothing of the logs; `tests.md`,
  the `e2e` verb and `nstack attest` have no step that reads them.
- Observed on the third project (#224): its window's end-to-end run writes the logs to a folder of
  its own and deletes it at the end, reading only the few lines it expects; the failures it
  provokes on purpose show in red, and an error nobody provoked would show in red too, with nothing
  to tell them apart; its screenshots were never read, the verifiers wrote "rendering not seen";
  a scenario that broke off kept no traceback, and failed `nstack attest` twice before its cause
  could be read.

A defect that only logs, or only shows, passes every gate the framework has. Each project invents
its own audit, or none. The decider sees red and cannot tell, from a green run, whether it was
meant.

## Goal

Every end-to-end run of a module keeps what it said and showed, fails on a warning or an error
nobody declared, quoting it, and a verifier of a visible change reads and cites what the run
showed — the same way in every project, without a project writing its own audit.

## Out of scope

- **A log format, a logging library, a monitoring stack.** The module logs as it does; the
  framework reads lines.
- **Unit tests' logs.** End-to-end runs, where a module runs as a user meets it.
- **Production logs and alerting.** Runs of a change, before it merges.
- **Judging a screenshot automatically.** A person, or a verifier session, looks.

---

## Prior art

| Product / reference | Solution chosen | What we keep from it |
|---|---|---|
| [cypress-fail-on-console-error](https://www.jsdelivr.com/package/npm/cypress-fail-on-console-error) | A browser console error fails the test; expected ones listed as patterns | **Fail on the unexpected, allow the declared** |
| [console-fail-test](https://classic.yarnpkg.com/en/package/console-fail-test) | A test that logs to the console fails after it ends | **Silence by default; a log is a finding** |
| [Playwright console and page errors](https://www.checklyhq.com/blog/how-to-monitor-javascript-logs-and-exceptions-with-playwright) | A fixture listens to `console` and `pageerror`, collects errors, asserts the list empty after each test | **Collect during the run, judge at its end** |
| Playwright traces and screenshots kept on failure; Cypress screenshots and videos as CI artefacts | The run's evidence kept beside its result | **Keep what the run showed** |

**The convention the user already knows:** a test run that turns red on an unexpected error in
the console, and the run's screenshots attached to it.

---

## Options considered

| Option | What the user experiences | Cost | Chosen? |
|---|---|---|---|
| Do nothing | Each project audits its logs, or not; red on screen unexplained | 0 | No |
| A. A playbook sentence: "read the logs" | The verifier may, the run never does | Low | Part of B |
| **B. Keep, audit, look: the run keeps its logs and screenshots; `nstack e2e` fails on a warning or an error the module did not declare, quoting the line; the verifier of a visible change cites what it saw** | A green run means nothing unexpected was said; red names the line | Medium | **Yes** |
| C. B, plus a dashboard of logs across runs | History | High | No: no reader for it yet |

## Decision

**Option B.**

1. **Keep.** A module's end-to-end run is given a folder for its evidence — its logs and its
   screenshots — kept after the run, beside its result, and kept by CI as the run's artefact; on a
   workstation, ignored by git.
2. **Audit.** After the module's `e2e` command, the engine reads the run's logs: every line at the
   level of a warning or an error fails the run, quoted, unless the module declares it — a pattern,
   and the scenario that provokes it. A declared pattern that no line matched is reported: the
   failure it stood for did not happen, and the declaration may be stale.
3. **Look.** The verification playbook asks the verifier of a change to a visible surface to read
   the run's screenshots and logs, and to cite what they saw in the evidence — never "rendering not
   seen" on a scenario passed.
4. **Kept when it breaks.** A run that stops halfway keeps what it had — the traceback, the last
   lines — so that its cause is read on the first failure, not the third.
5. **Where it applies.** Every module declaring an `e2e` command. A module whose logs the engine
   cannot read says so, and is told how to give them; nothing is guessed.

---

## Expected behaviour

**Nominal journey.** The window's run provokes a refused key on purpose; the module declares
`warn … key refused` for scenario S3. The run passes; its folder holds the logs and twelve
screenshots; CI keeps them. A change makes the recorder log `error: device lost` at start: the run
fails, quoting the line and its scenario's time; the author sees it at once.

**Edge cases.** A declared refusal no longer happens (the scenario was changed): the run passes and
says the declaration matched nothing. The run crashes in scenario S5: its folder keeps the
traceback; `nstack attest` records the run with it. A module that logs nowhere the engine can find:
the run says the logs were not read, and how to give them.

**Acceptance criteria** *(testable)*:

- [ ] Given a module's `e2e` run, then its logs and screenshots are kept after it, in CI as an
      artefact.
- [ ] Given a warning or an error in the run's logs that the module did not declare, then the run
      fails, quoting the line.
- [ ] Given a declared pattern that matched no line, then the run says so and does not fail.
- [ ] Given a run that stops halfway, then what it wrote until then is kept.
- [ ] Given the verification playbook, then it asks the verifier of a visible change to cite what
      the screenshots and logs showed.
- [ ] Given a module whose logs cannot be read, then the run says so, never a silent pass.

---

## Success criterion

By 2027-03-31: on the third project, every end-to-end run in CI keeps its evidence, no verifier
writes "rendering not seen" on a scenario passed, and at least one defect that only logged is
caught by the audit before review.

## Removal condition

Removed if, over two minor versions, the declared patterns grow to accept every line — the audit
then checks nothing — and no defect was caught by it.

## Impacts

- **The engine**: `nstack e2e` gives the folder, reads the logs after the command, says and fails.
- **The manifest**: a module declares where its logs are, if not where the engine looks, and the
  warnings and errors its scenarios provoke.
- **The skeleton**: `tests.md` and `verification.md` say keep, audit, look; CI's module checks keep
  the evidence as an artefact.
- **Projects**: a module with an `e2e` command declares what its scenarios provoke; until it
  does, its runs fail on what it already logs — a project takes the version when it has listed them.
- **The how** — the folder, how logs are found and their levels read, the declaration's shape, the
  artefact — goes to an ADR.
