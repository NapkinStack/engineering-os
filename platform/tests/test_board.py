"""D139, PDR-0016, ADR-0008: the plan shown on the forge, one way. Every case proves its rule
fails (P5) and names itself (P6). Run by platform/tests/run.sh.
"""

from __future__ import annotations

import datetime

from napkinstack import board

from test_plan import CHARTER, cycle, deliverable, framed

TODAY = datetime.date(2026, 10, 21)


def project(tmp_path, **cycles):
    framed(tmp_path, cycles=cycles or {"03-the-window.md": cycle(start=datetime.date(2026, 10, 17), goal="A window",
                                                                   deliverables=[
                                                                       deliverable(id="D1", state="accepted"),
                                                                       deliverable(id="D2", state="ready", title="Export"),
                                                                       deliverable(id="D3", state="dropped")])})
    return tmp_path


def by_key(found):
    shown, _ = found
    return {item.key: item for item in shown}


def test_an_accepted_cycle_is_a_milestone_due_on_its_end(tmp_path):
    shown = by_key(board.desired(project(tmp_path), today=TODAY))
    milestone = shown["03"]
    assert milestone.kind == "cycle" and milestone.state == "open"
    assert milestone.title == "Cycle 03-the-window"  # no heading of its own: the file's name
    assert milestone.due == "2026-11-07"
    assert "A window" in milestone.body and "1 of 2 accepted" in milestone.body
    assert board.marker("cycle", "03") in milestone.body


def test_each_deliverable_is_an_issue_closed_as_its_state_says(tmp_path):
    shown = by_key(board.desired(project(tmp_path), today=TODAY))
    accepted, ready, dropped = shown["D1"], shown["D2"], shown["D3"]
    assert (accepted.state, accepted.reason) == ("closed", "completed")
    assert (ready.state, ready.reason) == ("open", None)
    assert (dropped.state, dropped.reason) == ("closed", "not_planned")
    assert ready.title == "D2 — Export" and ready.cycle == "03"
    assert ready.labels == ["deliverable", "state: ready"]
    assert "- [ ] Given an order" in ready.body and "- [x] Given an order" in accepted.body
    assert "docs/project/cycles/03-the-window.md" in ready.body
    assert board.marker("deliverable", "D2") in ready.body


def test_a_proposed_cycle_is_not_shown_and_a_closed_one_is_closed(tmp_path):
    shown = by_key(board.desired(project(
        tmp_path, **{"01-old.md": cycle(status="closed", outcome="completed", ended_on="2026-10-01"),
                     "02-next.md": cycle(status="proposed", deliverables=[deliverable(state="proposed", acceptance=None)])}),
        today=TODAY))
    assert "02" not in shown and shown["01"].state == "closed"


def test_the_holder_is_said_and_assigned_when_a_handle(tmp_path):
    holders = {"D2": "@alice"}
    ready = by_key(board.desired(project(tmp_path), holders=holders, today=TODAY))["D2"]
    assert "held by** @alice" in ready.body and ready.assignee == "alice"
    noreply = {"D2": "Carol <12345+carol-gh@users.noreply.github.com>"}
    assert by_key(board.desired(project(tmp_path), holders=noreply, today=TODAY))["D2"].assignee == "carol-gh"
    plain = {"D2": "Bob <bob@example.org>"}
    assert by_key(board.desired(project(tmp_path), holders=plain, today=TODAY))["D2"].assignee is None


def test_the_pull_requests_naming_a_deliverable_are_listed(tmp_path):
    ready = by_key(board.desired(project(tmp_path), pulls={"D2": [12, 15]}, today=TODAY))["D2"]
    assert "**Pull requests**: #12, #15" in ready.body


def test_no_charter_no_cycle_nothing_shown(tmp_path):
    assert board.desired(tmp_path, today=TODAY) == ([], [])


# --- applied to a forge ------------------------------------------------------------------

import io
import json
import subprocess
import urllib.error
import urllib.parse

import pytest

from napkinstack import hold


class GitHub:
    """Milestones, issues, labels and search, kept in memory as GitHub keeps them."""

    def __init__(self):
        self.milestones, self.issues, self.labels, self.calls, self.pulls = {}, {}, {}, [], []
        self.assignable = {"alice"}
        self.next = 1

    def __call__(self, request, timeout=None):
        method, url = request.get_method(), urllib.parse.urlsplit(request.full_url)
        body = json.loads(request.data) if request.data else None
        self.calls.append((method, url.path, body))
        path = url.path.removeprefix("/repos/acme/p")
        query = urllib.parse.parse_qs(url.query)
        answer = self.answer(method, path, query, body)

        class Answer(io.BytesIO):
            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

        return Answer(json.dumps(answer).encode())

    def page(self, items, query):
        return items if query.get("page", ["1"])[0] == "1" else []

    def answer(self, method, path, query, body):
        if path == "/pulls":
            return self.page(self.pulls, query)
        if path.startswith("/assignees/"):
            if path.rsplit("/", 1)[1] not in self.assignable:
                raise urllib.error.HTTPError(path, 404, "Not Found", {}, io.BytesIO(b"{}"))
            return None
        if path == "/labels":
            if method == "POST":
                self.labels[body["name"]] = body
                return body
            return self.page(list(self.labels.values()), query)
        if path == "/milestones":
            if method == "POST":
                number, self.next = self.next, self.next + 1
                self.milestones[number] = {"number": number, "state": "open", **body}
                return self.milestones[number]
            return self.page(list(self.milestones.values()), query)
        if path.startswith("/milestones/"):
            self.milestones[int(path.rsplit("/", 1)[1])].update(body)
            return self.milestones[int(path.rsplit("/", 1)[1])]
        if path == "/issues":
            if method == "POST":
                number, self.next = self.next, self.next + 1
                self.issues[number] = self.shape({"number": number, "state": "open"}, body)
                return self.issues[number]
            wanted = query.get("labels", [""])[0]
            return self.page([issue for issue in self.issues.values()
                              if not wanted or wanted in {label["name"] for label in issue["labels"]}], query)
        if path.startswith("/issues/"):
            number = int(path.rsplit("/", 1)[1])
            self.issues[number] = self.shape(self.issues[number], body)
            return self.issues[number]
        raise AssertionError(f"unexpected {method} {path}")

    def shape(self, issue, body):
        issue = {**issue, **{key: value for key, value in body.items() if key not in ("labels", "milestone", "assignees")}}
        if "labels" in body:
            issue["labels"] = [{"name": name} for name in body["labels"]]
        if "milestone" in body:
            issue["milestone"] = {"number": body["milestone"]} if body["milestone"] else None
        if "assignees" in body:
            issue["assignees"] = [{"login": login} for login in body["assignees"]]
        return issue


@pytest.fixture
def forge(tmp_path, monkeypatch):
    site = GitHub()
    monkeypatch.setattr(hold.urllib.request, "urlopen", site)
    monkeypatch.setattr(board, "PACE", 0)
    monkeypatch.setenv("GH_TOKEN", "token")
    monkeypatch.delenv("GITHUB_API_URL", raising=False)
    root = project(tmp_path)
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(["git", "remote", "add", "origin", "https://github.com/acme/p.git"], cwd=root, check=True)
    monkeypatch.setattr(hold, "fetch", lambda root, again=False: None)  # nobody holds anything
    return root, site


def test_a_first_run_makes_the_milestone_the_issues_and_their_labels(forge, capsys):
    root, site = forge
    assert board.run(root, today=TODAY) == 0
    assert [m["title"] for m in site.milestones.values()] == ["Cycle 03-the-window"]
    assert site.milestones[1]["due_on"].startswith("2026-11-0")
    titles = {issue["title"]: issue for issue in site.issues.values()}
    assert set(titles) == {"D1 — Send an invoice", "D2 — Export", "D3 — Send an invoice"}
    assert titles["D1 — Send an invoice"]["state"] == "closed" and titles["D2 — Export"]["state"] == "open"
    assert all(issue["milestone"] == {"number": 1} for issue in site.issues.values())
    assert {"deliverable", "state: ready", "state: accepted", "state: dropped"} <= set(site.labels)
    assert "made milestone" in capsys.readouterr().out


def test_a_second_run_changes_nothing(forge, capsys):
    root, site = forge
    board.run(root, today=TODAY)
    before = len(site.calls)
    capsys.readouterr()
    board.run(root, today=TODAY)
    assert not [call for call in site.calls[before:] if call[0] != "GET"]
    assert "in step with the cycle files" in capsys.readouterr().out


def test_a_title_edited_on_the_forge_is_restored_and_said(forge, capsys):
    root, site = forge
    board.run(root, today=TODAY)
    issue = next(issue for issue in site.issues.values() if issue["title"] == "D2 — Export")
    issue["title"] = "Export (renamed by hand)"
    capsys.readouterr()
    board.run(root, today=TODAY)
    assert issue["number"] and site.issues[issue["number"]]["title"] == "D2 — Export"
    out = capsys.readouterr().out
    assert "updated issue D2 — Export: title" in out and "the plan is edited in the cycle files" in out


def test_an_issue_without_the_marker_is_never_touched(forge):
    root, site = forge
    site.issues[99] = {"number": 99, "state": "open", "title": "D2 — Export", "body": "a person's own issue",
                       "labels": [{"name": "deliverable"}], "milestone": None, "assignees": []}
    board.run(root, today=TODAY)
    assert site.issues[99]["body"] == "a person's own issue" and site.issues[99]["state"] == "open"
    assert not [call for call in site.calls if call[1].endswith("/issues/99")]


def test_a_deliverable_removed_from_the_file_closes_its_issue_never_deletes_it(forge, capsys):
    root, site = forge
    board.run(root, today=TODAY)
    path = root / "docs/project/cycles/03-the-window.md"
    path.write_text(path.read_text(encoding="utf-8").replace("id: D2", "id: D9"), encoding="utf-8")
    capsys.readouterr()
    board.run(root, today=TODAY)
    old = next(issue for issue in site.issues.values() if "deliverable D2 -->" in issue["body"])
    assert old["state"] == "closed" and old["state_reason"] == "not_planned"
    assert not [call for call in site.calls if call[0] == "DELETE"]


def test_a_dry_run_applies_nothing(forge, capsys):
    root, site = forge
    board.run(root, dry_run=True, today=TODAY)
    assert not [call for call in site.calls if call[0] != "GET"]
    assert "dry run" in capsys.readouterr().out


def test_without_a_token_nothing_is_called_and_it_is_said(forge, monkeypatch, capsys):
    root, site = forge
    monkeypatch.delenv("GH_TOKEN")
    assert board.run(root, today=TODAY) == 0
    assert site.calls == [] and "not shown" in capsys.readouterr().out


def test_a_refusal_is_said_and_the_run_succeeds(forge, monkeypatch, capsys):
    root, _ = forge

    def refuse(request, timeout=None):
        raise OSError("HTTP Error 403: Resource not accessible by integration")

    monkeypatch.setattr(hold.urllib.request, "urlopen", refuse)
    assert board.run(root, today=TODAY) == 0
    assert "not shown further" in capsys.readouterr().out


def test_the_pull_requests_naming_a_deliverable_appear_on_its_issue(forge):
    root, site = forge
    site.pulls = [{"number": 41, "body": "Deliverable: D2\n", "created_at": "2026-10-20T10:00:00Z"},
                  {"number": 40, "body": "deliverable: d2", "created_at": "2026-10-19T10:00:00Z"},
                  {"number": 39, "body": "Deliverable: D1", "created_at": "2026-10-18T10:00:00Z"}]
    board.run(root, today=TODAY)
    export = next(issue for issue in site.issues.values() if issue["title"] == "D2 — Export")
    assert "**Pull requests**: #41, #40" in export["body"]


def test_a_deliverable_with_no_identifier_is_not_shown(tmp_path):
    root = project(tmp_path, **{"03-the-window.md": cycle(deliverables=[deliverable(id=None), deliverable(id="D2")])})
    assert [item.key for item in board.desired(root, today=TODAY)[0] if item.kind == "deliverable"] == ["D2"]


# --- what the independent review of ADR-0008 asked -----------------------------------------

def held(monkeypatch, who="@alice", ident="D2"):
    found = hold.Hold(event="claim", person=who, sessions=["s"], since=1, worked=1)
    monkeypatch.setattr(hold, "read", lambda root, cycle, wanted: found if wanted == ident else hold.Hold())


def test_the_holder_is_assigned_when_the_repository_can_assign_them(forge, monkeypatch):
    root, site = forge
    held(monkeypatch)
    board.run(root, today=TODAY)
    export = next(issue for issue in site.issues.values() if issue["title"] == "D2 — Export")
    assert export["assignees"] == [{"login": "alice"}] and "held by** @alice" in export["body"]


def test_a_holder_the_repository_cannot_assign_is_said_in_the_body_only(forge, monkeypatch):
    root, site = forge
    held(monkeypatch, who="@stranger")
    board.run(root, today=TODAY)
    export = next(issue for issue in site.issues.values() if issue["title"] == "D2 — Export")
    assert export["assignees"] == [] and "held by** @stranger" in export["body"]


def test_holds_unread_leave_the_assignees_as_they_are(forge, monkeypatch, capsys):
    root, site = forge
    held(monkeypatch)
    board.run(root, today=TODAY)
    monkeypatch.setattr(hold, "fetch", lambda root, again=False: (_ for _ in ()).throw(hold.Unreachable("no credential")))
    capsys.readouterr()
    board.run(root, today=TODAY)
    export = next(issue for issue in site.issues.values() if issue["title"] == "D2 — Export")
    assert export["assignees"] == [{"login": "alice"}]
    assert "holders not shown" in capsys.readouterr().out


def test_a_person_s_milestone_holding_the_title_is_said_and_never_touched(forge, capsys):
    root, site = forge
    site.milestones[50] = {"number": 50, "title": "Cycle 03-the-window", "description": "ours, by hand", "state": "open"}
    site.next = 51
    board.run(root, today=TODAY)
    assert site.milestones[50]["description"] == "ours, by hand" and len(site.milestones) == 1
    assert "cycle 03 not shown: a milestone titled 'Cycle 03-the-window' exists" in capsys.readouterr().out


def test_a_renamed_cycle_file_keeps_its_milestone(forge):
    root, site = forge
    board.run(root, today=TODAY)
    path = root / "docs/project/cycles/03-the-window.md"
    path.rename(path.with_name("03-a-wider-window.md"))
    board.run(root, today=TODAY)
    assert len(site.milestones) == 1 and site.milestones[1]["title"] == "Cycle 03-a-wider-window"


def test_a_deliverable_moved_to_another_cycle_keeps_its_issue(forge):
    root, site = forge
    board.run(root, today=TODAY)
    from test_plan import write
    write(root, "cycles/04-next.md", cycle(status="closed", outcome="completed", ended_on="2026-10-20",
                                           deliverables=[deliverable(id="D2", title="Export", state="accepted")]))
    path = root / "docs/project/cycles/03-the-window.md"
    path.write_text(path.read_text(encoding="utf-8").replace("id: D2", "id: D7"), encoding="utf-8")
    before = {issue["number"] for issue in site.issues.values() if "deliverable D2 -->" in issue["body"]}
    board.run(root, today=TODAY)
    after = [issue for issue in site.issues.values() if "deliverable D2 -->" in issue["body"]]
    assert {issue["number"] for issue in after} == before
    assert after[0]["milestone"]["number"] != 1


def test_an_identifier_used_in_two_cycles_is_said_and_not_shown(tmp_path):
    from test_plan import write
    root = project(tmp_path)
    write(root, "cycles/02-before.md", cycle(status="closed", outcome="completed", ended_on="2026-10-01",
                                             deliverables=[deliverable(id="D2", state="accepted")]))
    shown, said = board.desired(root, today=TODAY)
    assert "D2" not in {item.key for item in shown}
    assert any(line.startswith("D2 not shown: its identifier is used in cycles 02, 03") for line in said)


def test_the_heading_titles_the_milestone(tmp_path):
    from test_plan import write
    write(tmp_path, "cycles/03-the-window.md", cycle(), body="\n# Cycle 03 — the window\n")
    write(tmp_path, "charter.md", CHARTER)
    shown, _ = board.desired(tmp_path, today=TODAY)
    assert shown[0].title == "Cycle 03 — the window"


def test_a_closed_issue_whose_reason_changes_is_rewritten(forge, monkeypatch):
    root, site = forge
    board.run(root, today=TODAY)
    path = root / "docs/project/cycles/03-the-window.md"
    path.write_text(path.read_text(encoding="utf-8").replace("state: dropped", "state: accepted"), encoding="utf-8")
    board.run(root, today=TODAY)
    d3 = next(issue for issue in site.issues.values() if "deliverable D3 -->" in issue["body"])
    assert d3["state"] == "closed" and d3["state_reason"] == "completed"


def test_a_reopened_deliverable_reopens_its_issue(forge):
    root, site = forge
    board.run(root, today=TODAY)
    path = root / "docs/project/cycles/03-the-window.md"
    path.write_text(path.read_text(encoding="utf-8").replace("state: accepted", "state: in-progress", 1), encoding="utf-8")
    board.run(root, today=TODAY)
    d1 = next(issue for issue in site.issues.values() if "deliverable D1 -->" in issue["body"])
    assert d1["state"] == "open" and d1["state_reason"] == "reopened"


def test_a_due_date_returned_with_another_time_is_not_a_change(forge, capsys):
    root, site = forge
    board.run(root, today=TODAY)
    site.milestones[1]["due_on"] = "2026-11-07T08:00:00Z"  # GitHub's own time of day
    site.milestones[1]["description"] += "\r\n"
    capsys.readouterr()
    board.run(root, today=TODAY)
    assert "updated milestone" not in capsys.readouterr().out


def test_items_a_person_put_in_the_milestone_are_counted_and_said(forge, capsys):
    root, site = forge
    board.run(root, today=TODAY)
    site.milestones[1].update(open_issues=3, closed_issues=2)  # the display's 3 issues, and 2 of a person's
    capsys.readouterr()
    board.run(root, today=TODAY)
    assert "2 item(s) in Cycle 03-the-window not from the plan" in capsys.readouterr().out


def test_pull_requests_older_than_the_shown_cycles_are_not_read(forge):
    root, site = forge
    site.pulls = [{"number": 41, "body": "Deliverable: D2", "created_at": "2026-10-20T10:00:00Z"},
                  {"number": 3, "body": "Deliverable: D2", "created_at": "2026-01-01T10:00:00Z"}]
    board.run(root, today=TODAY)
    export = next(issue for issue in site.issues.values() if issue["title"] == "D2 — Export")
    assert "#41" in export["body"] and "#3" not in export["body"]


def test_in_github_actions_what_is_not_shown_is_a_warning_and_in_the_summary(forge, monkeypatch, capsys, tmp_path):
    root, _ = forge
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    monkeypatch.setattr(hold, "fetch", lambda root, again=False: (_ for _ in ()).throw(hold.Unreachable("no credential")))
    board.run(root, today=TODAY)
    assert "::warning title=Plan on the forge::holders not shown" in capsys.readouterr().out
    assert "holders not shown" in summary.read_text(encoding="utf-8")


def test_a_secondary_rate_limit_stops_the_run_partially_shown(forge, monkeypatch, capsys):
    root, site = forge
    real = site.answer

    def limited(method, path, query, body):
        if method == "POST" and path == "/issues" and len(site.issues) >= 1:
            raise urllib.error.HTTPError(path, 403, "Forbidden", {},
                                         io.BytesIO(b'{"message": "You have exceeded a secondary rate limit."}'))
        return real(method, path, query, body)

    site.answer = limited
    assert board.run(root, today=TODAY) == 0
    assert "partially shown, the rest at the next run" in capsys.readouterr().out


# --- what the verifier of the build found -------------------------------------------------

class PacificGitHub(GitHub):
    """GitHub as it is: a milestone's due date kept as midnight, Pacific time, of the UTC day
    it was sent; label names unique whatever their case."""

    def answer(self, method, path, query, body):
        if path.startswith("/milestones") and body and "due_on" in body:
            sent = datetime.datetime.fromisoformat(body["due_on"].replace("Z", "+00:00"))
            pacific = (sent - datetime.timedelta(hours=8)).date()
            body = {**body, "due_on": f"{pacific}T08:00:00Z"}
        if path == "/labels" and method == "POST" and body["name"].lower() in {n.lower() for n in self.labels}:
            raise urllib.error.HTTPError(path, 422, "Unprocessable", {}, io.BytesIO(b'{"message": "Validation Failed"}'))
        return super().answer(method, path, query, body)


@pytest.fixture
def pacific(forge, monkeypatch):
    root, _ = forge
    site = PacificGitHub()
    monkeypatch.setattr(hold.urllib.request, "urlopen", site)
    return root, site


def test_the_due_date_is_the_cycle_s_own_on_github_and_never_rewritten(pacific, capsys):
    root, site = pacific
    board.run(root, today=TODAY)
    assert site.milestones[1]["due_on"].startswith("2026-11-07")
    capsys.readouterr()
    board.run(root, today=TODAY)
    assert "updated milestone" not in capsys.readouterr().out


def test_a_new_day_rewrites_nothing(forge, capsys):
    root, site = forge
    board.run(root, today=TODAY)
    capsys.readouterr()
    board.run(root, today=TODAY + datetime.timedelta(days=1))
    assert "updated" not in capsys.readouterr().out


def test_a_label_existing_in_another_case_is_used_as_it_is(pacific, capsys):
    root, site = pacific
    site.labels["Deliverable"] = {"name": "Deliverable"}
    board.run(root, today=TODAY)
    out = capsys.readouterr().out
    assert "not shown further" not in out and "made label deliverable" not in out
    capsys.readouterr()
    for issue in site.issues.values():  # GitHub names the label as it exists
        issue["labels"] = [{"name": "Deliverable" if l["name"] == "deliverable" else l["name"]} for l in issue["labels"]]
    board.run(root, today=TODAY)
    assert "updated issue" not in capsys.readouterr().out


def test_an_issue_whose_label_a_person_removed_is_still_the_display_s(forge):
    root, site = forge
    board.run(root, today=TODAY)
    export = next(issue for issue in site.issues.values() if issue["title"] == "D2 — Export")
    export["labels"] = []
    board.run(root, today=TODAY)
    again = [issue for issue in site.issues.values() if "deliverable D2 -->" in issue["body"]]
    assert len(again) == 1 and {"name": "deliverable"} in again[0]["labels"]


@pytest.mark.parametrize("acceptance", [5, "one line"], ids=["a number", "a string"])
def test_odd_acceptance_criteria_never_break_the_run(tmp_path, acceptance):
    root = project(tmp_path, **{"03-the-window.md": cycle(deliverables=[deliverable(state="dropped", acceptance=acceptance)])})
    shown, _ = board.desired(root, today=TODAY)
    issue = next(item for item in shown if item.kind == "deliverable")
    assert "- [ ] o\n" not in issue.body


def test_an_unexpected_failure_is_said_and_the_run_succeeds(forge, monkeypatch, capsys):
    root, _ = forge
    monkeypatch.setattr(board, "_apply", lambda *args, **kwargs: {}["boom"])
    assert board.run(root, today=TODAY) == 0
    assert "not shown further" in capsys.readouterr().out


def test_a_closed_cycle_says_its_count_and_no_appetite(tmp_path):
    root = project(tmp_path, **{"01-old.md": cycle(status="closed", outcome="completed", ended_on="2026-10-01")})
    milestone = next(item for item in board.desired(root, today=TODAY)[0] if item.kind == "cycle")
    assert "0 of 1 accepted" in milestone.body and "day " not in milestone.body and "circuit" not in milestone.body


def test_the_heading_is_found_past_a_rule_in_the_body(tmp_path):
    from test_plan import write
    write(tmp_path, "cycles/03-w.md", cycle(), body="\n# Cycle 03 — the window\n\n---\n\nmore\n")
    write(tmp_path, "charter.md", CHARTER)
    assert board.desired(tmp_path, today=TODAY)[0][0].title == "Cycle 03 — the window"


def test_a_display_issue_moved_out_of_a_cycle_is_not_counted_as_a_person_s(forge, capsys):
    root, site = forge
    board.run(root, today=TODAY)
    path = root / "docs/project/cycles/03-the-window.md"
    path.write_text(path.read_text(encoding="utf-8").replace("id: D2", "id: D9"), encoding="utf-8")
    board.run(root, today=TODAY)
    site.milestones[1].update(open_issues=1, closed_issues=3)  # D9 open; D1, D3 and the old D2 closed: all the display's
    capsys.readouterr()
    board.run(root, today=TODAY)
    assert "not from the plan" not in capsys.readouterr().out


def test_a_refused_permission_is_not_called_a_rate_limit(forge, monkeypatch, capsys):
    root, _ = forge

    def refuse(request, timeout=None):
        raise urllib.error.HTTPError(request.full_url, 403, "Forbidden", {},
                                     io.BytesIO(b'{"message": "Resource not accessible by integration"}'))

    monkeypatch.setattr(hold.urllib.request, "urlopen", refuse)
    board.run(root, today=TODAY)
    out = capsys.readouterr().out
    assert "Resource not accessible by integration" in out and "partially shown" not in out


def test_the_workflow_runs_on_merges_daily_and_by_hand_never_on_a_hold():
    """A hold's commits hold no file: GitHub reads the workflows of the pushed commit, so a push to
    nstack/hold/** can start none — the holders are shown by a daily run instead."""
    import yaml
    from pathlib import Path

    workflow = yaml.safe_load((Path(__file__).resolve().parents[2] / "skeleton/.github/workflows/plan-on-the-forge.yml")
                              .read_text(encoding="utf-8"))
    triggers = workflow.get(True) or workflow["on"]
    assert triggers["push"]["branches"] == ["main"] and triggers["schedule"] and "workflow_dispatch" in triggers
    assert workflow["permissions"] == {} and workflow["jobs"]["board"]["permissions"] == {
        "contents": "read", "issues": "write", "pull-requests": "read"}


def test_a_pull_request_opened_since_the_last_run_is_an_update_never_called_a_hand_edit(forge, capsys):
    """Seen on the third project: a run after a new pull request said "restored", as if a person had
    edited the issue."""
    root, site = forge
    board.run(root, today=TODAY)
    site.pulls = [{"number": 45, "body": "Deliverable: D2", "created_at": "2026-10-20T10:00:00Z"}]
    capsys.readouterr()
    board.run(root, today=TODAY)
    out = capsys.readouterr().out
    assert "updated issue D2 — Export: body" in out and "restored" not in out
