"""
What a module's end-to-end run said (PDR-0017, ADR-0009).

`nstack e2e` gives the run its folder, `NSTACK_EVIDENCE`, keeps the command's output there, and
then reads the log files the run wrote into it: a warning or an error the module did not declare
— in its manifest's `evidence.provoked` — is said, and judged by the module's criticality. The
version that brings the audit only reports; the project's next minor version judges.
"""

from __future__ import annotations

import json
import os
import re
import select
import signal
import subprocess
import sys
import time
from pathlib import Path

import yaml

FIRST = (0, 14)  # the first version carrying the audit: a project recording it reports, the next minor judges
FOLDER = Path(".evidence") / "e2e"
READ = (".log", ".jsonl")
KEPT = ("output.txt", "audit.json", ".running")
WIDTH = 64 * 1024  # a line read up to its first 64 KiB
DRAIN = 2.0  # seconds a pipe is drained after the command exits
STRICT = {"high", "critical"}  # where an undeclared warning fails
SHOWN = 10

WORDS = {"warn": "warning", "warning": "warning",
         "error": "error", "err": "error", "fatal": "error", "critical": "error", "panic": "error",
         "alert": "error", "emergency": "error",
         "info": "below", "information": "below", "debug": "below", "trace": "below", "notice": "below",
         "verbose": "below", "fine": "below"}
KEYS = ("level", "levelname", "severity", "lvl", "@l")
PINO = {40: "warning", 50: "error", 60: "error"}
COLOUR = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
LOGFMT = re.compile(r"^\S+=\S*(?:\s+\S+=\S*)*?\s*\blevel=\"?([A-Za-z]+)")  # a line of key=value pairs
STAMP = r"(?=\S*\d)(?=\S*[:./T-])[\d:.,/TZ+\-]+"  # a timestamp: a digit and a separator, never a lone number or dash
UPPER = "|".join(sorted((word.upper() for word in WORDS), key=len, reverse=True))
LOWER = "|".join(sorted(WORDS, key=len, reverse=True))
LEADING = re.compile(
    rf"^\s*\[?(?:{STAMP}\s+){{0,2}}\[?\s*"
    rf"(?:(?P<up>{UPPER})(?=[\s:\]])|(?P<any>(?i:{LOWER}))(?=:|\]))")
GLIB = re.compile(r"[\w.-]+-(WARNING|CRITICAL|MESSAGE|DEBUG|INFO) \*\*:")


def compile_levels(expression: str | None) -> re.Pattern | None:
    return re.compile(expression) if expression else None


def level_of(line: str, own: re.Pattern | None = None) -> str | None:
    """`warning`, `error`, `below` — or None when the line does not say its level."""
    if own is not None:
        found = own.search(line)
        if found and found.groupdict().get("level"):
            return WORDS.get(found["level"].lower())
    text = line.strip()
    if text.startswith("{"):
        try:
            data = json.loads(text)
        except ValueError:
            data = None
        if isinstance(data, dict):
            for key in KEYS:
                value = data.get(key)
                if isinstance(value, str):
                    return WORDS.get(value.strip().lower(), "below")
                if isinstance(value, int) and not isinstance(value, bool):
                    return PINO.get(value, "below")
                if value is not None:
                    return "below"
            return None
    plain = COLOUR.sub("", text)
    found = LEADING.match(plain)  # a leading word first: a message may hold "level=…"
    if found:
        return WORDS[(found["up"] or found["any"]).lower()]
    found = GLIB.search(plain)
    if found:
        return {"WARNING": "warning", "CRITICAL": "error"}.get(found[1], "below")
    found = LOGFMT.match(plain)
    if found:
        return WORDS.get(found[1].lower(), "below")
    return None


def _message(line: str) -> str:
    text = line.strip()
    if text.startswith("{"):
        try:
            data = json.loads(text)
        except ValueError:
            data = None
        if isinstance(data, dict):
            for key in ("message", "msg", "event"):
                if isinstance(data.get(key), str):
                    return data[key]
    plain = COLOUR.sub("", text)
    found = LEADING.match(plain)
    return plain[found.end():].strip(" :]") if found else plain


def suggest(line: str) -> str:
    """A declaration's pattern that matches this line, and its kin, again: the message, escaped,
    its numbers and hexadecimal identifiers made general."""
    general = (r"(?i:\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b"  # a UUID
               r"|\b0x[0-9a-f]+\b|\b(?=[0-9a-f]*\d)[0-9a-f]{8,}\b)|\d+")
    parts = re.split(f"({general})", _message(line)[:200])
    out = []
    for index, part in enumerate(parts):
        if index % 2:
            out.append(r"\d+" if part.isdigit() else "(?i:(?:0x)?[0-9a-f-]+)")
        else:
            out.append(re.escape(part))
    return "".join(out).strip() or re.escape(line.strip()[:80])


def _files(folder: Path) -> list[Path]:
    """The log files a run wrote into its folder: regular files, links never followed."""
    found = []
    for path in sorted(folder.rglob("*")):
        if path.name in KEPT or path.suffix not in READ:
            continue
        if path.is_symlink() or not path.is_file():
            continue
        found.append(path)
    return found


def _lines(path: Path):
    """(number, line) of a file, each line its first WIDTH characters — never a whole huge line held."""
    with open(path, encoding="utf-8", errors="replace", newline=None) as source:
        number = 0
        while True:
            chunk = source.readline(WIDTH)
            if not chunk:
                return
            number += 1
            line, ended = chunk.rstrip("\n"), chunk.endswith("\n")
            while not ended:
                rest = source.readline(WIDTH)
                if not rest:
                    break
                ended = rest.endswith("\n")
            yield number, line


def audit(folder: Path, declared: list[dict], criticality: str | None, step: str,
          levels: str | None = None) -> dict:
    """The audit of a run's folder: what was read, what nobody declared, the verdict."""
    own = compile_levels(levels)
    patterns = [(item, re.compile(item["pattern"])) for item in declared]
    matched: set[str] = set()
    undeclared, read, not_read = [], [], []
    for path in _files(folder):
        relative = path.relative_to(folder).as_posix()
        classified = False
        for number, line in _lines(path):
            if not line.strip():
                continue
            level = level_of(line, own)
            if level is None:
                continue
            classified = True
            if level == "below":
                continue
            plain = COLOUR.sub("", line)  # searched as the suggestion was built: without colour
            hit = [item for item, pattern in patterns if item["level"] == level and pattern.search(plain)]
            matched.update(item["pattern"] for item in hit)
            if not hit:
                undeclared.append({"file": relative, "line": number, "level": level,
                                   "text": line[:500], "suggest": suggest(line)})
        (read if classified else not_read).append(relative)
    strict = criticality not in {"prototype", "standard"}  # undeclared or unknown: judged as critical
    failing = [item for item in undeclared if item["level"] == "error" or strict]
    if step == "judge" and failing:
        verdict = "failed"
    elif undeclared:
        verdict = "reported"
    else:
        verdict = "passed"
    return {"step": step, "verdict": verdict, "read": [name for name in read if name not in not_read],
            "not_read": not_read, "undeclared": undeclared,
            "stale": [item["pattern"] for item in declared if item["pattern"] not in matched]}


# --- the project's step (§6) ------------------------------------------------------------------

VERSION = re.compile(r"v?(\d+)\.(\d+)")


def _minor(text: str) -> tuple[int, int] | None:
    try:
        data = yaml.safe_load(text) or {}
    except yaml.YAMLError:
        return None
    found = VERSION.match(str(data.get("_commit") or "")) if isinstance(data, dict) else None
    return (int(found[1]), int(found[2])) if found else None


def step(root: Path) -> str:
    """`judge` once the project's own history recorded a version carrying the audit at a minor below
    the one it is at; `report` otherwise — and without that history."""
    answers = root / ".copier-answers.yml"
    current = _minor(answers.read_text(encoding="utf-8")) if answers.is_file() else None
    if current is None:
        return "report"
    log = subprocess.run(["git", "log", "--format=%H", "--", ".copier-answers.yml"], cwd=root,
                         capture_output=True, text=True)
    for commit in log.stdout.split():
        shown = subprocess.run(["git", "show", f"{commit}:.copier-answers.yml"], cwd=root,
                               capture_output=True, text=True)
        past = _minor(shown.stdout) if shown.returncode == 0 else None
        if past is not None and FIRST <= past < current:
            return "judge"
    return "report"


# --- the run (§1, §2, §5, §7) ------------------------------------------------------------------

def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except (OSError, ValueError):
        return False
    return True


def prepare(root: Path, module: Path) -> Path | str:
    """The run's folder, emptied — or why it cannot be."""
    base, folder = module / ".evidence", module / FOLDER
    odd = next((path for path in (base, folder) if path.is_symlink() or (path.exists() and not path.is_dir())), None)
    if odd is not None:
        return (f"{odd.relative_to(root)} is a link or a file, not a folder of the module's own: nothing is "
                "emptied through it.\n      Action: remove it, then run again.")
    running = folder / ".running"
    if running.is_file():
        try:
            pid = int(running.read_text(encoding="utf-8").strip() or 0)
        except (OSError, ValueError):
            pid = 0
        if pid and _alive(pid):
            return f"another end-to-end run of this module is in progress (process {pid}).\n      Action: wait for it."
    folder.mkdir(parents=True, exist_ok=True)
    for path in sorted(folder.rglob("*"), reverse=True):
        try:
            if path.is_dir() and not path.is_symlink():
                path.rmdir()
            else:
                path.unlink()
        except OSError as error:
            return f"{path.relative_to(root)} cannot be removed ({error.strerror}).\n      Action: remove it, then run again."
    (folder / ".running").write_text(str(os.getpid()), encoding="utf-8")
    return folder


def run(command: str, cwd: Path, environment: dict, folder: Path) -> tuple[int, str | None]:
    """The command, its output shown live and kept as it comes, in bytes; the process waited for,
    the pipe drained two seconds after. Returns its exit code, and what still held the pipe."""
    out = sys.stdout.buffer if hasattr(sys.stdout, "buffer") else None
    with open(folder / "output.txt", "wb") as kept:
        process = subprocess.Popen(command, shell=True, cwd=cwd, env=environment,
                                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        source = process.stdout.fileno()

        def copy(timeout: float) -> bool:
            ready, _, _ = select.select([source], [], [], timeout)
            if not ready:
                return True
            chunk = os.read(source, 65536)
            if not chunk:
                return False
            kept.write(chunk)
            kept.flush()
            if out is not None:
                out.write(chunk)
                out.flush()
            else:
                print(chunk.decode("utf-8", "replace"), end="", flush=True)
            return True

        open_pipe = True
        try:
            while process.poll() is None and open_pipe:
                open_pipe = copy(0.2)
            process.wait()
        except KeyboardInterrupt:
            process.send_signal(signal.SIGINT)
            previous = signal.signal(signal.SIGINT, signal.SIG_IGN)  # a second interrupt: the audit still runs
            try:
                process.wait()
            finally:
                signal.signal(signal.SIGINT, previous)
        deadline = time.monotonic() + DRAIN
        while open_pipe and time.monotonic() < deadline:
            open_pipe = copy(max(0.0, deadline - time.monotonic()))
        process.stdout.close()
    held = ("a process the command started still holds its output, after it exited: what it writes now "
            "is not kept") if open_pipe else None
    return process.returncode, held


def declarations(manifest: Path) -> tuple[list[dict], str | None, str | None]:
    """The module's declared lines, its own level expression, its criticality."""
    try:
        data = yaml.safe_load(manifest.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return [], None, None
    section = data.get("evidence") if isinstance(data.get("evidence"), dict) else {}
    provoked = [item for item in section.get("provoked") or [] if isinstance(item, dict) and item.get("pattern")]
    criticality = (data.get("module") or {}).get("criticality") if isinstance(data.get("module"), dict) else None
    levels = section.get("levels") if isinstance(section.get("levels"), str) else None
    return provoked, levels, criticality


def say(root: Path, name: str, folder: Path, found: dict) -> list[str]:
    """The audit in a few lines."""
    where = folder.relative_to(root).as_posix()
    head = {"passed": "nothing undeclared", "reported": f"{len(found['undeclared'])} undeclared line(s), reported",
            "failed": f"{len(found['undeclared'])} undeclared line(s)"}[found["verdict"]]
    lines = [f"Evidence of {name}: {where} — {head} ({found['step']}; read: {', '.join(found['read']) or 'no log file'})"]
    for item in found["undeclared"][:SHOWN]:
        lines.append(f"  {item['level'].upper():8} {item['file']}:{item['line']}: {item['text'][:200]}")
        lines.append(f"           declare it: - {{pattern: {json.dumps(item['suggest'])}, level: {item['level']}, "
                     "scenario: <the scenario that provokes it>}")
    if len(found["undeclared"]) > SHOWN:
        lines.append(f"  … and {len(found['undeclared']) - SHOWN} more, in {where}/audit.json")
    for name_ in found["not_read"]:
        lines.append(f"  not read: {name_} — no line says its level in a form the engine knows; declare "
                     "evidence.levels, an expression with a group named level")
    for pattern in found["stale"]:
        lines.append(f"  declared, matched nothing: {json.dumps(pattern)} — the failure it stood for did not happen")
    if found["step"] == "report" and found["undeclared"]:
        lines.append("  Reported, not judged: this project's next minor version of NapkinStack fails on what is "
                     "undeclared then (an error at any criticality, a warning from high).")
    return lines


def finish(root: Path, name: str, module: Path, folder: Path, code: int, held: str | None) -> bool:
    """The audit after the command, whatever its exit code: True when the logs pass. The running
    mark is removed whatever happens."""
    try:
        declared, levels, criticality = declarations(module / "MANIFEST.yaml")
        commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True).stdout.strip()
        try:
            found = audit(folder, declared, criticality, step(root), levels)
        except (re.error, TypeError) as error:
            (folder / "audit.json").write_text(json.dumps({"commit": commit, "module": name, "exit": code,
                                                           "verdict": "unread", "error": str(error)}), encoding="utf-8")
            print(f"FAIL [e2e] module '{name}': a declaration cannot be read ({error}).\n      Action: nstack manifests.")
            return False
        record = {"commit": commit, "module": name, "exit": code, **found}
        (folder / "audit.json").write_text(json.dumps(record, indent=1, ensure_ascii=False), encoding="utf-8")
        for line in say(root, name, folder, found) + ([f"  {held}"] if held else []):
            print(line, flush=True)
        if found["verdict"] == "failed":
            print(f"FAIL [e2e] module '{name}': its run logged what it does not declare — see above.\n"
                  "      Action: fix the cause, or declare the line in evidence.provoked with the scenario that provokes it.")
            return False
        return True
    finally:
        (folder / ".running").unlink(missing_ok=True)
