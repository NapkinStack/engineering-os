# ADR-0009 — Audit a run's logs in its evidence folder

- **Status**: Accepted (2026-10-21), after an independent review (#231) that reshaped §1–§8: the
  step read from the project's history, the audit in the attested record, the output's pipe bounded,
  more log forms recognised and fewer misread, M12 stricter, suggestions that match again
- **Date**: 2026-10-21
- **Decision makers**: NapkinStack maintainers (`@NapkinStack/maintainers`)
- **Scope**: project — the engine (`nstack e2e`, `nstack manifests`), the manifest, the
  skeleton's playbooks
- **Reversibility**: easy — the audit is one step after the module's command, and its manifest
  section is optional; removing them leaves the command as it ran before

---

## Context

PDR-0017 decided *what*: an end-to-end run keeps its output, logs and screenshots in its evidence
folder; the engine reads the log files the run wrote there — JSON level keys, level-led lines;
an undeclared error fails, an undeclared warning is reported and fails from `high`; the version
that brings it only reports; a module declares what its scenarios provoke; the verifier of a
visible change cites what it saw. This record says *how*.

## Problem

How the folder reaches the module's command; how its output is kept while still shown live; which
files are read and how a line's level is recognised without imposing a format; the declaration's
shape and its check; how "report first, judge next" is carried; how an attested run says it.

## Constraints

- Any stack: a shell command, as `commands.e2e` already is (P1).
- No dependency beyond the engine's standard library and PyYAML.
- The run's output stays live on the terminal and in CI's log.
- No step a person must take for the version to pass (the maintainer's rule).
- One source for an expectation: the manifest for provoked lines, the scenario for asserted ones.

---

## Prior art

| Reference | What it does | What we take |
|---|---|---|
| `NSTACK_DIST` (D127) | `nstack release` empties `dist/<module>` and names it to the command | **The same hand-over**: a folder emptied, named in the environment |
| [pino levels](https://getpino.io/#/docs/api?id=loggerlevels-object), [Python `logging` levels](https://docs.python.org/3/library/logging.html#logging-levels), [`tracing` JSON](https://docs.rs/tracing-subscriber/latest/tracing_subscriber/fmt/format/struct.Json.html), [logfmt](https://brandur.org/logfmt) | Level as a key (`level`, `levelname`, `severity`) — a word or a number — or `level=` | **The forms recognised** |
| [pytest `filterwarnings`](https://docs.pytest.org/en/stable/how-to/capture-warnings.html), [cypress-fail-on-console-error](https://github.com/nils-hoyer/cypress-fail-on-console-error) | Expected messages declared as patterns | **A pattern per provoked line** |
| `tee` | Output shown and kept at once | **Live and kept** |

---

## Options considered

| Option | For | Against | Chosen? |
|---|---|---|---|
| Read the command's output for levels | No module change | Test runners print "ERROR" in names and summaries: noise; a log is not its runner's output | No — kept, not audited |
| Read logs wherever the module logs | No module change | No generic place; the third project's logs live in a temporary folder deleted at exit | No |
| **Read the files the run writes into the folder it is given** | One place, any stack; the module chooses what to give | The module writes its logs there | **Yes** |
| A declared regular expression for every module | Exact | A burden where common forms suffice | Only for an uncommon form |

## Decision

1. **The folder.** `nstack e2e` empties `<module>/.evidence/e2e/` and names it to the command as
   `NSTACK_EVIDENCE`, as `nstack release` does `NSTACK_DIST`. As `release` does, a `.evidence` or
   `.evidence/e2e` that is a link or a file fails the run and nothing is emptied through it; a file
   that cannot be removed fails the run, naming it. The run writes `.running` (its process id) in
   the folder; a second run of the module while that process lives fails, naming it. CI's module
   checks already keep `**/.evidence/` as the run's artefact.
2. **The output.** One pipe, standard error merged into standard output, read in byte chunks — a
   prompt without a newline still shows — and written unchanged to the terminal and to
   `output.txt`, never decoded. The engine waits for the command's process, not for the pipe's
   end: once it exits, what remains is drained for two seconds at most, then the pipe is closed and
   a process still holding it is said. An interrupt is passed to the command, and the audit still
   runs. `output.txt` is evidence, not audited: a runner's output is not a log.
3. **The logs read.** Regular files under the folder ending in `.log` or `.jsonl` — links not
   followed, `output.txt` and `audit.json` excepted — read as UTF-8 with replacement, universal
   newlines, each line up to its first 64 KiB. A line's level is recognised, in this order:
   - the module's own expression, `evidence.levels`, when it declares one; its group `level` is read
     with the words below;
   - a JSON object with `level`, `levelname`, `severity`, `lvl` or `@l`: a word — `warn`, `warning`
     (warning); `error`, `err`, `fatal`, `critical`, `panic`, `alert`, `emergency` (error); any
     case — or an integer of pino and bunyan, exactly 40 (warning), 50 or 60 (error); any other
     value is below a warning;
   - `level=<word>` (logfmt);
   - after colour codes are removed, at most two timestamp tokens (`[\d:.,/TZ+-]+`) and an opening
     bracket: an upper-case level word followed by a space, a colon or a bracket, or a level word
     in any case followed by a colon or a closing bracket — `ERROR …`, `[WARN] …`,
     `2026-10-21 10:00:00,123 WARNING msg`, `warning: …`; never `Error rate: 0%`;
   - GLib's `<Domain>-WARNING **:` (warning) and `<Domain>-CRITICAL **:` (error).

   A file with lines and no line classified is *not read*, said with the way to declare its form;
   it never fails the run.
4. **The declaration**, in the manifest:

   ```yaml
   evidence:
     provoked:                      # what the scenarios provoke, on purpose
       - pattern: "key refused"     # a Python regular expression, searched in the line
         level: warning             # warning | error
         scenario: S3               # for the reader; the engine checks the pattern
     levels: '^(?P<level>\w+)\|'    # optional: how this module's lines say their level
   ```

   `nstack manifests` checks it (M12): `evidence` a mapping of `provoked` and `levels` only;
   `provoked` a list of mappings of exactly `pattern` (compiling, and not matching an empty line —
   a pattern that accepts every line checks nothing), `level` and `scenario` (non-empty text);
   `levels` compiling with a group `level`. Each failure names its file and its action, as M1–M11
   do. A declaration accepts every line it matches, in any scenario: the scenario is not checked —
   a known limit, PDR-0017's choice.
5. **The audit.** It runs whatever the command's exit code; the run fails if either fails. Every
   warning- or error-level line is matched against the declarations of its level; an unmatched one
   is *undeclared*. A declaration no line matched is said, never failed. The verdict, by
   PDR-0017's severity: an undeclared error fails; an undeclared warning fails from criticality
   `high` — a criticality undeclared or unknown is judged as `critical`, as the module checks do —
   and is reported below.
6. **Report first, judge next — read from the project.** The audit judges when the project's
   recorded version (`_commit` in `.copier-answers.yml`) is at a minor above the first version
   that carried the audit **and recorded in the project's own history** (the log of
   `.copier-answers.yml`): a project that skips the reporting version reports for one minor from
   the version it lands on. Otherwise it reports; without that history (a shallow clone), it
   reports. One constant in the engine names the first version carrying the audit; no release
   flips a switch, and CI and an attested run judge a commit alike, whatever engine runs it. A
   reported line comes with the declaration that would accept it, ready to copy: its pattern built
   from the line's message (`message`, `msg` or `event` in JSON; the text after the level
   otherwise), escaped, its numbers and hexadecimal identifiers made general.
7. **What a run says and keeps.** At its end, `nstack e2e` prints the audit in a few lines — the
   folder, the files read and not read, the undeclared lines quoted with `file:line` (the first
   ten, then a count), the stale declarations — and writes it as `audit.json` (commit, module,
   step, verdict, files, lines, declarations). After the module checks, `nstack attest` adds to its
   record an `evidence` field: for each module whose `audit.json` names the commit attested, that
   audit and the folder's path relative to the project — never an absolute path, which would name
   a person's home in notes pushed to a shared remote. The record keeps the audit whatever the cap
   on a step's output.
8. **The playbooks.** `tests.md`: write the run's logs and screenshots into `NSTACK_EVIDENCE`;
   data that are not logs (recordings, events) elsewhere; a page's uncaught errors logged by the
   page itself through the application, or collected by a script the scenario injects
   (`window.onerror`, `unhandledrejection`) and written there — a driver may expose no console;
   assert expected lines in the scenario, declare provoked warnings and errors in the manifest,
   never both. `verification.md`: for a visible change, read the screenshots and logs and cite
   them.

- **Expected user value**: a defect that only logs is caught; red on screen is told from red meant.
- **How we will observe it**: PDR-0017's criterion.

## Success criterion

On the third project, its window's and its recorder's runs write their logs into
`NSTACK_EVIDENCE`; the first version's audit lists their undeclared lines; after their
declarations, the next version's runs pass, and an error introduced on purpose fails.

## Consequences

- `nstack e2e` takes a folder, a tee and an audit; `nstack manifests` gains M12 (its list of rules
  in the module's docstring and the handbook); `nstack attest` gains the record's `evidence` field.
- The module template's `e2e` comment and `evidence` section, `09-platform.md`'s `e2e` line
  (`NSTACK_EVIDENCE`), `tests.md` and `verification.md`; the CHANGELOG says the two steps.
- A module's end-to-end script changes where its logs go — a module's change, in its own pull
  request.
- `output.txt` and the screenshots may be large; CI's artefact already keeps them thirty days.

## Rejected alternatives

See *Options considered*.
