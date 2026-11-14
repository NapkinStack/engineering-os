"""D219 (#387): a workflow that fails on every run of the default branch goes unseen when it is not a
required check — every pull request merges green beside it. `nstack doctor` says so (N2), as
information: the exit code does not change. Read workflow by workflow: a quiet one never drops out
of a window busier ones fill.
"""

from __future__ import annotations

from napkinstack import doctor


def _run(conclusion: str, day: int, event: str = "push", workflow: str = "w") -> dict:
    return {"conclusion": conclusion, "status": "completed", "event": event,
            "created_at": f"2026-11-{day:02d}T10:00:00Z", "html_url": f"https://forge.example/runs/{workflow}-{day}"}


class Forge:
    def __init__(self, workflows: dict[str, list[dict]] | None, default: str = "trunk"):
        self.workflows, self.default, self.read = workflows, default, []

    def get(self, path, missing=False):
        self.read.append(path)
        if path == "":
            return {"default_branch": self.default}
        if self.workflows is None:
            raise doctor.NotVerified("read refused (HTTP 403): repository out of reach, or the token lacks the "
                                     "Administration: read permission")
        if path.startswith("/actions/workflows?"):
            return {"workflows": [{"id": index, "name": name, "state": "active"}
                                  for index, name in enumerate(self.workflows)]}
        index = int(path.split("/")[3])
        return {"workflow_runs": list(self.workflows.values())[index]}


def test_a_workflow_red_on_its_last_runs_of_the_default_branch_is_named_with_its_first_failure(capsys):
    forge = Forge({"Package Windows": [_run("failure", day, workflow="win") for day in (13, 12, 11, 10)]
                                      + [_run("timed_out", 9, workflow="win"), _run("success", 6, workflow="win")],
                   "CI": [_run("success", 13), _run("failure", 12)]})
    doctor._default_branch_runs(forge)
    out = capsys.readouterr().out
    assert any("branch=trunk" in path for path in forge.read), "the default branch, whatever its name"
    assert "RED            Package Windows: failed its last 5 runs on trunk, since 2026-11-09" in out, out
    assert "https://forge.example/runs/win-9" in out, "a timed-out run is a failure"
    assert "CI:" not in out, "a workflow whose last run passed is not said"


def test_two_failures_are_not_a_streak_and_a_fork_s_pull_request_is_not_the_branch_s(capsys):
    forge = Forge({"Nightly": [_run("failure", 13, "schedule"), _run("failure", 12, "schedule"),
                               _run("success", 11, "schedule")],
                   "CI": [_run("failure", day, "pull_request") for day in (13, 12, 11)] + [_run("success", 10)]})
    doctor._default_branch_runs(forge)
    out = capsys.readouterr().out
    assert "RED" not in out and "no workflow failing" in out, out


def test_runs_that_cannot_be_read_are_said_never_judged_nor_blamed_on_administration(capsys):
    doctor._default_branch_runs(Forge(None))
    out = capsys.readouterr().out
    assert "NOT READ" in out and "Actions: read" in out and "Administration" not in out, out
