"""The module checks: one job, `Module checks`, running the framework's script (ADR-0005).

The required check keeps its name (G4). The job starts on a clean checkout and the script ends
each module with its `clean` verb on a self-hosted runner, even after a failure (D106) — GitHub's
hosted machines are thrown away after each job, a self-hosted runner keeps what a job left.
What the script does with a failing module is run by platform/tests/run.sh.
"""

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / "skeleton/.github/workflows/module-checks.yml"
SCRIPT = ROOT / "skeleton/.nstack/check-modules.sh"
TEMPLATE = ROOT / "src/napkinstack/templates/module/MANIFEST.yaml"


def jobs():
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))["jobs"]


def test_the_module_checks_are_one_job_under_the_required_name():
    assert [job["name"] for job in jobs().values()] == ["Module checks"], (
        "each job is billed at least a minute; the required name is `Module checks` (G4, ADR-0005)")


def test_the_job_starts_on_a_clean_checkout_and_runs_the_framework_s_script():
    steps = next(iter(jobs().values()))["steps"]
    checkout = next(step for step in steps if str(step.get("uses", "")).startswith("actions/checkout@"))
    assert checkout["with"]["clean"] is True, "a project could turn the start's cleaning off unseen"
    assert any("bash .nstack/check-modules.sh" in str(step.get("run", "")) for step in steps)


def test_a_self_hosted_runner_needs_no_yaml_tool():
    for path in (WORKFLOW, SCRIPT):
        assert "yq" not in path.read_text(encoding="utf-8").split(), f"{path.name} calls yq"


def test_the_script_cleans_on_a_self_hosted_runner_only():
    text = SCRIPT.read_text(encoding="utf-8")
    assert 'nstack clean "$MODULE"' in text and "self-hosted" in text


def test_the_module_template_offers_the_verb():
    assert "#  clean:" in TEMPLATE.read_text(encoding="utf-8")
