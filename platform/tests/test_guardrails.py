"""
Guardrail checks of the fitness functions: every rule proves it fails (P5) and names
itself (P6).

A compliant module is the baseline; each case degrades it in exactly one way and checks
that the expected rule is reported, with no Python traceback (D8). Run by
platform/tests/run.sh.
"""

from __future__ import annotations

import copy
import datetime
import json
import os
import subprocess
from pathlib import Path

import pytest
import yaml

from napkinstack import cli, skills
from napkinstack.fitness import boundaries, hygiene, manifests

YESTERDAY = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()
VALID = {
    "module": {"name": "billing", "responsibility": "Bills the customers.",
               "owner": "acme/billing", "lifecycle": "active", "criticality": "standard",
               "user_facing": False},
    "provides": [], "consumes": [], "data": {"owns": [], "shared": []},
    "commands": {"check": "true", "test": "true"},
    "docs": {"readme": "README.md", "agents": "AGENTS.md"},
}


def degrade(base=VALID, **changes):
    """Copy of a manifest; `section__key=value`, `None` removes the key."""
    data = copy.deepcopy(base)
    for path, value in changes.items():
        target, keys = data, path.split("__")
        for key in keys[:-1]:
            target = target[key]
        if value is None:
            target.pop(keys[-1], None)
        else:
            target[keys[-1]] = value
    return data


def write_module(root: Path, name: str, manifest=VALID, sources: dict[str, str] | None = None) -> Path:
    folder = root / "modules" / name
    (folder / "tests").mkdir(parents=True)
    for file_ in ("AGENTS.md", "README.md"):
        (folder / file_).write_text("x\n", encoding="utf-8")
    text = manifest if isinstance(manifest, str) else yaml.safe_dump(manifest, allow_unicode=True)
    (folder / "MANIFEST.yaml").write_text(text, encoding="utf-8")
    for path, content in (sources or {}).items():
        (folder / path).parent.mkdir(parents=True, exist_ok=True)
        (folder / path).write_text(content, encoding="utf-8")
    return folder


def expect(code: int, output: str, rule: str, fails: bool) -> None:
    assert f"[{rule}]" in output, output
    assert code == (1 if fails else 0), output


def test_valid_manifest(tmp_path, capsys):
    write_module(tmp_path, "billing")
    assert manifests.run(tmp_path) == 0, capsys.readouterr().out


MANIFEST_CASES = {
    "M1 folder without manifest": (lambda r: (r / "modules" / "orphan").mkdir(parents=True), "M1", True),
    "M2 missing field": (lambda r: write_module(r, "billing", degrade(module__owner=None)), "M2", True),
    "M2 manifest as a list (D8)": (lambda r: write_module(r, "billing", "- a\n- list\n"), "M2", True),
    "M2 module section as text (D8)": (lambda r: write_module(r, "billing", degrade(module="text")), "M2", True),
    "M2 commands section as text (D8)": (lambda r: write_module(r, "billing", degrade(commands="make")), "M2", True),
    "M3 lifecycle": (lambda r: write_module(r, "billing", degrade(module__lifecycle="unknown")), "M3", True),
    "M3 criticality": (lambda r: write_module(r, "billing", degrade(module__criticality="severe")), "M3", True),
    "M4 two sentences": (lambda r: write_module(r, "billing", degrade(module__responsibility="Bills. Chases.")), "M4", False),
    "M4 conjunction": (lambda r: write_module(r, "billing", degrade(
        module__responsibility="Bills customers and sends the monthly statements to the accounting team every single month.")), "M4", False),
    "M5 deprecated without a date": (lambda r: write_module(r, "billing", degrade(module__lifecycle="deprecated")), "M5", True),
    "M5 date passed": (lambda r: write_module(r, "billing", degrade(
        module__lifecycle="deprecated", module__deprecation={"removal_date": YESTERDAY})), "M5", True),
    "M2 a contract's version as a number (D36)": (lambda r: write_module(r, "billing", degrade(
        provides=[{"contract": "billing-api", "version": 1, "path": "contracts/billing-api/v1"}])), "M2", True),
    "M2 a stability nobody knows (D36)": (lambda r: write_module(r, "billing", degrade(
        provides=[{"contract": "billing-api", "version": "v1", "path": "contracts/billing-api/v1",
                   "stability": "Stable"}])), "M2", True),
    "M2 a consumed contract's module as a number (D36)": (lambda r: write_module(r, "billing", degrade(
        consumes=[{"contract": "customers-api", "version": "v1", "module": 7}])), "M2", True),
    "M6 deprecated contract without a date": (lambda r: write_module(r, "billing", degrade(
        provides=[{"contract": "billing-api", "version": "v1", "stability": "deprecated"}])), "M6", True),
    "M6 date passed": (lambda r: write_module(r, "billing", degrade(provides=[
        {"contract": "billing-api", "version": "v1", "stability": "deprecated", "removal_date": YESTERDAY}])), "M6", True),
    "M7 missing verb, the module holds code": (lambda r: write_module(
        r, "billing", degrade(commands={"check": "true"}), {"src/app.py": "x\n"}), "M7", True),
    "M8 runbook missing": (lambda r: write_module(r, "billing", degrade(module__criticality="high")), "M8", True),
    "M9 AGENTS.md missing": (lambda r: (write_module(r, "billing") / "AGENTS.md").unlink(), "M9", True),
    "M9 tests missing": (lambda r: (write_module(r, "billing") / "tests").rmdir(), "M9", True),
    "M10 user_facing missing": (lambda r: write_module(r, "billing", degrade(module__user_facing=None)), "M10", True),
    "M10 user_facing as text": (lambda r: write_module(r, "billing", degrade(module__user_facing="yes")), "M10", True),
}


@pytest.mark.parametrize(("prepare", "rule", "fails"), MANIFEST_CASES.values(), ids=MANIFEST_CASES.keys())
def test_manifests(tmp_path, capsys, prepare, rule, fails):
    prepare(tmp_path)
    code = manifests.run(tmp_path)
    expect(code, capsys.readouterr().out, rule, fails)


def test_a_module_holding_only_its_description_declares_no_verb(tmp_path, capsys):
    """D33: nothing to check yet, so nothing to declare; docs/ and placeholders included."""
    folder = write_module(tmp_path, "billing", degrade(commands={}), {"docs/adr/0001.md": "x\n", "src/.gitkeep": ""})
    assert manifests.run(tmp_path) == 0, capsys.readouterr().out
    (folder / "src" / "app.py").write_text("x\n", encoding="utf-8")
    assert manifests.run(tmp_path) == 1
    assert "[M7] billing" in capsys.readouterr().out


def test_new_module_between_two_cycles_names_the_cycle(tmp_path, capsys):
    """D47: the charter is accepted; sending the reader back to framing would be false."""
    from test_plan import framed

    framed(tmp_path, cycles={})
    assert cli.main(["new-module", "face", "acme/web", "standard", "--root", str(tmp_path)]) == 0
    output = capsys.readouterr().out
    assert "No accepted cycle: delivery work needs one (K1)" in output, output
    assert "The project is not framed" not in output, output


def test_new_module_says_what_its_pull_requests_will_need(tmp_path, capsys):
    """D33: green as created; the sheet and the cycle named from facts nstack holds."""
    from test_plan import framed

    assert cli.main(["new-module", "face", "acme/web", "standard", "--user-facing", "--root", str(tmp_path)]) == 0
    output = capsys.readouterr().out
    assert "carries a test sheet (user-facing)" in output and "The project is not framed" in output, output
    for verb in ("check", "test"):
        assert cli.main([verb, "face", "--root", str(tmp_path)]) == 0
        assert f"face: holds only its description, nothing to {verb} yet." in capsys.readouterr().out
    framed(tmp_path)
    assert cli.main(["new-module", "back", "acme/web", "high", "--root", str(tmp_path)]) == 0
    output = capsys.readouterr().out
    assert "carries a test sheet (criticality high)" in output and "a ready deliverable of 01-first.md" in output, output


def test_the_first_edit_of_a_new_manifest_is_valid(tmp_path, capsys):
    """D40: uncommenting check and test, as M7 asks, gives a manifest M2 can read."""
    assert cli.main(["new-module", "billing", "acme/billing", "standard", "--root", str(tmp_path)]) == 0
    manifest = tmp_path / "modules" / "billing" / "MANIFEST.yaml"
    text = manifest.read_text(encoding="utf-8").replace("#  check:", "  check: 'true'").replace("#  test:", "  test: 'true'")
    manifest.write_text(text, encoding="utf-8")
    assert yaml.safe_load(text)["commands"] == {"check": "true", "test": "true"}
    capsys.readouterr()
    assert manifests.run(tmp_path) == 0, capsys.readouterr().out


def test_new_module_high_criticality_generates_a_runbook(tmp_path, capsys):
    """M8 requires a runbook from criticality=high on: the scaffolding must write it."""
    assert cli.main(["new-module", "demo", "acme/demo-team", "high", "--root", str(tmp_path)]) == 0
    assert (tmp_path / "modules" / "demo" / "docs" / "runbook.md").is_file(), capsys.readouterr().out
    capsys.readouterr()
    assert manifests.run(tmp_path) == 0, capsys.readouterr().out


def test_new_module_user_facing(tmp_path, capsys):
    """PDR-0003: a module declares whether a user sees it; the flag writes it."""
    assert cli.main(["new-module", "face", "acme/web", "standard", "--user-facing", "--root", str(tmp_path)]) == 0
    manifest = yaml.safe_load((tmp_path / "modules" / "face" / "MANIFEST.yaml").read_text(encoding="utf-8"))
    assert manifest["module"]["user_facing"] is True, capsys.readouterr().out
    capsys.readouterr()
    assert manifests.run(tmp_path) == 0, capsys.readouterr().out


CUSTOMERS = degrade(module__name="customers", module__owner="acme/customers")


def provides(manifest, module, versions=("v1",)):
    """The module provides `<module>-api` in each version, at contracts/<module>-api/<version>."""
    return {**manifest, "provides": [{"contract": f"{module}-api", "version": version,
                                      "path": f"contracts/{module}-api/{version}", "stability": "stable"}
                                     for version in versions]}


def consumes(manifest, module, version="v1"):
    return {**manifest, "consumes": [{"contract": f"{module}-api", "version": version, "module": module}]}


PRODUCER = provides(CUSTOMERS, "customers")
READS = {"src/client.py": 'SPEC = ROOT / "contracts" / "customers-api" / "v1" / "openapi.yaml"\n'}


def test_valid_boundaries(tmp_path, capsys):
    write_module(tmp_path, "billing")
    write_module(tmp_path, "customers", CUSTOMERS)
    assert boundaries.run(tmp_path) == 0, capsys.readouterr().out


def test_a_contract_read_and_declared_is_the_real_graph(tmp_path, capsys):
    """D29: the only dependency allowed between modules is seen, and warns of nothing."""
    write_contract(tmp_path, "customers-api/v1")
    write_module(tmp_path, "billing", consumes(VALID, "customers"), READS)
    write_module(tmp_path, "customers", PRODUCER)
    assert boundaries.run(tmp_path) == 0
    output = capsys.readouterr().out
    assert "billing → customers (contract customers-api)" in output and "WARNING" not in output, output


def write_contract(root: Path, *versions: str) -> None:
    """Contract documents under contracts/, the module that holds them in every project."""
    (root / "contracts").mkdir(exist_ok=True)
    (root / "contracts" / "MANIFEST.yaml").write_text("module: {name: contracts}\n", encoding="utf-8")
    for version in versions:
        (root / "contracts" / version).mkdir(parents=True)
        (root / "contracts" / version / "openapi.yaml").write_text("openapi: 3.1.0\n", encoding="utf-8")


BOUNDARY_CASES = {
    "B1 a contract read without being declared (P3)": ({
        "billing": (VALID, READS), "customers": (PRODUCER, {})}, "B1", True),
    "B1 another version than the one consumed": ({
        "billing": (consumes(VALID, "customers"), {"src/client.py": 'SPEC = "contracts/customers-api/v2"\n'}),
        "customers": (provides(CUSTOMERS, "customers", ("v1", "v2")), {})}, "B1", True),
    "B2 an import of another module": ({
        "billing": (VALID, {"src/app.py": "from modules.customers.api import customer\n"}),
        "customers": (CUSTOMERS, {})}, "B2", True),
    "B2 its package, even with its contract consumed": ({
        "billing": (consumes(VALID, "customers"), {**READS, "src/app.py": "from customers.models import Customer\n"}),
        "customers": (PRODUCER, {})}, "B2", True),
    "B2 internal implementation": ({
        "billing": (VALID, {"src/app.js": 'import { db } from "../customers/src/db";\n'}),
        "customers": (CUSTOMERS, {})}, "B2", True),
    "B2 a path into its folder, whatever the line (P2)": ({
        "billing": (VALID, {"src/app.py": 'sys.path.insert(0, "../customers/src")\n'}),
        "customers": (CUSTOMERS, {})}, "B2", True),
    "B2 its package named by code_name": ({
        "billing": (VALID, {"src/App.java": "import com.acme.customers.Customer;\n"}),
        "customers": (degrade(CUSTOMERS, module__code_name="com.acme.customers"), {})}, "B2", True),
    "B2 a Go import block (D41)": ({
        "billing": (VALID, {"src/app.go": 'import (\n\t"fmt"\n\t"example.com/shop/modules/customers"\n)\n'}),
        "customers": (CUSTOMERS, {})}, "B2", True),
    "B2 the module imported from the root package (D41)": ({
        "billing": (VALID, {"src/app.py": "from modules import customers\n"}),
        "customers": (CUSTOMERS, {})}, "B2", True),
    "B2 a path dependency in a build file": ({
        "billing": (VALID, {"pyproject.toml": 'customers = { path = "../customers" }\n'}),
        "customers": (CUSTOMERS, {})}, "B2", True),
    "B3 circular dependency": ({
        "billing": (VALID, {"src/app.py": "from modules.customers.api import customer\n"}),
        "customers": (CUSTOMERS, {"src/app.py": "from modules.billing.api import invoice\n"})},
        "B3", True),
    "B4 a contract consumed and never read": ({
        "billing": (consumes(VALID, "customers"), {}), "customers": (PRODUCER, {})}, "B4", False),
    "B5 another module's table": ({
        "billing": (degrade(data={"owns": ["invoices"], "shared": []}), {}),
        "customers": (CUSTOMERS, {"src/query.py": 'SQL = "SELECT * FROM invoices"\n'})}, "B5", True),
    "B6 a consumed contract nobody provides": ({
        "billing": (consumes(VALID, "customers"), READS), "customers": (CUSTOMERS, {})}, "B6", True),
    "B6 the wrong producer named": ({
        "billing": ({**VALID, "consumes": [{"contract": "customers-api", "version": "v1", "module": "orders"}]}, READS),
        "customers": (PRODUCER, {})}, "B6", True),
    "B7 a provided contract with no document": ({
        "customers": (provides(CUSTOMERS, "customers", ("v9",)), {})}, "B7", True),
}


@pytest.mark.parametrize(("modules_map", "rule", "fails"), BOUNDARY_CASES.values(), ids=BOUNDARY_CASES.keys())
def test_boundaries(tmp_path, capsys, modules_map, rule, fails):
    write_contract(tmp_path, "customers-api/v1", "customers-api/v2")
    for name, (manifest, sources) in modules_map.items():
        write_module(tmp_path, name, manifest, sources)
    code = boundaries.run(tmp_path)
    expect(code, capsys.readouterr().out, rule, fails)


def test_a_cycle_through_contracts_is_a_cycle(tmp_path, capsys):
    """D37: the contracts are the only dependency allowed, so B3 reads them."""
    write_contract(tmp_path, "customers-api/v1", "billing-api/v1")
    billing = consumes(provides(VALID, "billing"), "customers")
    customers = consumes(PRODUCER, "billing")
    write_module(tmp_path, "billing", billing, {"src/c.py": 'P = "contracts/customers-api/v1"\n'})
    write_module(tmp_path, "customers", customers, {"src/c.py": 'P = "contracts/billing-api/v1"\n'})
    assert boundaries.run(tmp_path) == 1
    assert "[B3] billing → customers → billing" in capsys.readouterr().out


def test_a_contract_outside_every_module_folder(tmp_path, capsys):
    """D39: nothing would compare its versions — V1 runs for the module holding a contract."""
    (tmp_path / "schemas" / "customers-api" / "v1").mkdir(parents=True)
    (tmp_path / "schemas" / "customers-api" / "v1" / "openapi.yaml").write_text("x\n", encoding="utf-8")
    producer = {**CUSTOMERS, "provides": [{"contract": "customers-api", "version": "v1",
                                           "path": "schemas/customers-api/v1"}]}
    write_module(tmp_path, "customers", producer)
    assert boundaries.run(tmp_path) == 1
    assert "[B7] customers" in capsys.readouterr().out


NOT_ANOTHER_MODULE = {
    "a submodule of its own named like another module": "from billing import customers\n",
    "a local file named like another module": 'import { list } from "./customers";\n',
    "a sentence naming the other module": "# Never reads customers directly: from `customers`, only the contract.\n",
    "a word that starts like another module": "from billing.customersupport import ticket\n",
    "a string naming another module's folder": 'assert not [p for p in sys.path if "modules/customers" in p]\n',
    "a subpackage of its own named like another module": "from billing.customers.models import Customer\n",
    "a relative import of its own": "from ..customers.models import Customer\n",
    "a local folder named like another module": 'import { list } from "./lib/customers/list";\n',
    "an alias of its own source root": 'import { list } from "@/customers/list";\n',
    "a Go package of its own": 'import "example.com/billing/customers/store"\n',
    "a file named like another module": 'DATA = open("../customers.csv")\n',
}


def test_an_own_folder_named_like_another_module(tmp_path, capsys):
    """D41: `../customers/view` from the module's own src/ui/ is its own src/customers/."""
    write_module(tmp_path, "billing", VALID, {"src/ui/page.ts": 'import { view } from "../customers/view";\n',
                                              "src/customers/view.ts": "export const view = 1;\n"})
    write_module(tmp_path, "customers", CUSTOMERS)
    assert boundaries.run(tmp_path) == 0, capsys.readouterr().out


def test_a_contract_stored_in_its_producer_folder(tmp_path, capsys):
    """D41: reading the contract where its producer keeps it is a contract read, not its code."""
    document = tmp_path / "modules" / "customers" / "contracts" / "customers-api" / "v1" / "openapi.yaml"
    producer = {**CUSTOMERS, "provides": [{"contract": "customers-api", "version": "v1",
                                           "path": "modules/customers/contracts/customers-api/v1"}]}
    write_module(tmp_path, "customers", producer)
    document.parent.mkdir(parents=True)
    document.write_text("x\n", encoding="utf-8")
    write_module(tmp_path, "billing", consumes(VALID, "customers"),
                 {"src/c.py": 'SPEC = "../../modules/customers/contracts/customers-api/v1/openapi.yaml"\n'})
    assert boundaries.run(tmp_path) == 0, capsys.readouterr().out


@pytest.mark.parametrize("line", NOT_ANOTHER_MODULE.values(), ids=NOT_ANOTHER_MODULE.keys())
def test_boundaries_no_false_positive(tmp_path, capsys, line):
    write_module(tmp_path, "billing", VALID, {"src/app.py": line})
    write_module(tmp_path, "customers", CUSTOMERS)
    assert boundaries.run(tmp_path) == 0, capsys.readouterr().out


MALFORMED = {
    "a contract as a list": {"consumes": [{"contract": ["a"], "version": "v1", "module": "customers"}]},
    "a table as a mapping": {"data": {"owns": [{"table": "invoices"}], "shared": []}},
    "a table as a number": {"data": {"owns": [2024], "shared": []}},
    "a code name as a number": {"module": {**VALID["module"], "code_name": 42}},
    "a module name as a number": {"module": {**VALID["module"], "name": 2024}},
}


@pytest.mark.parametrize("change", MALFORMED.values(), ids=MALFORMED.keys())
def test_a_malformed_manifest_is_reported_not_crashed_on(tmp_path, capsys, change):
    """D40: M2 names the field; boundaries reads around it, with no traceback (D8)."""
    write_contract(tmp_path, "customers-api/v1")
    write_module(tmp_path, "billing", {**VALID, **change}, {"src/app.py": 'P = "customers-api"\n'})
    write_module(tmp_path, "customers", PRODUCER)
    boundaries.run(tmp_path)
    assert manifests.run(tmp_path) == 1
    assert "[M2] billing" in capsys.readouterr().out


def test_no_git_on_the_path(tmp_path, capsys, monkeypatch):
    """D40: a module's files are still read — as outside a repository."""
    write_module(tmp_path, "billing", degrade(commands={}), {"src/app.py": "x\n"})
    monkeypatch.setenv("PATH", "")
    assert manifests.run(tmp_path) == 1
    assert "[M7] billing" in capsys.readouterr().out


def test_boundaries_unreadable_manifest_without_traceback(tmp_path, capsys):
    write_module(tmp_path, "billing")
    write_module(tmp_path, "customers", "- a\n- list\n")
    write_module(tmp_path, "inventory", degrade(module__name="inventory", consumes="customers"))
    assert boundaries.run(tmp_path) == 0, capsys.readouterr().out


def write_skills(root: Path, mapping) -> None:
    (root / "playbooks").mkdir()
    (root / "playbooks" / "tests.md").write_text("# Tests\n", encoding="utf-8")
    (root / ".nstack").mkdir()
    text = mapping if isinstance(mapping, str) else yaml.safe_dump(mapping, allow_unicode=True)
    (root / ".nstack" / "skills.yaml").write_text(text, encoding="utf-8")


TESTS = {"source": "playbooks/tests.md", "description": "Test strategy."}
SKILL_CASES = {
    "S2 source not found": {"skills": {"tests": TESTS, "missing": {**TESTS, "source": "playbooks/absent.md"}}},
    "S2 empty description": {"skills": {"tests": {**TESTS, "description": ""}}},
    "S2 mapping as a list (D8)": "- tests\n",
    "S2 entry as text (D8)": {"skills": {"tests": "playbooks/tests.md"}},
}


@pytest.mark.parametrize("mapping", SKILL_CASES.values(), ids=SKILL_CASES.keys())
def test_skills(tmp_path, capsys, mapping):
    write_skills(tmp_path, mapping)
    code = skills.run(tmp_path, check_only=True)
    expect(code, capsys.readouterr().out, "S2", True)


def repository(root: Path, files: dict[str, int]) -> str:
    """Git repository with two commits; returns the base. Files carry n lines."""
    env = {**os.environ, "GIT_AUTHOR_NAME": "test", "GIT_AUTHOR_EMAIL": "test@example.invalid",
           "GIT_COMMITTER_NAME": "test", "GIT_COMMITTER_EMAIL": "test@example.invalid"}

    def git(*args: str) -> str:
        return subprocess.run(["git", *args], cwd=root, env=env, check=True,
                              capture_output=True, text=True).stdout.strip()

    git("init", "-q", "--initial-branch=main")
    (root / "README.md").write_text("base\n", encoding="utf-8")
    git("add", "-A")
    git("commit", "-q", "-m", "base")
    base = git("rev-parse", "HEAD")
    for path, lines in files.items():
        (root / path).parent.mkdir(parents=True, exist_ok=True)
        (root / path).write_text("line\n" * lines, encoding="utf-8")
    git("add", "-A")
    git("commit", "-q", "-m", "change")
    return base


A_MODULE = {"modules/a/MANIFEST.yaml": 1, "modules/a/x.txt": 1}
TWO_MODULES = {**A_MODULE, "modules/b/MANIFEST.yaml": 1, "modules/b/y.txt": 1}
PR_CASES = {
    "P1 two modules": (TWO_MODULES, {}, "FAIL [P1]", 1),
    "P1 cross-module label": (TWO_MODULES, {"PR_LABELS": "cross-module"}, "WARNING [P1]", 0),
    "P1 another module's description changes no module": (
        {**A_MODULE, "modules/b/MANIFEST.yaml": 1, "modules/b/README.md": 1}, {}, "Modules touched : 1", 0),
    "P1 contracts/ is a module (D34)": (
        {**A_MODULE, "contracts/MANIFEST.yaml": 1, "contracts/a-api/v1/schema.json": 1}, {}, "FAIL [P1]", 1),
    "P2 over budget": ({"modules/a/x.txt": 3}, {"MAX_LINES": "1"}, "WARNING [P2] Over the review budget.", 0),
    "P2 an empty budget is the default (D40)": ({"modules/a/x.txt": 3}, {"MAX_LINES": ""}, "3/400 lines", 0),
    "P2 a budget that is no number (D40)": ({"modules/a/x.txt": 3}, {"MAX_FILES": "many"},
                                            "FAIL [pr-scope] MAX_FILES 'many' is not a number", 1),
}


@pytest.mark.parametrize(("files", "variables", "expected", "expected_code"), PR_CASES.values(), ids=PR_CASES.keys())
def test_pr_scope(tmp_path, capfd, monkeypatch, files, variables, expected, expected_code):
    base = repository(tmp_path, files)
    monkeypatch.delenv("PR_LABELS", raising=False)
    for name, value in variables.items():
        monkeypatch.setenv(name, value)
    code = cli.main(["pr-scope", "--root", str(tmp_path), "--base", base])
    output = capfd.readouterr().out
    assert expected in output, output
    assert code == expected_code, output


def test_pr_scope_on_an_unknown_base(tmp_path, capsys):
    """D40: a check that cannot read its base refuses, as compat and modules do."""
    repository(tmp_path, A_MODULE)
    assert cli.main(["pr-scope", "--root", str(tmp_path), "--base", "nope"]) == 1
    assert "FAIL [pr-scope] base 'nope' not found" in capsys.readouterr().out


def test_modules_changed_since(tmp_path, capsys):
    """One list of modules for CI: every folder holding a manifest, contracts/ included (D34)."""
    base = repository(tmp_path, {**A_MODULE, "contracts/MANIFEST.yaml": 1, "docs/notes.md": 1})
    assert cli.main(["modules", "--root", str(tmp_path), "--changed-since", base, "--json"]) == 0
    assert json.loads(capsys.readouterr().out) == [{"name": "a", "folder": "modules/a"},
                                                   {"name": "contracts", "folder": "contracts"}]
    assert cli.main(["modules", "--root", str(tmp_path), "--changed-since", "nope"]) == 1
    assert "FAIL [modules] base 'nope' not found" in capsys.readouterr().out


def moved(root: Path, *commands: list[str]) -> str:
    """A base holding modules a and b, then one commit running `commands`; returns the base."""
    repository(root, TWO_MODULES)
    env = {**os.environ, "GIT_AUTHOR_NAME": "test", "GIT_AUTHOR_EMAIL": "test@example.invalid",
           "GIT_COMMITTER_NAME": "test", "GIT_COMMITTER_EMAIL": "test@example.invalid"}
    base = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True).stdout.strip()
    for command in commands:
        subprocess.run(command, cwd=root, env=env, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-q", "-m", "change"], cwd=root, env=env, check=True)
    return base


def test_a_file_moved_between_modules_touches_both(tmp_path, capsys):
    """D38: git reports a rename under its new name only; the module it left changed too."""
    base = moved(tmp_path, ["git", "mv", "modules/a/x.txt", "modules/b/x.txt"])
    assert cli.main(["modules", "--root", str(tmp_path), "--changed-since", base, "--json"]) == 0
    assert [m["name"] for m in json.loads(capsys.readouterr().out)] == ["a", "b"]
    assert cli.main(["pr-scope", "--root", str(tmp_path), "--base", base]) == 1
    assert "FAIL [P1]" in capsys.readouterr().out


def test_a_file_named_in_any_script_is_seen(tmp_path, capsys):
    """D38: git quotes a non-ASCII name unless told otherwise; the module still changed."""
    base = moved(tmp_path, ["sh", "-c", "printf 'x' > 'modules/a/r\u00e9ponse.json' && git add -A"])
    assert cli.main(["modules", "--root", str(tmp_path), "--changed-since", base, "--json"]) == 0
    assert [m["name"] for m in json.loads(capsys.readouterr().out)] == ["a"]


OWNERS = {
    "team": ("acme/billing", True),
    "user": ("alice", True),
    "user with hyphens": ("a-l-i-c-e", True),
    "user of 39 characters": ("a" * 39, True),
    "leading hyphen": ("-alice", False),
    "trailing hyphen": ("alice-", False),
    "double hyphen": ("al--ice", False),
    "user of 40 characters": ("a" * 40, False),
    "team without a name": ("acme/", False),
    "space": ("bad owner", False),
}


@pytest.mark.parametrize(("owner", "accepted"), OWNERS.values(), ids=OWNERS.keys())
def test_new_module_owner(tmp_path, capsys, owner, accepted):
    """A team, or a user when the project has no organisation (PDR-0001, clarification)."""
    code = cli.main(["new-module", "--root", str(tmp_path), "--", "demo", owner, "standard"])
    output = capsys.readouterr().out
    assert code == (0 if accepted else 1), output
    assert accepted or f"FAIL [new-module] invalid owner '{owner}'" in output


# --- H: what a shared repository must not carry -----------------------------------------
# The offending paths are assembled at run time on purpose: written literally, they would
# be findings of H1 in this very file. The rule has no allowlist, and no file escapes it.
REFUSED = {
    "home of a named user": "/" + "home/alice/workspace/notes.md",
    "macOS home": "/" + "Users/alice/workspace/notes.md",
    "Windows home": "C:" + "\\Users\\alice\\workspace\\notes.md",
    "tilde on a real folder": "~/" + "Downloads/napkinstack-agent.private-key.pem",
}
ACCEPTED = {
    "dot-directory": "~/.config/napkinstack/settings.json",
    "placeholder": "~/<workspace>/project",
    "tilde alone": "the home directory, ~/, is where it lands",
    "a variable": "$HOME/workspace/project",
}


def tracked(root: Path, files: dict[str, str]) -> None:
    """A git repository whose tracked files carry the given contents."""
    env = {**os.environ, "GIT_AUTHOR_NAME": "test", "GIT_AUTHOR_EMAIL": "test@example.invalid",
           "GIT_COMMITTER_NAME": "test", "GIT_COMMITTER_EMAIL": "test@example.invalid"}
    subprocess.run(["git", "init", "-q", "--initial-branch=main"], cwd=root, check=True)
    for name, content in files.items():
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        (root / name).write_text(content, encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=root, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "files"], cwd=root, env=env, check=True)


@pytest.mark.parametrize("path", REFUSED.values(), ids=REFUSED.keys())
def test_hygiene(tmp_path, capsys, path):
    tracked(tmp_path, {"docs/runbook.md": f"Run it from {path}, then commit.\n"})
    code = hygiene.run(tmp_path)
    output = capsys.readouterr().out
    expect(code, output, "H1", True)
    assert "docs/runbook.md:1" in output, output


SAME_EVERYWHERE = {
    "a container image's working directory": ("Dockerfile", "WORKDIR /" + "home/node/app\n"),
    "a development container's user": (".devcontainer/devcontainer.json", '{"remoteUser": "vscode", "mounts": ["/' + 'home/vscode/.cache"]}\n'),
    "a composed service": ("compose.yaml", "services:\n  app:\n    working_dir: /" + "home/node/app\n"),
    "a CI runner's workspace, in prose": ("docs/ci.md", "The runner clones into /" + "home/runner/work, every time.\n"),
    "a tilde inside an address": ("docs/links.md", "See https://example.org/~" + "/docs for the manual.\n"),
}


@pytest.mark.parametrize(("name", "text"), SAME_EVERYWHERE.values(), ids=SAME_EVERYWHERE.keys())
def test_hygiene_accepts_an_image_or_a_runner(tmp_path, capsys, name, text):
    """D41: an image's home is the same on every machine; only one person's machine is refused."""
    tracked(tmp_path, {name: text})
    assert hygiene.run(tmp_path) == 0, capsys.readouterr().out


def test_hygiene_accepts_what_is_true_on_every_machine(tmp_path, capsys):
    tracked(tmp_path, {f"docs/{name}.md": f"{text}\n" for name, text in
                       zip(("a", "b", "c", "d"), ACCEPTED.values())})
    assert hygiene.run(tmp_path) == 0, capsys.readouterr().out


def test_hygiene_reads_only_tracked_files(tmp_path, capsys):
    tracked(tmp_path, {"docs/runbook.md": "nothing here\n"})
    (tmp_path / "scratch.md").write_text(f"{REFUSED['macOS home']}\n", encoding="utf-8")
    assert hygiene.run(tmp_path) == 0, capsys.readouterr().out


def test_hygiene_outside_a_git_repository(tmp_path, capsys):
    assert hygiene.run(tmp_path) == 0
    assert "not applicable" in capsys.readouterr().out


def test_hygiene_ignores_a_binary_file(tmp_path, capsys):
    tracked(tmp_path, {"docs/runbook.md": "nothing here\n"})
    (tmp_path / "logo.bin").write_bytes(b"\x00\x01\xff" + REFUSED["macOS home"].encode())
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)
    assert hygiene.run(tmp_path) == 0, capsys.readouterr().out


def test_hygiene_leaves_the_generator_its_own_file(tmp_path, capsys):
    """Copier writes .copier-answers.yml and forbids editing it by hand (ADR-0001)."""
    source = "_src_path: " + "/" + "home/alice/napkinstack-os\n"
    tracked(tmp_path, {".copier-answers.yml": source, "docs/answers.md": source})
    code = hygiene.run(tmp_path)
    output = capsys.readouterr().out
    expect(code, output, "H1", True)
    assert ".copier-answers.yml" not in output, output
    assert "docs/answers.md:1" in output, output
