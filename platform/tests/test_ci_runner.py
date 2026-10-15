"""D105: a project chooses the runner its CI runs on, with one repository variable.

The skeleton's jobs ran on GitHub's hosted Ubuntu, written in each job. A project whose
hosted minutes are unavailable — a private repository on a plan out of minutes — had no
way to point them at its own runner but to edit the workflows the framework owns, and
meet a conflict at every update.
"""

from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = sorted((ROOT / "skeleton/.github/workflows").glob("*.yml"))
RUNS_ON = "${{ vars.NSTACK_RUNS_ON || 'ubuntu-latest' }}"


def jobs():
    for path in WORKFLOWS:
        for name, job in yaml.safe_load(path.read_text(encoding="utf-8"))["jobs"].items():
            if "runs-on" in job:
                yield pytest.param(job["runs-on"], id=f"{path.name}:{name}")


def test_the_skeleton_has_workflows():
    assert WORKFLOWS, "no workflow found in the skeleton"


@pytest.mark.parametrize("runs_on", list(jobs()))
def test_every_job_runs_where_the_project_says(runs_on):
    assert runs_on == RUNS_ON, f"runs-on is {runs_on!r}: a project could not choose its runner"
