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
import os
import subprocess
from pathlib import Path

import pytest
import yaml

from napkinstack import cli, skills
from napkinstack.fitness import boundaries, manifests

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
    "M6 deprecated contract without a date": (lambda r: write_module(r, "billing", degrade(
        provides=[{"contract": "billing-api", "version": "v1", "stability": "deprecated"}])), "M6", True),
    "M6 date passed": (lambda r: write_module(r, "billing", degrade(provides=[
        {"contract": "billing-api", "version": "v1", "stability": "deprecated", "removal_date": YESTERDAY}])), "M6", True),
    "M7 missing verb": (lambda r: write_module(r, "billing", degrade(commands={"check": "true"})), "M7", True),
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


def consumes(manifest, module):
    return {**manifest, "consumes": [{"contract": f"{module}-api", "version": "v1", "module": module}]}


def test_valid_boundaries(tmp_path, capsys):
    write_module(tmp_path, "billing")
    write_module(tmp_path, "customers", CUSTOMERS)
    assert boundaries.run(tmp_path) == 0, capsys.readouterr().out


BOUNDARY_CASES = {
    "B1 undeclared reference": ({
        "billing": (VALID, {"src/app.py": "from modules.customers.api import customer\n"}),
        "customers": (CUSTOMERS, {})}, "B1", True),
    "B2 internal implementation": ({
        "billing": (consumes(VALID, "customers"), {"src/app.js": 'import { db } from "../customers/src/db";\n'}),
        "customers": (CUSTOMERS, {})}, "B2", True),
    "B3 circular dependency": ({
        "billing": (consumes(VALID, "customers"), {"src/app.py": "from modules.customers.api import customer\n"}),
        "customers": (consumes(CUSTOMERS, "billing"), {"src/app.py": "from modules.billing.api import invoice\n"})},
        "B3", True),
    "B4 unused dependency": ({
        "billing": (consumes(VALID, "customers"), {}), "customers": (CUSTOMERS, {})}, "B4", False),
    "B5 another module's table": ({
        "billing": (degrade(data={"owns": ["invoices"], "shared": []}), {}),
        "customers": (CUSTOMERS, {"src/query.py": 'SQL = "SELECT * FROM invoices"\n'})}, "B5", True),
}


@pytest.mark.parametrize(("modules_map", "rule", "fails"), BOUNDARY_CASES.values(), ids=BOUNDARY_CASES.keys())
def test_boundaries(tmp_path, capsys, modules_map, rule, fails):
    for name, (manifest, sources) in modules_map.items():
        write_module(tmp_path, name, manifest, sources)
    code = boundaries.run(tmp_path)
    expect(code, capsys.readouterr().out, rule, fails)


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


TWO_MODULES = {"modules/a/x.txt": 1, "modules/b/y.txt": 1}
PR_CASES = {
    "P1 two modules": (TWO_MODULES, {}, "FAIL [P1]", 1),
    "P1 cross-module label": (TWO_MODULES, {"PR_LABELS": "cross-module"}, "WARNING [P1]", 0),
    "P2 over budget": ({"modules/a/x.txt": 3}, {"MAX_LINES": "1"}, "WARNING [P2] Over the review budget.", 0),
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
