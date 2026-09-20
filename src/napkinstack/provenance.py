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
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import url2pathname

import yaml

ANSWERS = ".copier-answers.yml"
PUBLISHED = re.compile(r"v\d+\.\d+\.\d+")


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
    return distribution.version, f"a local checkout at {commit or 'an unknown commit'}"


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
            + ": these rules are no published version (PDR-0005).")
