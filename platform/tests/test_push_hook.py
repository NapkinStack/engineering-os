"""D232 (#420): the pre-push hook ran whatever `nstack` the workstation had. A project updated to
v0.30.0 declared `evidence.sealed`; every agent still on 0.29.0 had its push refused with
"M12 unknown key 'sealed'" — an older engine judging a newer project, refusing what the project's
version defines and able to pass what it refuses. Each agent put a shim on PATH to get through.

The hook now judges only with an engine at the project's version or ahead of it; one behind is
refused before any check, naming both versions and the command that installs the right one. The
hook is a project file: it holds for a workstation whose engine predates this fix.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "skeleton" / ".pre-commit-config.yaml"


def _entry() -> str:
    for repo in yaml.safe_load(CONFIG.read_text(encoding="utf-8"))["repos"]:
        for hook in repo["hooks"]:
            if hook["id"] == "nstack-fitness":
                return hook["entry"]
    raise AssertionError("no nstack-fitness hook")


def _push(tmp_path: Path, engine: str | None, commit: str, branch: str = "refs/heads/d1-work") \
        -> tuple[subprocess.CompletedProcess, list[str]]:
    """The hook's entry run as pre-commit runs it, in a project recording `commit`, with an
    `nstack` that answers `--version` as `engine` and logs every check it is asked for."""
    bin_ = tmp_path / "bin"
    bin_.mkdir()
    if engine is not None:
        (bin_ / "nstack").write_text(f"""#!/bin/sh
if [ "$1" = --version ]; then echo "{engine}"; exit 0; fi
echo "$1" >> "{tmp_path}/checks"
""", encoding="utf-8")
        (bin_ / "nstack").chmod(0o755)
    project = tmp_path / "project"
    (project / ".nstack").mkdir(parents=True)
    for script in (ROOT / "skeleton" / ".nstack").glob("*.sh"):
        (project / ".nstack" / script.name).write_bytes(script.read_bytes())
    (project / ".copier-answers.yml").write_text(f"_commit: {commit}\n_src_path: gh:NapkinStack/engineering-os\n",
                                                 encoding="utf-8")
    path = f"{bin_}:/usr/bin:/bin"
    result = subprocess.run(["sh", "-c", _entry()], cwd=project, capture_output=True, text=True,
                            env={**os.environ, "PATH": path, "PRE_COMMIT_REMOTE_BRANCH": branch}, timeout=60)
    checks = (tmp_path / "checks").read_text(encoding="utf-8").split() if (tmp_path / "checks").exists() else []
    return result, checks


@pytest.mark.parametrize("engine, commit", [
    ("nstack 0.29.0", "v0.30.0"),
    ("nstack 0.30.0", "v0.30.1"),                                       # behind by a patch
    ("nstack 0.29.0", "'v0.30.0'"),                                     # quoted, as Copier may write it
    ("nstack 0.29.0", "v0.30.0\r"),                                     # a file saved with CRLF
    ("nstack 0.29.0", "v0.30.0-3-g1a2b3c4"),                            # a pin past v0.30.0: behind it too
])
def test_an_engine_behind_the_project_is_refused_before_judging(tmp_path, engine, commit):
    result, checks = _push(tmp_path, engine, commit)
    said = result.stdout + result.stderr
    assert result.returncode == 1, said
    assert checks == [], "an engine behind the project judged it"
    assert engine in said and f"the project is on {commit.strip(chr(39)).strip()}." in said, said
    assert "Action: bash .nstack/install-engine.sh" in said, said


@pytest.mark.parametrize("engine, commit", [
    ("nstack 0.30.0", "v0.30.0"),                                       # level
    ("nstack 0.31.0", "v0.30.0"),                                       # ahead: an update starts there
    ("nstack 0.30.10", "v0.30.9"),                                      # compared as numbers, not text
    ("nstack 0.31.0", "v0.30.5"),                                       # a higher minor, a lower patch
    ("nstack 1.0.0", "v0.30.0"),                                        # a higher major
    ("nstack 0.31.0 — UNPUBLISHED: a local checkout at v0.30.0-8-gbc5eda3", "v0.31.0"),
    ("nstack 0.30.0", "v0.30.0-3-g1a2b3c4"),                            # at a pin's base: every run says the pin
])
def test_an_engine_level_with_the_project_or_ahead_judges(tmp_path, engine, commit):
    result, checks = _push(tmp_path, engine, commit)
    assert result.returncode == 0, result.stdout + result.stderr
    assert checks == ["manifests", "boundaries", "plan", "hygiene"], checks


def test_a_failed_check_still_refuses_the_push(tmp_path):
    result, _ = _push(tmp_path, "nstack 0.30.0", "v0.30.0")
    assert result.returncode == 0
    fails = tmp_path / "fails"
    fails.mkdir()
    (fails / "bin").mkdir()
    (fails / "bin" / "nstack").write_text('#!/bin/sh\n[ "$1" = --version ] && echo "nstack 0.30.0" && exit 0\n'
                                          '[ "$1" = plan ] && exit 1\nexit 0\n', encoding="utf-8")
    (fails / "bin" / "nstack").chmod(0o755)
    refused = subprocess.run(["sh", "-c", _entry()], cwd=tmp_path / "project", capture_output=True, text=True,
                             env={**os.environ, "PATH": f"{fails / 'bin'}:/usr/bin:/bin"}, timeout=60)
    assert refused.returncode == 1, refused.stdout + refused.stderr


def test_a_project_without_answers_is_judged_without_noise(tmp_path):
    result, checks = _push(tmp_path, "nstack 0.29.0", "v0.30.0")
    assert checks == ["manifests", "boundaries", "plan", "hygiene"] or result.returncode == 1
    (tmp_path / "checks").unlink(missing_ok=True)
    (tmp_path / "project" / ".copier-answers.yml").unlink()
    again = subprocess.run(["sh", "-c", _entry()], cwd=tmp_path / "project", capture_output=True, text=True,
                           env={**os.environ, "PATH": f"{tmp_path / 'bin'}:/usr/bin:/bin"}, timeout=60)
    assert again.returncode == 0 and again.stderr == "", again.stderr


def test_a_workstation_without_nstack_lets_ci_judge(tmp_path):
    result, checks = _push(tmp_path, None, "v0.30.0")
    assert result.returncode == 0 and "CI judges" in result.stdout, result.stdout + result.stderr


@pytest.mark.parametrize("branch, judged", [
    ("refs/heads/nstack/hold/03-the-window/D1", False),   # a hold's event: metadata only (#427)
    ("refs/notes/nstack/checks", False),                  # an attested record
    ("refs/heads/nstack/hold-not-a-hold", True),
    ("refs/heads/main", True),
])
def test_a_hold_s_event_is_pushed_without_judging_the_project(tmp_path, branch, judged):
    """#427: the default branch red, the hook refused every push, a hold's event included —
    `nstack unclaim` could not give a deliverable back. An event moves no file of the project."""
    result, checks = _push(tmp_path, "nstack 0.29.0", "v0.30.0", branch)
    if judged:
        assert result.returncode == 1 and checks == [], result.stdout
    else:
        assert result.returncode == 0 and checks == [], result.stdout + result.stderr
        assert "nstack's own record" in result.stdout



# --- #456: in an agent's session, a commit under another identity is never pushed -----------------

def _repo(tmp_path: Path) -> tuple[Path, dict]:
    """A project pushed once by the agent, its global configuration the agent's own."""
    agent_config = tmp_path / "agent.gitconfig"
    agent_config.write_text("[user]\n\tname = demo-scout[bot]\n\temail = 9001+demo-scout[bot]@users.noreply.github.com\n",
                            encoding="utf-8")
    env = {**os.environ, "GIT_CONFIG_GLOBAL": str(agent_config), "GIT_CONFIG_NOSYSTEM": "1", "NSTACK_AGENT": "scout"}
    for name in ("GIT_AUTHOR_NAME", "GIT_AUTHOR_EMAIL", "GIT_COMMITTER_NAME", "GIT_COMMITTER_EMAIL"):
        env.pop(name, None)
    bare, project = tmp_path / "remote.git", tmp_path / "project"
    subprocess.run(["git", "init", "-q", "--bare", str(bare)], check=True, env=env)
    subprocess.run(["git", "clone", "-q", str(bare), str(project)], check=True, env=env, capture_output=True)
    (project / ".nstack").mkdir()
    for script in (ROOT / "skeleton" / ".nstack").glob("*.sh"):
        (project / ".nstack" / script.name).write_bytes(script.read_bytes())
    subprocess.run(["git", "add", "-A"], cwd=project, check=True, env=env)
    subprocess.run(["git", "commit", "-q", "-m", "base"], cwd=project, check=True, env=env)
    subprocess.run(["git", "push", "-q", "origin", "HEAD:main"], cwd=project, check=True, env=env)
    subprocess.run(["git", "fetch", "-q"], cwd=project, check=True, env=env)
    return project, env


def _hook(project: Path, env: dict) -> subprocess.CompletedProcess:
    return subprocess.run(["sh", ".nstack/fitness-before-push.sh"], cwd=project, capture_output=True, text=True,
                          env={**env, "PATH": "/usr/bin:/bin", "PRE_COMMIT_TO_REF": "HEAD",
                               "PRE_COMMIT_REMOTE_BRANCH": "refs/heads/d1-work"}, timeout=60)


def test_an_agent_never_pushes_a_commit_under_another_identity(tmp_path):
    project, env = _repo(tmp_path)
    subprocess.run(["git", "-c", "user.name=f", "-c", "user.email=f@host.example", "commit", "-q", "--allow-empty",
                    "-m", "made up"], cwd=project, check=True, env=env)
    result = _hook(project, env)
    assert result.returncode == 1, result.stdout
    assert "FAIL [nstack] 1 commit(s) the remote does not hold yet are not agent scout's identity" in result.stdout, \
        result.stdout
    assert "f@host.example" not in result.stdout, "the address it would leak is not printed again"


def test_an_agent_s_own_commits_go_through_and_a_person_s_session_is_not_read(tmp_path):
    project, env = _repo(tmp_path)
    subprocess.run(["git", "commit", "-q", "--allow-empty", "-m", "mine"], cwd=project, check=True, env=env)
    assert "not agent scout's identity" not in _hook(project, env).stdout
    subprocess.run(["git", "-c", "user.name=p", "-c", "user.email=p@example.org", "commit", "-q", "--allow-empty",
                    "-m", "a person's"], cwd=project, check=True, env=env)
    person = {key: value for key, value in env.items() if key != "NSTACK_AGENT"}
    assert "identity" not in _hook(project, person).stdout



def test_a_person_s_name_under_the_agent_s_address_is_refused(tmp_path):
    project, env = _repo(tmp_path)
    subprocess.run(["git", "-c", "user.name=Real Name", "commit", "-q", "--allow-empty", "-m", "named"],
                   cwd=project, check=True, env=env)
    result = _hook(project, env)
    assert result.returncode == 1 and "Real Name" not in result.stdout, result.stdout


def test_a_push_of_several_refs_is_read_whole(tmp_path):
    """pre-commit names the first ref alone: another local branch holding a made-up identity is read too."""
    project, env = _repo(tmp_path)
    subprocess.run(["git", "commit", "-q", "--allow-empty", "-m", "mine"], cwd=project, check=True, env=env)
    subprocess.run(["git", "switch", "-q", "-c", "leaky"], cwd=project, check=True, env=env)
    subprocess.run(["git", "-c", "user.name=f", "-c", "user.email=f@host.example", "commit", "-q", "--allow-empty",
                    "-m", "made up"], cwd=project, check=True, env=env)
    subprocess.run(["git", "switch", "-q", "-"], cwd=project, check=True, env=env)
    assert _hook(project, env).returncode == 1


def test_records_fetched_from_the_remote_are_its_own_never_the_agent_s_to_push(tmp_path):
    """attest fetches the remote's notes beside its own: a person's record there is not pushed by the agent."""
    project, env = _repo(tmp_path)
    person = {**env, "GIT_CONFIG_GLOBAL": "/dev/null"}
    subprocess.run(["git", "-c", "user.name=p", "-c", "user.email=p@example.org", "notes", "--ref=nstack/checks",
                    "add", "-m", "a person's record", "HEAD"], cwd=project, check=True, env=person)
    subprocess.run(["git", "push", "-q", "origin", "refs/notes/nstack/checks"], cwd=project, check=True, env=env)
    subprocess.run(["git", "fetch", "-q", "origin", "+refs/notes/nstack/checks:refs/notes/nstack-remote/checks"],
                   cwd=project, check=True, env=env)
    subprocess.run(["git", "notes", "--ref=nstack/checks", "add", "-f", "-m", "the agent's", "HEAD"],
                   cwd=project, check=True, env=env)
    tip = subprocess.run(["git", "rev-parse", "refs/notes/nstack/checks"], cwd=project, capture_output=True,
                         text=True, check=True, env=env).stdout.strip()
    result = subprocess.run(["sh", ".nstack/fitness-before-push.sh"], cwd=project, capture_output=True, text=True,
                            env={**env, "PATH": "/usr/bin:/bin", "PRE_COMMIT_TO_REF": tip,
                                 "PRE_COMMIT_REMOTE_BRANCH": "refs/notes/nstack/checks"}, timeout=60)
    assert "not agent scout's identity" not in result.stdout, result.stdout


def test_what_claim_fetched_from_the_remote_is_its_own_whatever_origin_main_says(tmp_path):
    """#484: a squash merge the forge committed reached here through claim's own fetch
    (refs/nstack-remote/base), not origin/main: the remote holds it, the agent pushes nothing of it."""
    project, env = _repo(tmp_path)
    forge = {**env, "GIT_COMMITTER_NAME": "GitHub", "GIT_COMMITTER_EMAIL": "noreply@github.com"}
    subprocess.run(["git", "symbolic-ref", "HEAD", "refs/heads/main"], cwd=tmp_path / "remote.git", check=True, env=env)
    other = tmp_path / "other"
    subprocess.run(["git", "clone", "-q", "-b", "main", str(tmp_path / "remote.git"), str(other)], check=True, env=env, capture_output=True)
    subprocess.run(["git", "commit", "-q", "--allow-empty", "-m", "squash merge (#1)"], cwd=other, check=True, env=forge)
    subprocess.run(["git", "push", "-q", "origin", "HEAD:main"], cwd=other, check=True, env=env)
    subprocess.run(["git", "fetch", "-q", "origin", "+HEAD:refs/nstack-remote/base"], cwd=project, check=True, env=env)
    subprocess.run(["git", "switch", "-q", "-c", "issue-7-work", "refs/nstack-remote/base"], cwd=project, check=True, env=env)
    assert subprocess.run(["git", "merge-base", "--is-ancestor", "HEAD", "origin/main"], cwd=project, env=env).returncode, \
        "origin/main is stale, as claim's fetch leaves it"
    result = _hook(project, env)
    assert "not agent scout's identity" not in result.stdout, result.stdout


def test_a_forge_merge_brought_by_no_ref_the_hook_reads_is_fetched_before_refusing(tmp_path):
    """#484 again (D268): a merge of main made in another clone was fetched here into FETCH_HEAD and
    pushed by its sha; the forge's squash merge it carries reached this clone through no ref the hook
    reads, origin/main stale. Before refusing, the hook fetches the remote's default branch and counts
    again: the forge's commit is the remote's, the agent's merge its own."""
    project, env = _repo(tmp_path)
    forge = {**env, "GIT_COMMITTER_NAME": "GitHub", "GIT_COMMITTER_EMAIL": "noreply@github.com",
             "GIT_AUTHOR_NAME": "demo-lina[bot]", "GIT_AUTHOR_EMAIL": "9002+demo-lina[bot]@users.noreply.github.com"}
    subprocess.run(["git", "symbolic-ref", "HEAD", "refs/heads/main"], cwd=tmp_path / "remote.git", check=True, env=env)
    subprocess.run(["git", "switch", "-q", "-c", "issue-7-work"], cwd=project, check=True, env=env)
    subprocess.run(["git", "commit", "-q", "--allow-empty", "-m", "the agent's work"], cwd=project, check=True, env=env)
    other = tmp_path / "other"
    subprocess.run(["git", "clone", "-q", "-b", "main", str(tmp_path / "remote.git"), str(other)], check=True, env=env, capture_output=True)
    subprocess.run(["git", "commit", "-q", "--allow-empty", "-m", "squash merge (#1)"], cwd=other, check=True, env=forge)
    subprocess.run(["git", "push", "-q", "origin", "HEAD:main"], cwd=other, check=True, env=env)
    shared = tmp_path / "shared"
    subprocess.run(["git", "clone", "-q", "--shared", str(project), str(shared)], check=True, env=env, capture_output=True)
    subprocess.run(["git", "checkout", "-q", "origin/issue-7-work"], cwd=shared, check=True, env=env)
    subprocess.run(["git", "fetch", "-q", str(tmp_path / "remote.git"), "main"], cwd=shared, check=True, env=env)
    subprocess.run(["git", "merge", "-q", "--no-edit", "FETCH_HEAD"], cwd=shared, check=True, env=env)
    subprocess.run(["git", "fetch", "-q", str(shared), "HEAD"], cwd=project, check=True, env=env)
    merged = subprocess.run(["git", "rev-parse", "FETCH_HEAD"], cwd=project, capture_output=True, text=True,
                            check=True, env=env).stdout.strip()
    assert subprocess.run(["git", "merge-base", "--is-ancestor", "origin/main", merged], cwd=project, env=env).returncode == 0
    stale = subprocess.run(["git", "rev-parse", "origin/main"], cwd=project, capture_output=True, text=True, env=env).stdout
    result = subprocess.run(["sh", ".nstack/fitness-before-push.sh"], cwd=project, capture_output=True, text=True,
                            env={**env, "PATH": "/usr/bin:/bin", "PRE_COMMIT_TO_REF": merged, "PRE_COMMIT_REMOTE_NAME": "origin",
                                 "PRE_COMMIT_REMOTE_BRANCH": "refs/heads/issue-7-work"}, timeout=60)
    assert "not agent scout's identity" not in result.stdout, result.stdout
    assert subprocess.run(["git", "rev-parse", "origin/main"], cwd=project, capture_output=True, text=True,
                          env=env).stdout == stale, "the hook moves none of the person's remote-tracking branches"
    assert subprocess.run(["git", "rev-parse", "FETCH_HEAD"], cwd=project, capture_output=True, text=True,
                          env=env).stdout.strip() == merged, "nor FETCH_HEAD, which the agent may push again"


def test_a_made_up_identity_is_still_refused_after_the_hook_s_fetch(tmp_path):
    """D268: the fetch before refusing clears only what the remote holds; the agent's own commit
    under a made-up identity, on top of a stale origin/main, is still refused."""
    project, env = _repo(tmp_path)
    subprocess.run(["git", "symbolic-ref", "HEAD", "refs/heads/main"], cwd=tmp_path / "remote.git", check=True, env=env)
    other = tmp_path / "other"
    subprocess.run(["git", "clone", "-q", "-b", "main", str(tmp_path / "remote.git"), str(other)], check=True, env=env, capture_output=True)
    subprocess.run(["git", "commit", "-q", "--allow-empty", "-m", "squash merge (#1)"], cwd=other, check=True, env=env)
    subprocess.run(["git", "push", "-q", "origin", "HEAD:main"], cwd=other, check=True, env=env)
    subprocess.run(["git", "-c", "user.name=f", "-c", "user.email=f@host.example", "commit", "-q", "--allow-empty",
                    "-m", "made up"], cwd=project, check=True, env=env)
    result = _hook(project, {**env, "PRE_COMMIT_REMOTE_NAME": "origin"})
    assert result.returncode == 1 and "1 commit(s) the remote does not hold yet" in result.stdout, result.stdout


def test_the_hook_fetches_only_to_refuse_and_from_the_remote_pushed_to(tmp_path):
    """D268's verifier: a clean push fetches nothing; the fetch reads the remote pre-commit names, and a
    fetch that fails never says it was made."""
    project, env = _repo(tmp_path)
    subprocess.run(["git", "symbolic-ref", "HEAD", "refs/heads/main"], cwd=tmp_path / "remote.git", check=True, env=env)
    subprocess.run(["git", "commit", "-q", "--allow-empty", "-m", "mine"], cwd=project, check=True, env=env)
    clean = _hook(project, {**env, "PRE_COMMIT_REMOTE_NAME": "origin"})
    assert "identity" not in clean.stdout, clean.stdout
    assert subprocess.run(["git", "rev-parse", "--verify", "--quiet", "refs/nstack-remote/base"], cwd=project,
                          env=env).returncode, "a clean push fetched"
    subprocess.run(["git", "-c", "user.name=f", "-c", "user.email=f@host.example", "commit", "-q", "--allow-empty",
                    "-m", "made up"], cwd=project, check=True, env=env)
    missing = _hook(project, {**env, "PRE_COMMIT_REMOTE_NAME": "nowhere"})
    assert missing.returncode == 1 and "this hook fetched" not in missing.stdout, missing.stdout
    assert "git fetch, then push again" in missing.stdout
    named = _hook(project, {**env, "PRE_COMMIT_REMOTE_NAME": str(tmp_path / "remote.git")})
    assert named.returncode == 1 and "this hook fetched the remote's" in named.stdout, named.stdout
