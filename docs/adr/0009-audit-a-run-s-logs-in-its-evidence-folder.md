# ADR-0009 — Audit a run's logs in its evidence folder

- **Status**: Proposed (2026-10-21)
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
   `NSTACK_EVIDENCE`, as `nstack release` does `NSTACK_DIST`. CI's module checks already keep
   `**/.evidence/` as the run's artefact.
2. **The output.** The command's standard output and error are shown live and written to
   `output.txt` in the folder as they come — a run that breaks keeps what it printed, its
   traceback included. `output.txt` is evidence, not audited: a runner's output is not a log.
3. **The logs read.** Every file under the folder ending in `.log` or `.jsonl`, but `output.txt`.
   A line's level is recognised, in this order:
   - a JSON object with `level`, `levelname`, `severity` or `lvl`: a word (`warn`, `warning`,
     `error`, `err`, `fatal`, `critical`, any case) or a number (pino: 40 warning, 50 and 60
     error);
   - `level=<word>` (logfmt) anywhere in the line;
   - a level word leading the line, alone or after one timestamp token, followed by a space, a
     colon or a bracket: `ERROR …`, `[WARN] …`, `2026-10-21T10:00:00Z WARNING: …`;
   - a module's own expression, `evidence.levels`, with a named group `level`, when it declares
     one — tried first.

   A file with lines and no line classified is *not read*, said with the way to declare its form;
   it never fails the run.
4. **The declaration**, in the manifest:

   ```yaml
   evidence:
     provoked:                      # what the scenarios provoke, on purpose
       - pattern: "key refused"     # a regular expression, searched in the line
         level: warning             # warning | error
         scenario: S3               # for the reader; the engine checks the pattern
     levels: '^(?P<level>\w+)\|'    # optional: how this module's lines say their level
   ```

   `nstack manifests` checks it: a list of mappings with a compiling `pattern`, a known `level` and
   a `scenario`; `levels` compiling with a group `level` — else rule M12 fails.
5. **The audit.** After the command, every warning- or error-level line is matched against the
   declarations of its level; an unmatched one is *undeclared*. A declaration no line matched is
   said, never failed. The verdict, by PDR-0017's severity: an undeclared error fails; an
   undeclared warning fails from criticality `high`, and is reported below.
6. **Report first, judge next.** The engine holds the step it is at: in the version that brings
   the audit, every verdict is *reported* — each undeclared line listed with the declaration that
   would accept it, ready to copy; from the next minor version, it judges. The CHANGELOG says both.
7. **What a run says.** At its end, `nstack e2e` prints the audit in a few lines — the folder,
   the files read and not read, the undeclared lines quoted (first ten, then a count), the stale
   declarations — and writes the same as `audit.txt` in the folder. Run inside `nstack attest`,
   these lines are the module checks' step output the record keeps; the record says where the
   folder is on the workstation.
8. **The playbooks.** `tests.md`: write the run's logs and screenshots into `NSTACK_EVIDENCE`;
   log a page's uncaught errors there; assert expected lines in the scenario, declare provoked
   warnings and errors in the manifest — never both. `verification.md`: for a visible change,
   read the screenshots and logs and cite them.

- **Expected user value**: a defect that only logs is caught; red on screen is told from red meant.
- **How we will observe it**: PDR-0017's criterion.

## Success criterion

On the third project, its window's and its recorder's runs write their logs into
`NSTACK_EVIDENCE`; the first version's audit lists their undeclared lines; after their
declarations, the next version's runs pass, and an error introduced on purpose fails.

## Consequences

- `nstack e2e` takes a folder, a tee and an audit; `nstack manifests` gains M12.
- A module's end-to-end script changes where its logs go — a module's change, in its own pull
  request.
- `output.txt` and the screenshots may be large; CI's artefact already keeps them thirty days.

## Rejected alternatives

See *Options considered*.
