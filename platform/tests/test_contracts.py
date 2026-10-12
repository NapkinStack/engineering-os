"""
The contracts module is created by the first contract (PDR-0012, criterion 4).

A project used to be born with `contracts/`: a manifest, an owner, a runbook and a CI job for
a boundary between modules that did not exist yet. Nothing before its moment: the module is
created the day a first contract is, by the command that creates that contract.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from napkinstack import cli
from napkinstack.fitness import manifests

ROOT = Path(__file__).resolve().parents[2]
ANSWERS = "_commit: v0.0.1\n_src_path: https://example.invalid/t.git\ngithub_repo: acme/demo\nowner_team: acme/platform\nproject_name: Demo\n"


def project(root: Path) -> None:
    (root / ".copier-answers.yml").write_text(ANSWERS, encoding="utf-8")
    (root / ".github").mkdir()
    (root / ".github" / "CODEOWNERS").write_text("*  @acme/platform\n", encoding="utf-8")


def test_a_project_is_created_without_a_contracts_module() -> None:
    assert not (ROOT / "skeleton" / "contracts").exists(), "the skeleton still creates contracts/ before any contract"


def test_the_first_contract_creates_the_module_and_the_contract(tmp_path, capsys) -> None:
    project(tmp_path)
    assert cli.main(["new-contract", "session-audio", "--root", str(tmp_path)]) == 0, capsys.readouterr().out
    output = capsys.readouterr().out
    manifest = yaml.safe_load((tmp_path / "contracts" / "MANIFEST.yaml").read_text(encoding="utf-8"))
    assert manifest["module"]["owner"] == "acme/platform", manifest["module"]   # the foundation's owner, by default
    assert manifest["module"]["contact"].endswith("acme/demo/discussions")
    for part in ("AGENTS.md", "README.md", "docs/runbook.md", "tests", "session-audio/v1/README.md"):
        assert (tmp_path / "contracts" / part).exists(), part
    assert "/contracts/" in (tmp_path / ".github" / "CODEOWNERS").read_text(encoding="utf-8")
    assert "contracts/ created" in output and "contracts/session-audio/v1" in output, output
    assert manifests.run(tmp_path) == 0, capsys.readouterr().out     # the module is green as created


def test_a_second_contract_leaves_the_module_as_it_is(tmp_path, capsys) -> None:
    project(tmp_path)
    cli.main(["new-contract", "session-audio", "--root", str(tmp_path)])
    (tmp_path / "contracts" / "AGENTS.md").write_text("# ours now\n", encoding="utf-8")
    capsys.readouterr()
    assert cli.main(["new-contract", "transcript", "--root", str(tmp_path)]) == 0
    output = capsys.readouterr().out
    assert (tmp_path / "contracts" / "AGENTS.md").read_text(encoding="utf-8") == "# ours now\n"
    assert (tmp_path / "contracts" / "transcript" / "v1" / "README.md").is_file()
    assert "contracts/ created" not in output, output
    assert (tmp_path / ".github" / "CODEOWNERS").read_text(encoding="utf-8").count("/contracts/") == 1


@pytest.mark.parametrize(("name", "said"), [("Session Audio", "kebab-case"), ("tests", "reserved"), ("docs", "reserved")])
def test_a_name_that_cannot_be_a_contract_is_refused(tmp_path, capsys, name, said) -> None:
    project(tmp_path)
    assert cli.main(["new-contract", name, "--root", str(tmp_path)]) == 1
    assert said in capsys.readouterr().out
    assert not (tmp_path / "contracts").exists(), "a refused contract left a module behind"


def test_a_contract_that_exists_is_not_overwritten(tmp_path, capsys) -> None:
    project(tmp_path)
    cli.main(["new-contract", "session-audio", "--root", str(tmp_path)])
    capsys.readouterr()
    assert cli.main(["new-contract", "session-audio", "--root", str(tmp_path)]) == 1
    assert "already exists" in capsys.readouterr().out


def test_a_contract_with_a_schema_asks_the_module_for_its_commands(tmp_path, capsys) -> None:
    """The other side of the same rule: a page keeps the module green, a schema does not. The
    day a contract becomes executable, the module that holds it owes a way to check it (M7)."""
    project(tmp_path)
    cli.main(["new-contract", "session-audio", "--root", str(tmp_path)])
    (tmp_path / "contracts" / "session-audio" / "v1" / "schema.json").write_text("{}\n", encoding="utf-8")
    capsys.readouterr()
    assert manifests.run(tmp_path) == 1
    assert "[M7] contracts" in capsys.readouterr().out
