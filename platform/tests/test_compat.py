"""
Contract versions (D30): a frozen version changes only with a proof of compatibility. Every
case proves the rule fails (P5) and names itself (P6). Run by platform/tests/run.sh.
"""

from __future__ import annotations

import os
import subprocess

import pytest
import yaml

from napkinstack import cli
from test_guardrails import CUSTOMERS, VALID, consumes, provides, write_module

IDENTITY = {"GIT_AUTHOR_NAME": "test", "GIT_AUTHOR_EMAIL": "test@example.invalid",
            "GIT_COMMITTER_NAME": "test", "GIT_COMMITTER_EMAIL": "test@example.invalid"}
DOCUMENT = "contracts/customers-api/v1/openapi.yaml"
PROVEN = ('test -f "$NSTACK_BASE_PATH/openapi.yaml" && test -f "$NSTACK_HEAD_PATH/openapi.yaml" '
          '&& [ "$NSTACK_CONTRACT $NSTACK_VERSION" = "customers-api v1" ] '
          '&& ! diff -q "$NSTACK_BASE_PATH/openapi.yaml" "$NSTACK_HEAD_PATH/openapi.yaml" >/dev/null')


def git(root, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=root, env={**os.environ, **IDENTITY}, check=True,
                          capture_output=True, text=True).stdout.strip()


def contracts_module(root, compat: str | None) -> None:
    folder = root / "contracts"
    (folder / "customers-api" / "v1").mkdir(parents=True, exist_ok=True)
    manifest = {"module": {"name": "contracts"}, "commands": {"check": "true", "test": "true"}}
    if compat:
        manifest["commands"]["compat"] = compat
    (folder / "MANIFEST.yaml").write_text(yaml.safe_dump(manifest), encoding="utf-8")


def project(root, stability="experimental", consumer=True, compat=None) -> str:
    """customers provides customers-api v1, billing consumes it when `consumer`; returns the base."""
    git(root, "init", "-q", "--initial-branch=main")
    contracts_module(root, compat)
    (root / DOCUMENT).write_text("required: [id, name]\n", encoding="utf-8")
    producer = provides(CUSTOMERS, "customers")
    producer["provides"][0]["stability"] = stability
    write_module(root, "customers", producer)
    write_module(root, "billing", consumes(VALID, "customers") if consumer else VALID)
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "base")
    return git(root, "rev-parse", "HEAD")


def change(root, path=DOCUMENT, text="required: [id, fullName]\n") -> None:
    (root / path).parent.mkdir(parents=True, exist_ok=True)
    (root / path).write_text(text, encoding="utf-8")
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "change")


CASES = {
    "V1 a consumed version changed, no proof (P4)": (
        {}, {}, "FAIL [V1] customers-api v1 (consumed by billing) changed, and no merged compatibility command", 1),
    "V1 a stable version changed, no proof": (
        {"stability": "stable", "consumer": False}, {}, "FAIL [V1] customers-api v1 (stable) changed", 1),
    "V1 the proof did not prove it (D45)": (
        {"compat": "exit 3"}, {},
        "the compatibility command of module 'contracts' (contracts/MANIFEST.yaml) "
        "did not prove the change compatible (exit 3)", 1),
    "V1 the proof says compatible, with what it needs": (
        {"compat": PROVEN}, {}, "Contract version customers-api v1 (consumed by billing): proven compatible", 0),
    "an experimental version nobody consumes is free": (
        {"consumer": False}, {}, "No frozen contract version changed.", 0),
    "a new version beside it changes nothing merged": (
        {}, {"path": "contracts/customers-api/v2/openapi.yaml"}, "No frozen contract version changed.", 0),
}


@pytest.mark.parametrize(("setup", "edit", "expected", "code"), CASES.values(), ids=CASES.keys())
def test_contract_versions(tmp_path, capfd, setup, edit, expected, code):
    base = project(tmp_path, **setup)
    change(tmp_path, **edit)
    assert cli.main(["compat", "contracts", "--root", str(tmp_path), "--base", base]) == code
    output = capfd.readouterr().out
    assert expected in output, output


def test_frozen_is_read_at_the_base(tmp_path, capfd):
    """Dropping the consumer in the pull request that breaks the version thaws nothing."""
    base = project(tmp_path)
    billing = tmp_path / "modules" / "billing" / "MANIFEST.yaml"
    billing.write_text(yaml.safe_dump({**VALID, "consumes": []}), encoding="utf-8")
    change(tmp_path)
    assert cli.main(["compat", "--root", str(tmp_path), "--base", base]) == 1
    assert "FAIL [V1]" in capfd.readouterr().out


def test_the_proof_is_the_merged_one(tmp_path, capfd):
    """A pull request cannot bring the command that judges it: `compat: true` beside the break."""
    base = project(tmp_path)
    contracts_module(tmp_path, compat="true")
    change(tmp_path)
    assert cli.main(["compat", "--root", str(tmp_path), "--base", base]) == 1
    assert "no merged compatibility command" in capfd.readouterr().out


def test_another_module_does_not_run_the_proof(tmp_path, capfd):
    base = project(tmp_path)
    change(tmp_path)
    assert cli.main(["compat", "billing", "--root", str(tmp_path), "--base", base]) == 0
    assert "No frozen contract version changed." in capfd.readouterr().out


def test_a_frozen_version_outside_any_module(tmp_path, capfd):
    base = project(tmp_path)
    (tmp_path / "contracts" / "MANIFEST.yaml").unlink()
    change(tmp_path)
    assert cli.main(["compat", "billing", "--root", str(tmp_path), "--base", base]) == 1
    assert "which no module holds" in capfd.readouterr().out


MOVE = "contracts/customers-api/v1-current/openapi.yaml"


def move_the_version(root) -> None:
    """The frozen v1 moved to another folder, its provides[].path following it (D36)."""
    git(root, "mv", "contracts/customers-api/v1", "contracts/customers-api/v1-current")
    producer = root / "modules" / "customers" / "MANIFEST.yaml"
    producer.write_text(producer.read_text(encoding="utf-8").replace(
        "path: contracts/customers-api/v1\n", "path: contracts/customers-api/v1-current\n"), encoding="utf-8")


def test_a_frozen_version_moved_and_broken(tmp_path, capfd):
    """D36: moving v1 and breaking it is no removal — v1 is still provided, and judged."""
    base = project(tmp_path, compat="exit 3")
    move_the_version(tmp_path)
    change(tmp_path, path=MOVE)
    assert cli.main(["compat", "contracts", "--root", str(tmp_path), "--base", base]) == 1
    output = capfd.readouterr().out
    assert "moved to contracts/customers-api/v1-current" in output, output
    assert "did not prove the change compatible (exit 3)" in output, output


def test_a_frozen_version_moved_as_is(tmp_path, capfd):
    """D36: a move alone is judged by the same proof, against the new folder; git sees a rename."""
    base = project(tmp_path, compat='diff -r "$NSTACK_BASE_PATH" "$NSTACK_HEAD_PATH"')
    move_the_version(tmp_path)
    git(tmp_path, "commit", "-qam", "move")
    assert cli.main(["compat", "--root", str(tmp_path), "--base", base]) == 0
    assert "moved to contracts/customers-api/v1-current: proven compatible" in capfd.readouterr().out


def test_a_version_whose_document_arrives_now(tmp_path, capfd):
    """Consumed at the base with no document there — possible before B7: nothing merged to break."""
    base = project(tmp_path, compat="exit 3")
    git(tmp_path, "rm", "-q", DOCUMENT)
    git(tmp_path, "commit", "-q", "-m", "no document")
    base = git(tmp_path, "rev-parse", "HEAD")
    change(tmp_path)
    assert cli.main(["compat", "--root", str(tmp_path), "--base", base]) == 0
    assert "no document at the base, nothing merged to compare" in capfd.readouterr().out


def test_unknown_base(tmp_path, capfd):
    project(tmp_path)
    assert cli.main(["compat", "--root", str(tmp_path), "--base", "nope"]) == 1
    assert "FAIL [V1] base 'nope' not found" in capfd.readouterr().out


SCRIPT = "contracts/compare.sh"


def test_a_proof_that_calls_a_file_of_the_tree_runs_from_the_base(tmp_path, capfd):
    """D44: the change rewrites the script its own proof calls. The base's script judges it."""
    base = project(tmp_path, compat="sh compare.sh")
    (tmp_path / SCRIPT).write_text("exit 3\n", encoding="utf-8")
    git(tmp_path, "add", "-A")
    git(tmp_path, "commit", "-q", "-m", "the proof refuses a break")
    base = git(tmp_path, "rev-parse", "HEAD")
    (tmp_path / SCRIPT).write_text("exit 0\n", encoding="utf-8")   # the change rewrites its judge
    change(tmp_path)
    assert cli.main(["compat", "contracts", "--root", str(tmp_path), "--base", base]) == 1
    assert "FAIL [V1]" in capfd.readouterr().out


def test_a_proof_that_could_not_run_is_not_called_a_breaking_change(tmp_path, capfd):
    """D45: a missing tool is the absence of a proof, not the presence of a break."""
    base = project(tmp_path, compat="nstack-no-such-comparator")
    change(tmp_path)
    assert cli.main(["compat", "contracts", "--root", str(tmp_path), "--base", base]) == 1
    output = capfd.readouterr().out
    assert "did not prove the change compatible (exit 127)" in output, output
    assert "breaking change" not in output.split("Action:")[0], output


def test_the_command_is_printed_once(tmp_path, capfd):
    """D45: a multi-line command repeated inside the failure buries the comparator's verdict."""
    base = project(tmp_path, compat="echo comparing\nexit 3")
    change(tmp_path)
    assert cli.main(["compat", "contracts", "--root", str(tmp_path), "--base", base]) == 1
    assert capfd.readouterr().out.count("echo comparing") == 1


def test_a_module_without_a_folder_at_the_base(tmp_path, capfd):
    """The command is read as merged; if its module's folder is not there, say so, never crash."""
    base = project(tmp_path, compat="true")
    git(tmp_path, "mv", "contracts", "shared-contracts")
    producer = tmp_path / "modules" / "customers" / "MANIFEST.yaml"
    producer.write_text(producer.read_text(encoding="utf-8").replace(
        "path: contracts/", "path: shared-contracts/"), encoding="utf-8")
    change(tmp_path, path="shared-contracts/customers-api/v1/openapi.yaml")
    code = cli.main(["compat", "--root", str(tmp_path), "--base", base])
    output = capfd.readouterr().out
    assert code == 1 and "Traceback" not in output, output
