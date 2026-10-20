"""D133: a contract version's page is the contract, when someone relies on it (#200).

`is_description` counted a `README.md` at any depth as a module's description, and a contract's
page is `contracts/<name>/v<n>/README.md`: a pull request changing only the page of a version a
module consumes touched "0 modules", and no test sheet was asked — while `contracts/AGENTS.md`
says such a page is held by review and by nothing else. PDR-0012's relief stays for a version
nobody relies on yet: no consumer, no schema. Run by platform/tests/run.sh.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest
import yaml

from napkinstack import pull_request
from test_guardrails import VALID, degrade

IDENTITY = {"GIT_AUTHOR_NAME": "test", "GIT_AUTHOR_EMAIL": "test@example.invalid",
            "GIT_COMMITTER_NAME": "test", "GIT_COMMITTER_EMAIL": "test@example.invalid"}
CONTRACTS = degrade(module__name="contracts", module__responsibility="Holds the contracts.",
                    module__criticality="high")


def git(root, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=root, env={**os.environ, **IDENTITY}, check=True,
                          capture_output=True, text=True).stdout.strip()


def manifest(path: Path, data: dict) -> None:
    path.mkdir(parents=True, exist_ok=True)
    (path / "MANIFEST.yaml").write_text(yaml.safe_dump(data), encoding="utf-8")


def project(root: Path, consumed: bool, schema: bool) -> str:
    """A contracts module holding `orders/v1`, provided by `shop`; `billing` consumes it when
    `consumed`. Returns the base commit."""
    git(root, "init", "-q", "--initial-branch=main")
    manifest(root / "contracts", CONTRACTS)
    page = root / "contracts" / "orders" / "v1"
    page.mkdir(parents=True)
    (page / "README.md").write_text("# orders — version 1\n\nAn order is placed once.\n", encoding="utf-8")
    if schema:
        (page / "order.schema.json").write_text("{}\n", encoding="utf-8")
    manifest(root / "modules" / "shop", degrade(module__name="shop", provides=[
        {"contract": "orders", "version": "v1", "path": "contracts/orders/v1", "stability": "stable"}]))
    consumes = [{"contract": "orders", "version": "v1", "module": "shop"}] if consumed else []
    manifest(root / "modules" / "billing", degrade(module__name="billing", consumes=consumes))
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "base")
    return git(root, "rev-parse", "HEAD")


def page_changed(root: Path) -> list[str]:
    (root / "contracts/orders/v1/README.md").write_text(
        "# orders — version 1\n\nAn order may be placed twice.\n", encoding="utf-8")
    git(root, "commit", "-q", "-am", "the page says another thing")
    return ["contracts/orders/v1/README.md"]


@pytest.mark.parametrize("consumed, schema", [(True, False), (False, True), (True, True)])
def test_the_page_of_a_version_someone_relies_on_is_a_change_of_its_module(tmp_path, consumed, schema):
    base = project(tmp_path, consumed, schema)
    touched = pull_request.touched_modules(tmp_path, base, page_changed(tmp_path))
    assert list(touched) == ["contracts"]


def test_the_page_of_a_version_nobody_relies_on_yet_stays_a_description(tmp_path):
    base = project(tmp_path, consumed=False, schema=False)
    assert pull_request.touched_modules(tmp_path, base, page_changed(tmp_path)) == {}


def test_a_module_s_own_readme_stays_a_description(tmp_path):
    base = project(tmp_path, consumed=True, schema=True)
    (tmp_path / "contracts" / "README.md").write_text("# The contracts\n", encoding="utf-8")
    git(tmp_path, "add", "-A")
    git(tmp_path, "commit", "-q", "-m", "the module's own page")
    assert pull_request.touched_modules(tmp_path, base, ["contracts/README.md"]) == {}


def test_pr_check_asks_the_contracts_module_s_test_sheet_for_its_page(tmp_path, monkeypatch, capsys):
    base = project(tmp_path, consumed=True, schema=False)
    page_changed(tmp_path)
    monkeypatch.setenv("PR_BODY", "The page says another thing.")
    monkeypatch.delenv("PR_HEAD_SHA", raising=False)
    code = pull_request.run(tmp_path, base)
    out = capsys.readouterr().out
    assert code == 1 and "FAIL [T1]" in out and "contracts (criticality high)" in out, out
