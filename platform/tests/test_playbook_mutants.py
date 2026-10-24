"""D148: a verifier's mutants are bounded, restored and counted (#243).

A verifier showing a test pins a behaviour mutates the code by hand; a mutant that loops ran its
test binary for five hours and held a merge, the source still mutated. The verification playbook
says how mutants are run.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PLAYBOOK = ROOT / "skeleton/.nstack/playbooks/verification.md"


def text() -> str:
    return re.sub(r"\s+", " ", PLAYBOOK.read_text(encoding="utf-8"))


def test_the_field_s_tool_comes_before_a_hand_loop():
    for tool in ("cargo-mutants", "mutmut", "Stryker", "PIT"):
        assert tool in text(), f"verification.md: {tool} not named"


def test_each_hand_made_mutant_runs_under_a_time_limit_and_a_timeout_is_killed():
    assert "timeout" in text() and "a timeout counts as killed" in text()


def test_the_source_is_restored_on_every_exit():
    assert "trap" in text() and "on every exit" in text()


def test_the_report_counts_killed_survived_and_timed_out():
    assert "killed, survived, timed out" in text()
