"""
Who must approve a change, read from the code owners file as the forge reads it (PDR-0021).

On `approval: agent`, another agent approves what the code owners file names no
owner for; a human, what it names. So every path a human must approve — the project's rules,
its records, its answers, the code owners file itself, every module neither `prototype` nor
`standard` — must end on a rule with an owner. A pattern is read as a gitignore pattern, the
syntax the forge documents for the file, and the last rule that matches a path decides it.
"""

from __future__ import annotations

from pathlib import Path

import pathspec
import yaml

# What a human approves whatever the project answers: its rules, its barriers, its records, its answers.
KEPT_FOR_A_HUMAN = ("AGENTS.md", "CONTRIBUTING.md", ".nstack/", ".copier-answers.yml", "docs/",
                    ".pre-commit-config.yaml", ".yamllint.yaml", "SECURITY.md")
FORGE_FOLDER = {"github": ".github/", "gitlab": ".gitlab/", "forgejo": ".gitea/", "gitea": ".gitea/"}
NOBODY = "nstack-no-file-is-named-so"  # a path no rule names but a default owner


def rules(text: str) -> list[tuple[pathspec.PathSpec | None, list[str]]]:
    """Each rule of the file, in order: its pattern and its owners — none after a `#`."""
    found = []
    for line in text.splitlines():
        words = line.split("#", 1)[0].split()
        if not words:
            continue
        try:
            spec = pathspec.PathSpec.from_lines("gitignore", [words[0]])
        except (ValueError, TypeError):
            spec = None  # a pattern the forge would refuse covers nothing
        found.append((spec, words[1:]))
    return found


def owned(read: list[tuple[pathspec.PathSpec | None, list[str]]], path: str) -> bool:
    """Whether the last rule matching the path names an owner."""
    last = [owners for spec, owners in read if spec is not None and spec.match_file(path)]
    return bool(last and last[-1])


def wanted(root: Path) -> list[str]:
    """The paths a human must approve on `approval: agent`, folders ending with `/`."""
    from napkinstack.fitness.manifests import find_manifests
    from napkinstack.project import forge, ownership

    paths = [*KEPT_FOR_A_HUMAN, ownership(root).relative_to(root).as_posix()]
    if forge(root) in FORGE_FOLDER:
        paths.append(FORGE_FOLDER[forge(root)])
    for manifest in find_manifests(root):
        try:
            data = yaml.safe_load(manifest.read_text(encoding="utf-8")) or {}
        except (OSError, yaml.YAMLError):
            data = {}
        module = data.get("module") if isinstance(data, dict) else None
        # A value the engine does not know, or a manifest it cannot read, is judged as critical.
        if not isinstance(module, dict) or module.get("criticality") not in ("prototype", "standard"):
            paths.append(manifest.parent.relative_to(root).as_posix() + "/")
    return list(dict.fromkeys(paths))


def unowned(root: Path, text: str) -> tuple[bool, list[str]]:
    """Whether the file names a default owner, and the paths a human must approve that end on a
    rule with none — a folder by its own name and by every file it holds."""
    read = rules(text)
    missing = []
    for path in wanted(root):
        probes = [path + NOBODY] if path.endswith("/") else [path]
        folder = root / path
        if path.endswith("/") and folder.is_dir():
            probes += [file.relative_to(root).as_posix() for file in folder.rglob("*") if file.is_file()]
        if not all(owned(read, probe) for probe in probes):
            missing.append(path)
    return owned(read, NOBODY), missing
