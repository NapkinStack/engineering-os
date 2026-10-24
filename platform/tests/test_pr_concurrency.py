"""D146: the pull request's rules are judged on its last event (#248).

Each event — a push, an edit of the description, a label — starts a run that reads the
description and the head *as they were at that event*. On a runner that takes them out of
order, the run of an earlier event can finish last, and its stale verdict is the one the forge
shows: a compliant change looks red. A later event of the same pull request cancels the earlier
one's run (GitHub Actions `concurrency`).
"""

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / "skeleton/.github/workflows/pull-request.yml"


def test_a_later_event_of_the_pull_request_cancels_the_earlier_run():
    concurrency = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8")).get("concurrency")
    assert concurrency, f"{WORKFLOW.name}: no concurrency, an earlier event's run can finish last"
    assert "github.event.pull_request.number" in concurrency["group"], \
        f"{WORKFLOW.name}: the group must be the pull request, got {concurrency['group']!r}"
    assert concurrency.get("cancel-in-progress") is True, \
        f"{WORKFLOW.name}: cancel-in-progress must be true, or the earlier run still finishes"
