"""
The project's settings after init (#529): `nstack config` lists them, reads one, changes one.

Each is an answer in `.copier-answers.yml`, with a default when the file holds none. They are the
decider's word: a change is laid on a branch, for a pull request a human approves, never on the
default branch. The project is rendered again at its own version with the new answer, so the
files written from it — the code owners file for `approval` — follow, and the project's own lines
in them are kept, as `nstack update` keeps them.

The answers set at init — the project's name, its forge, its repository, its owner — are listed,
not changed here: `nstack update --forge` moves the forge, with the files it writes.

Usage :  nstack config [<setting> [<value>]] [--session <id>] [--root ROOT]
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import yaml

from napkinstack import project


@dataclass(frozen=True)
class Setting:
    kind: type  # str, int or bool, as copier.yml types the question
    default: Callable[[dict], object]  # from the other answers: `checks` follows the forge
    meaning: str
    choices: tuple[str, ...] = ()


# The decider's settings, as copier.yml declares them: a test holds the two the same.
SETTINGS: dict[str, Setting] = {
    "checks": Setting(str, lambda answers: "forge" if answers.get("forge", "github") == "github" else "attested",
                      "where a pull request's checks are judged: the forge's CI, or attested on a workstation",
                      ("forge", "attested")),
    "approval": Setting(str, lambda answers: "human",
                        "who approves a prototype or standard module: a human code owner, or also another agent",
                        ("human", "agent")),
    "hold_days": Setting(int, lambda answers: 7, "days without work before a hold of a deliverable is stale"),
    "agent_sockets": Setting(bool, lambda answers: False,
                             "whether an agent's sandbox opens Unix sockets, for audio, display or bus tests"),
    "review_budget_lines": Setting(int, lambda answers: 400,
                                   "lines a pull request changes before P2 warns, generated files left out"),
    "review_budget_files": Setting(int, lambda answers: 15, "files a pull request changes before P2 warns"),
}
AT_INIT = {"project_name": "set at init",
           "forge": "nstack update --forge <name> moves it, with the files it writes",
           "github_repo": "nstack update --forge github --github-repo <owner/name> changes it",
           "repository": "nstack update --forge <name> --repository <path> changes it",
           "owner_team": "set at init; the code owners file names it"}


class Unreadable(Exception):
    """The answers file is there and YAML cannot read it: no setting is guessed from it."""


def _read(root: Path) -> dict:
    if not (root / project.ANSWERS).is_file():
        return {}
    try:
        answers = project._answers(root)
    except (OSError, yaml.YAMLError) as error:
        raise Unreadable(f"{project.ANSWERS} cannot be read: {str(error).splitlines()[0]}") from error
    return answers if isinstance(answers, dict) else {}


def value(root: Path, name: str) -> tuple[object, str]:
    """A setting's value and where it comes from: the answers file, else the default. Raises
    Unreadable when the file is there and YAML cannot read it."""
    answers = _read(root)
    if name in answers and answers[name] is not None:
        return answers[name], project.ANSWERS
    return SETTINGS[name].default(answers), "default"


def _typed(name: str, current: object) -> str:
    """What a value of the wrong type is read as, where the engine reads it strictly: a quoted
    "true" is no bool, and an agent's sandbox stays closed."""
    kind = SETTINGS[name].kind
    if isinstance(current, kind) and not (kind is int and isinstance(current, bool)):
        return ""
    return f" — NOT a {kind.__name__}: written as text; nstack config {name} <value> writes it right"


def _parse(name: str, said: str) -> tuple[object, str | None]:
    setting = SETTINGS[name]
    if setting.kind is bool:
        if said.lower() in ("true", "yes", "on"):
            return True, None
        if said.lower() in ("false", "no", "off"):
            return False, None
        return None, "true or false"
    if setting.kind is int:
        return (int(said), None) if said.isdigit() and int(said) > 0 else (None, "a whole number above 0")
    return (said, None) if said in setting.choices else (None, " or ".join(setting.choices))


def _shown(item: object) -> str:
    return str(item).lower() if isinstance(item, bool) else str(item)


def run(root: Path, name: str | None = None, said: str | None = None, session: str | None = None) -> int:
    if not (root / project.ANSWERS).is_file():
        print(f"FAIL [config] {project.ANSWERS} not found in {root}: this folder is not a project created by "
              "nstack init.\n      Action: run the command at the project root, or pass --root.")
        return 1
    try:
        answers = _read(root)
    except Unreadable as error:
        print(f"FAIL [config] {error}.\n      Action: fix the file's YAML — git diff {project.ANSWERS} shows "
              "what changed — then run again.")
        return 1
    if name is None:
        print(f"The project's settings — the decider's, each changed in a pull request a human approves "
              f"(nstack config <setting> <value>):")
        for key, setting in SETTINGS.items():
            current, source = value(root, key)
            print(f"  {key:<20} {_shown(current):<10} ({source}) — {setting.meaning}{_typed(key, current)}")
        print("Set at init:")
        for key, how in AT_INIT.items():
            if key in answers:
                print(f"  {key:<20} {answers[key]} — {how}")
        return 0
    if name in AT_INIT:
        print(f"FAIL [config] {name} is not a setting this command changes: {AT_INIT[name]}.")
        return 1
    if name not in SETTINGS:
        print(f"FAIL [config] {name}: no such setting.\n      Action: nstack config lists them: "
              f"{', '.join(SETTINGS)}.")
        return 1
    current, source = value(root, name)
    if said is None:
        print(f"{name}: {_shown(current)} ({source}) — {SETTINGS[name].meaning}{_typed(name, current)}")
        return 0
    wanted, expected = _parse(name, said)
    if expected:
        print(f"FAIL [config] {name} '{said}' is not a value it takes.\n      Action: give {expected}.")
        return 1
    if name == "checks" and wanted == "forge" and project.forge(root) != "github":
        print(f"FAIL [config] checks forge on forge {project.forge(root)}: no CI is shipped off GitHub, so "
              "nothing would judge the project's pull requests.\n      Action: keep checks attested — each "
              "change's checks run and recorded by nstack attest (.nstack/handbook/07-governance.md §7).")
        return 1
    if os.environ.get("NSTACK_AGENT") and not session:
        print(f"FAIL [config] an agent's run (NSTACK_AGENT={os.environ['NSTACK_AGENT']}) commits the change: "
              "its commit must name the session, or pr-check's T2 refuses it.\n      Action: nstack config "
              f"{name} {said} --session <this session>.")
        return 1
    if wanted == current and source != "default":
        print(f"{name} is already {_shown(wanted)}: nothing to change.")
        return 0
    return project.change_answer(root, name, wanted, _shown(current), session)
