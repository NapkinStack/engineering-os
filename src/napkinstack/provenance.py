"""
Which framework judges a project (PDR-0005): a published version, or something nobody has
published — said out loud on every run that judges, never only in a file.

The engine's origin is what its installer recorded (PEP 610, direct_url.json): nothing for a
version from the registry; a repository with the ref it was asked for and the commit that ref
resolved to, or a local checkout, otherwise. A repository is a supported channel and never a
published one: a tag can be moved, and carries no attestation (ADR-0002).
"""

from __future__ import annotations

import importlib.metadata
import json
import re
import subprocess
import tomllib
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import url2pathname

import yaml

ANSWERS = ".copier-answers.yml"
PUBLISHED = re.compile(r"v\d+\.\d+\.\d+")


def version() -> str:
    """The engine's version. An editable install's metadata is written once, at install, and the
    checkout moves on: its own pyproject.toml says the version its source is at (D122)."""
    distribution = importlib.metadata.distribution("napkinstack")
    try:
        data = json.loads(distribution.read_text("direct_url.json") or "{}")
    except json.JSONDecodeError:  # read at import: a damaged record never stops the engine
        return distribution.version
    if data.get("dir_info", {}).get("editable"):
        source = Path(url2pathname(urlparse(data.get("url", "")).path)) / "pyproject.toml"
        try:
            return str(tomllib.loads(source.read_text(encoding="utf-8"))["project"]["version"])
        except (OSError, KeyError, tomllib.TOMLDecodeError):
            pass
    return distribution.version


def engine() -> tuple[str, str | None]:
    """(version, origin): origin is None for a version installed from the registry."""
    distribution = importlib.metadata.distribution("napkinstack")
    record = distribution.read_text("direct_url.json")
    if not record:
        return distribution.version, None
    data = json.loads(record)
    if "vcs_info" in data:
        # The installer records the ref it was asked for beside the commit (PEP 610). Naming it
        # says more than a bare sha — and no less: a tag can be moved, so this is still not the
        # published artefact (ADR-0002, clarified 2026-09-20).
        commit = str(data["vcs_info"].get("commit_id", ""))[:12]
        wanted = str(data["vcs_info"].get("requested_revision") or "")
        return distribution.version, (f"{data['url']} at {wanted} (commit {commit})" if wanted
                                      else f"{data['url']}@{commit}")
    if "archive_info" in data:
        return distribution.version, "an archive, not the registry"
    path = Path(url2pathname(urlparse(data.get("url", "")).path))
    commit = subprocess.run(["git", "describe", "--always", "--dirty"], cwd=path,
                            capture_output=True, text=True).stdout.strip() if path.is_dir() else ""
    if commit and not commit.endswith("-dirty") and subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=normal"], cwd=path,
            capture_output=True, text=True).stdout.strip():
        commit += "-dirty"  # a file git does not track yet runs as surely as one it does
    return version(), f"a local checkout at {commit or 'an unknown commit'}"


def checkout() -> Path | None:
    """The folder of the local checkout the engine is installed from, editable, or None."""
    distribution = importlib.metadata.distribution("napkinstack")
    try:
        data = json.loads(distribution.read_text("direct_url.json") or "{}")
    except json.JSONDecodeError:
        return None
    if not data.get("dir_info", {}).get("editable"):
        return None
    path = Path(url2pathname(urlparse(data.get("url", "")).path))
    return path if path.is_dir() else None


def holds(folder: Path, tag: str) -> bool:
    """Whether a checkout's HEAD holds a release: the tag is known there and is HEAD's ancestor."""
    known = subprocess.run(["git", "rev-parse", "--verify", "--quiet", f"refs/tags/{tag}^{{commit}}"],
                           cwd=folder, capture_output=True, text=True)
    if known.returncode:
        return False
    return subprocess.run(["git", "merge-base", "--is-ancestor", known.stdout.strip(), "HEAD"],
                          cwd=folder, capture_output=True).returncode == 0


def recorded(root: Path) -> str | None:
    """The framework version the project records, `_commit`, or None outside a project."""
    try:
        answers = yaml.safe_load((root / ANSWERS).read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return None
    return str(answers.get("_commit") or "") or None


def judged_by(root: Path) -> str:
    """The line every judging command prints first."""
    version, origin = engine()
    project = recorded(root)
    on = f", project recorded at {project}" if project else ""
    if origin is None and (project is None or PUBLISHED.fullmatch(project)):
        return f"Judged by NapkinStack {version}, published{on}."
    source = origin or f"napkinstack {version}"
    unpublished = project if project and not PUBLISHED.fullmatch(project) else None
    return (f"Judged by an UNPUBLISHED NapkinStack — {source}"
            + (f", project pinned to {unpublished}" if unpublished else on)
            + ": these rules are no published version.")


def behind(root: Path) -> str | None:
    """What a workstation is told when its engine is older than the project it runs in (D90).

    A teammate's update, once merged, leaves every other workstation there: a command the
    project's manual names answers "invalid choice", and a verdict comes from rules the project
    has left. Said before anything else, on every command — the one that does not exist included.
    An engine ahead of the project is not said: it is the state an update starts from."""
    project = recorded(root)
    if not project or not PUBLISHED.fullmatch(project):
        return None
    version, _ = engine()
    try:
        here = tuple(int(part) for part in version.split(".")[:3])
    except ValueError:
        return None
    wanted = project.removeprefix("v")
    if here >= tuple(int(part) for part in wanted.split(".")):
        return None
    return (f"This workstation runs nstack {version}; the project is on {project}. A command it names "
            "may not exist here, and a verdict given here is not CI's.\n"
            f'      Action: uv tool install "napkinstack=={wanted}" --with-executables-from pre-commit')
