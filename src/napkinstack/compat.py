"""
Contract versions (D30): a merged version that someone relies on changes only with a proof
that the change is additive (docs/os/03-contracts.md §3 and §4).

Rule:
  V1  a frozen contract version changes only when the compatibility command of the module
      holding it, commands.compat, proves the change compatible

A version is frozen when, at the base, a module consumes it or its producer declares it
stable or deprecated. Both the freeze and the proof are read at the base: a pull request can
neither thaw what it changes nor replace the command that judges it — a new proof is merged
on its own first.
An experimental version nobody consumes is free to change — nobody can break. Its files are
those under provides[].path; a new version beside it changes nothing merged.

The command is the project's (P1: no format assumed): an OpenAPI, protobuf or JSON Schema
comparator, named in docs/tooling-profile.md. It runs from the holding module's folder with
  NSTACK_CONTRACT   the contract's name                    catalog-api
  NSTACK_VERSION    the version                            v1
  NSTACK_BASE_PATH  the version as merged, extracted to a temporary folder
  NSTACK_HEAD_PATH  the version as changed, in the working tree
and exits 0 when the change is compatible.

Usage :  nstack compat [module] [--root ROOT] [--base BASE]
Output:  0 when every changed frozen version is proven compatible, 1 otherwise.
"""

from __future__ import annotations

import io
import os
import subprocess
import tarfile
import tempfile
from pathlib import Path

import yaml

from napkinstack.fitness.manifests import MODULE_DIRS, find_manifests

FROZEN_STABILITIES = {"stable", "deprecated"}


def _git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=root, capture_output=True, text=True)


def _load(text: str) -> dict:
    try:
        data = yaml.safe_load(text) or {}
    except yaml.YAMLError:
        return {}
    return data if isinstance(data, dict) else {}


def _entries(data: dict, section: str) -> list[dict]:
    value = data.get(section)
    return [entry for entry in value if isinstance(entry, dict)] if isinstance(value, list) else []


def frozen_versions(root: Path, base: str) -> dict[tuple[str, str], tuple[str, str]]:
    """(contract, version) -> (path, why it is frozen), from the manifests at the base."""
    manifests = [_load(_git(root, "show", f"{base}:{path}").stdout)
                 for path in _git(root, "ls-tree", "-r", "--name-only", base).stdout.split()
                 if path.endswith("/MANIFEST.yaml") and path.split("/")[0] in MODULE_DIRS
                 and len(path.split("/")) in (2, 3)]
    consumers: dict[tuple[str, str], list[str]] = {}
    for data in manifests:
        name = (data.get("module") or {}).get("name") if isinstance(data.get("module"), dict) else None
        for entry in _entries(data, "consumes"):
            consumers.setdefault((entry.get("contract"), entry.get("version")), []).append(str(name))
    frozen = {}
    for data in manifests:
        for entry in _entries(data, "provides"):
            key, path = (entry.get("contract"), entry.get("version")), entry.get("path")
            if not isinstance(path, str) or not all(isinstance(part, str) for part in key):
                continue
            if key in consumers:
                frozen[key] = (path.strip("/"), f"consumed by {', '.join(sorted(consumers[key]))}")
            elif entry.get("stability") in FROZEN_STABILITIES:
                frozen[key] = (path.strip("/"), entry["stability"])
    return frozen


def _holder(root: Path, path: str) -> tuple[str, Path] | None:
    """The module whose folder holds `path`: its name and folder."""
    for manifest in sorted(find_manifests(root), key=lambda m: -len(m.parent.parts)):
        folder = manifest.parent.relative_to(root).as_posix()
        if path == folder or path.startswith(f"{folder}/"):
            return manifest.parent.name, manifest.parent
    return None


def _extract(root: Path, base: str, path: str, into: Path) -> Path:
    archive = subprocess.run(["git", "archive", "--format=tar", base, "--", path], cwd=root,
                             capture_output=True, check=True).stdout
    with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
        tar.extractall(into, filter="data")
    return into / path


def run(root: Path, module: str | None, base: str) -> int:
    if _git(root, "rev-parse", "--verify", "--quiet", f"{base}^{{commit}}").returncode:
        print(f"FAIL [V1] base '{base}' not found: the merged contract versions cannot be read.\n"
              "      Action: fetch the history (fetch-depth: 0), or pass an existing commit.")
        return 1
    fork = _git(root, "merge-base", base, "HEAD").stdout.strip() or base
    changed = _git(root, "diff", "--name-only", f"{fork}...HEAD").stdout.split()
    failures, checked = [], []
    for (contract, version), (path, why) in sorted(frozen_versions(root, fork).items()):
        if not any(file == path or file.startswith(f"{path}/") for file in changed):
            continue
        holder = _holder(root, path)
        label = f"{contract} {version} ({why})"
        if holder is None:
            failures.append(f"[V1] {label} changed at '{path}', which no module holds: nothing declares "
                            "how its versions are compared.\n      Action: keep contracts under contracts/ "
                            "(docs/os/03-contracts.md §2).")
            continue
        if module is not None and holder[0] != module:
            continue
        if not (root / path).exists():
            checked.append(f"{label}: removed — its consumers are checked by B6")
            continue
        if not _git(root, "ls-tree", "-r", "--name-only", fork, "--", path).stdout.strip():
            checked.append(f"{label}: no document at the base, nothing merged to compare")
            continue
        name, folder = holder
        where = f"{folder.relative_to(root).as_posix()}/MANIFEST.yaml"
        commands = _load(_git(root, "show", f"{fork}:{where}").stdout).get("commands")
        command = commands.get("compat") if isinstance(commands, dict) else None
        if not command:
            failures.append(f"[V1] {label} changed, and no merged compatibility command proves the "
                            f"change compatible.\n      Action: declare commands.compat in {where} in a "
                            "pull request of its own (docs/tooling-profile.md), or publish the change as "
                            "a new version beside it (docs/os/03-contracts.md §4).")
            continue
        with tempfile.TemporaryDirectory() as temporary:
            env = {**os.environ, "NSTACK_CONTRACT": contract, "NSTACK_VERSION": version,
                   "NSTACK_BASE_PATH": str(_extract(root, fork, path, Path(temporary))),
                   "NSTACK_HEAD_PATH": str(root / path)}
            print(f"-> {name}: {command}", flush=True)
            code = subprocess.run(command, shell=True, cwd=folder, env=env).returncode
        if code:
            failures.append(f"[V1] {label}: `{command}` exited with {code}, a breaking change.\n"
                            "      Action: publish it as a new version beside it, then migrate its "
                            "consumers (expand/contract, docs/os/03-contracts.md §4).")
        else:
            checked.append(f"{label}: proven compatible")
    for line in checked:
        print(f"Contract version {line}.")
    for failure in failures:
        print(f"FAIL {failure}")
    if failures:
        return 1
    if not checked:
        print("No frozen contract version changed.")
    return 0
