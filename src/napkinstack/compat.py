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
those under provides[].path; a new version beside it changes nothing merged. A version still
provided at the head is judged wherever it now lives: moving it is no removal (D36).

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

from napkinstack.fitness.manifests import MODULE_DIRS, changed_files, contract_entries, find_manifests

FROZEN_STABILITIES = {"stable", "deprecated"}


def _git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=root, capture_output=True, text=True)


def _load(text: str) -> dict:
    try:
        data = yaml.safe_load(text) or {}
    except yaml.YAMLError:
        return {}
    return data if isinstance(data, dict) else {}


def frozen_versions(root: Path, base: str) -> dict[tuple[str, str], tuple[str, str]]:
    """(contract, version) -> (path, why it is frozen), from the manifests at the base."""
    manifests = [_load(_git(root, "show", f"{base}:{path}").stdout)
                 for path in _git(root, "ls-tree", "-r", "--name-only", base).stdout.split()
                 if path.endswith("/MANIFEST.yaml") and path.split("/")[0] in MODULE_DIRS
                 and len(path.split("/")) in (2, 3)]
    consumers: dict[tuple[str, str], list[str]] = {}
    for data in manifests:
        name = (data.get("module") or {}).get("name") if isinstance(data.get("module"), dict) else None
        for entry in contract_entries(data, "consumes"):
            consumers.setdefault((entry.get("contract"), entry.get("version")), []).append(str(name))
    frozen = {}
    for data in manifests:
        for entry in contract_entries(data, "provides"):
            key, path = (entry.get("contract"), entry.get("version")), entry.get("path")
            if not isinstance(path, str) or not all(isinstance(part, str) for part in key):
                continue
            if key in consumers:
                frozen[key] = (path.strip("/"), f"consumed by {', '.join(sorted(consumers[key]))}")
            elif entry.get("stability") in FROZEN_STABILITIES:
                frozen[key] = (path.strip("/"), entry["stability"])
    return frozen


def provided_now(root: Path) -> dict[tuple[str, str], str]:
    """(contract, version) -> path, from the manifests at the head."""
    now = {}
    for manifest in find_manifests(root):
        for entry in contract_entries(_load(manifest.read_text(encoding="utf-8")), "provides"):
            key, path = (entry.get("contract"), entry.get("version")), entry.get("path")
            if isinstance(path, str) and all(isinstance(part, str) for part in key):
                now[key] = path.strip("/")
    return now


def _holder(root: Path, path: str) -> tuple[str, Path] | None:
    """The module whose folder holds `path`: its name and folder."""
    for manifest in sorted(find_manifests(root), key=lambda m: -len(m.parent.parts)):
        folder = manifest.parent.relative_to(root).as_posix()
        if path == folder or path.startswith(f"{folder}/"):
            return manifest.parent.name, manifest.parent
    return None


def _base_tree(root: Path, base: str, into: Path) -> Path:
    """The whole repository as it is at the base. The proof runs here, so the change it judges
    cannot rewrite what judges it — a script, a fixture, anything it reads (D44). Measured on
    2026-09-20: 7 ms for 1.6 MB."""
    archive = subprocess.run(["git", "archive", "--format=tar", base], cwd=root,
                             capture_output=True, check=True).stdout
    with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
        tar.extractall(into, filter="data")
    return into


def run(root: Path, module: str | None, base: str) -> int:
    if _git(root, "rev-parse", "--verify", "--quiet", f"{base}^{{commit}}").returncode:
        print(f"FAIL [V1] base '{base}' not found: the merged contract versions cannot be read.\n"
              "      Action: fetch the history (fetch-depth: 0), or pass an existing commit.")
        return 1
    fork = _git(root, "merge-base", base, "HEAD").stdout.strip() or base
    changed = changed_files(root, fork)
    now = provided_now(root)
    failures, checked = [], []
    for (contract, version), (path, why) in sorted(frozen_versions(root, fork).items()):
        target = now.get((contract, version))
        if not any(file == place or file.startswith(f"{place}/") for file in changed
                   for place in {path, target} if place):
            continue
        label = f"{contract} {version} ({why})"
        if target is None:
            checked.append(f"{label}: no longer provided — its consumers are checked by B6")
            continue
        if target != path:
            label += f", moved to {target}"
        holder = _holder(root, target)
        if holder is None:
            failures.append(f"[V1] {label} changed at '{target}', which no module holds: nothing declares "
                            "how its versions are compared.\n      Action: keep contracts under contracts/ "
                            "(docs/os/03-contracts.md §2).")
            continue
        if module is not None and holder[0] != module:
            continue
        if not (root / target).exists():
            failures.append(f"[V1] {label}: provided at '{target}', which holds no document (B7).\n"
                            "      Action: commit the version there, or correct provides[].path.")
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
            tree = _base_tree(root, fork, Path(temporary))
            where_it_runs = tree / folder.relative_to(root)
            if not where_it_runs.is_dir():
                failures.append(f"[V1] {label}: module '{name}' has no folder at the base, so its "
                                f"compatibility command cannot be run as merged.\n      Action: "
                                "declare the command where the module now lives, in a pull request "
                                "of its own (docs/os/03-contracts.md §4).")
                continue
            env = {**os.environ, "NSTACK_CONTRACT": contract, "NSTACK_VERSION": version,
                   "NSTACK_BASE_PATH": str(tree / path), "NSTACK_HEAD_PATH": str(root / target)}
            print(f"-> {name}: {command}", flush=True)
            code = subprocess.run(command, shell=True, cwd=where_it_runs, env=env).returncode
        if code:
            failures.append(f"[V1] {label}: the compatibility command of module '{name}' ({where}) "
                            f"did not prove the change compatible (exit {code}).\n"
                            "      Action: read the comparator's output above. If the change is "
                            "breaking, publish it as a new version beside this one and migrate its "
                            "consumers (expand/contract, docs/os/03-contracts.md §4). If the command "
                            "could not run — a missing tool, no network — fix the command: V1 cannot "
                            "pass without a proof.")
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
