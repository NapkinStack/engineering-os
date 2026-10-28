"""D137, PDR-0015, ADR-0007: a contributor takes a deliverable in one gesture a second taker
cannot also win; a hold nobody works on is taken over, recorded. Every case proves its rule
fails (P5) and names itself (P6). Run by platform/tests/run.sh.
"""

from __future__ import annotations

import datetime
import os
import subprocess
from pathlib import Path

import pytest

from napkinstack import hold

IDENTITY = {"GIT_AUTHOR_NAME": "test", "GIT_AUTHOR_EMAIL": "test@example.invalid",
            "GIT_COMMITTER_NAME": "test", "GIT_COMMITTER_EMAIL": "test@example.invalid"}
CYCLE = """---
goal: "A window"
status: accepted
appetite_weeks: 3
start: 2026-10-17
end: 2026-11-07
deliverables:
  - id: D1
    title: "Resume an interrupted recording"
    module: capture
    state: ready
    acceptance:
      - "Given a cut, when it resumes, then nothing is lost"
  - id: D2
    title: "Export"
    module: export
    state: proposed
---

# Cycle 03 — the window
"""
CHARTER = """---
status: accepted
decider: "@dana"
success_criteria:
  - "Used at every meeting"
---

# Charter
"""
REF = "nstack/hold/03-the-window/D1"
DAY = 86400


def git(root, *args: str, env: dict | None = None) -> str:
    return subprocess.run(["git", *args], cwd=root, env={**os.environ, **IDENTITY, **(env or {})},
                          check=True, capture_output=True, text=True).stdout.strip()


@pytest.fixture(autouse=True)
def _identity(monkeypatch):
    for name, value in IDENTITY.items():
        monkeypatch.setenv(name, value)
    monkeypatch.delenv("GH_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)


@pytest.fixture
def shared(tmp_path) -> Path:
    """A shared remote holding a framed project with an accepted cycle."""
    seed = tmp_path / "seed"
    (seed / "docs/project/cycles").mkdir(parents=True)
    (seed / "docs/project/charter.md").write_text(CHARTER, encoding="utf-8")
    (seed / "docs/project/cycles/03-the-window.md").write_text(CYCLE, encoding="utf-8")
    (seed / ".copier-answers.yml").write_text("_commit: v0.11.1\nproject_name: p\n", encoding="utf-8")
    git(seed, "init", "-q", "--initial-branch=main")
    git(seed, "add", "-A")
    git(seed, "commit", "-q", "-m", "first")
    remote = tmp_path / "remote.git"
    git(tmp_path, "clone", "-q", "--bare", str(seed), str(remote))
    return remote


def clone(shared: Path, name: str) -> Path:
    folder = shared.parent / name
    git(shared.parent, "clone", "-q", str(shared), str(folder))
    return folder


def remote_events(shared: Path) -> list[str]:
    return git(shared, "log", "--format=%(trailers:key=Hold-Event,valueonly,separator=)", REF).splitlines()


def ago(days: float) -> dict:
    when = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=days)
    return {"GIT_COMMITTER_DATE": when.isoformat(), "GIT_AUTHOR_DATE": when.isoformat()}


def test_a_free_ready_deliverable_is_held_by_its_session_and_person(shared, capsys):
    alice = clone(shared, "alice")
    assert hold.claim(alice, "D1", session="alice-d1", person="@alice") == 0
    out = capsys.readouterr().out
    assert remote_events(shared) == ["claim"]
    trailers = git(shared, "log", "-1", "--format=%(trailers)", REF)
    assert "Hold-Person: @alice" in trailers and "Agent-Session: alice-d1" in trailers
    assert "d1-resume-an-interrupted-recording" in git(shared, "branch", "--list", "d1-*")
    assert "held by @alice" in out


def test_a_branch_name_keeps_whole_words():
    assert hold.slug("The decider goes through one real meeting, end to end") == "the-decider-goes-through-one-real"
    assert hold.slug("Résumé: a cut — resumed!") == "resume-a-cut-resumed"


def test_a_second_person_is_refused_and_told_who_holds_it(shared, capsys):
    hold.claim(clone(shared, "alice"), "D1", session="alice-d1", person="@alice")
    capsys.readouterr()
    assert hold.claim(clone(shared, "bob"), "D1", session="bob-d1", person="@bob") == 1
    out = capsys.readouterr().out
    assert "FAIL [hold]" in out and "@alice" in out and "alice-d1" in out
    assert remote_events(shared) == ["claim"]


def test_two_claims_at_once_leave_one_hold_and_the_refusal_names_it(shared, capsys, monkeypatch):
    alice, bob = clone(shared, "alice"), clone(shared, "bob")
    assert hold.claim(alice, "D1", session="alice-d1", person="@alice") == 0
    real = hold.fetch
    # Bob read D1 free a moment before Alice pushed: his first read misses her hold.
    monkeypatch.setattr(hold, "fetch", lambda root, again=False: real(root) if again or root != bob else hold.remote(root))
    capsys.readouterr()
    assert hold.claim(bob, "D1", session="bob-d1", person="@bob") == 1
    out = capsys.readouterr().out
    assert "taken first" in out and "@alice" in out
    assert remote_events(shared) == ["claim"]


def test_the_holder_claiming_again_renews_and_adds_the_session(shared):
    alice = clone(shared, "alice")
    hold.claim(alice, "D1", session="alice-d1", person="@alice")
    assert hold.claim(alice, "D1", session="alice-d1-again", person="@alice") == 0
    assert remote_events(shared) == ["renew", "claim"]
    state = hold.read(alice, "03-the-window", "D1")
    assert state.sessions == ["alice-d1", "alice-d1-again"]


@pytest.mark.parametrize("deliverable, said", [("D2", "is 'proposed'"), ("D9", "not in 03-the-window")])
def test_a_deliverable_not_ready_or_not_in_the_cycle_is_refused(shared, capsys, deliverable, said):
    assert hold.claim(clone(shared, "alice"), deliverable, session="s", person="@alice") == 1
    assert said in capsys.readouterr().out


def test_a_hold_worked_on_cannot_be_taken_over(shared, capsys):
    hold.claim(clone(shared, "alice"), "D1", session="alice-d1", person="@alice")
    capsys.readouterr()
    assert hold.claim(clone(shared, "bob"), "D1", session="bob-d1", person="@bob", take_over=True) == 1
    assert "stale from" in capsys.readouterr().out
    assert remote_events(shared) == ["claim"]


def test_a_stale_hold_is_taken_over_recorded_and_the_previous_work_kept(shared, monkeypatch):
    alice = clone(shared, "alice")
    for name, value in ago(10).items():
        monkeypatch.setenv(name, value)
    hold.claim(alice, "D1", session="alice-d1", person="@alice")
    for name in ("GIT_COMMITTER_DATE", "GIT_AUTHOR_DATE"):
        monkeypatch.delenv(name)
    work = git(shared, "rev-parse", "d1-resume-an-interrupted-recording")
    assert hold.claim(clone(shared, "bob"), "D1", session="bob-d1", person="@bob", take_over=True) == 0
    assert remote_events(shared) == ["take-over", "claim"]
    assert "Hold-Previous: @alice (alice-d1)" in git(shared, "log", "-1", "--format=%(trailers)", REF)
    assert git(shared, "rev-parse", "d1-resume-an-interrupted-recording") == work


def test_work_on_a_deliverable_s_branch_keeps_its_hold_fresh(shared, monkeypatch, capsys):
    alice = clone(shared, "alice")
    for name, value in ago(10).items():
        monkeypatch.setenv(name, value)
    hold.claim(alice, "D1", session="alice-d1", person="@alice")
    for name in ("GIT_COMMITTER_DATE", "GIT_AUTHOR_DATE"):
        monkeypatch.delenv(name)
    git(alice, "switch", "-q", "-c", "d1-second-part", "origin/main")
    git(alice, "commit", "-q", "--allow-empty", "-m", "today's work")
    git(alice, "push", "-q", "origin", "d1-second-part")
    capsys.readouterr()
    assert hold.claim(clone(shared, "bob"), "D1", session="bob-d1", person="@bob", take_over=True) == 1


def test_the_project_s_limit_is_the_decider_s_answer(shared, monkeypatch):
    alice = clone(shared, "alice")
    for name, value in ago(3).items():
        monkeypatch.setenv(name, value)
    hold.claim(alice, "D1", session="alice-d1", person="@alice")
    for name in ("GIT_COMMITTER_DATE", "GIT_AUTHOR_DATE"):
        monkeypatch.delenv(name)
    bob = clone(shared, "bob")
    assert hold.claim(bob, "D1", session="bob-d1", person="@bob", take_over=True) == 1
    (bob / ".copier-answers.yml").write_text("_commit: v0.11.1\nproject_name: p\nhold_days: 2\n",
                                             encoding="utf-8")
    git(bob, "commit", "-q", "-am", "the decider: two days")
    assert hold.claim(bob, "D1", session="bob-d1", person="@bob", take_over=True) == 0


def test_the_holder_releases_and_the_deliverable_is_free(shared):
    alice = clone(shared, "alice")
    hold.claim(alice, "D1", session="alice-d1", person="@alice")
    assert hold.release(alice, "D1", person="@alice") == 0
    assert remote_events(shared) == ["release", "claim"]
    assert hold.claim(clone(shared, "bob"), "D1", session="bob-d1", person="@bob") == 0


def test_another_person_cannot_release_a_live_hold_and_the_decider_can(shared, capsys):
    hold.claim(clone(shared, "alice"), "D1", session="alice-d1", person="@alice")
    capsys.readouterr()
    assert hold.release(clone(shared, "bob"), "D1", person="@bob") == 1
    assert "FAIL [hold]" in capsys.readouterr().out
    assert hold.release(clone(shared, "dana"), "D1", person="@dana") == 0
    assert remote_events(shared) == ["release", "claim"]


def test_with_no_remote_the_hold_is_local_and_says_so(shared, capsys):
    alone = clone(shared, "alone")
    git(alone, "remote", "remove", "origin")
    assert hold.claim(alone, "D1", session="s", person="@alice") == 0
    assert "local only" in capsys.readouterr().out
    assert git(alone, "log", "-1", "--format=%(trailers:key=Hold-Event,valueonly)", REF) == "claim"


# --- found by the verifier of part 1 ----------------------------------------------------

def test_a_default_branch_not_named_main_with_no_remote_head_still_gives_a_work_branch(shared, capsys):
    git(shared, "branch", "-m", "main", "trunk")
    git(shared, "symbolic-ref", "HEAD", "refs/heads/trunk")
    alice = clone(shared, "alice")
    git(alice, "remote", "set-head", "origin", "-d")
    assert hold.claim(alice, "D1", session="alice-d1", person="@alice") == 0
    assert git(shared, "rev-parse", "d1-resume-an-interrupted-recording^") == git(shared, "rev-parse", "trunk")


def test_the_work_branch_starts_from_the_remote_s_default_branch_as_it_is_now(shared):
    alice, other = clone(shared, "alice"), clone(shared, "other")
    git(other, "commit", "-q", "--allow-empty", "-m", "main advanced")
    git(other, "push", "-q", "origin", "main")
    hold.claim(alice, "D1", session="alice-d1", person="@alice")
    assert git(shared, "rev-parse", "d1-resume-an-interrupted-recording^") == git(shared, "rev-parse", "main")


def test_an_unreachable_remote_is_said_never_taken_first(shared, capsys):
    alice = clone(shared, "alice")
    hold.claim(alice, "D1", session="alice-d1", person="@alice")
    git(alice, "remote", "set-url", "origin", str(shared.parent / "nowhere.git"))
    capsys.readouterr()
    assert hold.claim(alice, "D1", session="alice-d1", person="@alice") == 1
    out = capsys.readouterr().out
    assert "unreachable" in out and "taken first" not in out


@pytest.mark.parametrize("one, other, alike", [
    ("@alice", "Alice <alice@example.org>", True),
    ("@dana", "Dana Lee <dlee@example.org>", False),  # a full name is not a handle
    ("@dana", "Someone <dana@example.org>", True),  # the email's local part is
    ("@alice", "@bob", False),
    ("", "@", False),
])
def test_a_person_named_by_handle_or_by_git_identity_is_one_person(one, other, alike):
    assert hold.same(one, other) is alike


def test_the_decider_releases_under_their_git_identity(shared, monkeypatch):
    hold.claim(clone(shared, "alice"), "D1", session="alice-d1", person="@alice")
    dana = clone(shared, "dana")
    monkeypatch.setenv("GIT_AUTHOR_NAME", "Dana")
    monkeypatch.setenv("GIT_AUTHOR_EMAIL", "dana@example.org")
    assert hold.release(dana, "D1") == 0


@pytest.mark.parametrize("person, session", [("mallory\nHold-Person: dana", "s"), ("@m", "s\nHold-Event: release")])
def test_a_line_break_in_a_person_or_a_session_is_refused(shared, capsys, person, session):
    assert hold.claim(clone(shared, "m"), "D1", session=session, person=person) == 1
    assert "FAIL [hold]" in capsys.readouterr().out


def test_two_claims_in_one_second_by_one_person_are_still_two_commits(shared, monkeypatch, capsys):
    for name, value in ago(0).items():
        monkeypatch.setenv(name, value)
    alice, twin = clone(shared, "alice"), clone(shared, "twin")
    assert hold.claim(alice, "D1", person="@alice") == 0
    real = hold.fetch
    # The twin read D1 free a moment before the first claim landed, in the same second.
    monkeypatch.setattr(hold, "fetch", lambda root, again=False: real(root) if again or root != twin else hold.remote(root))
    capsys.readouterr()
    assert hold.claim(twin, "D1", person="@alice") == 1
    assert "taken first" in capsys.readouterr().out


# --- part 2: who holds what, said by plan; K5 in pr-check --------------------------------

def test_plan_says_who_holds_what_and_what_is_stale(shared, monkeypatch, capsys):
    alice = clone(shared, "alice")
    for name, value in ago(10).items():
        monkeypatch.setenv(name, value)
    hold.claim(alice, "D1", session="alice-d1", person="@alice")
    for name in ("GIT_COMMITTER_DATE", "GIT_AUTHOR_DATE"):
        monkeypatch.delenv(name)
    capsys.readouterr()
    assert hold.show(clone(shared, "bob")) == 0
    out = capsys.readouterr().out
    assert "Holds in 03-the-window" in out
    assert "D1" in out and "STALE" in out and "@alice" in out and "--take-over" in out


def test_plan_says_a_free_deliverable_free(shared, capsys):
    hold.show(clone(shared, "bob"))
    assert "D1  free" in capsys.readouterr().out


def test_plan_never_fails_on_a_remote_it_cannot_read(shared, capsys):
    bob = clone(shared, "bob")
    git(bob, "remote", "set-url", "origin", str(shared.parent / "nowhere.git"))
    assert hold.show(bob) == 0
    assert "holds not read" in capsys.readouterr().out


AUTHORED = ({"bob"}, {"bob-d1"}, [])


def test_k5_refuses_a_pull_request_for_a_deliverable_another_session_holds(shared):
    from napkinstack import pull_request

    hold.claim(clone(shared, "alice"), "D1", session="alice-d1", person="@alice")
    failed, said = [], []
    pull_request.check_hold(clone(shared, "bob"), "Deliverable: D1", set(), AUTHORED,
                            lambda rule, message: failed.append((rule, message)), said.append)
    assert [rule for rule, _ in failed] == ["K5"] and "@alice" in failed[0][1]


@pytest.mark.parametrize("authorship", [({"x"}, {"alice-d1"}, []), ({"alice"}, set(), [])],
                         ids=["by its session", "by its person's account"])
def test_k5_accepts_the_holder_s_pull_request(shared, authorship):
    from napkinstack import pull_request

    hold.claim(clone(shared, "alice"), "D1", session="alice-d1", person="@alice")
    failed = []
    pull_request.check_hold(clone(shared, "bob"), "Deliverable: D1", set(), authorship,
                            lambda rule, message: failed.append(rule), lambda message: None)
    assert failed == []


def test_k5_asks_nothing_of_a_deliverable_nobody_holds(shared):
    from napkinstack import pull_request

    failed = []
    pull_request.check_hold(clone(shared, "bob"), "Deliverable: D1", set(), AUTHORED,
                            lambda rule, message: failed.append(rule), lambda message: None)
    assert failed == []


def test_k5_unread_is_said_never_failed(shared):
    from napkinstack import pull_request

    hold.claim(clone(shared, "alice"), "D1", session="alice-d1", person="@alice")
    bob = clone(shared, "bob")
    git(bob, "remote", "set-url", "origin", str(shared.parent / "nowhere.git"))
    failed, said = [], []
    pull_request.check_hold(bob, "Deliverable: D1", set(), AUTHORED,
                            lambda rule, message: failed.append(rule), said.append)
    assert failed == [] and any("K5" in line and "not read" in line for line in said)


# --- found by the verifier of part 2a ---------------------------------------------------

MANIFEST = """module:
  name: capture
  owner: "acme/team"
  criticality: prototype
  lifecycle: active
"""


def delivery(clone_root: Path, body: str, labels: str, monkeypatch, session: str | None = None,
             who: tuple[str, str] | None = None) -> int:
    """pr-check on a branch that changes the capture module, as CI runs it."""
    from napkinstack import pull_request

    (clone_root / "modules/capture").mkdir(parents=True, exist_ok=True)
    (clone_root / "modules/capture/MANIFEST.yaml").write_text(MANIFEST, encoding="utf-8")
    git(clone_root, "add", "-A")
    git(clone_root, "commit", "-q", "-m", "the module")
    git(clone_root, "push", "-q", "origin", "HEAD:main")
    git(clone_root, "fetch", "-q")
    (clone_root / "modules/capture/code.py").write_text("x = 1\n", encoding="utf-8")
    git(clone_root, "add", "-A")
    env = {"GIT_AUTHOR_NAME": who[0], "GIT_AUTHOR_EMAIL": who[1],
           "GIT_COMMITTER_NAME": who[0], "GIT_COMMITTER_EMAIL": who[1]} if who else {}
    git(clone_root, "commit", "-q", "-m", "work" + (f"\n\nAgent-Session: {session}" if session else ""), env=env)
    monkeypatch.setenv("PR_BODY", body)
    monkeypatch.setenv("PR_LABELS", labels)
    monkeypatch.delenv("PR_AUTHOR", raising=False)
    return pull_request.run(clone_root, "origin/main")


def test_k5_through_pr_check_refuses_another_session(shared, monkeypatch, capsys):
    hold.claim(clone(shared, "alice"), "D1", session="alice-d1", person="@alice")
    assert delivery(clone(shared, "bob"), "Deliverable: D1", "", monkeypatch, session="bob-d1") == 1
    assert "FAIL [K5]" in capsys.readouterr().out


def test_the_out_of_cycle_label_lifts_k5(shared, monkeypatch, capsys):
    hold.claim(clone(shared, "alice"), "D1", session="alice-d1", person="@alice")
    body = "Deliverable: D1\n\nOut of cycle: a production incident"
    delivery(clone(shared, "bob"), body, "out-of-cycle", monkeypatch, session="bob-d1")
    assert "[K5]" not in capsys.readouterr().out


def test_k5_is_silent_in_an_unframed_project(shared, monkeypatch, capsys):
    hold.claim(clone(shared, "alice"), "D1", session="alice-d1", person="@alice")
    bob = clone(shared, "bob")
    charter = bob / "docs/project/charter.md"
    charter.write_text(charter.read_text(encoding="utf-8").replace("status: accepted", "status: proposed"),
                       encoding="utf-8")
    delivery(bob, "Deliverable: D1", "", monkeypatch, session="bob-d1")
    assert "[K5]" not in capsys.readouterr().out


@pytest.mark.parametrize("name, email", [("Carol Doe", "12345+carol-gh@users.noreply.github.com"),
                                         ("Bob", "bob@example.org")], ids=["noreply", "plain"])
def test_k5_knows_the_holder_by_the_git_identity_they_claimed_with(shared, monkeypatch, capsys, name, email):
    holder = clone(shared, "holder")
    monkeypatch.setenv("GIT_AUTHOR_NAME", name)
    monkeypatch.setenv("GIT_AUTHOR_EMAIL", email)
    hold.claim(holder, "D1")
    for variable, value in IDENTITY.items():
        monkeypatch.setenv(variable, value)
    capsys.readouterr()
    delivery(holder, "Deliverable: D1", "", monkeypatch, who=(name, email))
    assert "[K5]" not in capsys.readouterr().out


def test_a_noreply_address_names_its_github_account():
    assert hold.same("@carol-gh", "Carol Doe <12345+carol-gh@users.noreply.github.com>")


def test_a_display_name_alone_never_names_an_account():
    assert not hold.same("@bob", "Bob <robert@example.org>")


def test_k3_and_k5_read_a_lowercase_identifier_alike(shared, monkeypatch, capsys):
    hold.claim(clone(shared, "alice"), "D1", session="alice-d1", person="@alice")
    delivery(clone(shared, "bob"), "Deliverable: d1", "", monkeypatch, session="bob-d1")
    out = capsys.readouterr().out
    assert "FAIL [K5]" in out and "[K3] deliverable d1 is not in" not in out


def test_plan_shows_the_holds_even_when_its_rules_fail(shared, capsys):
    from napkinstack import cli

    bob = clone(shared, "bob")
    cycle = bob / "docs/project/cycles/03-the-window.md"
    cycle.write_text(cycle.read_text(encoding="utf-8").replace("end: 2026-11-07", "end: 2026-11-08"),
                     encoding="utf-8")
    args = cli.build_parser().parse_args(["plan", "--root", str(bob)])
    assert args.func(args) == 1
    assert "Holds in 03-the-window" in capsys.readouterr().out


def test_a_stale_hold_tells_its_holder_to_renew_and_others_to_take_over(shared, monkeypatch, capsys):
    for name, value in ago(10).items():
        monkeypatch.setenv(name, value)
    hold.claim(clone(shared, "alice"), "D1", session="alice-d1", person="@alice")
    for name in ("GIT_COMMITTER_DATE", "GIT_AUTHOR_DATE"):
        monkeypatch.delenv(name)
    capsys.readouterr()
    hold.show(clone(shared, "bob"))
    out = capsys.readouterr().out
    assert "its holder renews (nstack claim D1)" in out and "--take-over" in out


# --- part 2b: shown on the forge -----------------------------------------------------------

class Forge:
    """GitHub's API as the claim calls it: each request recorded, each answer given."""

    def __init__(self, pulls=(), repository=None):
        self.calls, self.pulls, self.headers = [], list(pulls), []
        self.repository = {"default_branch": "main"} if repository is None else repository

    def __call__(self, request, timeout=None):
        import io
        import json as j
        import urllib.parse

        body = j.loads(request.data) if request.data else None
        self.calls.append((request.get_method(), request.full_url, body))
        self.headers.append({key.lower(): value for key, value in request.header_items()})
        if request.get_method() == "GET" and "/pulls" in request.full_url:
            query = urllib.parse.parse_qs(urllib.parse.urlsplit(request.full_url).query)
            head = query.get("head", [""])[0]
            answer = [pull for pull in self.pulls if not head or f"acme:{pull['head']['ref']}" == head]
        elif request.get_method() == "GET":
            answer = self.repository
        elif request.full_url.endswith("/pulls"):
            answer = {"html_url": "https://github.com/acme/p/pull/7", "number": 7}
        else:
            answer = {"html_url": "https://github.com/acme/p/pull/3#issuecomment-1"}

        class Answer(io.BytesIO):
            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

        return Answer(j.dumps(answer).encode())


def on_github(folder: Path, shared: Path) -> Path:
    git(folder, "config", f"url.{shared}.insteadOf", "https://github.com/acme/p.git")
    git(folder, "remote", "set-url", "origin", "https://github.com/acme/p.git")
    return folder


def test_a_claim_opens_a_draft_pull_request_naming_the_deliverable(shared, monkeypatch, capsys):
    forge = Forge()
    monkeypatch.setattr(hold.urllib.request, "urlopen", forge)
    monkeypatch.setenv("GH_TOKEN", "token")
    assert hold.claim(on_github(clone(shared, "alice"), shared), "D1", session="alice-d1", person="@alice") == 0
    opened = [body for method, url, body in forge.calls if method == "POST" and url.endswith("/repos/acme/p/pulls")]
    assert len(opened) == 1
    assert opened[0]["draft"] is True and opened[0]["head"] == "d1-resume-an-interrupted-recording"
    assert opened[0]["base"] == "main" and "Deliverable: D1" in opened[0]["body"]
    assert "pull/7" in capsys.readouterr().out


def test_without_a_token_the_display_is_skipped_and_said(shared, capsys):
    hold.claim(clone(shared, "alice"), "D1", session="alice-d1", person="@alice")
    assert "not shown on a forge" in capsys.readouterr().out


def test_a_take_over_tells_the_previous_holder_on_their_open_pull_request(shared, monkeypatch, capsys):
    for name, value in ago(10).items():
        monkeypatch.setenv(name, value)
    hold.claim(clone(shared, "alice"), "D1", session="alice-d1", person="@alice")
    for name in ("GIT_COMMITTER_DATE", "GIT_AUTHOR_DATE"):
        monkeypatch.delenv(name)
    forge = Forge(pulls=[{"number": 3, "head": {"ref": "d1-resume-an-interrupted-recording"}},
                         {"number": 4, "head": {"ref": "d10-other"}}])
    monkeypatch.setattr(hold.urllib.request, "urlopen", forge)
    monkeypatch.setenv("GH_TOKEN", "token")
    capsys.readouterr()
    assert hold.claim(on_github(clone(shared, "bob"), shared), "D1", session="bob-d1", person="@bob",
                      take_over=True) == 0
    told = [(url, body) for method, url, body in forge.calls if url.endswith("/comments")]
    assert [url.rsplit("/", 2)[-2] for url, _ in told] == ["3"]
    assert "@bob" in told[0][1]["body"] and "@alice" in told[0][1]["body"]
    assert not any(url.endswith("/pulls") and method == "POST" for method, url, _ in forge.calls)


def test_a_forge_that_refuses_is_said_and_the_hold_stands(shared, monkeypatch, capsys):
    def refuse(request, timeout=None):
        raise OSError("HTTP Error 422: draft pull requests are not supported in this repository")

    monkeypatch.setattr(hold.urllib.request, "urlopen", refuse)
    monkeypatch.setenv("GH_TOKEN", "token")
    assert hold.claim(on_github(clone(shared, "alice"), shared), "D1", session="alice-d1", person="@alice") == 0
    assert "not shown on GitHub" in capsys.readouterr().out
    assert remote_events(shared) == ["claim"]


# --- part 2b: what a newcomer reads -------------------------------------------------------

SKELETON = Path(__file__).resolve().parents[2] / "skeleton"


def test_contributing_says_how_several_contributors_share_a_project():
    """PDR-0015, point 7: each of the four, pointing to the handbook page that holds the detail —
    joining in its own section since D179, the rest in *Working with several contributors*."""
    page = (SKELETON / "CONTRIBUTING.md.jinja").read_text(encoding="utf-8")
    section = "".join(page.split(f"## {title}", 1)[1].split("\n## ", 1)[0]
                      for title in ("Joining the project", "Working with several contributors"))
    said = {
        "shared by module": ("by module", "02-modules.md"),
        "joining": ("CODEOWNERS", "INSTALL.md"),
        "any agent": ("AGENTS.md", ".nstack/playbooks/"),
        "take first": ("nstack claim", "project.md"),
    }
    for point, (words, pointer) in said.items():
        assert words in section and pointer in section, f"{point}: '{words}' and '{pointer}' expected"


def test_the_kernel_tells_an_agent_to_take_its_deliverable_and_stop_on_a_hold():
    kernel = (SKELETON / "AGENTS.md").read_text(encoding="utf-8")
    assert "nstack claim D<n> --session" in kernel and "held by someone else" in kernel.lower()


# --- found by the verifier of part 2b ---------------------------------------------------

def stale_alice(shared, monkeypatch):
    for name, value in ago(10).items():
        monkeypatch.setenv(name, value)
    hold.claim(clone(shared, "alice"), "D1", session="alice-d1", person="@alice")
    for name in ("GIT_COMMITTER_DATE", "GIT_AUTHOR_DATE"):
        monkeypatch.delenv(name)


def test_a_take_over_tells_only_pull_requests_from_this_repository_s_work_branches(shared, monkeypatch, capsys):
    """A fork's branch of the same name is no work on the hold: GitHub's head filter, owner:branch,
    asks for this repository's branches only."""
    stale_alice(shared, monkeypatch)
    forge = Forge(pulls=[{"number": 3, "head": {"ref": "d1-resume-an-interrupted-recording"}}])
    monkeypatch.setattr(hold.urllib.request, "urlopen", forge)
    monkeypatch.setenv("GH_TOKEN", "token")
    hold.claim(on_github(clone(shared, "bob"), shared), "D1", session="bob-d1", person="@bob", take_over=True)
    asked = [url for method, url, _ in forge.calls if method == "GET" and "/pulls" in url]
    assert asked and all("head=acme%3Ad1-" in url or "head=acme:d1-" in url for url in asked)


def test_a_new_holder_on_an_existing_branch_is_said_on_its_open_pull_request(shared, monkeypatch, capsys):
    alice = clone(shared, "alice")
    hold.claim(alice, "D1", session="alice-d1", person="@alice")
    hold.release(alice, "D1", person="@alice")
    forge = Forge(pulls=[{"number": 3, "head": {"ref": "d1-resume-an-interrupted-recording"}}])
    monkeypatch.setattr(hold.urllib.request, "urlopen", forge)
    monkeypatch.setenv("GH_TOKEN", "token")
    capsys.readouterr()
    assert hold.claim(on_github(clone(shared, "bob"), shared), "D1", session="bob-d1", person="@bob") == 0
    told = [body["body"] for method, url, body in forge.calls if url.endswith("/issues/3/comments")]
    assert len(told) == 1 and "@bob" in told[0]
    assert "#3 told" in capsys.readouterr().out


@pytest.mark.parametrize("repository", [[], None, {"no": "default branch"}], ids=["list", "null", "no field"])
def test_an_odd_answer_from_the_forge_never_escapes_after_the_hold(shared, monkeypatch, capsys, repository):
    forge = Forge(repository=repository)
    monkeypatch.setattr(hold.urllib.request, "urlopen", forge)
    monkeypatch.setenv("GH_TOKEN", "token")
    assert hold.claim(on_github(clone(shared, "alice"), shared), "D1", session="alice-d1", person="@alice") == 0
    assert remote_events(shared) == ["claim"]


def test_a_truncated_answer_never_escapes_after_the_hold(shared, monkeypatch, capsys):
    import http.client

    def truncated(request, timeout=None):
        raise http.client.IncompleteRead(b"{}")

    monkeypatch.setattr(hold.urllib.request, "urlopen", truncated)
    monkeypatch.setenv("GH_TOKEN", "token")
    assert hold.claim(on_github(clone(shared, "alice"), shared), "D1", session="alice-d1", person="@alice") == 0
    assert "not shown on GitHub" in capsys.readouterr().out


def test_the_forge_s_own_reason_is_said(shared, monkeypatch, capsys):
    import io
    import urllib.error

    def refuse(request, timeout=None):
        raise urllib.error.HTTPError(request.full_url, 422, "Unprocessable Content", {},
                                     io.BytesIO(b'{"message": "Draft pull requests are not supported in this repository."}'))

    monkeypatch.setattr(hold.urllib.request, "urlopen", refuse)
    monkeypatch.setenv("GH_TOKEN", "token")
    hold.claim(on_github(clone(shared, "alice"), shared), "D1", session="alice-d1", person="@alice")
    assert "Draft pull requests are not supported" in capsys.readouterr().out


def test_requests_carry_the_api_version_the_engine_and_json(shared, monkeypatch):
    from napkinstack import doctor

    forge = Forge()
    monkeypatch.setattr(hold.urllib.request, "urlopen", forge)
    monkeypatch.setenv("GH_TOKEN", "token")
    hold.claim(on_github(clone(shared, "alice"), shared), "D1", session="alice-d1", person="@alice")
    for headers in forge.headers:
        assert headers.get("x-github-api-version") == doctor.API_VERSION
        assert headers.get("user-agent", "").startswith("nstack/")
    posted = [h for (method, _, _), h in zip(forge.calls, forge.headers) if method == "POST"]
    assert posted and all(h.get("content-type") == "application/json" for h in posted)


def test_an_empty_api_address_is_the_default_one(shared, monkeypatch):
    forge = Forge()
    monkeypatch.setattr(hold.urllib.request, "urlopen", forge)
    monkeypatch.setenv("GH_TOKEN", "token")
    monkeypatch.setenv("GITHUB_API_URL", "")
    hold.claim(on_github(clone(shared, "alice"), shared), "D1", session="alice-d1", person="@alice")
    assert forge.calls and all(url.startswith("https://api.github.com/") for _, url, _ in forge.calls)


def test_the_definition_of_ready_asks_the_deliverable_held():
    page = (SKELETON / ".nstack/handbook/05-workflow.md").read_text(encoding="utf-8")
    ready = page.split("## 6. Definition of Ready", 1)[1].split("\n## ", 1)[0]
    assert "nstack claim" in ready


def test_the_kernel_says_where_the_person_comes_from_and_agrees_with_the_engine():
    kernel = (SKELETON / "AGENTS.md").read_text(encoding="utf-8")
    assert "asked once" in kernel and "never git's user" in kernel
    assert "take another ready deliverable" in kernel


# --- part 2c: the forge refuses a forced push on a hold (G20) ----------------------------

class Rules:
    """A forge answering the rules that apply to a branch, and the rulesets they come from, as
    doctor reads them. A hold is two levels under the prefix — cycle, then deliverable — and a
    ruleset's `**` stops at a slash (GitHub's fnmatch, FNM_PATHNAME): the probe has a hold's depth."""

    def __init__(self, on_holds, bypass=()):
        self.on_holds, self.bypass = on_holds, list(bypass)

    def get(self, path, missing=False):
        if path.startswith("/rulesets/"):
            return {"id": 9, "bypass_actors": self.bypass}
        assert path == f"/rules/branches/{hold.PREFIX}/probe/probe", path
        return [{"type": kind, "ruleset_id": 9} for kind in self.on_holds]


@pytest.mark.parametrize("kinds, kept", [(["non_fast_forward", "deletion"], True), (["non_fast_forward"], False),
                                         (["deletion"], False), ([], False)])
def test_g20_reads_forced_pushes_and_deletion_refused_on_the_holds(kinds, kept):
    from napkinstack import doctor

    assert doctor.CHECKS["G20"](Rules(kinds)) is kept


def test_g20_is_planned_as_a_ruleset_of_its_own_on_the_holds():
    from napkinstack import settings

    calls, _ = settings.plan(None, {"G20"})
    assert [(closed, method, path) for closed, method, path, _ in calls] == [("G20", "POST", "/rulesets")]
    body = calls[0][3]
    assert body["conditions"]["ref_name"]["include"] == ["refs/heads/nstack/hold/**/*"]
    assert {rule["type"] for rule in body["rules"]} == {"non_fast_forward", "deletion"}
    assert body["bypass_actors"] == [] and body["enforcement"] == "active"


def test_g20_is_out_of_reach_where_rulesets_are_and_said_in_the_manual():
    from napkinstack import doctor

    assert "G20" in doctor.PRIVATE_PLAN
    setting = next(setting for rule, setting, _ in doctor.CHECKLIST if rule == "G20")
    assert f"- [ ] {setting}" in (SKELETON / ".nstack/handbook/INSTALL.md.jinja").read_text(encoding="utf-8")


def test_g20_is_a_gap_when_someone_may_bypass_the_holds_ruleset():
    from napkinstack import doctor

    assert doctor.CHECKS["G20"](Rules(["non_fast_forward", "deletion"],
                                      bypass=[{"actor_id": 5, "actor_type": "RepositoryRole"}])) is False


def test_the_settings_say_both_rulesets_are_created_once(tmp_path, capsys):
    from napkinstack import settings

    (tmp_path / ".copier-answers.yml").write_text("github_repo: acme/p\n", encoding="utf-8")
    settings.run(tmp_path)
    said = " ".join(capsys.readouterr().out.split())
    assert "nstack-checklist exists" in said and "nstack-holds does" in said


def test_every_page_names_the_holds_pattern_a_ruleset_matches_at_their_depth():
    from napkinstack import doctor

    manual = (SKELETON / ".nstack/handbook/INSTALL.md.jinja").read_text(encoding="utf-8")
    assert "a second ruleset, on the branches `nstack/hold/**/*`" in manual
    assert "- [ ] Hold branches `nstack/hold/**/*`" in manual
    record = next((SKELETON.parent / "docs/adr").glob("0007-*.md")).read_text(encoding="utf-8")
    assert "`nstack/hold/**/*`" in record
    assert all("nstack/hold/**/*" in " ".join(entry) for entry in doctor.CHECKLIST if entry[0] == "G20")


def test_plan_s_holds_say_how_many_are_held_and_stale(shared, monkeypatch, capsys):
    hold.claim(clone(shared, "alice"), "D1", session="alice-d1", person="@alice")
    capsys.readouterr()
    hold.show(clone(shared, "bob"))
    assert "Holds in 03-the-window: 1 held, of which 0 stale (" in capsys.readouterr().out


# --- D149: a claim made from the work's own branch makes no second one (#232) ----------------

def test_a_claim_from_a_deliverable_s_branch_makes_no_other(shared, capsys):
    alice = clone(shared, "alice")
    git(alice, "switch", "-q", "-c", "d1-log-audit", "origin/main")
    git(alice, "commit", "-q", "--allow-empty", "-m", "the work")
    git(alice, "push", "-q", "origin", "d1-log-audit")
    capsys.readouterr()
    assert hold.claim(alice, "D1", session="alice-d1", person="@alice") == 0
    out = capsys.readouterr().out
    assert "work continues on d1-log-audit" in out, out
    assert "git switch" not in out, out
    heads = git(shared, "for-each-ref", "--format=%(refname:short)", "refs/heads/d1-*").split()
    assert heads == ["d1-log-audit"], f"a second work branch was made: {heads}"


def test_a_deliverable_s_branch_not_pushed_is_taken_and_said_to_push(shared, capsys):
    alice = clone(shared, "alice")
    git(alice, "switch", "-q", "-c", "d1-log-audit", "origin/main")
    capsys.readouterr()
    assert hold.claim(alice, "D1", session="alice-d1", person="@alice") == 0
    out = capsys.readouterr().out
    assert "work continues on d1-log-audit" in out and "git push -u origin d1-log-audit" in out, out
    assert not git(shared, "for-each-ref", "refs/heads/d1-*")


def test_another_deliverable_s_branch_is_not_taken_for_this_one(shared, capsys):
    alice = clone(shared, "alice")
    git(alice, "switch", "-q", "-c", "d10-something-else", "origin/main")
    assert hold.claim(alice, "D1", session="alice-d1", person="@alice") == 0
    assert git(shared, "rev-parse", "--verify", "--quiet", "d1-resume-an-interrupted-recording")


# --- D165: a hold lasts its cycle (#280) -------------------------------------------------------

@pytest.mark.parametrize("after", ["between two cycles", "under the next cycle"])
def test_a_hold_ends_with_its_cycle_and_unclaim_says_so(shared, capsys, after):
    alice = clone(shared, "alice")
    hold.claim(alice, "D1", session="alice-d1", person="@alice")
    cycle = alice / "docs/project/cycles/03-the-window.md"
    cycle.write_text(CYCLE.replace("status: accepted", "status: closed\noutcome: completed\nended_on: 2026-11-07")
                     .replace("state: ready", "state: accepted"), encoding="utf-8")
    if after == "under the next cycle":
        (alice / "docs/project/cycles/04-next.md").write_text(
            CYCLE.replace("2026-10-17", "2026-11-08").replace("2026-11-07", "2026-11-29"), encoding="utf-8")
    git(alice, "add", "-A")
    git(alice, "commit", "-q", "-m", "closure")
    capsys.readouterr()
    assert hold.release(alice, "D1", person="@bob") == 0
    out = capsys.readouterr().out
    assert "D1's hold ended with 03-the-window (closed): a hold lasts its cycle, nothing to release" in out, out
    assert "nstack/hold/03-the-window/D1 is kept, the hold's record" in out, out
    assert remote_events(shared) == ["claim"]
