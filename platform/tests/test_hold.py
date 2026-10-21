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
