"""D137, PDR-0015, ADR-0007: a contributor takes a deliverable in one gesture a second taker
cannot also win; a hold nobody works on is taken over, recorded. Every case proves its rule
fails (P5) and names itself (P6). Run by platform/tests/run.sh.
"""

from __future__ import annotations

import datetime
import os
import re
import subprocess
from pathlib import Path

import time
import pytest
import yaml

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


def test_the_holding_session_claiming_again_renews(shared):
    alice = clone(shared, "alice")
    hold.claim(alice, "D1", session="alice-d1", person="@alice")
    assert hold.claim(alice, "D1", session="alice-d1", person="alice") == 0  # the @ or not, one person
    assert remote_events(shared) == ["renew", "claim"]
    assert hold.read(alice, "03-the-window", "D1").sessions == ["alice-d1"]


def test_another_session_of_the_same_person_is_refused_and_named_the_way_out(shared, capsys):
    """#315: two agents of one person are two holders (D181); neither renews the other's hold."""
    hold.claim(clone(shared, "alice"), "D1", session="agent-one", person="@alice")
    capsys.readouterr()
    assert hold.claim(clone(shared, "other"), "D1", session="agent-two", person="alice") == 1
    out = capsys.readouterr().out
    assert "FAIL [hold] D1 is held by @alice, session agent-one, since" in out
    assert "--take-over" in out and "asks" in out
    assert remote_events(shared) == ["claim"]


MARC = "9003+demo-marc[bot]@users.noreply.github.com"


def as_agent(monkeypatch, email: str, agent: str | None = "marc") -> None:
    """A session committing as `email`, its own global configuration naming it — as nstack agent run's."""
    import tempfile

    config = Path(tempfile.mkdtemp()) / "gitconfig"
    config.write_text(f"[user]\n\temail = {email}\n", encoding="utf-8")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(config))
    monkeypatch.setenv("GIT_COMMITTER_EMAIL", email)
    monkeypatch.setenv("GIT_AUTHOR_EMAIL", email)
    if agent:
        monkeypatch.setenv("NSTACK_AGENT", agent)
    else:
        monkeypatch.delenv("NSTACK_AGENT", raising=False)


def test_an_agent_restarted_renews_its_own_hold_under_a_new_session(shared, capsys, monkeypatch):
    """#498 (D271): a restart changes the agent's session, never its identity. Every event that put a
    session on the hold was committed under the identity this agent's session commits with: the agent
    renews its own hold, said and recorded, and both sessions stay on it for K5."""
    as_agent(monkeypatch, MARC)
    hold.claim(clone(shared, "marc"), "D1", session="marc-before", person="@alice")
    capsys.readouterr()
    after = clone(shared, "marc-after")
    assert hold.claim(after, "D1", session="marc-after", person="@alice") == 0
    out = capsys.readouterr().out
    assert f"D1 renewed: held by @alice, session marc-after — the same agent identity {MARC} as session " \
           "marc-before" in out, out
    assert remote_events(shared) == ["renew", "claim"]
    assert hold.read(after, "03-the-window", "D1").sessions == ["marc-before", "marc-after"]
    assert "Hold-Previous: @alice (marc-before)" in git(shared, "log", "-1", "--format=%B", REF)


def test_a_clone_s_own_identity_is_not_the_agent_s(shared, capsys, monkeypatch, tmp_path):
    """D271's verifier: a clone whose local user.email is the hold's identity commits under it, but the
    agent's own (global) configuration names another: no renewal by identity."""
    agent_config = tmp_path / "ines.gitconfig"
    agent_config.write_text("[user]\n\temail = 9004+demo-ines[bot]@users.noreply.github.com\n", encoding="utf-8")
    as_agent(monkeypatch, MARC)
    hold.claim(clone(shared, "marc"), "D1", session="marc-before", person="@alice")
    monkeypatch.delenv("GIT_COMMITTER_EMAIL")
    monkeypatch.delenv("GIT_AUTHOR_EMAIL")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(agent_config))
    monkeypatch.setenv("NSTACK_AGENT", "ines")
    other = clone(shared, "other")
    git(other, "config", "user.email", MARC)
    assert hold.claim(other, "D1", session="ines-1", person="@alice") == 1
    assert remote_events(shared) == ["claim"]


def test_a_hold_whose_sessions_came_from_two_identities_is_renewed_by_neither(shared, capsys, monkeypatch):
    """Identity is the relief only when one identity put every session on the hold; a person's renewal
    with no session adds none (D271's verifier)."""
    as_agent(monkeypatch, MARC)
    marc = clone(shared, "marc")
    hold.claim(marc, "D1", session="marc-1", person="@alice")
    as_agent(monkeypatch, "alice@example.org", None)
    assert hold.claim(clone(shared, "alice"), "D1", person="@alice") == 0  # a person with no session renews
    as_agent(monkeypatch, MARC)
    assert hold.claim(clone(shared, "marc-2"), "D1", session="marc-2", person="@alice") == 0, "no session, no identity"
    as_agent(monkeypatch, "9004+demo-ines[bot]@users.noreply.github.com", "ines")
    assert hold.claim(clone(shared, "ines"), "D1", session="marc-2", person="@alice") == 0  # a session it names
    as_agent(monkeypatch, MARC)
    assert hold.claim(clone(shared, "marc-3"), "D1", session="marc-3", person="@alice") == 1, "ines put a session on it"


def test_an_agent_restarted_gives_its_own_hold_back_from_its_new_session(shared, capsys, monkeypatch):
    """D272: what renews a restarted agent's hold releases it too — nstack unclaim from the new session,
    in the agent's own run; outside an agent's run, the same command is still refused."""
    as_agent(monkeypatch, MARC)
    hold.claim(clone(shared, "marc"), "D1", session="marc-before", person="@alice")
    after = clone(shared, "marc-after")
    as_agent(monkeypatch, MARC, None)
    capsys.readouterr()
    assert hold.release(after, "D1", session="marc-after", person="@alice") == 1
    assert "nstack agent run" in capsys.readouterr().out
    as_agent(monkeypatch, MARC)
    assert hold.release(after, "D1", session="marc-after", person="@alice") == 0, capsys.readouterr().out
    assert remote_events(shared) == ["release", "claim"]


def test_a_claim_refused_for_want_of_its_person_says_so(shared, capsys):
    """D272: a session that named no --person reads git's user and is refused as anyone else; the refusal
    says which person holds it, as unclaim's does, and the command it prints survives the shell."""
    hold.claim(clone(shared, "alice"), "D1", session="alice-d1", person="Alice Smith <alice@example.org>")
    capsys.readouterr()
    assert hold.claim(clone(shared, "bob"), "D1", session="alice-d2") == 1
    out = capsys.readouterr().out
    assert "No --person was given" in out and "--person 'Alice Smith <alice@example.org>'" in out, out
    assert hold.claim(clone(shared, "carol"), "D1", session="alice-d2", person="Alice Smith <alice@example.org>") == 1
    out = capsys.readouterr().out
    assert "No --person was given" not in out, out
    assert "nstack claim D1 --take-over --person 'Alice Smith <alice@example.org>' --session alice-d2" in out, out
    assert hold.release(clone(shared, "dan"), "D1", session="dan-d1") == 1
    assert "run again with --person 'Alice Smith <alice@example.org>'" in capsys.readouterr().out


@pytest.mark.parametrize("email, agent", [
    ("9004+demo-ines[bot]@users.noreply.github.com", "ines"),   # another agent of the same person (#315)
    (MARC, None),                                               # one identity, sessions outside nstack agent run
])
def test_another_identity_or_a_session_outside_an_agent_s_still_needs_the_person_s_word(shared, capsys, monkeypatch,
                                                                                         email, agent):
    as_agent(monkeypatch, MARC)
    hold.claim(clone(shared, "marc"), "D1", session="marc-before", person="@alice")
    capsys.readouterr()
    as_agent(monkeypatch, email, agent)
    assert hold.claim(clone(shared, "other"), "D1", session="other", person="@alice") == 1
    assert "--take-over" in capsys.readouterr().out
    assert hold.release(clone(shared, "other2"), "D1", session="other", person="@alice") == 1  # D272: nor gives it back
    assert ("in nstack agent run" in capsys.readouterr().out) == (agent is None), "the restart's way, said outside it"
    assert remote_events(shared) == ["claim"]


def test_a_hold_another_identity_put_a_session_on_is_not_renewed_by_identity(shared, capsys, monkeypatch):
    """Taken over by marc from ines's session: ines's later session is not marc's, and marc's own
    new session finds only its identity since the take-over."""
    as_agent(monkeypatch, "9004+demo-ines[bot]@users.noreply.github.com", "ines")
    hold.claim(clone(shared, "ines"), "D1", session="ines-1", person="@alice")
    as_agent(monkeypatch, MARC)
    assert hold.claim(clone(shared, "marc"), "D1", session="marc-1", person="@alice", take_over=True) == 0
    as_agent(monkeypatch, "9004+demo-ines[bot]@users.noreply.github.com", "ines")
    assert hold.claim(clone(shared, "ines-2"), "D1", session="ines-2", person="@alice") == 1
    as_agent(monkeypatch, MARC)
    assert hold.claim(clone(shared, "marc-2"), "D1", session="marc-2", person="@alice") == 0
    assert remote_events(shared) == ["renew", "take-over", "claim"]


def test_the_person_s_word_takes_over_from_their_other_session_at_once(shared, capsys):
    """Not stale: the hold is the person's to move, recorded with the session it left."""
    hold.claim(clone(shared, "alice"), "D1", session="agent-one", person="@alice")
    capsys.readouterr()
    other = clone(shared, "other")
    assert hold.claim(other, "D1", session="agent-two", person="@alice", take_over=True) == 0
    assert "taken over from @alice, session agent-one" in capsys.readouterr().out
    assert remote_events(shared) == ["take-over", "claim"]
    state = hold.read(other, "03-the-window", "D1")
    assert state.person == "@alice" and state.sessions == ["agent-two"]
    assert "Hold-Previous: @alice (agent-one)" in git(shared, "log", "-1", "--format=%B", REF)
    assert hold.claim(other, "D1", session="agent-one", person="@alice") == 1  # and it does not flip back


def test_what_the_refusal_says_to_run_works_as_written(shared, capsys):
    """The kernel forbids git's user as the person: a command naming none would be refused again."""
    hold.claim(clone(shared, "alice"), "D1", session="agent-one", person="@alice")
    capsys.readouterr()
    other = clone(shared, "other")
    assert hold.release(other, "D1", session="agent-two", person="@alice") == 1
    assert "--person @alice" in capsys.readouterr().out
    assert hold.claim(other, "D1", session="agent-two", person="@alice", take_over=True) == 0


def test_the_decider_gives_back_a_hold_their_own_session_holds(shared):
    hold.claim(clone(shared, "dana"), "D1", session="s1", person="@dana")
    assert hold.release(clone(shared, "other"), "D1", session="s2", person="@dana") == 0


def test_a_padded_session_is_written_stripped(shared):
    alice = clone(shared, "alice")
    assert hold.claim(alice, "D1", session="  s1 ", person="@alice") == 0
    assert hold.read(alice, "03-the-window", "D1").sessions == ["s1"]
    assert "Agent-Session: s1\n" in git(shared, "log", "-1", "--format=%B", REF) + "\n"


def test_a_session_is_the_same_whatever_its_case_or_spaces(shared):
    alice = clone(shared, "alice")
    hold.claim(alice, "D1", session="Agent-One", person="@alice")
    assert hold.claim(alice, "D1", session=" agent-one ", person="@alice") == 0
    assert remote_events(shared) == ["renew", "claim"]


def test_another_session_of_the_same_person_does_not_unclaim_either(shared, capsys):
    """#315 by the other door: release, then claim."""
    hold.claim(clone(shared, "alice"), "D1", session="agent-one", person="@alice")
    capsys.readouterr()
    assert hold.release(clone(shared, "other"), "D1", session="agent-two", person="@alice") == 1
    assert "--take-over" in capsys.readouterr().out
    assert remote_events(shared) == ["claim"]


@pytest.mark.parametrize("first, second", [("agent-one", None), (None, "agent-two"), (None, None)])
def test_a_person_with_no_session_on_one_side_renews(shared, first, second):
    """A person at the keyboard has no session: nothing to tell apart, the person's name answers."""
    alice = clone(shared, "alice")
    hold.claim(alice, "D1", session=first, person="@alice")
    assert hold.claim(alice, "D1", session=second, person="@alice") == 0
    assert remote_events(shared) == ["renew", "claim"]


def test_an_older_hold_flipped_between_two_sessions_still_renews_for_either(shared):
    """What v0.19.4 let happen stays readable: both sessions are on its events."""
    alice = clone(shared, "alice")
    hold.claim(alice, "D1", session="agent-one", person="@alice")
    tip = hold.read(alice, "03-the-window", "D1")
    assert hold._record(alice, "origin", "03-the-window", "D1",
                        hold._event(alice, tip.tip, "D1", "renew", "@alice", "agent-two"))[0]
    assert hold.claim(alice, "D1", session="agent-one", person="@alice") == 0


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


def test_k5_s_action_names_the_agent_s_run_and_survives_the_shell(shared):
    """D272: the renewal K5 offers works only in nstack agent run, and a person git names — a name and an
    address — is quoted in the commands it prints."""
    from napkinstack import pull_request

    hold.claim(clone(shared, "alice"), "D1", session="alice-d1", person="Alice Smith <alice@example.org>")
    failed = []
    pull_request.check_hold(clone(shared, "bob"), "Deliverable: D1", set(), AUTHORED,
                            lambda rule, message: failed.append((rule, message)), lambda _: None)
    message = failed[0][1]
    assert "in nstack agent run" in message and "--person 'Alice Smith <alice@example.org>'" in message, message


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


def test_k5_reads_the_holder_s_session_on_the_merge_that_brings_the_former_work(shared, monkeypatch, capsys):
    """#439: a deliverable taken over on the decider's word; the new session merges the default branch
    into the former session's branch and opens the pull request. Its only commit is the merge, which
    K5 never read: the holder's own pull request was refused, and the way out K5 offered — moving the
    hold back to the former session — would have undone the take-over."""
    from napkinstack import pull_request

    hold.claim(clone(shared, "alice"), "D1", session="alice-new", person="@alice")
    holder = clone(shared, "holder")
    assert delivery(holder, "Deliverable: D1", "", monkeypatch, session="alice-old") == 1  # the former work alone
    carol = clone(shared, "carol")
    (carol / "elsewhere.txt").write_text("main moved\n", encoding="utf-8")
    git(carol, "add", "-A")
    git(carol, "commit", "-q", "-m", "main moved")
    git(carol, "push", "-q", "origin", "HEAD:main")
    git(holder, "fetch", "-q")
    git(holder, "merge", "-q", "--no-ff", "origin/main", "-m", "Merge main\n\nAgent-Session: alice-new")
    capsys.readouterr()
    pull_request.run(holder, "origin/main")
    assert "[K5]" not in capsys.readouterr().out


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


@pytest.mark.parametrize("url", ["https://user:secret@github.com/acme/p.git", "ssh://git@github.com/acme/p.git",
                                 "ssh://deploy@github.com/acme/p.git", "git@github.com:acme/p.git",
                                 "https://github.com/acme/p"])
def test_a_github_remote_is_read_whatever_user_it_names(url):
    from napkinstack.doctor import ON_GITHUB

    assert ON_GITHUB.search(url).group(1) == "acme/p"


@pytest.mark.parametrize("url", ["https://evil.com/@github.com/acme/p", "https://github.com.evil.com/acme/p",
                                 "https://github.com@evil.com/acme/p", "https://evil.com?@github.com/acme/p",
                                 "https://evil.com#@github.com/acme/p", "https://evil.com/gh:acme/p",
                                 "https://evil.com/x/git@github.com:acme/p", "http://github.com/acme/p"])
def test_another_host_is_never_read_as_github(url):
    """Git reads the host up to the first `/`, `?` or `#` after the scheme, and the last `@` before
    it: each of these addresses is another host's, and its writes would go to a repository it is not."""
    from napkinstack.doctor import ON_GITHUB

    assert ON_GITHUB.search(url) is None


def test_an_enterprise_remote_s_host_is_never_taken_from_a_user():
    assert hold.SERVER.fullmatch("https://evil.com?@ghe.example/acme/p.git") is None


def test_from_an_agent_s_clone_the_claim_opens_its_draft_pull_request(shared, monkeypatch, capsys):
    """#522: `nstack agent add` sets the clone's remote to agent.remote(), whose user keeps the
    person's ~/.netrc out; the forge's reader took that remote for none, and skipped every write."""
    from napkinstack import agent

    monkeypatch.delenv("GITHUB_SERVER_URL", raising=False)
    url = agent.remote("acme/p")
    alice = clone(shared, "alice")
    git(alice, "config", f"url.{shared}.insteadOf", url)
    git(alice, "remote", "set-url", "origin", url)
    forge = Forge()
    monkeypatch.setattr(hold.urllib.request, "urlopen", forge)
    monkeypatch.setenv("GH_TOKEN", "token")
    assert hold._forge(alice, "origin")[1] == "acme/p"
    assert hold.claim(alice, "D1", session="alice-d1", person="@alice") == 0
    assert [url for method, url, _ in forge.calls if method == "POST" and url.endswith("/repos/acme/p/pulls")]


def test_without_a_token_the_display_is_skipped_and_said(shared, capsys):
    hold.claim(clone(shared, "alice"), "D1", session="alice-d1", person="@alice")
    assert "not shown on a forge (no GitHub remote, or no token); nstack plan shows who holds what" \
        in capsys.readouterr().out


def test_off_github_the_claim_says_where_the_hold_is_seen(shared, capsys, monkeypatch):
    alice = clone(shared, "alice")
    (alice / ".copier-answers.yml").write_text("_commit: v0.11.1\nproject_name: p\nforge: gitlab\n", encoding="utf-8")
    monkeypatch.setenv("GH_TOKEN", "a-token")
    assert hold.claim(alice, "D1", session="alice-d1", person="@alice") == 0
    assert "not shown — forge gitlab; nstack plan shows who holds what" in capsys.readouterr().out
    hold.show(alice)
    assert "@alice" in capsys.readouterr().out


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
    # no -u: an agent's sandbox write-protects .git/config, where the upstream is written (D212)
    assert "work continues on d1-log-audit" in out and "Next: git push origin d1-log-audit" in out, out
    assert not git(shared, "for-each-ref", "refs/heads/d1-*")


def test_another_deliverable_s_branch_is_not_taken_for_this_one(shared, capsys):
    alice = clone(shared, "alice")
    git(alice, "switch", "-q", "-c", "d10-something-else", "origin/main")
    assert hold.claim(alice, "D1", session="alice-d1", person="@alice") == 0
    assert git(shared, "rev-parse", "--verify", "--quiet", "d1-resume-an-interrupted-recording")


def _start_branch(shared: Path, branch: str, title: str) -> None:
    """A branch `claim` started for a D1 titled otherwise — an earlier cycle's, never deleted."""
    tree = git(shared, "rev-parse", "main^{tree}")
    start = git(shared, "commit-tree", tree, "-p", "main", "-m", f"Start D1 — {title}")
    git(shared, "update-ref", f"refs/heads/{branch}", start)


def test_another_cycle_s_start_branch_of_the_same_id_is_not_taken_for_this_one(shared, capsys):
    _start_branch(shared, "d1-an-older-title", "An older title")
    capsys.readouterr()
    assert hold.claim(clone(shared, "alice"), "D1", session="alice-d1", person="@alice") == 0
    out = capsys.readouterr().out
    assert "work continues on d1-an-older-title" not in out, out
    assert "work branch d1-resume-an-interrupted-recording created" in out, out
    assert git(shared, "rev-parse", "--verify", "--quiet", "d1-resume-an-interrupted-recording")


def test_this_deliverable_s_own_start_branch_is_still_taken(shared, capsys):
    _start_branch(shared, "d1-resume-an-interrupted-recording", "Resume an interrupted recording")
    capsys.readouterr()
    assert hold.claim(clone(shared, "alice"), "D1", session="alice-d1", person="@alice") == 0
    assert "work continues on d1-resume-an-interrupted-recording" in capsys.readouterr().out


def test_a_retitled_deliverable_s_worked_branch_is_still_its_own(shared, capsys):
    alice = clone(shared, "alice")
    hold.claim(alice, "D1", session="alice-d1", person="@alice")
    git(alice, "switch", "-q", "d1-resume-an-interrupted-recording")
    (alice / "resume.txt").write_text("work\n", encoding="utf-8")
    git(alice, "add", "resume.txt")
    git(alice, "commit", "-q", "-m", "Resume from the last chunk")
    git(alice, "push", "-q", "origin", "d1-resume-an-interrupted-recording")
    git(alice, "switch", "-q", "main")
    cycle = alice / "docs/project/cycles/03-the-window.md"
    cycle.write_text(cycle.read_text(encoding="utf-8").replace("Resume an interrupted recording", "Resume a cut recording"),
                     encoding="utf-8")
    git(alice, "commit", "-q", "-am", "Retitle D1")
    git(alice, "push", "-q", "origin", "main")
    capsys.readouterr()
    assert hold.claim(alice, "D1", session="alice-d1", person="@alice") == 0
    assert "work branch" not in capsys.readouterr().out
    assert git(shared, "for-each-ref", "--format=%(refname:short)", "refs/heads/d1-*") == "d1-resume-an-interrupted-recording"


def test_a_renewed_hold_with_no_work_branch_makes_one(shared, capsys):
    alice = clone(shared, "alice")
    hold.claim(alice, "D1", session="alice-d1", person="@alice")
    git(shared, "branch", "-D", "d1-resume-an-interrupted-recording")
    git(alice, "branch", "-D", "d1-resume-an-interrupted-recording")
    capsys.readouterr()
    assert hold.claim(alice, "D1", session="alice-d1", person="@alice") == 0
    out = capsys.readouterr().out
    assert "D1 renewed" in out and "work branch d1-resume-an-interrupted-recording created" in out, out
    assert git(shared, "rev-parse", "--verify", "--quiet", "d1-resume-an-interrupted-recording")


def test_a_renewed_hold_whose_work_is_merged_makes_no_branch_again(shared, capsys):
    alice = clone(shared, "alice")
    hold.claim(alice, "D1", session="alice-d1", person="@alice")
    git(alice, "commit", "-q", "--allow-empty", "-m", "Resume an interrupted recording (D1) (#5)")
    git(alice, "push", "-q", "origin", "main")
    git(shared, "branch", "-D", "d1-resume-an-interrupted-recording")
    git(alice, "branch", "-D", "d1-resume-an-interrupted-recording")
    capsys.readouterr()
    assert hold.claim(alice, "D1", session="alice-d1", person="@alice") == 0
    assert "work branch" not in capsys.readouterr().out
    assert not git(shared, "for-each-ref", "refs/heads/d1-*")


def test_a_renewed_hold_with_its_work_branch_says_nothing_of_it(shared, capsys):
    alice = clone(shared, "alice")
    hold.claim(alice, "D1", session="alice-d1", person="@alice")
    capsys.readouterr()
    assert hold.claim(alice, "D1", session="alice-d1", person="@alice") == 0
    out = capsys.readouterr().out
    assert "D1 renewed" in out and "work branch" not in out and "work continues" not in out, out


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


def test_a_delivery_of_a_held_ready_deliverable_is_never_told_to_edit_the_cycle_file(shared):
    # D183: the cycle file is under `docs/`, which a human approves on approval agent; the hold
    # already says the work started, so a delivery is asked nothing of the plan's file.
    from napkinstack import pull_request

    alice = clone(shared, "alice")
    today = datetime.date(2026, 10, 20)  # inside the cycle, whatever the day the test runs
    said: list[str] = []
    pull_request.check_cycle(alice, "Deliverable: D1", set(), today, lambda *a: None, said.append)
    assert len(said) == 1 and "nstack claim D1" in said[0] and "never in a delivery's" in said[0], said
    assert hold.claim(alice, "D1", session="alice-d1", person="@alice") == 0
    said.clear()
    pull_request.check_cycle(alice, "Deliverable: D1", set(), today, lambda *a: None, said.append)
    assert said == []


def finished(shared: Path, alice: Path, state: str = "accepted") -> None:
    """D1's state moved on main, as a delivery's acceptance does."""
    path = alice / "docs/project/cycles/03-the-window.md"
    git(alice, "switch", "-q", "main")
    git(alice, "pull", "-q", "origin", "main")
    path.write_text(path.read_text(encoding="utf-8").replace("state: ready", f"state: {state}"), encoding="utf-8")
    git(alice, "add", "-A")
    git(alice, "commit", "-q", "-m", "D1 accepted")
    git(alice, "push", "-q", "origin", "main")


def test_plan_names_the_empty_start_branch_its_done_deliverable_left(shared, capsys):
    """#316: never the pull request's, refused by git branch -d, and named by nothing."""
    alice = clone(shared, "alice")
    hold.claim(alice, "D1", session="s", person="@alice")
    branch = "d1-resume-an-interrupted-recording"
    finished(shared, alice)
    capsys.readouterr()
    hold.show(alice)
    out = capsys.readouterr().out
    assert "Empty start branches left" in out
    assert f"{branch}  (local, remote)" in out and "nstack plan --prune removes them" in out
    assert "--delete" not in out, "never a bare delete, which would take work pushed since (#516)"


def test_plan_says_nothing_of_a_start_branch_still_in_use(shared, capsys):
    alice = clone(shared, "alice")
    hold.claim(alice, "D1", session="s", person="@alice")
    capsys.readouterr()
    hold.show(alice)
    assert "Empty start branches left" not in capsys.readouterr().out


def test_plan_says_nothing_of_a_branch_holding_work(shared, capsys):
    """Work is never called left over, however done the deliverable."""
    alice = clone(shared, "alice")
    hold.claim(alice, "D1", session="s", person="@alice")
    branch = "d1-resume-an-interrupted-recording"
    git(alice, "switch", "-q", branch)
    (alice / "work.txt").write_text("work", encoding="utf-8")
    git(alice, "add", "-A")
    git(alice, "commit", "-q", "-m", "work")
    git(alice, "push", "-q", "origin", branch)
    finished(shared, alice)
    capsys.readouterr()
    hold.show(alice)
    assert "Empty start branches left" not in capsys.readouterr().out


def test_plan_says_nothing_of_a_branch_empty_but_not_a_claim_s(shared, capsys):
    alice = clone(shared, "alice")
    hold.claim(alice, "D1", session="s", person="@alice")
    finished(shared, alice)
    git(alice, "commit", "-q", "--allow-empty", "-m", "a note someone keeps")
    git(alice, "push", "-q", "origin", "HEAD:refs/heads/d1-kept")
    git(alice, "reset", "-q", "--hard", "HEAD~1")
    capsys.readouterr()
    hold.show(alice)
    assert "d1-kept" not in capsys.readouterr().out


def land(alice: Path, message: str) -> None:
    git(alice, "switch", "-q", "main")
    git(alice, "pull", "-q", "origin", "main")
    git(alice, "commit", "-q", "--allow-empty", "-m", message)
    git(alice, "push", "-q", "origin", "main")


@pytest.mark.parametrize("title", ["resume: nothing lost (D1) (#7)", "D1a — resume, first part (#7)",
                                   "resume, second part (D1b) (#7)"])
def test_plan_names_it_once_the_work_landed_though_the_state_is_unmoved(shared, capsys, title):
    """A delivery never edits the cycle file (D183): at the kernel's Close the state is still ready.
    A part's title lands as deliver counts it (D300, #560)."""
    alice = clone(shared, "alice")
    hold.claim(alice, "D1", session="s", person="@alice")
    land(alice, title)
    capsys.readouterr()
    hold.show(alice)
    assert "d1-resume-an-interrupted-recording" in capsys.readouterr().out.split("Empty start branches left")[-1]


def test_a_mere_mention_is_no_landing(shared, capsys):
    """A live hold's branch is never named because a commit spoke of it."""
    alice = clone(shared, "alice")
    hold.claim(alice, "D1", session="s", person="@alice")
    land(alice, "docs: note that the export waits for D1")
    capsys.readouterr()
    hold.show(alice)
    assert "Empty start branches left" not in capsys.readouterr().out


def test_a_deliverable_line_is_a_landing(shared, capsys):
    alice = clone(shared, "alice")
    hold.claim(alice, "D1", session="s", person="@alice")
    land(alice, "Resume a recording\n\nDeliverable: D1")
    capsys.readouterr()
    hold.show(alice)
    assert "Empty start branches left" in capsys.readouterr().out


def test_a_malformed_cycle_is_no_traceback_in_plan(shared, capsys):
    alice = clone(shared, "alice")
    (alice / "docs/project/cycles/02-old.md").write_text("---\nstatus: closed\ndeliverables: 5\n---\n", encoding="utf-8")
    assert hold.show(alice) == 0


def test_a_checkout_behind_never_names_a_branch_held_in_a_cycle_it_knows(shared, capsys):
    """D7 is closed-cycle here; another clone moved it to the current cycle and holds it."""
    alice = clone(shared, "alice")
    old = alice / "docs/project/cycles/02-old.md"
    old.write_text("---\nstatus: completed\ndeliverables:\n  - id: D7\n    title: x\n---\n", encoding="utf-8")
    git(alice, "commit", "-q", "--allow-empty", "-m", "Start D7 — x")
    git(alice, "push", "-q", "origin", "HEAD:refs/heads/d7-x")
    git(alice, "reset", "-q", "--hard", "HEAD~1")
    tip = hold._event(alice, None, "D7", "claim", "@bob", "bob-d7")
    git(alice, "push", "-q", "origin", f"{tip}:refs/heads/nstack/hold/03-the-window/D7")
    capsys.readouterr()
    hold.show(alice)
    assert "d7-x" not in capsys.readouterr().out


def test_another_deliverable_s_number_is_no_landing(shared, capsys):
    alice = clone(shared, "alice")
    hold.claim(alice, "D1", session="s", person="@alice")
    land(alice, "something else (D10) (#7)")
    capsys.readouterr()
    hold.show(alice)
    assert "Empty start branches left" not in capsys.readouterr().out


def test_a_deliverable_this_checkout_does_not_know_is_left_alone(shared, capsys):
    """Another's claim, on a cycle file newer than this checkout: never told to delete it."""
    alice = clone(shared, "alice")
    git(alice, "commit", "-q", "--allow-empty", "-m", "Start D3 — new one")
    git(alice, "push", "-q", "origin", "HEAD:refs/heads/d3-new-one")
    git(alice, "reset", "-q", "--hard", "HEAD~1")
    capsys.readouterr()
    hold.show(alice)
    assert "d3-new-one" not in capsys.readouterr().out


def test_two_commits_on_a_start_branch_are_not_named(shared, capsys):
    alice = clone(shared, "alice")
    hold.claim(alice, "D1", session="s", person="@alice")
    branch = "d1-resume-an-interrupted-recording"
    git(alice, "switch", "-q", branch)
    git(alice, "commit", "-q", "--allow-empty", "-m", "second")
    git(alice, "push", "-q", "origin", branch)
    finished(shared, alice)
    capsys.readouterr()
    hold.show(alice)
    assert "Empty start branches left" not in capsys.readouterr().out


def test_without_a_remote_only_the_local_delete_is_named(shared, capsys):
    alone = clone(shared, "alone")
    git(alone, "remote", "remove", "origin")
    hold.claim(alone, "D1", session="s", person="@alice")
    git(alone, "branch", "--list")
    path = alone / "docs/project/cycles/03-the-window.md"
    path.write_text(path.read_text(encoding="utf-8").replace("state: ready", "state: accepted"), encoding="utf-8")
    git(alone, "add", "-A")
    git(alone, "commit", "-q", "-m", "accepted")
    capsys.readouterr()
    hold.show(alone)
    out = capsys.readouterr().out
    assert "d1-resume-an-interrupted-recording  (local)" in out and "remote" not in out.split("Empty start")[-1]


def landed(alice: Path, message: str, date: str | None = None) -> None:
    """A commit on main, as a merged pull request leaves one."""
    git(alice, "switch", "-q", "main")
    git(alice, "commit", "-q", "--allow-empty", "-m", message,
        env={"GIT_COMMITTER_DATE": date} if date else None)
    git(alice, "push", "-q", "origin", "main")


def merged_said(root: Path, capsys) -> str:
    capsys.readouterr()
    hold.show(root)
    out = capsys.readouterr().out
    return out.split("Merged, not recorded")[1].split("\n\n")[0] if "Merged, not recorded" in out else ""


def test_plan_tells_a_deliverable_merged_from_one_waiting_and_counts_its_pull_requests(shared, capsys):
    """#328: `0 of N accepted` says nothing of what is merged. Several pull requests may deliver one
    deliverable, so a merge is said, and moves no state."""
    alice = clone(shared, "alice")
    landed(alice, "capture: first part (D1)")
    landed(alice, "Second part\n\nDeliverable: D1\n")
    said = merged_said(alice, capsys)
    assert "D1  2 merges" in said
    path = alice / "docs/project/cycles/03-the-window.md"
    assert "state: ready" in path.read_text(encoding="utf-8")


def test_plan_says_no_merge_of_an_accepted_deliverable_a_mention_or_another_cycle(shared, capsys):
    alice = clone(shared, "alice")
    landed(alice, "A note that speaks of D1 and of D12")
    assert merged_said(alice, capsys) == ""
    landed(alice, "capture: an earlier cycle's work (D1)", date="2020-01-01T12:00:00+00:00")
    assert merged_said(alice, capsys) == "", "an id carried over: its older merge is not this cycle's"
    landed(alice, "capture: the work (D1)")
    assert "D1  1 merge" in merged_said(alice, capsys)
    finished(shared, alice)
    assert merged_said(alice, capsys) == ""


def merged_lines(root: Path, capsys) -> list[str]:
    return [line.strip() for line in merged_said(root, capsys).splitlines()[1:]]


@pytest.mark.parametrize("message", ["x (D1)", "x (D1) (#12)", "x (D1, second of three)", "x (D2, D1)",
                                     "D1 — x", "Second part\n\nDeliverable: D1\n", "Second\n\ndeliverable: d1\n",
                                     "D1a — x", "x (D1b)", "x (D1c) (#12)", "x (D2, D1b)"])
def test_each_form_a_delivery_takes_is_counted(shared, capsys, message):
    alice = clone(shared, "alice")
    landed(alice, message)
    assert "D1  1 merge" in merged_lines(alice, capsys)


@pytest.mark.parametrize("message", ["x (D12)", "Second\n\nDeliverable: D12\n", "D12 — x", "Start D1 — x",
                                     "x\n\nD1 — capture\n", "x\n\n* part (D1)\n", "See (D1) for this", "x (see D1)",
                                     "D1ab — x", "D1A — x", "D12a — x", "x (D1ab)"])
def test_another_id_or_a_mere_mention_counts_nothing(shared, capsys, message):
    alice = clone(shared, "alice")
    landed(alice, message)
    assert merged_lines(alice, capsys) == []


def test_a_revert_takes_its_merge_off(shared, capsys):
    alice = clone(shared, "alice")
    landed(alice, "x (D1) (#5)")
    landed(alice, "y (D1) (#6)")
    landed(alice, 'Revert "x (D1) (#5)"')
    assert merged_lines(alice, capsys) == ["D1  1 merge"]
    landed(alice, 'Revert "y (D1) (#6)"')
    assert merged_lines(alice, capsys) == []


def test_an_old_dated_commit_hides_no_earlier_merge(shared, capsys):
    """`git log --since` stops at the first older commit: a wrong clock lost every merge before it."""
    alice = clone(shared, "alice")
    landed(alice, "one (D1)")
    landed(alice, "old (D2)", date="2020-01-01T12:00:00+00:00")
    landed(alice, "later")
    assert merged_lines(alice, capsys) == ["D1  1 merge"]


@pytest.mark.parametrize("zone", ["UTC", "America/Los_Angeles", "Asia/Tokyo"])
def test_the_first_day_of_a_cycle_is_the_same_on_every_machine(shared, capsys, monkeypatch, zone):
    alice = clone(shared, "alice")
    landed(alice, "before (D1)", date="2026-10-16T23:59:59+00:00")
    landed(alice, "on (D1)", date="2026-10-17T00:00:00+00:00")
    monkeypatch.setenv("TZ", zone)
    assert merged_lines(alice, capsys) == ["D1  1 merge"]


def test_without_a_remote_the_local_default_branch_is_read(shared, capsys):
    alice = clone(shared, "alice")
    landed(alice, "x (D1)")
    git(alice, "remote", "remove", "origin")
    assert merged_lines(alice, capsys) == ["D1  1 merge"]


def test_an_id_no_pattern_could_read_breaks_nothing(shared, capsys):
    alice = clone(shared, "alice")
    path = alice / "docs/project/cycles/03-the-window.md"
    path.write_text(path.read_text(encoding="utf-8").replace("id: D1\n", 'id: "D(1"\n'), encoding="utf-8")
    git(alice, "add", "-A")
    landed(alice, "x")
    assert merged_lines(alice, capsys) == []


def test_a_merge_commit_counts_once_not_each_commit_it_brought(shared, capsys):
    alice = clone(shared, "alice")
    git(alice, "switch", "-q", "-c", "side")
    for part in ("one", "two", "three"):
        git(alice, "commit", "-q", "--allow-empty", "-m", f"{part} (D1)")
    git(alice, "switch", "-q", "main")
    git(alice, "merge", "-q", "--no-ff", "-m", "Merge the work (D1)", "side")
    git(alice, "push", "-q", "origin", "main")
    assert merged_lines(alice, capsys) == ["D1  1 merge"]


# PDR-0022: an agent records a delivery, a rule checks it, the state is computed.

def two_criteria(root: Path) -> None:
    path = root / "docs/project/cycles/03-the-window.md"
    path.write_text(path.read_text(encoding="utf-8").replace(
        '      - "Given a cut, when it resumes, then nothing is lost"\n',
        '      - "Given a cut, when it resumes, then nothing is lost"\n      - "Given a second cut, then it resumes"\n'),
        encoding="utf-8")
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "two criteria")
    git(root, "push", "-q", "origin", "main")


def plain_plan(root: Path, capsys) -> str:
    capsys.readouterr()
    hold.show(root)
    return capsys.readouterr().out


def test_a_merged_deliverable_is_recorded_with_no_pull_request_and_is_no_longer_held(shared, capsys):
    alice = clone(shared, "alice")
    hold.claim(alice, "D1", session="s", person="@alice")
    landed(alice, "the work (D1) (#7)")
    head = git(alice, "rev-parse", "origin/main").strip()
    assert hold.deliver(alice, "D1", ["#7"], session="s", person="@alice") == 0
    assert git(alice, "rev-parse", "origin/main").strip() == head, "nothing lands on the default branch"
    out = plain_plan(alice, capsys)
    assert "D1  delivered by @alice" in out and "#7" in out and "held by" not in out
    assert "0 held" in out and "Merged, not recorded" not in out
    assert hold.delivered(alice, *hold.plan.accepted_cycle(alice)) == {"D1"}


def test_each_criterion_answers_or_none_is_recorded(shared, capsys):
    alice = clone(shared, "alice")
    two_criteria(alice)
    landed(alice, "one (D1) (#7)")
    landed(alice, "two (D1) (#8)")
    assert hold.deliver(alice, "D1", ["1=#7"], person="@alice") == 1
    out = capsys.readouterr().out
    assert "FAIL [deliver]" in out and "criterion 2" in out and "Given a second cut" in out and "Action:" in out
    assert hold.deliver(alice, "D1", ["1=#7", "2=#8"], person="@alice") == 0
    assert hold.read(alice, "03-the-window", "D1").criteria == ["1 #7", "2 #8"]


def test_a_criterion_held_by_several_merges_keeps_each_one(shared, capsys):
    """#346: a criterion held by three pull requests, given three times, kept the last and dropped the
    others, saying nothing. Each is kept, in the order given, once."""
    alice = clone(shared, "alice")
    two_criteria(alice)
    for number in (7, 8, 9):
        landed(alice, f"part {number} (D1) (#{number})")
    assert hold.deliver(alice, "D1", ["1=#7", "1=#8", "1=#7", "#9"], person="@alice") == 0
    assert hold.read(alice, "03-the-window", "D1").criteria == ["1 #7 #8 #9", "2 #9"]
    assert hold.delivered(alice, *hold.plan.accepted_cycle(alice)) == {"D1"}
    landed(alice, 'Revert "part 7 (D1) (#7)" (#10)')  # the first answer of a criterion, not its last
    hold.refresh(alice)
    assert hold.delivered(alice, *hold.plan.accepted_cycle(alice)) == set()


def test_each_answer_of_a_criterion_is_checked_not_only_its_last(shared, capsys):
    alice = clone(shared, "alice")
    landed(alice, "the work (D1) (#7)")
    landed(alice, "another's work (D2) (#99)")
    assert hold.deliver(alice, "D1", ["1=#99", "1=#7"], person="@alice") == 1
    assert "#99 is no merge of D1" in capsys.readouterr().out


@pytest.mark.parametrize("given, said", [(["#99"], "#99"), (["nothing"], "nothing"), (["3=#7"], "criterion 3"),
                                         (["#7\nHold-Event: release"], "#7")])
def test_an_answer_that_names_no_merge_of_the_deliverable_is_refused(shared, capsys, given, said):
    alice = clone(shared, "alice")
    landed(alice, "the work (D1) (#7)")
    landed(alice, "another's work (D2) (#99)")
    assert hold.deliver(alice, "D1", given, person="@alice") == 1
    assert said in capsys.readouterr().out
    assert not hold.read(alice, "03-the-window", "D1").recorded


def test_a_commit_answers_where_the_forge_gave_no_number_and_the_acceptance_issue_too(shared, capsys):
    alice = clone(shared, "alice")
    landed(alice, "the work (D1)")
    sha = git(alice, "rev-parse", "HEAD").strip()
    assert hold.deliver(alice, "D1", ["#55"], person="@alice") == 1
    path = alice / "docs/project/cycles/03-the-window.md"
    path.write_text(path.read_text(encoding="utf-8") + "\n### D1\n\nIts acceptance issue: #55\n", encoding="utf-8")
    git(alice, "add", "-A")
    git(alice, "commit", "-q", "-m", "names the issue")
    git(alice, "push", "-q", "origin", "main")
    assert hold.deliver(alice, "D1", [f"1={sha[:9]}"], person="@alice", session="a") == 0
    assert hold.release(alice, "D1", person="@alice") == 0
    assert hold.deliver(alice, "D1", ["#55"], person="@alice") == 0


def test_no_merge_is_refused_however_the_agent_words_it(shared, capsys):
    alice = clone(shared, "alice")
    hold.claim(alice, "D1", session="s", person="@alice")
    landed(alice, "a note speaking of D1")
    assert hold.deliver(alice, "D1", ["#7"], session="s", person="@alice") == 1
    out = capsys.readouterr().out
    assert "no merge" in out and "Action:" in out
    # #347: a spike whose product is a record has no merge to record; the refusal names its door.
    assert "A spike whose product is a record" in out and "module: null" in out and "framing.md" in out
    assert hold.read(alice, "03-the-window", "D1").held


def test_every_merge_reverted_refuses_the_record_and_reopens_one_made(shared, capsys):
    alice = clone(shared, "alice")
    hold.claim(alice, "D1", session="s", person="@alice")
    landed(alice, "the work (D1) (#7)")
    assert hold.deliver(alice, "D1", ["#7"], session="s", person="@alice") == 0
    landed(alice, 'Revert "the work (D1) (#7)"')
    hold.refresh(alice)
    assert hold.delivered(alice, *hold.plan.accepted_cycle(alice)) == set()
    assert "D1  free — delivered, then a merge it names was reverted: back in work" in plain_plan(alice, capsys)
    assert hold.deliver(alice, "D1", ["#7"], session="s", person="@alice") == 1
    assert hold.claim(alice, "D1", session="s2", person="@bob") == 0, "anyone takes it back"


def test_only_the_person_or_the_decider_records_a_hold_not_stale(shared, capsys):
    alice, bob = clone(shared, "alice"), clone(shared, "bob")
    hold.claim(alice, "D1", session="s", person="@alice")
    landed(alice, "the work (D1) (#7)")
    git(bob, "pull", "-q", "origin", "main")
    assert hold.deliver(bob, "D1", ["#7"], session="b", person="@bob") == 1
    assert "held by @alice" in capsys.readouterr().out
    assert hold.deliver(bob, "D1", ["#7"], session="another", person="@alice") == 0, "a person's new session"


def test_a_delivered_deliverable_is_never_stale_and_cannot_be_taken(shared, capsys, monkeypatch):
    alice, bob = clone(shared, "alice"), clone(shared, "bob")
    hold.claim(alice, "D1", session="s", person="@alice")
    landed(alice, "the work (D1) (#7)")
    hold.deliver(alice, "D1", ["#7"], session="s", person="@alice")
    now = time.time()
    monkeypatch.setattr(hold.time, "time", lambda: now + 30 * hold.DAY)
    git(bob, "pull", "-q", "origin", "main")
    out = plain_plan(bob, capsys)
    assert "STALE" not in out and "D1  delivered" in out
    for take_over in (False, True):
        assert hold.claim(bob, "D1", session="b", person="@bob", take_over=take_over) == 1
        assert "already delivered" in capsys.readouterr().out


def test_recording_again_changes_nothing_and_a_wrong_record_is_withdrawn(shared, capsys):
    alice = clone(shared, "alice")
    landed(alice, "the work (D1) (#7)")
    assert hold.deliver(alice, "D1", ["#7"], person="@alice") == 0
    tip = hold.read(alice, "03-the-window", "D1").tip
    assert hold.deliver(alice, "D1", ["#7"], person="@alice") == 0
    assert hold.read(alice, "03-the-window", "D1").tip == tip
    assert hold.release(alice, "D1", person="@alice") == 0
    assert hold.delivered(alice, *hold.plan.accepted_cycle(alice)) == set()


def test_a_shallow_clone_never_reads_as_back_in_work_and_refuses_to_record(shared, capsys, monkeypatch):
    alice = clone(shared, "alice")
    landed(alice, "the work (D1) (#7)")
    hold.deliver(alice, "D1", ["#7"], person="@alice")
    monkeypatch.setattr(hold, "_read_merges", lambda *a: hold.Merges())
    monkeypatch.setattr(hold, "_shallow", lambda root: True)
    assert hold.delivered(alice, *hold.plan.accepted_cycle(alice)) == {"D1"}
    assert "merges not read" in plain_plan(alice, capsys)
    bob = clone(shared, "bob")
    assert hold.release(alice, "D1", person="@alice") == 0
    git(bob, "fetch", "-q")
    assert hold.deliver(bob, "D1", ["#7"], person="@bob") == 1
    assert "unshallow" in capsys.readouterr().out


def test_a_closure_writes_the_states_from_the_records_and_nothing_else(shared, capsys):
    alice = clone(shared, "alice")
    landed(alice, "the work (D1) (#7)")
    hold.deliver(alice, "D1", ["#7"], person="@alice")
    path = alice / "docs/project/cycles/03-the-window.md"
    before = path.read_text(encoding="utf-8")
    assert hold.write_states(alice) == 0
    assert path.read_text(encoding="utf-8") == before.replace("state: ready", "state: accepted", 1)
    assert "D1" in capsys.readouterr().out
    assert "state: proposed" in path.read_text(encoding="utf-8")
    assert hold.write_states(alice) == 0, "nothing left to write is no failure"


def test_the_stale_hold_of_merged_work_says_to_record_it(shared, capsys, monkeypatch):
    alice = clone(shared, "alice")
    hold.claim(alice, "D1", session="s", person="@alice")
    landed(alice, "the work (D1) (#7)")
    now = time.time()
    monkeypatch.setattr(hold.time, "time", lambda: now + 30 * hold.DAY)
    assert "nstack deliver D1" in plain_plan(alice, capsys).split("Merged, not recorded")[0]


# What the independent verifier broke in the first version of PDR-0022's record.

@pytest.mark.parametrize("revert", [
    'Revert "x (D1) (#5)"', 'Revert "x (D1) (#5)" (#6)', 'Merge pull request #6 from o/revert-5-x\n\nRevert "x (D1) (#5)"'])
def test_a_revert_in_each_shape_a_forge_writes_takes_the_record_down(shared, capsys, revert):
    alice = clone(shared, "alice")
    landed(alice, "x (D1) (#5)")
    assert hold.deliver(alice, "D1", ["#5"], person="@alice") == 0
    landed(alice, revert)
    hold.refresh(alice)
    assert hold.delivered(alice, *hold.plan.accepted_cycle(alice)) == set()


def test_a_git_revert_of_a_merge_named_only_in_its_body_is_read_by_its_sha(shared, capsys):
    alice = clone(shared, "alice")
    landed(alice, "feature (#5)\n\nDeliverable: D1\n")
    sha = git(alice, "rev-parse", "HEAD").strip()
    assert hold.deliver(alice, "D1", ["#5"], person="@alice") == 0
    landed(alice, f'Revert "feature (#5)"\n\nThis reverts commit {sha}.\n')
    hold.refresh(alice)
    assert hold.delivered(alice, *hold.plan.accepted_cycle(alice)) == set()


def test_the_forge_s_merge_commit_is_a_merge_of_what_its_title_names(shared, capsys):
    alice = clone(shared, "alice")
    landed(alice, "Merge pull request #5 from o/d1-x\n\nx (D1)\n")
    assert hold.deliver(alice, "D1", ["#5"], person="@alice") == 0


def test_a_reapplied_merge_brings_the_record_back_and_a_later_one_does_not_excuse_a_cited_revert(shared, capsys):
    alice = clone(shared, "alice")
    landed(alice, "x (D1) (#5)")
    hold.deliver(alice, "D1", ["#5"], person="@alice")
    landed(alice, 'Revert "x (D1) (#5)"')
    landed(alice, "typo (D1) (#9)")
    hold.refresh(alice)
    assert hold.delivered(alice, *hold.plan.accepted_cycle(alice)) == set(), "the record cites what is gone"
    landed(alice, 'Reapply "x (D1) (#5)"')
    hold.refresh(alice)
    assert hold.delivered(alice, *hold.plan.accepted_cycle(alice)) == {"D1"}


def test_a_revert_of_an_earlier_cycle_s_commit_touches_nothing_of_this_one(shared, capsys):
    alice = clone(shared, "alice")
    landed(alice, "old (D1) (#3)", date="2020-01-01T12:00:00+00:00")
    landed(alice, "x (D1) (#5)")
    hold.deliver(alice, "D1", ["#5"], person="@alice")
    landed(alice, 'Revert "old (D1) (#3)"')
    hold.refresh(alice)
    assert hold.delivered(alice, *hold.plan.accepted_cycle(alice)) == {"D1"}


def test_a_start_moved_or_removed_never_reads_as_a_revert(shared, capsys):
    alice = clone(shared, "alice")
    landed(alice, "x (D1) (#5)")
    hold.deliver(alice, "D1", ["#5"], person="@alice")
    path = alice / "docs/project/cycles/03-the-window.md"
    path.write_text(path.read_text(encoding="utf-8").replace("start: 2026-10-17", "start: 2099-01-01"), encoding="utf-8")
    assert "reverted" not in plain_plan(alice, capsys)
    assert hold.claim(alice, "D1", session="b", person="@bob") == 1


def test_a_record_never_goes_stale_for_a_stranger_s_unclaim_and_its_recorder_withdraws_it(shared, capsys, monkeypatch):
    alice = clone(shared, "alice")
    hold.claim(alice, "D1", session="a", person="@alice")
    hold.release(alice, "D1", session="a", person="@alice")
    landed(alice, "x (D1) (#5)")
    hold.deliver(alice, "D1", ["#5"], session="b", person="@bob")
    assert "delivered by @bob" in plain_plan(alice, capsys)
    now = time.time()
    monkeypatch.setattr(hold.time, "time", lambda: now + 30 * hold.DAY)
    assert hold.release(alice, "D1", person="@mallory") == 1
    assert "only who recorded it" in capsys.readouterr().out
    assert hold.release(alice, "D1", session="c", person="@bob") == 0


def test_a_session_on_the_hold_records_under_another_name_a_stranger_does_not(shared, capsys):
    alice = clone(shared, "alice")
    hold.claim(alice, "D1", session="sa", person="@alice")
    landed(alice, "x (D1) (#5)")
    assert hold.deliver(alice, "D1", ["#5"], session="other", person="@bot") == 1
    assert hold.deliver(alice, "D1", ["#5"], session="SA", person="@bot") == 0


def test_the_decider_records_a_hold_not_theirs(shared, capsys):
    alice = clone(shared, "alice")
    hold.claim(alice, "D1", session="s", person="@alice")
    landed(alice, "x (D1) (#5)")
    decider = hold.plan.read_front_matter(alice / hold.plan.CHARTER)[0]["decider"]
    assert hold.deliver(alice, "D1", ["#5"], person=decider) == 0


@pytest.mark.parametrize("where", ["criterion", "elsewhere"])
def test_an_issue_named_by_accident_answers_nothing(shared, capsys, where):
    alice = clone(shared, "alice")
    landed(alice, "x (D1) (#5)")
    path = alice / "docs/project/cycles/03-the-window.md"
    text = path.read_text(encoding="utf-8")
    text = text.replace("then nothing is lost", "then nothing is lost, see #7") if where == "criterion" else text + "\nSee #7.\n"
    path.write_text(text, encoding="utf-8")
    assert hold.deliver(alice, "D1", ["#7"], person="@alice") == 1


def test_a_commit_of_another_deliverable_answers_nothing(shared, capsys):
    alice = clone(shared, "alice")
    landed(alice, "mine (D1) (#5)")
    landed(alice, "theirs (D2) (#6)")
    assert hold.deliver(alice, "D1", [git(alice, "rev-parse", "HEAD").strip()[:9]], person="@alice") == 1


def test_a_hand_pushed_record_with_no_criterion_is_no_record(shared, capsys):
    found = hold.Hold(event="deliver", person="@nobody")
    assert not found.recorded and not found.held


@pytest.mark.parametrize("cycle, wrong", [
    ("  - id: D1\n    title: 'x'\n    state: 'ready'\n    module: capture\n    acceptance:\n      - \"a\"\n  - title: y\n    id: D12\n    state: proposed\n", None),
    ("  - id: D1\n    title: 'x'\n    notes: |\n      state: draft here\n    state: ready\n    acceptance:\n      - \"a\"\n", None),
    ("  - id: D1\n    title: 'x'\n    acceptance:\n      - \"a\n        state: open\"\n    state: ready\n", None),
])
def test_writing_the_states_changes_the_state_alone(shared, capsys, cycle, wrong):
    alice = clone(shared, "alice")
    path = alice / "docs/project/cycles/03-the-window.md"
    text = re.sub(r"deliverables:\n.*?---", lambda m: "deliverables:\n" + cycle + "---", path.read_text(encoding="utf-8"), count=1, flags=re.S)
    path.write_text(text, encoding="utf-8")
    git(alice, "add", "-A")
    git(alice, "commit", "-q", "-m", "form")
    landed(alice, "x (D1) (#5)")
    assert hold.deliver(alice, "D1", ["#5"], person="@alice") == 0
    assert hold.write_states(alice) == 0
    after = hold.plan.read_front_matter(path)[0]["deliverables"]
    before = yaml.safe_load(cycle)
    before[0]["state"] = "accepted"
    assert after == before


def test_writing_the_states_keeps_crlf_and_a_shallow_clone_refuses(shared, capsys, monkeypatch):
    alice = clone(shared, "alice")
    landed(alice, "x (D1) (#5)")
    hold.deliver(alice, "D1", ["#5"], person="@alice")
    path = alice / "docs/project/cycles/03-the-window.md"
    monkeypatch.setattr(hold, "_shallow", lambda root: True)
    assert hold.write_states(alice) == 1
    monkeypatch.undo()
    before = path.read_bytes()
    assert hold.write_states(alice) == 0
    assert path.read_bytes() == before.replace(b"state: ready", b"state: accepted", 1)


@pytest.mark.parametrize("ident, states", [(None, False), ("D1", True)])
def test_the_command_takes_a_deliverable_or_the_states(shared, capsys, ident, states):
    assert hold.deliver_command(clone(shared, "alice"), ident, [], None, None, states) == 1
    assert "FAIL [deliver]" in capsys.readouterr().out


def test_the_plan_counts_delivered_and_the_project_view_too(shared, capsys):
    alice = clone(shared, "alice")
    landed(alice, "x (D1) (#5)")
    hold.deliver(alice, "D1", ["#5"], person="@alice")
    assert "0 of 2 accepted · 1 delivered" in hold.plan.progress(alice)
    capsys.readouterr()
    hold.plan.show(alice)
    assert "1 delivered" in capsys.readouterr().out


def test_the_command_line_refreshes_before_it_counts_and_fetches_once(shared, capsys, monkeypatch):
    alice, bob = clone(shared, "alice"), clone(shared, "bob")
    landed(alice, "x (D1) (#5)")
    hold.deliver(alice, "D1", ["#5"], person="@alice")
    calls = []
    real = hold.fetch
    monkeypatch.setattr(hold, "fetch", lambda *a, **k: calls.append(1) or real(*a, **k))
    from napkinstack import cli
    capsys.readouterr()
    assert cli.main(["plan", "--root", str(bob)]) in (0, None, 1)
    out = capsys.readouterr().out
    assert "1 delivered" in out and len(calls) == 1


def test_k3_says_a_delivered_deliverable_is_delivered_and_not_to_claim_it(shared, capsys):
    from napkinstack import pull_request

    alice = clone(shared, "alice")
    landed(alice, "x (D1) (#5)")
    hold.deliver(alice, "D1", ["#5"], person="@alice")
    warned, failed = [], []
    pull_request.check_cycle(alice, "Deliverable: D1", set(), datetime.date(2026, 10, 20),
                             lambda code, text: failed.append(code), warned.append)
    assert not failed and len(warned) == 1 and "on record as delivered" in warned[0] and "nstack claim" not in warned[0]


def test_a_reworded_revert_is_read_by_the_commit_it_names(shared, capsys):
    alice = clone(shared, "alice")
    landed(alice, "x (D1) (#5)")
    sha = git(alice, "rev-parse", "HEAD").strip()
    hold.deliver(alice, "D1", ["#5"], person="@alice")
    landed(alice, f"undo the window work\n\nThis reverts commit {sha}.\n")
    hold.refresh(alice)
    assert hold.delivered(alice, *hold.plan.accepted_cycle(alice)) == set()


def test_a_revert_of_a_reworded_title_is_read_by_its_pull_request(shared, capsys):
    alice = clone(shared, "alice")
    landed(alice, "x (D1) (#5)")
    hold.deliver(alice, "D1", ["#5"], person="@alice")
    landed(alice, 'Revert "another title (#5)"')
    hold.refresh(alice)
    assert hold.delivered(alice, *hold.plan.accepted_cycle(alice)) == set()


def test_writing_the_states_refuses_when_more_than_the_state_would_change(shared, capsys, monkeypatch):
    alice = clone(shared, "alice")
    landed(alice, "x (D1) (#5)")
    hold.deliver(alice, "D1", ["#5"], person="@alice")
    path = alice / "docs/project/cycles/03-the-window.md"
    before = path.read_text(encoding="utf-8")
    monkeypatch.setattr(hold, "_with_state", lambda front, ident: front.replace("Export", "Changed"))
    assert hold.write_states(alice) == 1
    assert path.read_text(encoding="utf-8") == before


def test_a_cycle_not_accepted_reads_no_record(shared, monkeypatch):
    alice = clone(shared, "alice")
    monkeypatch.setattr(hold, "delivered", lambda root, path, data: {"D1"})
    assert hold.plan.delivered_in(alice, alice, {"status": "closed"}) == set()
    assert hold.plan.delivered_in(alice, alice, {"status": "accepted"}) == {"D1"}


# The second round: a commit is both what it reverts and what it delivers.

def merges_of(root: Path) -> hold.Merges:
    hold.refresh(root)
    hold._fetched.pop(root, None)
    return hold._read_merges(root, hold.remote(root), hold.plan.accepted_cycle(root)[1])


@pytest.mark.parametrize("body", ["* wip\n\n* Revert \"wip\"\n\nThis reverts commit deadbeefdeadbeef.\n",
                                  "This reverts commit 1234567890ab\n"])
def test_a_squash_listing_a_revert_of_its_own_branch_is_still_a_delivery(shared, body):
    alice = clone(shared, "alice")
    landed(alice, f"D1 — feature (#5)\n\n{body}")
    assert hold.deliver(alice, "D1", ["#5"], person="@alice") == 0


def test_a_delivery_of_one_reverting_another_does_both(shared):
    alice = clone(shared, "alice")
    landed(alice, "x (D1) (#5)")
    sha = git(alice, "rev-parse", "HEAD").strip()
    landed(alice, f"D2 — y (#6)\n\nAlso:\nThis reverts commit {sha}.\n")
    found = merges_of(alice)
    assert "D1" not in found.live and [one[1] for one in found.live["D2"]] == ["6"]


@pytest.mark.parametrize("revert", ['Revert "D1 — x" (#6)\n\nReverts o/r#5', 'Merge pull request #6 from o/revert-5-d1-x\n\nRevert "D1 — x"',
                                    'Revert "Merge pull request #5 from o/d1-x"'])
def test_the_forge_s_revert_titled_without_the_number_is_read(shared, revert):
    alice = clone(shared, "alice")
    landed(alice, "D1 — x (#5)")
    assert hold.deliver(alice, "D1", ["#5"], person="@alice") == 0
    landed(alice, revert)
    hold.refresh(alice)
    assert hold.delivered(alice, *hold.plan.accepted_cycle(alice)) == set()


def test_a_revert_of_several_takes_each_off(shared):
    alice = clone(shared, "alice")
    landed(alice, "a (D1) (#5)")
    first = git(alice, "rev-parse", "HEAD").strip()
    landed(alice, "b (D2) (#6)")
    second = git(alice, "rev-parse", "HEAD").strip()
    landed(alice, f'Revert "both" (#7)\n\nThis reverts commit {first}.\n\nThis reverts commit {second}.\n')
    found = merges_of(alice)
    assert not found.live and set(found.reverted) == {"D1", "D2"}


@pytest.mark.parametrize("again", ['Reapply "D1 — x (#5)" (#7)', 'Revert "Revert "D1 — x (#5)"" (#7)',
                                   'Revert "Revert "D1 — x (#5)" (#6)" (#7)'])
def test_a_reapply_brings_the_merge_back_and_is_citable(shared, again):
    alice = clone(shared, "alice")
    landed(alice, "D1 — x (#5)")
    landed(alice, 'Revert "D1 — x (#5)" (#6)')
    landed(alice, again)
    found = merges_of(alice)
    assert [one[1] for one in found.live["D1"]] == ["5"] and "D1" not in found.reverted
    assert {one[1] for one in found.citable["D1"]} == {"5", "7"}
    assert hold.deliver(alice, "D1", ["#7"], person="@alice") == 0


def test_a_reapply_never_reverted_is_a_merge(shared):
    alice = clone(shared, "alice")
    landed(alice, 'Reapply "D1 — x (#5)" (#9)')
    assert [one[1] for one in merges_of(alice).live["D1"]] == ["9"]


@pytest.mark.parametrize("body", ["", "Deliverable: D1\n", "x (D1)\n\nDeliverable: D1\n"])
def test_a_forge_merge_commit_is_read_whatever_its_body_holds(shared, body):
    alice = clone(shared, "alice")
    landed(alice, f"Merge pull request #5 from o/d1-x\n\n{body}")
    assert merges_of(alice).live.get("D1", []) == ([] if not body else merges_of(alice).live["D1"])
    if body:
        assert merges_of(alice).live["D1"][0][1] == "5"


def test_k3_reads_the_records_on_ci_s_fresh_clone(shared, capsys):
    from napkinstack import pull_request

    alice = clone(shared, "alice")
    landed(alice, "x (D1) (#5)")
    hold.deliver(alice, "D1", ["#5"], person="@alice")
    warned = []
    pull_request.check_cycle(clone(shared, "fresh"), "Deliverable: D1", set(), datetime.date(2026, 10, 20),
                             lambda code, text: None, warned.append)
    assert len(warned) == 1 and "on record as delivered" in warned[0]


def carried(alice: Path, line: str = "") -> None:
    landed(alice, "x (D1) (#3)", date="2020-01-01T12:00:00+00:00")
    if line:
        path = alice / "docs/project/cycles/03-the-window.md"
        path.write_text(path.read_text(encoding="utf-8") + line, encoding="utf-8")


def test_a_deliverable_carried_over_is_recorded_only_by_the_issue_the_cycle_names_for_it(shared, capsys):
    alice = clone(shared, "alice")
    carried(alice, "\n| D1, D2 on a Mac | The colleague | [#449](https://example.invalid/449) |\n")
    assert hold.deliver(alice, "D1", ["#3"], person="@alice") == 1, "an earlier cycle's merge answers nothing"
    assert hold.deliver(alice, "D1", ["#449"], person="@alice") == 0
    assert hold.delivered(alice, *hold.plan.accepted_cycle(alice)) == {"D1"}


def test_an_id_with_no_merge_ever_is_still_refused_and_the_table_of_another_is_no_answer(shared, capsys):
    alice = clone(shared, "alice")
    path = alice / "docs/project/cycles/03-the-window.md"
    path.write_text(path.read_text(encoding="utf-8") + "\n| D2 | #449 |\n", encoding="utf-8")
    assert hold.deliver(alice, "D1", ["#449"], person="@alice") == 1
    carried(alice)
    assert hold.deliver(alice, "D1", ["#449"], person="@alice") == 1


def test_a_subheading_stays_in_its_deliverable_s_section(shared, capsys):
    alice = clone(shared, "alice")
    landed(alice, "x (D1) (#5)")
    path = alice / "docs/project/cycles/03-the-window.md"
    path.write_text(path.read_text(encoding="utf-8") + "\n### D1\n\n#### Criteria\n\nIssue #81\n\n### D2\n\nIssue #82\n", encoding="utf-8")
    assert hold.deliver(alice, "D1", ["#82"], person="@alice") == 1
    assert hold.deliver(alice, "D1", ["#81"], person="@alice") == 0


# The third round: a chain of reverts, and what was merged before the cycle.

def chained(alice: Path, *messages: str) -> hold.Merges:
    for message in messages:
        landed(alice, message)
    return merges_of(alice)


@pytest.mark.parametrize("chain", [
    ['D1 — x', 'Revert "D1 — x"', 'Reapply "D1 — x"', 'Revert "Reapply "D1 — x""'],
    ['D1 — x', 'Revert "D1 — x"', 'Reapply "D1 — x"', 'Revert "D1 — x"'],
    ['D1 — x (#3)', 'Revert "D1 — x (#3)" (#4)', 'Revert "Revert "D1 — x (#3)" (#4)" (#5)',
     'Revert "Revert "Revert "D1 — x (#3)" (#4)" (#5)" (#6)'],
    ['D1 — x', 'Revert "D1 — x"', 'Revert "Revert "D1 — x""', 'Revert "Revert "Revert "D1 — x"""'],
])
def test_a_chain_of_reverts_ending_gone_is_gone(shared, chain):
    found = chained(clone(shared, "alice"), *chain)
    assert "D1" not in found.live and "D1" in found.reverted


def test_a_reapply_counts_one_change(shared):
    found = chained(clone(shared, "alice"), "D1 — x (#3)", 'Revert "D1 — x (#3)"', 'Reapply "D1 — x (#3)"')
    assert len(found.live["D1"]) == 1


def test_a_reapply_with_only_a_deliverable_line_is_a_merge(shared):
    found = chained(clone(shared, "alice"), 'Reapply "add thing"\n\nDeliverable: D1\n')
    assert "D1" in found.live


@pytest.mark.parametrize("date", ["2020-01-02T12:00:00+00:00", None])
def test_an_earlier_merge_reverted_is_no_carried_delivery(shared, capsys, date):
    alice = clone(shared, "alice")
    carried(alice, "\n| D1 | #99 |\n")
    landed(alice, 'Revert "x (D1) (#3)" (#4)', date=date)
    assert hold.deliver(alice, "D1", ["#99"], person="@alice") == 1


def test_a_small_fix_reverted_leaves_a_carried_record_standing(shared):
    alice = clone(shared, "alice")
    carried(alice, "\n| D1 | #99 |\n")
    assert hold.deliver(alice, "D1", ["#99"], person="@alice") == 0
    landed(alice, "D1 — small fix (#7)")
    landed(alice, 'Revert "D1 — small fix (#7)"')
    hold.refresh(alice)
    assert hold.delivered(alice, *hold.plan.accepted_cycle(alice)) == {"D1"}


def test_a_revert_naming_an_earlier_commit_stops_there_even_if_the_words_match(shared):
    alice = clone(shared, "alice")
    landed(alice, "D1 — x", date="2020-01-01T12:00:00+00:00")
    old = git(alice, "rev-parse", "HEAD").strip()
    landed(alice, "D1 — x (#7)")
    found = chained(alice, f'Revert "D1 — x"\n\nThis reverts commit {old}.\n')
    assert "D1" in found.live


@pytest.mark.parametrize("line", ["D1 of the earlier cycle was closed by #99; unrelated.", "See D1-legacy-notes and #99.", "| D1-old | #99 |"])
def test_a_sentence_mentioning_the_id_answers_nothing_for_a_carried_deliverable(shared, capsys, line):
    alice = clone(shared, "alice")
    carried(alice, f"\n{line}\n")
    assert hold.deliver(alice, "D1", ["#99"], person="@alice") == 1


def test_a_commit_git_cannot_decode_breaks_nothing(shared):
    alice = clone(shared, "alice")
    tree = git(alice, "rev-parse", "HEAD^{tree}").strip()
    parent = git(alice, "rev-parse", "HEAD").strip()
    raw = (f"tree {tree}\nparent {parent}\nauthor t <t@e.invalid> 1800000000 +0000\ncommitter t <t@e.invalid> 1800000000 +0000\n\n").encode() + b"caf\xe9 (D1) (#3)\n"
    sha = subprocess.run(["git", "hash-object", "-t", "commit", "-w", "--stdin"], cwd=alice, input=raw, capture_output=True, check=True).stdout.decode().strip()
    git(alice, "push", "-q", "origin", f"{sha}:refs/heads/main")
    assert "D1" in merges_of(alice).live


# D216 (#385): work no cycle plans — a bug found in review, a flaky test — is held the same way.
ISSUE_REF = "nstack/hold/issues/issue-14"


def test_an_issue_is_held_once_and_the_second_taker_is_told_who(shared, capsys):
    alice = clone(shared, "alice")
    assert hold.claim(alice, "#14", session="alice-14", person="@alice") == 0
    out = capsys.readouterr().out
    assert "issue-14 taken: held by @alice, session alice-14" in out, out
    assert git(shared, "log", "-1", "--format=%(trailers:key=Hold-Event,valueonly)", ISSUE_REF) == "claim"
    assert "issue-14-work" in git(shared, "branch", "--list", "issue-14-*")
    assert hold.claim(clone(shared, "bob"), "#14", session="bob-14", person="@bob") == 1
    out = capsys.readouterr().out
    assert "FAIL [hold] issue-14 is held by @alice, session alice-14" in out and "take another issue" in out, out


def test_an_issue_is_held_in_a_project_with_no_cycle(tmp_path, capsys):
    seed = tmp_path / "seed"
    seed.mkdir()
    (seed / "README.md").write_text("p\n", encoding="utf-8")
    git(seed, "init", "-q", "--initial-branch=main")
    git(seed, "add", "-A")
    git(seed, "commit", "-q", "-m", "first")
    remote = tmp_path / "remote.git"
    git(tmp_path, "clone", "-q", "--bare", str(seed), str(remote))
    assert hold.claim(clone(remote, "alice"), "#7", person="@alice") == 0, capsys.readouterr().out


def test_an_issue_s_holder_gives_it_back_and_plan_lists_the_issues_held(shared, capsys):
    alice = clone(shared, "alice")
    hold.claim(alice, "#14", session="alice-14", person="@alice")
    hold.claim(alice, "#9", session="alice-9", person="@alice")
    assert hold.release(alice, "#9", session="alice-9", person="@alice") == 0
    capsys.readouterr()
    bob = clone(shared, "bob")
    hold.refresh(bob)
    hold.show(bob)
    out = capsys.readouterr().out
    assert "Issues held (1):\n  #14  held by @alice, session alice-14" in out, out
    assert "#9" not in out


def test_an_issue_s_hold_renewed_with_no_work_branch_left_starts_one(tmp_path, capsys):
    """Unframed: no cycle to read merges from — the renew guard of a deliverable never applies."""
    seed = tmp_path / "seed"
    seed.mkdir()
    (seed / "README.md").write_text("p\n", encoding="utf-8")
    git(seed, "init", "-q", "--initial-branch=main")
    git(seed, "add", "-A")
    git(seed, "commit", "-q", "-m", "first")
    remote = tmp_path / "remote.git"
    git(tmp_path, "clone", "-q", "--bare", str(seed), str(remote))
    alice = clone(remote, "alice")
    assert hold.claim(alice, "7", session="a", person="@alice") == 0
    git(alice, "push", "-q", "origin", "--delete", "issue-7-work")
    git(alice, "branch", "-D", "issue-7-work")
    assert hold.claim(alice, "issue-7", session="a", person="@alice") == 0, capsys.readouterr().out
    assert "issue-7-work" in git(remote, "branch", "--list", "issue-7-*")


def test_an_issue_s_comment_never_publishes_an_address(shared, monkeypatch):
    posted = []
    monkeypatch.setattr(hold, "_forge", lambda root, name: ("api", "acme/p", "t"))
    monkeypatch.setattr(hold, "_call", lambda forge, method, path, body=None: posted.append(body) or {})
    hold._show_issue(shared, "origin", "14", "Alice Doe <alice@example.org>", "s-1")
    assert posted == [{"body": "Held by Alice Doe, session s-1 (nstack claim '#14'): work on branches issue-14-…."}]


# --- A push the clone's own hook refuses is no hold that moved (D236, #427) ---
# Measured downstream on 2026-11-18: the default branch red, the pre-push hook refused every push,
# and `unclaim` said twice "hold moved meanwhile" while the hold was the same here and on origin.

def test_a_release_refused_by_a_pre_push_hook_says_the_hook_s_reason_not_a_moved_hold(shared, capsys):
    """Reproducer of #427: a push the clone's own pre-push hook refuses is said as a hold that moved."""
    alice = clone(shared, "alice")
    assert hold.claim(alice, "D1", session="alice-d1", person="@alice") == 0
    hook = alice / ".git/hooks/pre-push"
    hook.write_text("#!/bin/sh\necho 'fitness: B1 the default branch is red'\necho 'and on stderr' >&2\nexit 1\n",
                    encoding="utf-8")
    hook.chmod(0o755)
    capsys.readouterr()
    assert hold.release(alice, "D1", session="alice-d1", person="@alice") == 1
    out = capsys.readouterr().out
    assert remote_events(shared) == ["claim"]
    assert "moved meanwhile" not in out and "run nstack plan" not in out, out
    assert "B1 the default branch is red" in out and "and on stderr" in out, out
    assert "FAIL [hold] D1: the push was refused" in out, out


def test_a_hold_that_really_moved_keeps_its_message(shared, monkeypatch, capsys):
    """Its neighbour: the remote's hold moved between this clone's read and its push."""
    alice = clone(shared, "alice")
    assert hold.claim(alice, "D1", session="agent-one", person="@alice") == 0
    assert hold.claim(clone(shared, "other"), "D1", session="agent-two", person="@alice", take_over=True) == 0
    stale = hold.fetch  # alice's read is the one before the take-over: the race, held still
    monkeypatch.setattr(hold, "fetch", lambda root, again=False: stale(root) if again else hold.remote(root))
    capsys.readouterr()
    assert hold.release(alice, "D1", session="agent-one", person="@alice") == 1
    out = capsys.readouterr().out
    assert "FAIL [hold] D1's hold moved meanwhile" in out and "run nstack plan, then again" in out, out
    assert remote_events(shared) == ["take-over", "claim"]


def test_a_delivery_refused_by_a_pre_push_hook_says_the_hook_s_reason(shared, capsys):
    alice = clone(shared, "alice")
    assert hold.claim(alice, "D1", session="alice-d1", person="@alice") == 0
    landed(alice, "the work (D1) (#7)")
    hook = alice / ".git/hooks/pre-push"
    hook.write_text("#!/bin/sh\necho 'the hook says no'\nexit 1\n", encoding="utf-8")
    hook.chmod(0o755)
    capsys.readouterr()
    assert hold.deliver(alice, "D1", ["#7"], session="alice-d1", person="@alice") == 1
    out = capsys.readouterr().out
    assert "moved meanwhile" not in out and "FAIL [deliver] D1: the push was refused" in out, out
    assert "the hook says no" in out, out


def test_a_claim_refused_by_a_pre_push_hook_says_the_hook_s_reason(shared, capsys):
    alice = clone(shared, "alice")
    hook = alice / ".git/hooks/pre-push"
    hook.write_text("#!/bin/sh\necho 'the hook says no'\nexit 1\n", encoding="utf-8")
    hook.chmod(0o755)
    assert hold.claim(alice, "D1", session="alice-d1", person="@alice") == 1
    out = capsys.readouterr().out
    assert "FAIL [hold] D1: the push was refused, and the hold did not move" in out and "the hook says no" in out
    assert "taken first" not in out and git(shared, "for-each-ref", "refs/heads/nstack/hold").strip() == ""


def test_a_remote_unreadable_after_a_refusal_is_not_said_unmoved(shared, monkeypatch, capsys):
    alice = clone(shared, "alice")
    assert hold.claim(alice, "D1", session="alice-d1", person="@alice") == 0
    (alice / ".git/hooks/pre-push").write_text("#!/bin/sh\necho 'no route to host' >&2\nexit 1\n", encoding="utf-8")
    (alice / ".git/hooks/pre-push").chmod(0o755)
    first = hold.fetch

    def gone(root, again=False):
        if again:
            raise hold.Unreachable("no answer")
        return first(root)
    monkeypatch.setattr(hold, "fetch", gone)
    capsys.readouterr()
    assert hold.release(alice, "D1", session="alice-d1", person="@alice") == 1
    out = capsys.readouterr().out
    assert "whether the hold moved is not known" in out and "did not move" not in out, out


def test_an_event_the_remote_took_before_git_failed_is_said_recorded(shared, monkeypatch, capsys):
    """git can fail after the remote took the ref (a connection cut on the answer): the event is on record."""
    alice = clone(shared, "alice")
    assert hold.claim(alice, "D1", session="alice-d1", person="@alice") == 0
    pushed = hold._record
    monkeypatch.setattr(hold, "_record", lambda *args: (pushed(*args), (False, "connection reset"))[1])
    capsys.readouterr()
    assert hold.release(alice, "D1", session="alice-d1", person="@alice") == 0
    out = capsys.readouterr().out
    assert "D1 released by @alice" in out and "moved meanwhile" not in out, out
    assert remote_events(shared) == ["release", "claim"]


def test_a_clone_of_a_working_clone_never_says_nobody_holds_a_held_deliverable(shared, capsys):
    # A verifier's `git clone --shared` of a working clone: its remote is that clone, whose holds
    # are what it fetched from the forge (refs/remotes, nstack's mirror), never its own branches.
    # A fetch of the remote's branches brings no hold there: not read, and said — never "nobody".
    from napkinstack import pull_request

    alice = clone(shared, "alice")
    assert hold.claim(alice, "D1", session="alice-d1", person="@alice") == 0
    git(alice, "fetch", "-q", "origin")  # the hold, as git's own fetch keeps it: refs/remotes/origin
    verifier = shared.parent / "verifier"
    git(shared.parent, "clone", "-q", "--shared", str(alice), str(verifier))
    git(verifier, "checkout", "-q", "--detach")
    today = datetime.date(2026, 10, 20)
    warned: list[str] = []
    pull_request.check_cycle(verifier, "Deliverable: D1", set(), today, lambda *a: None, warned.append)
    assert not any("nobody holds it" in line for line in warned), warned
    pull_request.check_hold(verifier, "Deliverable: D1", set(), (set(), set(), []), lambda *a: None,
                            warned.append)
    said = "\n".join(warned)
    assert "[K5] the holds are not read: who holds D1" in said and "clone" in said and "not the shared remote" in said, said
    git(verifier, "remote", "set-url", "origin", (alice).as_uri())  # file://, a local path too
    warned.clear()
    pull_request.check_cycle(verifier, "Deliverable: D1", set(), today, lambda *a: None, warned.append)
    assert not any("nobody holds it" in line for line in warned), warned
    capsys.readouterr()
    assert hold.claim(verifier, "#7", session="v", person="@v") == 1  # never a hold pushed into the clone
    out = capsys.readouterr().out
    assert out.count("Action:") == 1 and "point origin at the shared remote" in out, out


def _ready_d2(folder: Path) -> None:
    cycle = folder / "docs/project/cycles/03-the-window.md"
    cycle.write_text(cycle.read_text(encoding="utf-8").replace("state: proposed", "state: ready"), encoding="utf-8")
    git(folder, "commit", "-q", "-am", "D2 ready")


def test_a_claim_reads_the_cycle_on_the_remote_s_default_branch(shared, capsys):
    """#505 (D273): a checkout behind the default branch still takes what the default branch made
    ready, and a cycle changed only in the checkout gives nothing to take — the hold lives on the
    remote, and so does the cycle it is taken from."""
    alice = clone(shared, "alice")  # before D2 is made ready on the default branch
    planner = clone(shared, "planner")
    _ready_d2(planner)
    git(planner, "push", "-q", "origin", "main")
    assert hold.claim(alice, "D2", session="alice-d2", person="@alice") == 0, capsys.readouterr().out
    bob = clone(shared, "bob")
    git(bob, "reset", "-q", "--hard", "HEAD~1")
    git(planner, "reset", "-q", "--hard", "HEAD~1")
    git(planner, "push", "-q", "--force", "origin", "main")  # the default branch: D2 proposed again
    _ready_d2(bob)  # this checkout alone says ready
    capsys.readouterr()
    assert hold.claim(bob, "D2", session="bob-d2", person="@bob") == 1
    out = capsys.readouterr().out
    assert "origin's default branch" in out and "differs from the default branch" in out, out


def test_the_remote_s_cycles_are_read_as_plan_reads_them(shared, capsys):
    """D273's verifier: a template is no cycle, and a closed cycle holding a date no calendar holds
    is a file that cannot be read — never a traceback."""
    planner = clone(shared, "planner")
    folder = planner / "docs/project/cycles"
    (folder / "_template.md").write_text("---\nstatus: accepted\ndeliverables: []\n---\n", encoding="utf-8")
    (folder / "01-before.md").write_text("---\nstatus: closed\nstart: 2026-02-30\n---\n", encoding="utf-8")
    git(planner, "add", "-A")
    git(planner, "commit", "-q", "-m", "a template and an old cycle")
    git(planner, "push", "-q", "origin", "main")
    assert hold.claim(clone(shared, "alice"), "D1", session="alice-d1", person="@alice") == 0, capsys.readouterr().out


def test_a_claim_never_pushes_a_hold_into_a_working_clone(shared, capsys):
    """#505 (D273): a `git clone --shared` of a working clone that mirrors no hold has that clone for
    its remote. A hold pushed there is seen by nobody else: refused, and said — a bare repository
    stays a shared remote."""
    alice = clone(shared, "alice")
    verifier = shared.parent / "verifier"
    git(shared.parent, "clone", "-q", "--shared", str(alice), str(verifier))
    capsys.readouterr()
    assert hold.claim(verifier, "D1", session="v", person="@v") == 1
    out = capsys.readouterr().out
    assert "not the shared remote" in out and "git remote set-url origin" in out, out
    assert not git(alice, "for-each-ref", "refs/heads/nstack"), "no hold pushed into the working clone"


@pytest.mark.parametrize("bare", [True, False], ids=["a bare repository with a remote", "a working tree nobody cloned"])
def test_a_local_hub_stays_a_shared_remote(shared, capsys, bare):
    """D273's verifier: with no forge, a team's hub may be a local repository — bare, even cloned from
    elsewhere, or the decider's own working tree, which is nobody's clone. Its holds are everyone's."""
    hub = shared.parent / "hub"
    git(shared.parent, "clone", "-q", *(["--bare"] if bare else []), str(shared), str(hub))
    if not bare:
        git(hub, "remote", "remove", "origin")
    agent = shared.parent / "agent"
    git(shared.parent, "clone", "-q", str(hub), str(agent))
    assert hold.claim(agent, "D1", session="a-d1", person="@alice") == 0, capsys.readouterr().out
    assert git(hub, "for-each-ref", "--format=%(refname)", "refs/heads/nstack") == f"refs/heads/{REF}"


def test_a_branch_tracking_a_local_branch_reads_the_holds_of_origin(shared):
    from napkinstack import attest

    alice = clone(shared, "alice")
    git(alice, "checkout", "-q", "-b", "feat", "--track", "main")
    assert attest._remote(alice) == "origin"


def test_where_nobody_holds_a_ready_deliverable_k3_names_the_remote_it_read(shared):
    from napkinstack import pull_request

    alice = clone(shared, "alice")
    warned: list[str] = []
    pull_request.check_cycle(alice, "Deliverable: D1", set(), datetime.date(2026, 10, 20), lambda *a: None,
                             warned.append)
    assert len(warned) == 1 and "nobody holds it on origin" in warned[0], warned


def test_the_holding_session_releases_without_naming_its_person_again(shared, capsys):
    # The session that holds a deliverable gives it back: the person is the hold's, never git's
    # user — on an agent's workstation, git's user is the agent's own identity.
    alice = clone(shared, "alice")
    assert hold.claim(alice, "D1", session="alice-d1", person="@alice") == 0
    capsys.readouterr()
    assert hold.release(alice, "D1", session="alice-d1") == 0, capsys.readouterr().out
    assert "released by @alice" in capsys.readouterr().out
    assert remote_events(shared) == ["release", "claim"]


def test_a_session_that_does_not_hold_it_is_told_to_name_its_person(shared, capsys):
    alice = clone(shared, "alice")
    assert hold.claim(alice, "D1", session="alice-d1", person="@alice") == 0
    capsys.readouterr()
    assert hold.release(alice, "D1", session="other") == 1
    said = capsys.readouterr().out
    assert "No --person was given: git's user, test <test@example.invalid>, was read" in said and "--person @alice" in said, said
    assert remote_events(shared) == ["claim"]


def test_the_holding_session_is_matched_whatever_its_case_and_spaces(shared, capsys):
    alice = clone(shared, "alice")
    assert hold.claim(alice, "D1", session="alice-d1", person="@alice") == 0
    assert hold.release(alice, "D1", session=" ALICE-D1 ") == 0
    assert remote_events(shared) == ["release", "claim"]


def test_another_person_s_session_never_releases_for_the_holder(shared, capsys):
    assert hold.claim(clone(shared, "alice"), "D1", session="alice-d1", person="@alice") == 0
    bob = clone(shared, "bob")
    assert hold.claim(bob, "#7", session="bob-7", person="@bob") == 0
    assert hold.release(bob, "D1", session="bob-7") == 1
    assert remote_events(shared) == ["claim"]


START = "d1-resume-an-interrupted-recording"


def test_deliver_removes_the_empty_start_branch_its_claim_left(shared, capsys):
    """#516 (D279): an agent may not delete a remote branch; the start branch claim pushed is the
    framework's own — one empty commit —, so recording the delivery removes it, here and on the remote."""
    alice = clone(shared, "alice")
    hold.claim(alice, "D1", session="s", person="@alice")
    git(alice, "switch", "-q", "main")
    landed(alice, "the work (D1) (#7)")
    capsys.readouterr()
    assert hold.deliver(alice, "D1", ["#7"], session="s", person="@alice") == 0
    out = capsys.readouterr().out
    assert f"Empty start branch {START} removed" in out, out
    assert not git(shared, "for-each-ref", f"refs/heads/{START}")
    assert not git(alice, "for-each-ref", f"refs/heads/{START}")


def test_deliver_never_removes_a_start_branch_someone_worked_on(shared, capsys):
    alice = clone(shared, "alice")
    hold.claim(alice, "D1", session="s", person="@alice")
    git(alice, "switch", "-q", START)
    git(alice, "commit", "-q", "--allow-empty", "-m", "work goes on here")
    git(alice, "push", "-q", "origin", START)
    git(alice, "switch", "-q", "main")
    landed(alice, "the work (D1) (#7)")
    assert hold.deliver(alice, "D1", ["#7"], session="s", person="@alice") == 0
    assert git(shared, "for-each-ref", f"refs/heads/{START}"), "a branch with work stays"


def test_plan_prune_removes_what_plan_names_and_nothing_else(shared, capsys):
    """#516 (D279): a deliverable that moved on without a delivery — deferred, or the cycle's — never meets
    deliver; the decider removes every empty start `nstack plan` names in one command."""
    alice = clone(shared, "alice")
    hold.claim(alice, "D1", session="s", person="@alice")
    finished(shared, alice, "deferred")
    capsys.readouterr()
    assert hold.prune_starts(alice) == 0
    out = capsys.readouterr().out
    assert f"Empty start branch {START} removed" in out, out
    assert not git(shared, "for-each-ref", f"refs/heads/{START}")
    assert hold.prune_starts(alice) == 0
    assert "No empty start branch" in capsys.readouterr().out


def _ready_and_claim_d2(shared: Path, alice: Path) -> str:
    cycle = alice / "docs/project/cycles/03-the-window.md"
    git(alice, "switch", "-q", "main")
    cycle.write_text(cycle.read_text(encoding="utf-8").replace("state: proposed", "state: ready"), encoding="utf-8")
    git(alice, "commit", "-q", "-am", "D2 ready")
    git(alice, "push", "-q", "origin", "main")
    hold.claim(alice, "D2", session="s2", person="@alice")
    git(alice, "switch", "-q", "main")
    return next(line.split()[-1] for line in git(alice, "branch", "--list", "d2-*").splitlines())


def test_deliver_removes_its_own_start_branch_and_no_other_deliverable_s(shared, capsys):
    """D279's verifier: D2's empty start, D2 deferred, is plan --prune's — never D1's delivery's."""
    alice = clone(shared, "alice")
    hold.claim(alice, "D1", session="s", person="@alice")
    d2 = _ready_and_claim_d2(shared, alice)
    cycle = alice / "docs/project/cycles/03-the-window.md"
    text = cycle.read_text(encoding="utf-8")
    cycle.write_text(text.replace('    title: "Export"\n    module: export\n    state: ready',
                                  '    title: "Export"\n    module: export\n    state: deferred'), encoding="utf-8")
    git(alice, "commit", "-q", "-am", "D2 deferred")
    git(alice, "push", "-q", "origin", "main")
    landed(alice, "the work (D1) (#7)")
    assert hold.deliver(alice, "D1", ["#7"], session="s", person="@alice") == 0
    assert not git(shared, "for-each-ref", f"refs/heads/{START}")
    assert git(shared, "for-each-ref", f"refs/heads/{d2}"), "another deliverable's start is not this delivery's"


def test_a_start_branch_pushed_to_since_it_was_read_is_kept_and_no_delete_is_offered(shared, capsys):
    """D279's verifier: the lease keeps a branch someone pushed work to after the fetch, and nothing then
    offers the bare delete that would take it."""
    alice = clone(shared, "alice")
    hold.claim(alice, "D1", session="s", person="@alice")
    git(alice, "switch", "-q", "main")
    landed(alice, "the work (D1) (#7)")
    hold.fetch(alice)
    chosen = hold._empty_start_branches(alice, "origin", hold.plan.accepted_cycle(alice)[1]["deliverables"])
    assert START in chosen
    bob = clone(shared, "bob")
    git(bob, "switch", "-q", START)
    (bob / "f.txt").write_text("work\n", encoding="utf-8")
    git(bob, "add", "f.txt")
    git(bob, "commit", "-q", "-m", "work")
    git(bob, "push", "-q", "origin", START)
    removed, kept = hold._remove_starts(alice, "origin", chosen)
    assert git(shared, "for-each-ref", f"refs/heads/{START}"), "bob's work stays"
    assert any("pushed to since" in line for line in removed) and not any("--delete" in line for line in kept)


def test_a_start_commit_amended_with_work_is_never_removed(shared, capsys):
    alice = clone(shared, "alice")
    hold.claim(alice, "D1", session="s", person="@alice")
    git(alice, "switch", "-q", START)
    (alice / "f.txt").write_text("work\n", encoding="utf-8")
    git(alice, "add", "f.txt")
    git(alice, "commit", "-q", "--amend", "--no-edit")
    git(alice, "push", "-q", "-f", "origin", START)
    git(alice, "switch", "-q", "main")
    landed(alice, "the work (D1) (#7)")
    assert hold.deliver(alice, "D1", ["#7"], session="s", person="@alice") == 0
    assert git(shared, "for-each-ref", f"refs/heads/{START}") and git(alice, "for-each-ref", f"refs/heads/{START}")
