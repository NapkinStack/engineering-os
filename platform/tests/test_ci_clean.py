"""D106: a module's job cleans what it left, on a runner that outlives it.

GitHub's hosted machines are thrown away after each job; a self-hosted runner keeps every
job's build outputs until the same repository's next job checks out over them. Measured on
the third project: a Rust module's job left 1.5 GB on a runner with 3.5 GB free. The job
starts clean (checkout's `clean`) and ends clean (the module's `clean` verb), even after a
failure.
"""

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / "skeleton/.github/workflows/module-checks.yml"
TEMPLATE = ROOT / "src/napkinstack/templates/module/MANIFEST.yaml"


def steps():
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))["jobs"]["validate"]["steps"]


def test_a_module_job_starts_on_a_clean_checkout():
    checkout = next(step for step in steps() if str(step.get("uses", "")).startswith("actions/checkout@"))
    assert checkout["with"]["clean"] is True, "a project could turn the start's cleaning off unseen"


def test_a_module_job_ends_with_its_clean_verb_on_a_self_hosted_runner_even_after_a_failure():
    last = steps()[-1]
    assert last["name"] == "clean"
    assert 'nstack clean "$MODULE"' in last["run"]
    condition = last["if"].replace(" ", "")
    assert "always()" in condition, "a failed test would leave the build behind"
    assert "runner.environment=='self-hosted'" in condition, "hosted machines are thrown away"


def test_the_module_template_offers_the_verb():
    assert "#  clean:" in TEMPLATE.read_text(encoding="utf-8")
